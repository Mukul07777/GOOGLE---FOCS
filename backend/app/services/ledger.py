"""Cost ledger: every successful AI call is recorded with its tokens and list-price cost.

Writes happen on a background thread in small batches, so recording never slows an answer down.
The user is taken from the request (set by middleware from the login token).
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from contextvars import ContextVar
from typing import Any

from app.core.config import settings
from app.models._util import utcnow

log = logging.getLogger("focs.ledger")

current_user: ContextVar[int | None] = ContextVar("focs_ledger_user", default=None)

_queue: queue.Queue[dict[str, Any]] = queue.Queue()
_writer: threading.Thread | None = None
_writer_lock = threading.Lock()


def price(model: str) -> tuple[float, float]:
    return settings.MODEL_PRICES_USD.get(model, settings.DEFAULT_PRICE_USD)


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    p_in, p_out = price(model)
    return (prompt_tokens * p_in + completion_tokens * p_out) / 1_000_000


def record(feature: str, model: str, usage: dict[str, Any] | None) -> None:
    """Queue one call for the ledger. Never raises: cost tracking must not break a feature."""
    try:
        prompt = int((usage or {}).get("prompt_tokens") or 0)
        completion = int((usage or {}).get("completion_tokens") or 0)
        usd = cost_usd(model, prompt, completion)
        _queue.put({"created_at": utcnow(), "user_id": current_user.get(), "feature": feature, "model": model,
                    "prompt_tokens": prompt, "completion_tokens": completion, "cost_usd": usd})
        _ensure_writer()
        _spend(usd, current_user.get())
    except Exception:  # pragma: no cover - defensive
        log.exception("could not record an AI call")


def record_cost(feature: str, model: str, usd: float) -> None:
    """Queue a call that is priced by something other than tokens (speech to text: by the minute)."""
    try:
        usd = max(0.0, float(usd))
        _queue.put({"created_at": utcnow(), "user_id": current_user.get(), "feature": feature, "model": model,
                    "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": usd})
        _ensure_writer()
        _spend(usd, current_user.get())
    except Exception:  # pragma: no cover - defensive
        log.exception("could not record an AI call")


# ---------------------------------------------------------------- what may be spent
# Two limits, so that AI is paid for by what students pay:
# * each student's own spend over 30 days (AI_CEILING_*_INR, checked by services/usage), kept here as a running total;
# * free accounts' spend today, all together (FREE_AI_DAY_FLOOR_INR plus a share of the last 30 days' Pro income).
_budget_lock = threading.Lock()
_today: dict[str, Any] = {"day": None, "usd": 0.0, "warned": False}  # free accounts' and shared work's spend today
_paying: dict[int, tuple[bool, float]] = {}  # user id -> (on a paid plan, when that was looked up)
_user_usd: dict[int, list[float]] = {}       # user id -> [spend in the last 30 days, when read from the ledger]
_free_budget: list[float] = [0.0, -1e9]      # [today's budget for free accounts in rupees, when worked out]
PAYING_TTL_S = 300
USER_SPEND_TTL_S = 600
CEILING_DAYS = 30


def _roll() -> None:
    """Start the running total for a new day (call with the lock held). After a restart it starts from what the
    ledger already holds for today, so a restart doesn't reset the budget."""
    day = utcnow().date()
    if _today["day"] == day:
        return
    from datetime import datetime

    from sqlalchemy import func, or_, select

    from app.core.database import SessionLocal
    from app.models.llm_call import LlmCall
    from app.models.user import User

    try:
        with SessionLocal() as db:
            paying = select(User.id).where(User.plan.in_(("pro", "team")))
            spent = float(db.scalar(select(func.coalesce(func.sum(LlmCall.cost_usd), 0.0)).where(
                LlmCall.created_at >= datetime.combine(day, datetime.min.time()),
                or_(LlmCall.user_id.is_(None), LlmCall.user_id.not_in(paying)))) or 0.0)
    except Exception:  # noqa: BLE001 - the budget must never stop the app
        log.warning("could not read today's AI spend; counting from zero", exc_info=True)
        spent = 0.0
    _today.update(day=day, usd=spent, warned=False)


def _spend(usd: float, user_id: int | None) -> None:
    if user_id is not None:
        with _budget_lock:
            if user_id in _user_usd:
                _user_usd[user_id][0] += usd
        if pays(user_id):  # a paying student's AI is paid for by their pass, not by the free budget
            return
    with _budget_lock:
        _roll()
        _today["usd"] += usd


def spent_today_inr() -> float:
    """What free accounts (and shared work) have spent on AI today, in rupees."""
    with _budget_lock:
        _roll()
        return _today["usd"] * settings.USD_INR


def free_budget_inr() -> float:
    """Today's AI budget for free accounts: the daily floor plus a share of what Pro brought in over the last 30
    days, spread over those days. Worked out every few minutes."""
    if time.monotonic() - _free_budget[1] < USER_SPEND_TTL_S:
        return _free_budget[0]
    from datetime import timedelta

    from sqlalchemy import func, select

    from app.core.database import SessionLocal
    from app.models.payment import Payment

    try:
        with SessionLocal() as db:
            income = float(db.scalar(select(func.coalesce(func.sum(Payment.amount_inr), 0)).where(
                Payment.status == "paid", Payment.purpose.like("pro_%") | (Payment.purpose == "mocks"),
                Payment.paid_at >= utcnow() - timedelta(days=CEILING_DAYS))) or 0)
    except Exception:  # noqa: BLE001
        log.warning("could not read Pro income; using the floor alone", exc_info=True)
        income = 0.0
    _free_budget[:] = [settings.FREE_AI_DAY_FLOOR_INR + settings.FREE_AI_REVENUE_SHARE * income / CEILING_DAYS,
                       time.monotonic()]
    return _free_budget[0]


def over_budget() -> bool:
    """Free accounts have spent today's budget (0 for both settings: no budget)."""
    if not settings.FREE_AI_DAY_FLOOR_INR and not settings.FREE_AI_REVENUE_SHARE:
        return False
    budget = free_budget_inr()
    if spent_today_inr() < budget:
        return False
    with _budget_lock:
        if not _today["warned"]:
            _today["warned"] = True
            log.warning("Free accounts spent today's AI budget (Rs %.0f): they get offline answers until 05:30 IST. "
                        "Raise FREE_AI_DAY_FLOOR_INR or FREE_AI_REVENUE_SHARE if this is real use.", budget)
    return True


def user_spend_inr(user_id: int) -> float:
    """What this student's AI has cost in the last 30 days, in rupees: read from the ledger every few minutes, with
    the calls made since added as they happen."""
    with _budget_lock:
        hit = _user_usd.get(user_id)
        if hit and time.monotonic() - hit[1] < USER_SPEND_TTL_S:
            return hit[0] * settings.USD_INR
    from datetime import timedelta

    from sqlalchemy import func, select

    from app.core.database import SessionLocal
    from app.models.llm_call import LlmCall

    flush()  # calls still queued count too
    with SessionLocal() as db:
        usd = float(db.scalar(select(func.coalesce(func.sum(LlmCall.cost_usd), 0.0)).where(
            LlmCall.user_id == user_id, LlmCall.created_at >= utcnow() - timedelta(days=CEILING_DAYS))) or 0.0)
    with _budget_lock:
        _user_usd[user_id] = [usd, time.monotonic()]
    return usd * settings.USD_INR


def pays(user_id: int) -> bool:
    """Whether the student is on a paid plan (looked up at most every few minutes)."""
    hit = _paying.get(user_id)
    if hit and time.monotonic() - hit[1] < PAYING_TTL_S:
        return hit[0]
    from app.core.database import SessionLocal
    from app.models.user import User

    with SessionLocal() as db:
        user = db.get(User, user_id)
        paid = bool(user and user.plan in ("pro", "team") and (user.pro_until is None or user.pro_until > utcnow()))
    _paying[user_id] = (paid, time.monotonic())
    return paid


def forget_plan(user_id: int) -> None:
    """The student's plan just changed (a payment): look it up afresh next time."""
    _paying.pop(user_id, None)
    _free_budget[1] = -1e9  # and Pro income changed: work the free budget out again


def flush() -> int:
    """Write everything queued so far (also used by tests and on shutdown). Returns rows written."""
    from app.core.database import SessionLocal
    from app.models.llm_call import LlmCall

    rows = []
    while True:
        try:
            rows.append(_queue.get_nowait())
        except queue.Empty:
            break
    if not rows:
        return 0
    try:
        with SessionLocal() as db:
            db.add_all(LlmCall(**r) for r in rows)
            db.commit()
    except Exception:
        log.exception("could not write %d ledger rows", len(rows))
        return 0
    return len(rows)


def _ensure_writer() -> None:
    global _writer
    with _writer_lock:
        if _writer and _writer.is_alive():
            return
        _writer = threading.Thread(target=_run, name="focs-ledger", daemon=True)
        _writer.start()


def _run() -> None:
    while True:
        try:
            first = _queue.get(timeout=30)
        except queue.Empty:
            continue
        _queue.put(first)  # flush() drains everything, including this one
        time.sleep(2)  # small batches instead of one write per call
        flush()

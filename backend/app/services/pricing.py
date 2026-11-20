"""What Pro costs. Each kind of student has its own prices for a month, six months and a year, with a launch offer
for the first PRO_OFFER_PLACES students who pay. A Pro student's AI may cost, in any 30 days, at most what the pass
they are on brings in over 30 days after the payment fee: whatever they paid, no student can cost Focs more."""
from __future__ import annotations

import threading
import time

from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models._util import utcnow
from app.models.payment import Payment

# The kinds of student with their own prices. Exam targets without one of their own (GATE, UPSC, CA, other) pay the
# exam price until they get one.
SECTORS = {
    "exam": {"label": "JEE / NEET", "hint": "Entrance exams"},
    "college": {"label": "College", "hint": "B.Tech & placements"},
    "school": {"label": "School", "hint": "Class 1 to 12 (CBSE)"},
    "ssc": {"label": "SSC CGL", "hint": "Government jobs"},
}
PASSES = {"month": "1 month", "semester": "6 months", "year": "1 year"}
PAYMENT_FEE = 0.0236  # Razorpay: 2%, plus 18% GST on it
PLACES_TTL_S = 60.0
PASS_TTL_S = 300.0

_lock = threading.Lock()
_places = [0, -1e9]  # students who took an offer place, and when they were counted
_running: dict[int, tuple[float | None, float]] = {}  # user -> (their pass's 30-day ceiling, when looked up)


def sector_of(exam_target: str | None) -> str:
    target = exam_target or "jee"
    if target.startswith("college") or target == "coding":
        return "college"
    if target.startswith("cbse"):
        return "school"
    if target.startswith("ssc"):
        return "ssc"
    return "exam"


def days(pass_id: str) -> int:
    return {"month": settings.PRO_DAYS, "semester": settings.PRO_SEMESTER_DAYS, "year": settings.PRO_YEAR_DAYS}[pass_id]


def _listed(prices: dict, sector: str, pass_id: str) -> int:
    return int((prices.get(sector) or prices.get("exam") or {}).get(pass_id) or 0)


def places_taken() -> int:
    """Students who have paid for Pro at a launch-offer price (counted again at most once a minute)."""
    with _lock:
        if time.monotonic() - _places[1] < PLACES_TTL_S:
            return int(_places[0])
    with SessionLocal() as db:
        taken = db.scalar(select(func.count(func.distinct(Payment.user_id)))
                          .where(Payment.launch_offer.is_(True), Payment.status == "paid")) or 0
    with _lock:
        _places[:] = [taken, time.monotonic()]
    return int(taken)


def offer() -> dict | None:
    """The launch offer while it runs: its places and how many are left. Once they are taken it ends by itself."""
    if settings.PRO_OFFER_PLACES <= 0 or not settings.PRO_OFFER_PRICES_INR:
        return None
    left = settings.PRO_OFFER_PLACES - places_taken()
    return {"places": settings.PRO_OFFER_PLACES, "left": left} if left > 0 else None


def price(sector: str, pass_id: str, offer_open: bool | None = None) -> tuple[int, bool]:
    """What this pass costs this kind of student now (0: not on sale), and whether that is the launch offer."""
    regular = _listed(settings.PRO_PRICES_INR, sector, pass_id)
    if not regular:
        return 0, False
    cut = _listed(settings.PRO_OFFER_PRICES_INR, sector, pass_id)
    if offer_open is None:
        offer_open = offer() is not None
    return (cut, True) if offer_open and 0 < cut < regular else (regular, False)


def ceiling_inr(amount_inr: int, pass_days: int) -> float:
    """What a pass of this price and length may spend on AI in any 30 days: what it brings in over 30 days after the
    payment fee, never more than AI_CEILING_PRO_INR (0: no ceiling)."""
    if not settings.AI_CEILING_PRO_INR:
        return 0.0
    return min(settings.AI_CEILING_PRO_INR, amount_inr / max(1, pass_days) * 30 * (1 - PAYMENT_FEE))


def _hours(ceiling: float) -> int:
    """About how many lecture hours a 30-day ceiling holds, rounded down to 5."""
    return int(ceiling / settings.LECTURE_HOUR_INR // 5 * 5)


def passes(sector: str, offer_open: bool | None = None) -> list[dict]:
    """The ways this kind of student can buy Pro now. save_pct is against paying month by month; regular_inr is the
    price struck through while the launch offer runs."""
    if offer_open is None:
        offer_open = offer() is not None
    month = price(sector, "month", offer_open)[0] / days("month")
    out = []
    for pass_id, label in PASSES.items():
        amount, launch = price(sector, pass_id, offer_open)
        if amount:
            n = days(pass_id)
            out.append({"id": pass_id, "label": label, "price_inr": amount, "days": n,
                        "regular_inr": _listed(settings.PRO_PRICES_INR, sector, pass_id) if launch else None,
                        "per_month_inr": round(amount / n * 30),
                        "save_pct": max(0, round(100 * (1 - amount / n / month))) if month else 0,
                        "fair_use_hours": _hours(ceiling_inr(amount, n)) if settings.AI_CEILING_PRO_INR else None})
    return out


def fair_use_hours(sector: str, offer_open: bool | None = None) -> int | None:
    """The lecture hours every 30 days that each of this kind's passes holds at least (None: no ceiling)."""
    hours = [p["fair_use_hours"] for p in passes(sector, offer_open) if p["fair_use_hours"] is not None]
    return min(hours) if hours else None


def pass_ceiling_inr(user_id: int) -> float | None:
    """The 30-day AI ceiling of the Pro pass this student is on now; None when no paid pass is running (Pro given by
    an admin or a dev server), which then has AI_CEILING_PRO_INR."""
    hit = _running.get(user_id)
    if hit and time.monotonic() - hit[1] < PASS_TTL_S:
        return hit[0]
    now = utcnow()
    with SessionLocal() as db:
        running = db.scalars(select(Payment).where(
            Payment.user_id == user_id, Payment.status == "paid", Payment.purpose.like("pro_%"),
            Payment.covers_from <= now, Payment.covers_to > now).order_by(Payment.id.desc()).limit(1)).first()
        ceiling = ceiling_inr(running.amount_inr, (running.covers_to - running.covers_from).days) if running else None
    _running[user_id] = (ceiling, time.monotonic())
    return ceiling


def forget(user_id: int) -> None:
    """A Pro payment just went through: count the places and look up the student's pass afresh."""
    _running.pop(user_id, None)
    with _lock:
        _places[1] = -1e9

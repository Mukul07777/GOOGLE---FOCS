"""Payments through Razorpay: a Pro pass (a month, six months or a year), full mock tests bought one at a time or in a
pack, one mentor call, or a seat in a mentor's master session.

The server creates an order, the browser opens Razorpay's checkout (UPI, cards, netbanking), and the payment counts
only when its signature checks out against our secret, or when Razorpay's webhook says it was captured (so it still
counts if the student closed the tab). Fulfilling is idempotent: the signature and the webhook can both arrive.
Without Razorpay keys a dev server offers a test payment instead; a production server says payments aren't set up.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import timedelta
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models._util import utcnow
from app.models.mentor import GroupSeat, GroupSession, MentorCall
from app.models.payment import Payment
from app.models.user import User
from app.services import ledger, pricing
from app.services.mentors import seat_holds, slot_taken

log = logging.getLogger("focs.payments")
ORDERS_URL = "https://api.razorpay.com/v1/orders"


LOCAL = {"127.0.0.1", "::1", "localhost"}

# The purposes of Pro payments (what each costs and how long it runs: services/pricing.py)
PRO_PASSES = tuple(f"pro_{pass_id}" for pass_id in pricing.PASSES)


def is_local(request) -> bool:
    """A request from the machine the server runs on. Anything that came through a proxy is not, whatever it claims."""
    return bool(request.client) and request.client.host in LOCAL and "x-forwarded-for" not in request.headers


def dev_allowed(local: bool) -> bool:
    """Dev shortcuts (switching plans, test payments): a dev server, and only from the machine it runs on."""
    return settings.ALLOW_DEV_UPGRADE and not settings.is_production and (local or not settings.DEV_FEATURES_LOCAL_ONLY)


def provider(local: bool = False) -> str | None:
    if settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET:
        return "razorpay"
    if dev_allowed(local):
        return "dev"
    return None


def is_pro(user: User) -> bool:
    return user.plan in ("pro", "team") and (user.pro_until is None or user.pro_until > utcnow())


def start(db: Session, user: User, purpose: str, amount_inr: int, description: str, ref_id: int | None = None,
          local: bool = False, launch_offer: bool = False) -> dict[str, Any]:
    """A payment waiting to be made, and what the browser needs to open the checkout."""
    kind = provider(local)
    if kind is None:
        raise HTTPException(status_code=503, detail="Payments aren't set up on this server yet.")
    payment = Payment(user_id=user.id, purpose=purpose, ref_id=ref_id, amount_inr=amount_inr, provider=kind,
                      launch_offer=launch_offer)
    db.add(payment)
    db.flush()
    if kind == "razorpay":
        try:
            r = httpx.post(ORDERS_URL, auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET), timeout=15,
                           json={"amount": amount_inr * 100, "currency": "INR", "receipt": f"focs-{payment.id}",
                                 "notes": {"purpose": purpose, "user": str(user.id)}})
            r.raise_for_status()
            payment.order_id = r.json()["id"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            log.warning("razorpay order failed: %s", exc)
            db.rollback()
            raise HTTPException(status_code=502, detail="Couldn't reach the payment provider. Try again in a minute.") from exc
    db.commit()
    return {"payment_id": payment.id, "provider": kind, "key_id": settings.RAZORPAY_KEY_ID if kind == "razorpay" else None,
            "order_id": payment.order_id, "amount_paise": amount_inr * 100, "amount_inr": amount_inr, "currency": "INR",
            "description": description, "prefill": {"name": user.full_name, "email": user.email}}


def signature_ok(order_id: str, payment_id: str, signature: str) -> bool:
    if not settings.RAZORPAY_KEY_SECRET or not order_id or not payment_id:  # with no secret anyone could sign
        return False
    expected = hmac.new(settings.RAZORPAY_KEY_SECRET.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def webhook_ok(body: bytes, signature: str) -> bool:
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        return False
    expected = hmac.new(settings.RAZORPAY_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def fulfil(db: Session, payment: Payment, provider_payment_id: str | None = None) -> Payment:
    """The payment is in: give what it bought. Safe to call twice."""
    if payment.status in ("paid", "refund_due", "refunded"):
        return payment
    payment.status, payment.paid_at = "paid", utcnow()
    payment.provider_payment_id = provider_payment_id or payment.provider_payment_id
    if payment.purpose in PRO_PASSES:
        user = db.get(User, payment.user_id)
        base = max(utcnow(), user.pro_until or utcnow())  # added after any Pro time left
        payment.covers_from = base
        payment.covers_to = user.pro_until = base + timedelta(days=pricing.days(payment.purpose.removeprefix("pro_")))
        if user.plan != "team":
            user.plan = "pro"
        ledger.forget_plan(user.id)
        pricing.forget(user.id)
    elif payment.purpose == "mocks":
        pass  # ref_id holds how many were bought; mock.credits counts them from the paid row
    elif payment.purpose == "mentor_call":
        call = db.get(MentorCall, payment.ref_id)
        if call is None or call.status == "cancelled" or slot_taken(db, call.mentor_id, call.starts_at, ignore=call.id):
            payment.status = "refund_due"  # paid after the hold lapsed and someone else took the slot
            if call is not None:
                call.status, call.cancelled_by = "cancelled", "system"
        else:
            call.status, call.held_until = "booked", None
    elif payment.purpose == "session_seat":
        seat = db.get(GroupSeat, payment.ref_id)
        session = db.get(GroupSession, seat.session_id) if seat else None
        others = [s for s in db.query(GroupSeat).filter(GroupSeat.session_id == seat.session_id, GroupSeat.id != seat.id)
                  if seat_holds(s, utcnow())] if seat else []
        if seat is None or seat.status == "cancelled" or session is None or session.status != "scheduled" or len(others) >= session.seats:
            payment.status = "refund_due"  # paid after the hold lapsed and the session filled, or it was cancelled meanwhile
            if seat is not None:
                seat.status = "cancelled"
        else:
            seat.status, seat.held_until = "booked", None
    db.commit()
    return payment

"""Plans and payments. Pro is bought a month, six months or a year at a time through Razorpay (UPI works; no card
needed), at the price for the student's kind (services/pricing.py); dev servers can also switch plans directly and pay
with a test button."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import bearer, get_current_user, get_db, require_student, user_from_token
from app.models.payment import Payment
from app.models.user import User
from app.schemas.auth import UserOut
from app.services import payments, pricing

router = APIRouter(prefix="/billing", tags=["billing"])

def _minutes(m: int) -> str:
    return "unlimited" if not m else f"{m // 60} hours" if m % 60 == 0 and m > 60 else f"{m} minutes"


def _lecture_line(hours: float, lead: str) -> str:
    if not hours:
        return f"{lead} every lecture"
    if hours < 1:
        return f"{lead} {round(hours * 60)} minutes of lecture a day"
    n = f"{hours:g}"
    return f"{lead} {n} hour{'' if n == '1' else 's'} of lecture a day"


def plan_list(sector: str = "exam", offer_open: bool | None = None) -> list[dict]:
    """The plans as this kind of student sees them, worded from the current settings (so a changed price or limit
    can't drift). Pro's price is its month pass; regular_inr is struck through while the launch offer runs."""
    if offer_open is None:
        offer_open = pricing.offer() is not None
    month = next((p for p in pricing.passes(sector, offer_open) if p["id"] == "month"), None)
    fair_use = pricing.fair_use_hours(sector, offer_open)
    pro_extra = ([f"A live master session with a mentor every week, included ({settings.GROUP_SESSION_MINUTES} min)"]
                 if settings.PRO_GROUP_SESSIONS_PER_WEEK else [])
    return [
        {"id": "free", "name": "Starter", "price_inr": 0, "period": "forever",
         "tagline": "Everything you need to try Focs on your next lecture.",
         # Lecture notes are promised in hours because they are metered in lecture time (services/usage.py), not in
         # boards: a PW lecture hour is anything from 15 to 40 of them.
         "features": [_lecture_line(settings.LECTURE_HOURS_FREE, "Live board capture & AI notes for") + " (basic notes after it: a lecture never stops)",
                      "Lectures another Focs student already captured: free, outside your allowance",
                      f"Lecture captions: {_minutes(settings.CAPTION_MINUTES_FREE_WEEK)} a week", "1 full mock test a week (chapter tests for classes without a full paper)"
                      + (f"; more from ₹{settings.MOCK_PACK_INR} for {settings.MOCK_PACK_SIZE}" if settings.MOCK_PACK_INR else f"; more at ₹{settings.MOCK_PRICE_INR} each" if settings.MOCK_PRICE_INR else ""),
                      "Pop quizzes, doubts & flashcards", "Mentors: free chat; calls and sessions at the mentor's price",
                      "Study rooms up to 5 friends"]},
        {"id": "pro", "name": "Pro", "price_inr": month["price_inr"] if month else None, "period": "month", "highlight": True,
         "regular_inr": month["regular_inr"] if month else None,
         "tagline": "For students studying every day.",
         "features": [*pro_extra,
                      _lecture_line(settings.LECTURE_HOURS_PRO, "AI notes for up to") + ", however much the teacher writes"
                      + (f" (fair use: about {fair_use} hours every 30 days)" if fair_use else ""),
                      f"{settings.USAGE_PRO_WINDOW // max(1, settings.USAGE_FREE_WINDOW)}× Starter's daily AI for doubts, quizzes and practice",
                      "Lectures another Focs student already captured: free, outside your allowance",
                      f"Lecture captions: {_minutes(settings.CAPTION_MINUTES_PRO_WEEK)} a week",
                      "Unlimited full mock and chapter tests with full analysis", "AI practice sets & subjective answer grading",
                      "Doubt solver with Socratic mode", "Study rooms up to 50"]},
        {"id": "team", "name": "Institute", "price_inr": None, "period": "custom",
         "tagline": "Coaching centres and colleges.",
         "features": ["Everything in Pro, no usage caps", "Batch analytics for teachers", "Custom exam patterns",
                      "SSO & admin controls", "Dedicated support"]},
    ]


class PlanChange(BaseModel):
    plan: Literal["free", "pro", "team"]


class ConfirmIn(BaseModel):
    razorpay_order_id: str = Field(default="", max_length=60)
    razorpay_payment_id: str = Field(default="", max_length=60)
    razorpay_signature: str = Field(default="", max_length=200)


@router.get("/plans")
def plans(request: Request, sector: str | None = Query(None, max_length=20), db: Session = Depends(get_db),
          credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    """The plans and Pro passes for one kind of student: the one asked for, else the signed-in student's own, else
    JEE / NEET. Pro is always bought at the price of the student's own kind, whichever was shown."""
    if sector is None:
        user = user_from_token(credentials.credentials if credentials else None, db)
        sector = pricing.sector_of(user.exam_target) if user else "exam"
    elif sector not in pricing.SECTORS:
        raise HTTPException(status_code=404, detail="Unknown kind of student")
    local = payments.is_local(request)
    offer = pricing.offer()
    return {"plans": plan_list(sector, offer is not None), "dev_upgrade": payments.dev_allowed(local),
            "payments": payments.provider(local), "pro_days": settings.PRO_DAYS, "call_price_inr": settings.MENTOR_CALL_PRICE_INR,
            "sector": sector, "sectors": [{"id": key, **about} for key, about in pricing.SECTORS.items()], "offer": offer,
            "passes": pricing.passes(sector, offer is not None), "pro_sessions_per_week": settings.PRO_GROUP_SESSIONS_PER_WEEK,
            "captions_min_week": {"free": settings.CAPTION_MINUTES_FREE_WEEK, "pro": settings.CAPTION_MINUTES_PRO_WEEK}}


@router.post("/dev-upgrade", response_model=UserOut)
def dev_upgrade(body: PlanChange, request: Request, db: Session = Depends(get_db), user: User = Depends(require_student)):
    if not payments.dev_allowed(payments.is_local(request)):
        raise HTTPException(status_code=403, detail="Payments are not configured on this server yet.")
    user.plan = body.plan
    user.pro_until = None
    db.commit()
    db.refresh(user)
    return user


@router.post("/pro", status_code=201)
def buy_pro(request: Request, plan: Literal["month", "semester", "year"] = "month", db: Session = Depends(get_db),
            user: User = Depends(require_student)):  # Pro is a student's pass
    """Pay for Pro: a month, six months or a year (added on top of any Pro time left), at the price for what the
    student prepares for: the launch offer's while it runs."""
    if user.plan == "team":
        raise HTTPException(status_code=409, detail="Your Institute plan already includes everything in Pro.")
    price, launch = pricing.price(pricing.sector_of(user.exam_target), plan)
    if not price:
        raise HTTPException(status_code=404, detail="That Pro pass isn't on sale right now.")
    return payments.start(db, user, f"pro_{plan}", price, f"Focs Pro · {pricing.PASSES[plan]}", local=payments.is_local(request),
                          launch_offer=launch)


@router.post("/mocks", status_code=201)
def buy_mocks(request: Request, pack: Literal["one", "pack"] = "one", db: Session = Depends(get_db),
              user: User = Depends(require_student)):
    """Pay for full mock tests without Pro: one, or a pack. They are used once the week's own are gone, and never
    run out with time."""
    from app.services import mock

    offer = next((o for o in mock.mock_offers() if o["id"] == pack), None)
    if user.plan == "team" or mock.mocks_per_week(user.plan) == 0:
        raise HTTPException(status_code=409, detail="Your plan already has unlimited mock tests.")
    if offer is None:
        raise HTTPException(status_code=404, detail="Mock tests aren't on sale one at a time right now.")
    n = offer["count"]
    return payments.start(db, user, "mocks", offer["price_inr"], f"Focs · {n} full mock test{'s' if n > 1 else ''}",
                          ref_id=n, local=payments.is_local(request))


@router.post("/payments/{payment_id}/confirm")
def confirm(payment_id: int, body: ConfirmIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The checkout says it's paid: check Razorpay's signature (a dev server's test payment needs none) and fulfil."""
    payment = db.get(Payment, payment_id)
    if payment is None or payment.user_id != user.id:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payment.provider == "dev":
        if not payments.dev_allowed(payments.is_local(request)):
            raise HTTPException(status_code=403, detail="Test payments only work on a dev server.")
    elif body.razorpay_order_id != payment.order_id or not payments.signature_ok(payment.order_id, body.razorpay_payment_id, body.razorpay_signature):
        raise HTTPException(status_code=400, detail="That payment couldn't be verified. If money was taken, it will be matched shortly or refunded.")
    payments.fulfil(db, payment, body.razorpay_payment_id or None)
    db.refresh(user)
    return {"status": payment.status, "purpose": payment.purpose, "user": UserOut.model_validate(user)}


@router.post("/webhook", include_in_schema=False)
async def webhook(request: Request, db: Session = Depends(get_db)):
    """Razorpay → payment.captured / order.paid: the payment counts even if the student's tab never came back."""
    body = await request.body()
    if not payments.webhook_ok(body, request.headers.get("X-Razorpay-Signature", "")):
        raise HTTPException(status_code=400, detail="Bad signature")
    event = (await request.json()) if body else {}
    entity = (((event.get("payload") or {}).get("payment") or {}).get("entity")) or {}
    order_id = entity.get("order_id")
    if event.get("event") in ("payment.captured", "order.paid") and order_id:
        payment = db.scalar(select(Payment).where(Payment.order_id == order_id))
        if payment is not None:
            payments.fulfil(db, payment, entity.get("id"))
    return {"ok": True}


@router.get("/me")
def my_billing(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(select(Payment).where(Payment.user_id == user.id, Payment.status != "created").order_by(Payment.id.desc()).limit(20)).all()
    return {"plan": user.plan or "free", "pro": payments.is_pro(user), "pro_until": user.pro_until.isoformat() + "Z" if user.pro_until else None,
            "payments": [{"id": p.id, "purpose": p.purpose, "amount_inr": p.amount_inr, "status": p.status,
                          "paid_at": p.paid_at.isoformat() + "Z" if p.paid_at else None} for p in rows]}

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._util import utcnow


class Payment(Base):
    """One payment: a Pro pass, a mentor call or a master-session seat. Created before the checkout opens; paid once
    Razorpay's signature (or its webhook) confirms it. A refund owed (a call the mentor cancelled) is marked for the admin to send."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(12))                    # pro_month | pro_semester | mocks | mentor_call | session_seat (12 chars at most)
    ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True)   # the call (or master-session seat) paid for; for mocks, how many
    amount_inr: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(10))                    # razorpay | dev (a test payment, dev servers only)
    status: Mapped[str] = mapped_column(String(10), default="created", index=True)  # created | paid | failed | refund_due | refunded
    order_id: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    provider_payment_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # a Pro pass: bought at the launch-offer price (it takes one of the offer's places), and the time it runs
    # (after any Pro time left when it was bought); the student's AI ceiling follows the pass running now
    launch_offer: Mapped[bool] = mapped_column(Boolean, default=False)
    covers_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    covers_to: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

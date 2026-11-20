"""Prices that pay for the AI they include: each kind of student has its own prices and a launch offer for the first
students, no Pro pass can cost Focs more than it brought in, each student's AI is capped over 30 days, and free
accounts together are paid for by a share of Pro income."""
from datetime import timedelta

import pytest

from app.core.config import settings
from app.core.database import SessionLocal
from app.models._util import utcnow
from app.models.llm_call import LlmCall
from app.models.payment import Payment
from app.models.user import User
from app.services import ledger, pricing, usage

RAZORPAY_FEE = 0.0236  # 2% plus GST on the fee


def _user(client, email, exam="jee"):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "Price Student", "password": "correct-horse-1", "exam_target": exam})
    assert r.status_code == 201, r.text
    with SessionLocal() as db:
        return {"Authorization": f"Bearer {r.json()['access_token']}"}, db.query(User).filter(User.email == email).one().id


def _spent(user_id, inr):
    with SessionLocal() as db:
        db.add(LlmCall(user_id=user_id, feature="board_notes", model="test", cost_usd=inr / settings.USD_INR))
        db.commit()
    ledger._user_usd.pop(user_id, None)  # read from the ledger again


def _pay(client, h, plan="month"):
    checkout = client.post(f"/api/billing/pro?plan={plan}", headers=h).json()
    assert client.post(f"/api/billing/payments/{checkout['payment_id']}/confirm", headers=h, json={}).status_code == 200
    return checkout


@pytest.mark.parametrize("offer", [True, False])
@pytest.mark.parametrize("sector", list(pricing.SECTORS))
def test_every_pro_pass_pays_for_the_most_ai_a_student_can_use(sector, offer):
    """Whatever a student paid, at the offer or the regular price: the AI their pass may use in 30 days is no more
    than it brought in over 30 days, and a longer pass costs less a month."""
    passes = pricing.passes(sector, offer)
    assert [p["id"] for p in passes] == ["month", "semester", "year"]
    for p in passes:
        brought_in = p["price_inr"] / p["days"] * 30 * (1 - RAZORPAY_FEE)
        assert pricing.ceiling_inr(p["price_inr"], p["days"]) <= brought_in + 1e-9, f"{sector} {p['id']} can't cover its AI"
        assert (p["regular_inr"] is not None) == offer and (not offer or p["price_inr"] < p["regular_inr"])
    assert passes[2]["per_month_inr"] < passes[1]["per_month_inr"] < passes[0]["per_month_inr"]


def test_the_offer_holds_the_lecture_hours_the_founders_chose():
    """At LECTURE_HOUR_INR: JEE / NEET about 90 lecture hours every 30 days at the launch offer, college 70, school 50."""
    assert pricing.fair_use_hours("exam", True) >= 90
    assert pricing.fair_use_hours("college", True) >= 70
    assert pricing.fair_use_hours("school", True) >= 50
    assert all(pricing.fair_use_hours(s, False) > pricing.fair_use_hours(s, True) for s in pricing.SECTORS)
    assert [pricing.price(s, "month", True)[0] for s in ("exam", "college", "school")] == [249, 199, 149]


def test_the_ceilings_hold_what_the_plans_promise():
    """Pro: 7 hours of lecture notes a day, and a 30-day fair use worth well over a hundred lecture hours at what a
    lecture hour was measured to cost; Starter: its half hour a day, every day of the month."""
    assert settings.USAGE_WINDOW_HOURS == 24 and settings.LECTURE_HOURS_PRO == 7
    assert settings.AI_CEILING_PRO_INR / settings.LECTURE_HOUR_INR >= 100
    assert settings.AI_CEILING_FREE_INR >= 30 * settings.LECTURE_HOURS_FREE * settings.LECTURE_HOUR_INR
    assert settings.LECTURE_HOUR_INR >= 2.5  # measured Rs 2.1-3.4 on free tiers (2026-10-20): lower only after re-measuring


def test_the_plans_say_what_a_study_day_holds(client):
    data = client.get("/api/billing/plans").json()
    starter, pro = data["plans"][0], data["plans"][1]
    assert data["sector"] == "exam" and [s["id"] for s in data["sectors"]] == ["exam", "college", "school", "ssc"]
    assert data["offer"]["places"] == settings.PRO_OFFER_PLACES and 0 < data["offer"]["left"] <= settings.PRO_OFFER_PLACES
    assert pro["price_inr"] == 249 and pro["regular_inr"] == 359 and data["passes"][0]["regular_inr"] == 359
    assert "30 minutes of lecture a day" in starter["features"][0]
    assert "up to 7 hours of lecture a day" in pro["features"][0] and "fair use: about 90 hours" in pro["features"][0]
    assert any("Starter's daily AI for doubts" in f for f in pro["features"])
    assert any("already captured: free" in f for f in pro["features"]) and any("already captured: free" in f for f in starter["features"])
    assert [p["id"] for p in data["passes"]] == ["month", "semester", "year"]
    assert data["passes"][2]["per_month_inr"] < data["passes"][1]["per_month_inr"] < data["passes"][0]["per_month_inr"]
    school = client.get("/api/billing/plans?sector=school").json()
    assert school["sector"] == "school" and school["plans"][1]["price_inr"] == 149 and school["plans"][1]["regular_inr"] == 249
    assert "fair use: about 50 hours" in school["plans"][1]["features"][0]
    assert client.get("/api/billing/plans?sector=astronauts").status_code == 404


@pytest.mark.parametrize("exam,sector,month", [("neet", "exam", 249), ("college_cse", "college", 199), ("coding", "college", 199),
                                               ("cbse_12", "school", 149), ("gate_cs", "exam", 249)])
def test_each_kind_of_student_pays_its_own_price(client, exam, sector, month):
    """A student sees and pays the price for what they prepare for (kinds without their own pay the exam price)."""
    h, _ = _user(client, f"kind.{exam}@example.com", exam)
    assert client.get("/api/billing/plans", headers=h).json()["sector"] == sector
    assert client.post("/api/billing/pro", headers=h).json()["amount_inr"] == month
    # what the page was showing doesn't change what they pay
    assert client.get("/api/billing/plans?sector=school", headers=h).json()["sector"] == "school"
    assert client.post("/api/billing/pro", headers=h).json()["amount_inr"] == month


def test_the_launch_offer_ends_once_its_places_are_taken(client, monkeypatch):
    pricing.forget(0)
    monkeypatch.setattr(settings, "PRO_OFFER_PLACES", pricing.places_taken() + 1)  # one place left
    first, uid = _user(client, "offer.first@example.com")
    second, _ = _user(client, "offer.second@example.com")
    assert client.get("/api/billing/plans").json()["offer"]["left"] == 1
    assert client.post("/api/billing/pro", headers=second).json()["amount_inr"] == 249  # an unpaid checkout takes no place
    assert _pay(client, first)["amount_inr"] == 249
    with SessionLocal() as db:
        assert db.query(Payment).filter_by(user_id=uid, status="paid").one().launch_offer
    data = client.get("/api/billing/plans").json()
    assert data["offer"] is None and data["plans"][1]["price_inr"] == 359 and data["plans"][1]["regular_inr"] is None
    assert "fair use: about 115 hours" in data["plans"][1]["features"][0]
    assert client.post("/api/billing/pro", headers=second).json()["amount_inr"] == 359
    assert client.post("/api/billing/pro", headers=first).json()["amount_inr"] == 359  # the place was for one pass


def test_a_students_ai_ceiling_follows_the_pass_they_bought(client):
    """A school student's ₹149 month may spend what ₹149 brings in, not what the dearest pass does."""
    h, uid = _user(client, "ceiling.school@example.com", "cbse_11")
    _pay(client, h)
    with SessionLocal() as db:
        user = db.get(User, uid)
        assert usage.ceiling_inr(user) == pytest.approx(149 * (1 - RAZORPAY_FEE), rel=1e-3)
        _spent(uid, 140)
        assert usage.can_spend(db, user, "doubt")
        _spent(uid, 10)
        assert not usage.can_spend(db, user, "doubt")  # Rs 150 is more than the month brought in


def test_a_year_pass_adds_a_year(client):
    h, uid = _user(client, "year.pass@example.com")
    checkout = client.post("/api/billing/pro?plan=year", headers=h).json()
    assert checkout["amount_inr"] == pricing.price("exam", "year")[0] and checkout["description"] == "Focs Pro · 1 year"
    assert client.post(f"/api/billing/payments/{checkout['payment_id']}/confirm", headers=h, json={}).status_code == 200
    with SessionLocal() as db:
        u = db.get(User, uid)
        assert u.plan == "pro" and timedelta(days=364) < u.pro_until - utcnow() <= timedelta(days=365)


def test_a_students_ai_is_capped_over_30_days(client):
    h, uid = _user(client, "ceiling@example.com")
    with SessionLocal() as db:
        user = db.get(User, uid)
        assert usage.can_spend(db, user, "doubt")
        _spent(uid, settings.AI_CEILING_FREE_INR + 1)  # more than Starter's 30 days hold
        assert not usage.can_spend(db, user, "doubt")
        with pytest.raises(Exception) as refused:
            usage.require(db, user, "doubt")
        assert refused.value.status_code == 402 and "fair-use" in refused.value.detail
    assert client.get("/api/usage", headers=h).json()["fair_use_pct"] == 100
    with SessionLocal() as db:  # older than 30 days: it no longer counts
        db.query(LlmCall).filter(LlmCall.user_id == uid).update({LlmCall.created_at: utcnow() - timedelta(days=31)})
        db.commit()
    ledger._user_usd.pop(uid, None)
    with SessionLocal() as db:
        assert usage.can_spend(db, db.get(User, uid), "doubt")


def test_pro_has_its_own_higher_ceiling(client):
    _, uid = _user(client, "ceiling.pro@example.com")
    with SessionLocal() as db:
        user = db.get(User, uid)
        user.plan = "pro"
        db.commit()
        _spent(uid, settings.AI_CEILING_FREE_INR + 1)
        assert usage.can_spend(db, user, "doubt")  # past Starter's ceiling, well inside Pro's
        _spent(uid, settings.AI_CEILING_PRO_INR)
        assert not usage.can_spend(db, user, "doubt")


def test_free_accounts_are_paid_for_by_pro_income(client, monkeypatch):
    monkeypatch.setattr(settings, "FREE_AI_DAY_FLOOR_INR", 50.0)
    monkeypatch.setattr(settings, "FREE_AI_REVENUE_SHARE", 0.2)
    monkeypatch.setattr(ledger, "_free_budget", [0.0, -1e9])
    before = ledger.free_budget_inr()
    _, uid = _user(client, "income@example.com")
    with SessionLocal() as db:
        db.add(Payment(user_id=uid, purpose="pro_year", amount_inr=3000, provider="dev", status="paid", paid_at=utcnow()))
        db.commit()
    monkeypatch.setattr(ledger, "_free_budget", [0.0, -1e9])
    assert ledger.free_budget_inr() == pytest.approx(before + 0.2 * 3000 / 30)  # Rs 20 a day more

    # what a Pro student spends is paid for by their pass: it doesn't use up the free accounts' budget
    with SessionLocal() as db:
        db.get(User, uid).plan = "pro"
        db.commit()
    ledger.forget_plan(uid)
    today = ledger.spent_today_inr()
    token = ledger.current_user.set(uid)
    try:
        ledger.record_cost("lecture_audio", "test", 1.0)
    finally:
        ledger.current_user.reset(token)
    assert ledger.spent_today_inr() == pytest.approx(today)
    ledger.record_cost("question_bank", "test", 0.01)  # shared work does count
    assert ledger.spent_today_inr() == pytest.approx(today + 0.01 * settings.USD_INR)


def _set_lecture_time(uid, seconds, plan=None):
    with SessionLocal() as db:
        user = db.get(User, uid)
        if plan:
            user.plan = plan
        user.lecture_day_start, user.lecture_day_seconds = utcnow(), seconds
        db.commit()


@pytest.mark.parametrize("plan,hours", [("pro", 7), ("free", 0.5)])
def test_lecture_notes_are_capped_in_hours_a_day(client, monkeypatch, plan, hours):
    """Pro: AI notes for 7 hours of lecture a day, Starter half an hour; past that the lecture carries on with basic notes."""
    from app.services import ai
    from tests.conftest import board_png

    written = []
    def notes(text, exam, prev_topic=None, offline_only=False, patient=True, board=None):
        if offline_only:  # what a student gets past the cap: basic notes, no AI
            return {"is_lecture": True, "topic": "Capped", "subject": "Physics", "notes_md": "## Basic notes", "source": "offline"}
        written.append(text)
        return {"is_lecture": True, "topic": "Capped", "subject": "Physics", "notes_md": "## AI notes", "source": "ai"}

    monkeypatch.setattr(ai, "generate_notes", notes)
    assert usage.lecture_limit_s(plan) == round(hours * 3600)
    h, uid = _user(client, f"lecture.hours.{plan}@example.com")

    def board(lines):
        sid = client.post("/api/sessions", headers=h, json={"title": "Capped"}).json()["id"]
        return client.post(f"/api/capture/{sid}/frame", headers=h, files={"frame": ("f.png", board_png(lines), "image/png")}).json()

    _set_lecture_time(uid, round(hours * 3600) - 30, plan)
    r = board([f"Capped board one {plan}", "F = m a", "a = F / m"])
    assert r["status"] == "created" and not r["basic_mode"] and len(written) == 1
    _set_lecture_time(uid, round(hours * 3600))
    r = board([f"Capped board two {plan}", "p = m v", "F = dp / dt"])
    assert r["status"] == "created" and r["basic_mode"] and len(written) == 1  # basic notes, no AI
    assert client.get("/api/usage", headers=h).json()["lecture"]["pct"] == 100

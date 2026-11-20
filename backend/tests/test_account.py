"""Data rights: export everything, delete everything."""
from tests.conftest import board_png


def _register(client, email):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "Ira Shah", "password": "correct-horse-1",
                                                 "exam_target": "neet"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_export_and_delete_account(client):
    h = _register(client, "ira@example.com")
    s = client.post("/api/sessions", headers=h, json={"title": "Cell biology"}).json()
    img = board_png(["Mitochondria", "Powerhouse of the cell", "ATP synthesis"])
    assert client.post(f"/api/capture/{s['id']}/frame", headers=h, files={"frame": ("f.png", img, "image/png")}).status_code == 200
    client.post("/api/quiz/attempt", headers=h, json={"question": "q", "q_type": "mcq", "correct": False})
    client.post("/api/flashcards", headers=h, json={"front": "ATP?", "back": "Energy currency"})
    code = client.post("/api/rooms", headers=h, json={"name": "Bio squad"}).json()["code"]

    r = client.get("/api/auth/export", headers=h)
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    data = r.json()
    assert data["profile"]["email"] == "ira@example.com" and "hashed_pw" not in str(data)
    assert data["lectures"][0]["title"] == "Cell biology" and data["lectures"][0]["boards"]
    assert data["answers"] and data["flashcards"]

    assert client.post("/api/auth/delete-account", headers=h, json={"password": "correct-horse-1", "confirm": "delete"}).status_code == 422
    assert client.post("/api/auth/delete-account", headers=h, json={"password": "wrong-password", "confirm": "DELETE"}).status_code == 400
    assert client.post("/api/auth/delete-account", headers=h, json={"password": "correct-horse-1", "confirm": "DELETE"}).status_code == 204

    assert client.post("/api/auth/login", json={"email": "ira@example.com", "password": "correct-horse-1"}).status_code == 401
    assert client.get("/api/auth/me", headers=h).status_code == 401
    other = _register(client, "ira2@example.com")
    assert client.post("/api/rooms/join", headers=other, json={"code": code}).status_code == 404


def test_deleting_an_account_with_payments(client):
    """An open, unpaid checkout used to block deleting the account (payments pointed at the user). A paid one is kept
    for the accounts, on a row with no name, email or way to sign in."""
    from app.core.database import SessionLocal
    from app.models.payment import Payment
    from app.models.user import User

    for email, status in (("unpaid@example.com", "created"), ("paid@example.com", "paid")):
        h = _register(client, email)
        uid = client.get("/api/auth/me", headers=h).json()["id"]
        with SessionLocal() as db:
            db.add(Payment(user_id=uid, purpose="pro_month", amount_inr=249, provider="razorpay", status=status))
            db.commit()
        assert client.post("/api/auth/delete-account", headers=h, json={"password": "correct-horse-1", "confirm": "DELETE"}).status_code == 204
        with SessionLocal() as db:
            user = db.get(User, uid)
            kept = db.query(Payment).filter(Payment.user_id == uid).count()
            if status == "created":
                assert user is None and kept == 0
            else:
                assert kept == 1 and user.email.endswith("@deleted.invalid") and user.full_name == "Deleted account" and not user.is_active
        assert client.post("/api/auth/login", json={"email": email, "password": "correct-horse-1"}).status_code == 401

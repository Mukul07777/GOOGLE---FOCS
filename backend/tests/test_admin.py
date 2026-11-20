"""Admin dashboard, cost ledger and model routing."""
import pytest

from app.core.config import settings
from app.services import ledger
from app.services.llm import Provider, llm


def _register(client, email, name="Admin Person"):
    r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": name, "password": "correct-horse-1", "exam_target": "jee"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()["user"]["id"]


def test_cost_ledger_prices_and_attribution(client):
    h, uid = _register(client, "ledger.user@example.com", "Ledger User")
    ledger.flush()
    token = ledger.current_user.set(uid)
    try:
        ledger.record("board_notes", "openai/gpt-oss-20b", {"prompt_tokens": 1000, "completion_tokens": 1000})
        ledger.record("doubt", "openai/gpt-oss-120b", {"prompt_tokens": 2000, "completion_tokens": 500})
        ledger.record("doubt", "some/unknown-model", None)  # missing usage never breaks anything
    finally:
        ledger.current_user.reset(token)
    assert ledger.flush() == 3
    assert ledger.cost_usd("openai/gpt-oss-20b", 1000, 1000) == pytest.approx(0.000375)
    assert ledger.cost_usd("openai/gpt-oss-120b", 2000, 500) == pytest.approx(0.0006)

    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.llm_call import LlmCall

    with SessionLocal() as db:
        rows = db.scalars(select(LlmCall).where(LlmCall.user_id == uid)).all()
    assert {r.feature for r in rows} == {"board_notes", "doubt"} and len(rows) == 3
    assert sum(r.cost_usd for r in rows) == pytest.approx(0.000975)

    # deleting the account keeps the cost history, anonymised
    assert client.post("/api/auth/delete-account", headers=h, json={"password": "correct-horse-1", "confirm": "DELETE"}).status_code == 204
    with SessionLocal() as db:
        assert not db.scalars(select(LlmCall).where(LlmCall.user_id == uid)).all()
        assert len([r for r in db.scalars(select(LlmCall).where(LlmCall.user_id.is_(None))) if r.feature in ("board_notes", "doubt")]) >= 3


def _admin_login(client, username="admin@focs", password="panel-password-1"):
    return client.post("/api/admin/login", json={"username": username, "password": password})


@pytest.fixture
def admin_panel(monkeypatch):
    from app.core.security import hash_password

    monkeypatch.setattr(settings, "ADMIN_USERNAME", "admin@focs")
    monkeypatch.setattr(settings, "ADMIN_PASSWORD_HASH", hash_password("panel-password-1"))


def test_admin_panel_has_its_own_sign_in(client, admin_panel):
    member, _ = _register(client, "member.only@example.com", "Member Only")
    assert client.get("/api/admin/overview", headers=member).status_code == 401  # a student login never opens it
    assert client.get("/api/admin/overview").status_code == 401

    assert _admin_login(client, password="wrong-password-1").status_code == 401
    assert _admin_login(client, username="root@focs").status_code == 401
    r = _admin_login(client, username="  Admin@Focs ")  # the ID is not case-sensitive
    assert r.status_code == 200 and r.json()["username"] == "admin@focs"
    admin = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get("/api/admin/me", headers=admin).json() == {"username": "admin@focs"}
    assert client.get("/api/auth/me", headers=admin).status_code == 401  # and the admin session is no student login
    assert "is_admin" not in client.get("/api/auth/me", headers=member).json()

    uid = client.get("/api/auth/me", headers=member).json()["id"]
    token = ledger.current_user.set(uid)
    ledger.record("pop_quiz", "openai/gpt-oss-20b", {"prompt_tokens": 1800, "completion_tokens": 550})
    ledger.current_user.reset(token)
    data = client.get("/api/admin/overview", headers=admin).json()
    assert data["goal"]["target"] == settings.GOAL_CUSTOMERS and data["users"]["total"] >= 1
    assert data["users"]["active"]["day"] >= 1  # signing in counts as being seen
    assert data["ai_cost"]["total"]["usd"] > 0 and data["ai_cost"]["calls"] >= 1
    assert any(f["feature"] == "pop_quiz" for f in data["ai_cost"]["by_feature"])
    assert len(data["series"]) == 30 and data["revenue"]["payments_connected"] is False
    found = client.get("/api/admin/users?q=member.only", headers=admin).json()
    assert len(found) == 1 and found[0]["email"] == "member.only@example.com"


def test_new_admin_password_signs_old_sessions_out(client, admin_panel, monkeypatch):
    from app.core.security import hash_password

    admin = {"Authorization": f"Bearer {_admin_login(client).json()['token']}"}
    assert client.get("/api/admin/me", headers=admin).status_code == 200
    monkeypatch.setattr(settings, "ADMIN_PASSWORD_HASH", hash_password("a-brand-new-password"))
    assert client.get("/api/admin/me", headers=admin).status_code == 401
    assert _admin_login(client, password="a-brand-new-password").status_code == 200


def test_admin_sign_in_resists_guessing(client, admin_panel):
    from app.core import ratelimit

    codes = [_admin_login(client, password=f"guess-number-{i}").status_code for i in range(6)]
    assert codes[:5] == [401] * 5 and codes[5] == 429  # fast guessing: 5 a minute

    ratelimit.reset()
    for _ in range(3):  # signing in and out again and again never locks the real admin out
        assert _admin_login(client).status_code == 200
        ratelimit.reset()
    for _ in range(10):
        ratelimit.record("admin-login-failed:testclient")  # 10 wrong tries in the last 15 minutes
    r = _admin_login(client)
    assert r.status_code == 429 and "minutes" in r.json()["detail"]  # even the right password waits


def test_admin_sign_in_off_until_a_password_is_set(client, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_PASSWORD_HASH", "")
    r = _admin_login(client)
    assert r.status_code == 503 and "set_admin.bat" in r.json()["detail"]


def test_admin_hash_survives_the_env_file(tmp_path):
    """bcrypt hashes are full of "$": the quoted form set_admin.py writes must load back unchanged."""
    from app.core.config import Settings
    from app.core.security import hash_password, verify_password

    hashed = hash_password("panel-password-1")
    env = tmp_path / ".env"
    env.write_text(f"ADMIN_USERNAME=boss@focs\nADMIN_PASSWORD_HASH='{hashed}'\n", encoding="utf-8")
    loaded = Settings(_env_file=str(env))
    assert loaded.ADMIN_USERNAME == "boss@focs" and loaded.ADMIN_PASSWORD_HASH == hashed
    assert verify_password("panel-password-1", loaded.ADMIN_PASSWORD_HASH)


def test_light_jobs_try_the_cheaper_model_first(monkeypatch):
    chain = [Provider("primary:openai/gpt-oss-120b", "https://x", "k", "openai/gpt-oss-120b"),
             Provider("primary:openai/gpt-oss-20b", "https://x", "k", "openai/gpt-oss-20b"),
             Provider("fallback:gemini-3.1-flash-lite", "https://y", "k", "gemini-3.1-flash-lite")]
    monkeypatch.setattr("app.services.llm.providers", lambda: list(chain))
    tried: list[str] = []
    monkeypatch.setattr(type(llm), "_call", lambda self, p, *a, **k: tried.append(p.model) or "ok")

    assert llm.chat_with_model([{"role": "user", "content": "x"}], tier="light")[1] == "openai/gpt-oss-20b"
    assert llm.chat_with_model([{"role": "user", "content": "x"}])[1] == "openai/gpt-oss-120b"
    assert tried == ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]


def test_expensive_model_is_not_in_the_default_chain():
    from app.core.config import Settings

    defaults = Settings(_env_file=None)
    assert "qwen" not in defaults.LLM_MODEL and "qwen" not in defaults.LLM_FALLBACK_MODEL
    assert defaults.LLM_FALLBACK_MODEL.split(",")[0] == "gemini-3.1-flash-lite"


def test_set_admin_script_updates_env_in_place(tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path

    from app.core.config import Settings
    from app.core.security import hash_password, verify_password

    spec = importlib.util.spec_from_file_location("set_admin", Path(__file__).parents[1] / "scripts" / "set_admin.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    env = tmp_path / ".env"
    env.write_text("GROQ_API_KEY=keep-me\nADMIN_USERNAME=old@focs\nSECRET_KEY=keep-me-too\n", encoding="utf-8")
    monkeypatch.setattr(script, "ENV", env)

    hashed = hash_password("panel-password-1")
    script.save({"ADMIN_USERNAME": "admin@focs", "ADMIN_PASSWORD_HASH": f"'{hashed}'"})
    text = env.read_text(encoding="utf-8")
    assert "GROQ_API_KEY=keep-me" in text and "SECRET_KEY=keep-me-too" in text and "old@focs" not in text
    loaded = Settings(_env_file=str(env))
    assert loaded.ADMIN_USERNAME == "admin@focs" and verify_password("panel-password-1", loaded.ADMIN_PASSWORD_HASH)


def test_admin_id_on_the_student_sign_in_points_to_the_panel(client, admin_panel):
    r = client.post("/api/auth/login", json={"email": " Admin@Focs ", "password": "panel-password-1"})
    assert r.status_code == 409 and "/admin" in r.json()["detail"] and "token" not in r.text
    r = client.post("/api/auth/login", json={"email": "not-an-email", "password": "whatever-123"})
    assert r.status_code == 401 and r.json()["detail"] == "Incorrect email or password."

from fastapi.testclient import TestClient

from app.main import create_app


def test_head_matches_get_without_body():
    c = TestClient(create_app())
    for path in ("/api/health", "/", "/robots.txt"):
        g, h = c.get(path), c.head(path)
        assert h.status_code == g.status_code == 200, path
        assert h.content == b""


def test_head_on_missing_route_is_404_not_405():
    assert TestClient(create_app()).head("/api/does-not-exist").status_code == 404


def test_ready_checks_database(monkeypatch):
    c = TestClient(create_app())
    ok = c.get("/api/health/ready")
    assert ok.status_code == 200 and ok.json() == {"status": "ok", "database": "ok"}

    import app.main as main

    class Dead:
        def connect(self):
            raise RuntimeError("db down")
    monkeypatch.setattr(main, "engine", Dead())
    bad = c.get("/api/health/ready")
    assert bad.status_code == 503 and bad.json()["database"] == "down"
    assert "db down" not in bad.text  # no internals leaked
    assert c.head("/api/health/ready").status_code == 503

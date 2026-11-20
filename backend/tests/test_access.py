"""Who may use what (role-based access). Every route of the API is called signed out, as a student, as a mentor and
with a student's token on the admin panel, and each must answer as app/api/__init__.py says:
- signed out: 401 everywhere but the few public routes;
- a mentor: 403 on every route of a student area (studying and the AI), and on each student-only endpoint;
- a student: 403 on each mentor-only endpoint;
- a student's or a mentor's token: 401 on the admin panel.
A new route is checked the day it is added; a new public one must be added to PUBLIC below, on purpose."""
import re

import pytest
from fastapi.routing import APIRoute
from starlette.websockets import WebSocketDisconnect

from app import api as api_pkg

PUBLIC = {
    ("POST", "/api/auth/register"), ("POST", "/api/auth/login"), ("POST", "/api/auth/google"),
    ("POST", "/api/auth/login/verify"), ("POST", "/api/auth/login/resend"),  # the second step: the challenge is the proof
    ("POST", "/api/auth/forgot-password"), ("POST", "/api/auth/reset-password"),
    ("POST", "/api/admin/login"), ("GET", "/api/billing/plans"), ("POST", "/api/billing/webhook"),
    ("GET", "/api/mentors/photos/{name}"), ("GET", "/api/prep/options"), ("GET", "/api/parent/view/{token}"),
}


def _routes():
    """(method, path, module name, names of the route's own dependencies) for every HTTP route under /api."""
    owner = {id(m.router): m.__name__.rsplit(".", 1)[-1] for m in api_pkg.STUDENT_AREAS + api_pkg.SHARED_AREAS}

    def names(dependant, out):
        for d in dependant.dependencies:
            out.add(getattr(d.call, "__name__", ""))
            names(d, out)
        return out

    found = []
    for inc in api_pkg.api_router.routes:
        router = getattr(inc, "original_router", None)
        for r in (router.routes if router else [inc]):
            if isinstance(r, APIRoute):
                for method in r.methods - {"HEAD"}:
                    found.append((method, "/api" + r.path if not r.path.startswith("/api") else r.path,
                                  owner.get(id(router), ""), names(r.dependant, set())))
    assert len(found) > 150  # the walk found the routes (FastAPI keeps included routers whole)
    return found


ROUTES = _routes()
STUDENT_AREA = {m.__name__.rsplit(".", 1)[-1] for m in api_pkg.STUDENT_AREAS}


def _call(client, method, path, token=None):
    url = re.sub(r"\{[^}]+\}", "1", path)
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.request(method, url, headers=headers, json={})


@pytest.fixture(scope="module")
def tokens(client):
    def make(email, **extra):
        r = client.post("/api/auth/register", json={"accepted_terms": True, "email": email, "full_name": "Access Check", "password": "correct-horse-1",
                                                    "accepted_terms": True, **extra})
        assert r.status_code == 201, r.text
        return r.json()["access_token"]
    return {"student": make("access.student@example.com", exam_target="jee"), "mentor": make("access.mentor@example.com", role="mentor")}


def test_every_route_but_the_public_ones_needs_a_sign_in(client):
    open_ = [(m, p) for m, p, _, _ in ROUTES if (m, p) not in PUBLIC and _call(client, m, p).status_code != 401]
    assert open_ == []


def test_a_mentor_account_is_refused_every_student_area_and_student_endpoint(client, tokens):
    targets = [(m, p) for m, p, mod, deps in ROUTES if (m, p) not in PUBLIC and (mod in STUDENT_AREA or "require_student" in deps)]
    assert len(targets) > 120
    let_in = [(m, p, r.status_code) for m, p in targets if (r := _call(client, m, p, tokens["mentor"])).status_code != 403]
    assert let_in == []
    assert "it's for students" in _call(client, "GET", "/api/sessions", tokens["mentor"]).json()["detail"]


def test_a_student_account_is_refused_every_mentor_endpoint(client, tokens):
    targets = [(m, p) for m, p, _, deps in ROUTES if "require_mentor" in deps]
    assert len(targets) >= 10
    let_in = [(m, p, r.status_code) for m, p in targets if (r := _call(client, m, p, tokens["student"])).status_code != 403]
    assert let_in == []


def test_the_admin_panel_takes_only_its_own_sign_in(client, tokens):
    targets = [(m, p) for m, p, _, deps in ROUTES if "require_admin" in deps]
    assert len(targets) >= 10
    for who in ("student", "mentor"):
        let_in = [(m, p, who) for m, p in targets if _call(client, m, p, tokens[who]).status_code != 401]
        assert let_in == []


def test_each_role_still_reaches_its_own_side(client, tokens):
    assert _call(client, "GET", "/api/sessions", tokens["student"]).status_code == 200
    assert _call(client, "GET", "/api/mentors/me", tokens["mentor"]).status_code == 200
    assert _call(client, "GET", "/api/mentors/me", tokens["student"]).status_code == 403
    for who in ("student", "mentor"):  # the account, notifications and price list are everyone's
        assert _call(client, "GET", "/api/auth/me", tokens[who]).status_code == 200
        assert _call(client, "GET", "/api/notifications", tokens[who]).status_code == 200
        assert _call(client, "GET", "/api/billing/plans", tokens[who]).status_code == 200
    assert _call(client, "POST", "/api/billing/pro", tokens["mentor"]).status_code == 403  # Pro is a student's pass


def test_a_mentor_cant_join_a_study_room(client, tokens):
    code = client.post("/api/rooms", headers={"Authorization": f"Bearer {tokens['student']}"}, json={"name": "Access room"}).json()["code"]
    with client.websocket_connect(f"/api/rooms/ws/{code}") as ws:
        ws.send_json({"type": "auth", "token": tokens["mentor"]})
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == 4403


def test_no_one_can_give_themselves_a_role_or_a_plan(client, tokens):
    h = {"Authorization": f"Bearer {tokens['student']}"}
    me = client.patch("/api/auth/me", headers=h, json={"role": "mentor", "plan": "pro", "is_active": True, "full_name": "Still Student"}).json()
    assert me["role"] == "student" and me["plan"] == "free" and me["full_name"] == "Still Student"

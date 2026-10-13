import pytest
from sqlalchemy import select

from app.database import models as m
from tests.conftest import ADMIN_PIN, Client
from app.main import app


def fresh():
    return Client(app, base_url="http://127.0.0.1")


def test_admin_pages_redirect_when_signed_out(client):
    r = client.get("/admin", follow_redirects=False)
    assert r.status_code == 303 and "/admin/" in r.headers["location"]
    assert client.get("/admin/import", follow_redirects=False).status_code == 303
    assert client.get("/admin/prompts/new", follow_redirects=False).status_code == 303
    assert client.get("/api/admin/prompts").status_code == 401
    assert "sign-in is required" in client.get("/api/admin/statistics").json()["error"]["message"]


def test_first_run_setup_and_hashed_storage(admin, db):
    cred = db.scalar(select(m.AdminCredential))
    assert cred is not None
    assert ADMIN_PIN not in (cred.pin_hash, cred.salt) and len(cred.pin_hash) == 64 and len(cred.salt) == 32 and cred.iterations >= 100_000
    assert ADMIN_PIN not in str(cred.__dict__)
    # the setup screen is no longer available once a PIN exists
    r = fresh().post("/api/admin/setup", json={"pin": "another1", "confirm": "another1"})
    assert r.status_code == 409


def test_salts_are_unique():
    from app.core.security import hash_pin
    assert hash_pin("same-pin")[0] != hash_pin("same-pin")[0]
    assert hash_pin("same-pin")[1] != hash_pin("same-pin")[1]


@pytest.mark.parametrize("pin", ["", "123", "aaaaaaaa"])
def test_weak_pins_rejected_at_setup(pin):
    from app.core.security import validate_pin_strength
    assert validate_pin_strength(pin)


def test_login_logout_and_session_cookie_flags(admin):
    c = fresh()
    bad = c.post("/api/admin/login", json={"pin": "wrong-pin"})
    assert bad.status_code == 401 and "not correct" in bad.json()["error"]["message"] and "attempt" in bad.json()["error"]["hint"]
    ok = c.post("/api/admin/login", json={"pin": ADMIN_PIN})
    assert ok.status_code == 200
    cookie = ok.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "max-age=" in cookie
    assert c.get("/api/admin/status").json() == {"configured": True, "authenticated": True}
    assert c.get("/admin").status_code == 200
    c.post("/api/admin/logout")
    assert c.get("/api/admin/status").json()["authenticated"] is False
    assert c.get("/api/admin/prompts").status_code == 401


def test_pin_never_appears_in_html_or_logs(admin, caplog):
    html = admin.get("/admin").text
    assert ADMIN_PIN not in html
    assert "Local PIN authentication is intended for a local demonstration" in html
    fresh().post("/api/admin/login", json={"pin": ADMIN_PIN})
    assert ADMIN_PIN not in caplog.text


def test_tampered_or_expired_session_is_rejected(admin):
    c = fresh()
    c.cookies.set("pch_session", "forged.value.here")
    assert c.get("/api/admin/prompts").status_code == 401
    from app.api.deps import session_manager
    mgr = session_manager()
    nonce = None
    from app.database.connection import get_session_factory
    with get_session_factory()() as db:
        nonce = db.scalar(select(m.AdminCredential)).session_nonce
    token = mgr.create_session(nonce)
    assert mgr.read_session(token, nonce) == (True, "ok")
    assert mgr.read_session(token, "different-nonce")[0] is False
    mgr_short = type(mgr)("test-secret-key-not-used-anywhere-else-0123456789", 1)
    mgr_short.max_age = -1  # force expiry
    assert mgr_short.read_session(token, nonce) == (False, "expired")
    c.cookies.set("pch_session", token)
    assert c.get("/api/admin/prompts").status_code == 200


def test_expired_session_gives_actionable_message(admin, monkeypatch):
    import app.api.deps as deps
    c = fresh()
    c.post("/api/admin/login", json={"pin": ADMIN_PIN})
    real = deps.session_manager()
    monkeypatch.setattr(real, "max_age", -1)
    r = c.get("/api/admin/prompts")
    assert r.status_code == 401 and "expired" in r.json()["error"]["message"]
    page = c.get("/admin", follow_redirects=False)
    assert page.status_code == 303


def test_rate_limit_locks_after_repeated_failures(admin, db):
    c = fresh()
    codes = [c.post("/api/admin/login", json={"pin": f"wrong-{i}"}).status_code for i in range(6)]
    assert codes[:4] == [401] * 4 and codes[4] == 429 and codes[5] == 429
    locked = c.post("/api/admin/login", json={"pin": ADMIN_PIN})  # even the right PIN is refused while locked
    assert locked.status_code == 429 and "minute" in locked.json()["error"]["message"]
    cred = db.scalar(select(m.AdminCredential))
    cred.failed_attempts, cred.locked_until = 0, None
    db.commit()
    assert c.post("/api/admin/login", json={"pin": ADMIN_PIN}).status_code == 200


def test_login_form_flow_with_csrf(admin):
    c = fresh()
    page = c.get("/admin/login")
    assert page.status_code == 200 and "Administrator sign-in" in page.text
    token = c.cookies.get("pch_csrf")
    bad = c.post("/admin/login", data={"pin": "nope", "csrf_token": token}, follow_redirects=False)
    assert bad.status_code == 401 and "not correct" in bad.text
    good = c.post("/admin/login", data={"pin": ADMIN_PIN, "csrf_token": token, "next": "/admin/import"}, follow_redirects=False)
    assert good.status_code == 303 and good.headers["location"] == "/admin/import"
    assert c.get("/admin/import").status_code == 200
    evil = c.post("/admin/login", data={"pin": ADMIN_PIN, "csrf_token": token, "next": "//evil.example.com"}, follow_redirects=False)
    assert evil.headers["location"] == "/admin"  # open redirects are not possible


def test_admin_pages_render_when_signed_in(admin):
    for path in ("/admin", "/admin/prompts/new", "/admin/prompts/1/edit", "/admin/import", "/admin/content"):
        r = admin.get(path)
        assert r.status_code == 200, path
    assert "Create backup" in admin.get("/admin").text


def test_admin_listing_and_statistics(admin):
    r = admin.get("/api/admin/prompts", params={"status": "published", "page_size": 5}).json()
    assert r["total"] >= 75 and len(r["items"]) == 5
    assert admin.get("/api/admin/prompts", params={"q": "sql"}).json()["total"] >= 5
    stats = admin.get("/api/admin/statistics").json()
    assert stats["total_prompts"] >= 75 and "events" in stats and "top_prompts" in stats
    assert isinstance(admin.get("/api/admin/imports").json(), list)
    assert isinstance(admin.get("/api/admin/validation-errors").json(), list)


def test_validation_errors_are_logged_without_values(admin):
    secret = "SuperSecretValue123"
    admin.post("/api/prompts", json={"title": "ab", "description": secret, "full_prompt": "x"})
    entries = admin.get("/api/admin/validation-errors").json()
    assert entries and secret not in str(entries)


def test_content_management_endpoints(admin):
    glossary = admin.post("/api/glossary", json={"term": "Test Term", "definition": "A term used by tests.", "example": ""})
    assert glossary.status_code == 201
    assert admin.post("/api/glossary", json={"term": "test term", "definition": "Duplicate term."}).status_code == 409
    assert admin.put(f"/api/glossary/{glossary.json()['id']}", json={"term": "Test Term", "definition": "Updated definition text."}).status_code == 200
    assert admin.delete(f"/api/glossary/{glossary.json()['id']}").status_code == 200

    mod = {"number": 99, "title": "Admin Lesson", "summary": "s", "objective": "Learn admin things", "explanation": "This lesson has enough explanation text.",
           "tips": ["t"], "common_mistakes": ["m"], "checks": [{"question": "Which is right?", "options": ["A", "B"], "correct_index": 1, "explanation": "B"}]}
    made = admin.post("/api/learning/modules", json=mod)
    assert made.status_code == 201
    assert admin.post("/api/learning/modules", json={**mod, "title": "Other"}).status_code == 409  # duplicate lesson number
    assert admin.post("/api/learning/modules", json={**mod, "number": 98, "explanation": " "}).status_code in (422,)  # empty lesson
    assert admin.post("/api/learning/modules", json={**mod, "number": 98, "checks": [{"question": "Q?????", "options": ["A", "B"], "correct_index": 5}]}).status_code == 422
    assert admin.patch(f"/api/learning/modules/{made.json()['id']}/flags", json={"published": False}).status_code == 200
    from tests.conftest import Client as C
    assert all(x["number"] != 99 for x in C(app, base_url="http://127.0.0.1").get("/api/learning/modules").json())
    assert admin.delete(f"/api/learning/modules/{made.json()['id']}").status_code == 200

    ex = {"scenario": "Admin Example", "weak_prompt": "Do it.", "improved_prompt": "Act as an analyst.\n\nTask:\nSummarise the report in five bullets.", "problems": ["vague"], "improvements": ["clear"]}
    e = admin.post("/api/examples", json=ex)
    assert e.status_code == 201 and e.json()["improved_score"] > e.json()["weak_score"]
    assert admin.post("/api/examples", json=ex).status_code == 409
    assert admin.delete(f"/api/examples/{e.json()['id']}").status_code == 200


def test_change_pin_invalidates_other_sessions(admin, db):
    other = fresh()
    other.post("/api/admin/login", json={"pin": ADMIN_PIN})
    me = fresh()
    me.post("/api/admin/login", json={"pin": ADMIN_PIN})
    r = me.post("/api/admin/change-pin", json={"current": ADMIN_PIN, "new": "new-pin-9876", "confirm": "new-pin-9876"})
    assert r.status_code == 200
    assert other.get("/api/admin/prompts").status_code == 401  # signed out everywhere else
    assert me.get("/api/admin/prompts").status_code == 200
    back = me.post("/api/admin/change-pin", json={"current": "new-pin-9876", "new": ADMIN_PIN, "confirm": ADMIN_PIN})
    assert back.status_code == 200
    assert me.post("/api/admin/change-pin", json={"current": "bad", "new": "abcdef1", "confirm": "abcdef1"}).status_code == 401
    assert me.post("/api/admin/change-pin", json={"current": ADMIN_PIN, "new": "abcdef1", "confirm": "different"}).status_code == 422
    admin.cookies.clear()
    admin.post("/api/admin/login", json={"pin": ADMIN_PIN})

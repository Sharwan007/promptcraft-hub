from tests.conftest import Client
from app.main import app


def test_csrf_required_for_state_changes_without_json():
    c = Client(app, base_url="http://127.0.0.1")
    c.get("/api/health")  # receives the CSRF cookie
    r = c.request("POST", "/api/favorites/1", no_csrf=True)
    assert r.status_code == 403
    assert "token" in r.json()["error"]["message"].lower()


def test_csrf_header_must_match_cookie():
    c = Client(app, base_url="http://127.0.0.1")
    c.get("/api/health")
    r = c.request("POST", "/api/favorites/1", headers={"X-CSRF-Token": "forged"})
    assert r.status_code == 403


def test_cross_origin_requests_are_blocked():
    c = Client(app, base_url="http://127.0.0.1")
    r = c.post("/api/prompts/analyze", json={"prompt": "Write a report"}, headers={"Origin": "http://evil.example.com"})
    assert r.status_code == 403


def test_form_post_needs_csrf_field():
    c = Client(app, base_url="http://127.0.0.1")
    c.get("/admin/setup")
    r = c.request("POST", "/admin/login", data={"pin": "x"}, no_csrf=True, follow_redirects=False)
    assert r.status_code == 403


def test_html_is_escaped_in_search_highlight(client):
    r = client.get("/prompts", params={"q": "<script>alert(1)</script>"})
    assert r.status_code == 200
    assert "<script>alert(1)</script>" not in r.text


def test_cors_only_allows_local_origin(client):
    r = client.options("/api/prompts", headers={"Origin": "http://evil.example.com", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in r.headers
    r = client.options("/api/prompts", headers={"Origin": "http://127.0.0.1:8000", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == "http://127.0.0.1:8000"

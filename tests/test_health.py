def test_health_endpoint(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["app"] == "PromptCraft Hub" and body["database"] == "ok"
    assert isinstance(body["pid"], int)


def test_home_page_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    for text in ("Start here", "Build a Prompt", "Improve a Prompt", "Diagnose a Prompt", "Prompt of the day", "Quick prompt-engineering tips"):
        assert text in r.text
    assert "Build better prompts. Get better results." in r.text


def test_prompt_library_page(client):
    r = client.get("/prompts")
    assert r.status_code == 200
    assert "Prompt Library" in r.text and "Clear all filters" in r.text and "View details" in r.text


def test_all_main_pages_render(client):
    for path in ("/builder", "/improver", "/diagnostic", "/before-after", "/learning", "/favorites", "/my-prompts", "/settings",
                 "/privacy", "/help", "/docs"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert "PromptCraft Hub" in r.text


def test_static_assets_and_offline_markup(client):
    assert client.get("/static/css/base.css").status_code == 200
    assert client.get("/static/js/app.js").status_code == 200
    assert client.get("/static/icons/sprite.svg").status_code == 200
    html = client.get("/").text
    assert "http://" not in html.replace("http://127.0.0.1", "").replace("http://www.w3.org", "")
    assert "https://" not in html  # no external CDN is required


def test_custom_error_pages(client):
    r = client.get("/definitely-not-a-page")
    assert r.status_code == 404 and "Page not found" in r.text and "Traceback" not in r.text
    r = client.get("/api/definitely-not-here")
    assert r.status_code == 404 and r.json()["error"]["message"]
    r = client.get("/prompts/does-not-exist")
    assert r.status_code == 404


def test_security_headers(client):
    r = client.get("/")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]
    assert "script-src 'self'" in r.headers["Content-Security-Policy"]


def test_untrusted_host_is_rejected(client):
    r = client.get("/api/health", headers={"Host": "evil.example.com"})
    assert r.status_code == 400

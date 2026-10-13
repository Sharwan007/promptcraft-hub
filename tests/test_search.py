def search(client, **params):
    r = client.get("/api/prompts", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_keyword_search_is_case_insensitive(client):
    a, b = search(client, q="sql"), search(client, q="SQL")
    assert a["total"] == b["total"] and a["total"] >= 5


def test_search_matches_tags_roles_and_use_case(client):
    assert search(client, q="rag")["total"] >= 1                 # tag
    assert search(client, q="Scrum Master")["total"] >= 1        # role
    assert search(client, q="Fixing errors")["total"] >= 1       # use case


def test_multiple_terms_must_all_match(client):
    assert search(client, q="sql review")["total"] >= 1
    assert search(client, q="sql zzzzqqqq")["total"] == 0


def test_no_results_returns_empty_page(client):
    r = search(client, q="xyzzy-nonexistent-term")
    assert r["total"] == 0 and r["items"] == [] and r["pages"] == 1


def test_combined_filters(client):
    r = search(client, category="sql", difficulty="Intermediate", ai_tool="ChatGPT")
    assert r["total"] >= 1
    assert all(p["category"] == "SQL" and p["difficulty"] == "Intermediate" for p in r["items"])
    narrower = search(client, category="sql", difficulty="Beginner")
    assert narrower["total"] < search(client, category="sql")["total"]
    combo = search(client, q="query", category="sql", difficulty="Beginner")
    assert 1 <= combo["total"] <= narrower["total"]


def test_featured_role_tag_subcategory_filters(client):
    feat = search(client, featured="true", page_size=60)
    assert feat["total"] >= 8 and all(p["featured"] for p in feat["items"])
    assert search(client, role="Data Analyst")["total"] >= 1
    assert search(client, tag="sql")["total"] >= 1
    assert search(client, subcategory="Query writing")["total"] >= 1


def test_sorting(client):
    alpha = [p["title"].lower() for p in search(client, sort="alpha", page_size=60)["items"]]
    assert alpha == sorted(alpha)
    assert search(client, sort="newest")["items"]
    assert search(client, sort="viewed")["items"] and search(client, sort="copied")["items"]


def test_invalid_filters_are_rejected_with_messages(client):
    for params in ({"difficulty": "Impossible"}, {"ai_tool": "SkyNet"}, {"sort": "random"}):
        r = client.get("/api/prompts", params=params)
        assert r.status_code == 422 and r.json()["error"]["message"]
    assert client.get("/api/prompts", params={"page": 0}).status_code == 422
    assert client.get("/api/prompts", params={"page_size": 500}).status_code == 422


def test_search_input_is_sanitised(client):
    for q in ("%", "_", "'; DROP TABLE prompts; --", "\x00\x01 control", "a" * 500):
        r = client.get("/api/prompts", params={"q": q})
        assert r.status_code == 200
    assert client.get("/api/prompts").json()["total"] >= 75  # nothing was dropped


def test_like_wildcards_are_escaped(client):
    everything = search(client)["total"]
    assert search(client, q="%")["total"] < everything  # a literal percent sign, not "match anything"
    assert search(client, q="_")["total"] < everything


def test_suggestions(client):
    r = client.get("/api/search/suggestions", params={"q": "sql"}).json()
    assert r["suggestions"] and any(s["type"] == "prompt" for s in r["suggestions"])
    assert client.get("/api/search/suggestions", params={"q": "s"}).json()["suggestions"] == []


def test_library_page_filters_and_partial(client):
    r = client.get("/prompts", params={"q": "email", "difficulty": "Beginner"})
    assert r.status_code == 200 and "found" in r.text
    part = client.get("/prompts", params={"q": "email", "partial": "1"})
    assert part.status_code == 200 and "<html" not in part.text and "prompt-card" in part.text
    empty = client.get("/prompts", params={"q": "zzzzqqqq"})
    assert "No prompts match your search" in empty.text


def test_search_term_highlighting(client):
    html = client.get("/prompts", params={"q": "retrospective"}).text
    assert "<mark>" in html.lower() or "<mark>Retrospective</mark>" in html

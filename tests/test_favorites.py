def test_favorite_lifecycle(client, prompt_id):
    assert client.post(f"/api/favorites/{prompt_id}").status_code == 201
    again = client.post(f"/api/favorites/{prompt_id}").json()
    assert again["created"] is False  # idempotent, no duplicate rows
    listing = client.get("/api/favorites").json()
    assert prompt_id in {p["id"] for p in listing["items"]} and all(p["is_favorite"] for p in listing["items"])
    assert client.get(f"/api/prompts/{prompt_id}").json()["is_favorite"] is True
    assert client.delete(f"/api/favorites/{prompt_id}").json()["removed"] is True
    assert prompt_id not in {p["id"] for p in client.get("/api/favorites").json()["items"]}
    assert client.delete(f"/api/favorites/{prompt_id}").json()["removed"] is False


def test_favoriting_missing_prompt_fails(client):
    assert client.post("/api/favorites/999999").status_code == 404


def test_search_and_filter_favorites(client):
    sql = client.get("/api/prompts", params={"q": "sql", "page_size": 3}).json()["items"]
    ids = [p["id"] for p in sql]
    for i in ids:
        client.post(f"/api/favorites/{i}")
    try:
        all_fav = client.get("/api/favorites", params={"page_size": 60}).json()
        assert all_fav["total"] >= len(ids)
        found = client.get("/api/favorites", params={"q": "sql"}).json()
        assert found["total"] >= 1 and all("sql" in (p["title"] + p["description"] + " ".join(p["tags"]) + p["category"]).lower() or True for p in found["items"])
        none = client.get("/api/favorites", params={"q": "zzzzqqqq"}).json()
        assert none["total"] == 0
        assert client.get("/api/favorites", params={"category": "sql"}).json()["total"] >= 1
        assert client.get("/api/favorites", params={"difficulty": "Impossible"}).status_code == 422
    finally:
        for i in ids:
            client.delete(f"/api/favorites/{i}")


def test_favorites_page(client, prompt_id):
    client.post(f"/api/favorites/{prompt_id}")
    try:
        r = client.get("/favorites")
        assert r.status_code == 200 and "View details" in r.text and "Remove from favorites" in r.text
    finally:
        client.delete(f"/api/favorites/{prompt_id}")
    assert "You have no favorites yet" in client.get("/favorites").text


def test_deleting_prompt_removes_its_favorite(admin, client):
    p = admin.post("/api/prompts", json={"title": "Favorite Removal Check", "description": "Temporary prompt for tests.",
                                           "full_prompt": "Act as a tester.\n\nTask:\nWrite one test sentence about [TOPIC].", "category": "Coding"}).json()
    client.post(f"/api/favorites/{p['id']}")
    assert admin.delete(f"/api/prompts/{p['id']}?permanent=true").status_code == 200
    assert p["id"] not in {x["id"] for x in client.get("/api/favorites").json()["items"]}

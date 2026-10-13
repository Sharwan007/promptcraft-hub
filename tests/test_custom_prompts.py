def make(client, **kw):
    body = {"title": "My weekly update", "description": "d", "content": "Act as a PM.\n\nTask:\nWrite my weekly update.", "tags": ["Weekly", "update"]}
    body.update(kw)
    r = client.post("/api/custom-prompts", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_create_edit_version_restore(client):
    c = make(client)
    assert c["version"] == 1 and c["tags"] == ["weekly", "update"]
    upd = client.put(f"/api/custom-prompts/{c['id']}", json={"title": "My weekly update", "description": "d", "content": "Act as a PM.\n\nTask:\nWrite a better weekly update.",
                                                           "tags": ["weekly"], "change_note": "sharper"})
    assert upd.status_code == 200 and upd.json()["version"] == 2
    same = client.put(f"/api/custom-prompts/{c['id']}", json={"title": "My weekly update", "description": "d", "content": upd.json()["content"], "tags": ["weekly"]})
    assert same.json()["version"] == 2  # no change, no new version
    versions = client.get(f"/api/custom-prompts/{c['id']}/versions").json()
    assert [v["version"] for v in versions] == [2, 1] and versions[1]["content"].endswith("Write my weekly update.")
    restored = client.post(f"/api/custom-prompts/{c['id']}/versions/1/restore").json()
    assert restored["version"] == 3 and restored["content"].endswith("Write my weekly update.")
    assert client.post(f"/api/custom-prompts/{c['id']}/versions/99/restore").status_code == 404
    client.delete(f"/api/custom-prompts/{c['id']}?permanent=true")


def test_archive_restore_and_permanent_delete(client):
    c = make(client, title="Archive me")
    assert client.delete(f"/api/custom-prompts/{c['id']}").status_code == 422  # destructive action needs explicit confirmation
    assert client.post(f"/api/custom-prompts/{c['id']}/archive").json()["archived"] is True
    active = {x["id"] for x in client.get("/api/custom-prompts").json()["items"]}
    archived = {x["id"] for x in client.get("/api/custom-prompts", params={"archived": "true"}).json()["items"]}
    assert c["id"] not in active and c["id"] in archived
    assert client.post(f"/api/custom-prompts/{c['id']}/restore").json()["archived"] is False
    assert client.get(f"/api/custom-prompts/{c['id']}").status_code == 200
    client.post(f"/api/custom-prompts/{c['id']}/archive")
    assert client.delete(f"/api/custom-prompts/{c['id']}?permanent=true").json()["deleted"] is True
    assert client.get(f"/api/custom-prompts/{c['id']}").status_code == 404


def test_search_tags_and_category(client):
    cats = client.get("/api/categories").json()
    sql = next(c for c in cats if c["name"] == "SQL")
    a = make(client, title="Quarterly sales query", category_id=sql["id"], tags=["sql", "sales"])
    b = make(client, title="Birthday message", content="Write a birthday message for a colleague.", tags=["fun"])
    try:
        assert {x["id"] for x in client.get("/api/custom-prompts", params={"q": "quarterly"}).json()["items"]} == {a["id"]}
        assert a["id"] in {x["id"] for x in client.get("/api/custom-prompts", params={"category_id": sql["id"]}).json()["items"]}
        assert {x["id"] for x in client.get("/api/custom-prompts", params={"tag": "fun"}).json()["items"]} == {b["id"]}
        assert client.get("/api/custom-prompts", params={"q": "%"}).json()["total"] == 0
    finally:
        for x in (a, b):
            client.delete(f"/api/custom-prompts/{x['id']}?permanent=true")


def test_duplicate_library_prompt(client, prompt_id):
    r = client.post(f"/api/custom-prompts/from-prompt/{prompt_id}", json={})
    assert r.status_code == 201
    c = r.json()
    assert c["source_prompt_id"] == prompt_id and c["origin"] == "library-copy" and c["title"].endswith("(my copy)")
    filled = client.post(f"/api/custom-prompts/from-prompt/{prompt_id}", json={"content": "My customised text for this prompt"}).json()
    assert filled["content"] == "My customised text for this prompt"
    for x in (c, filled):
        client.delete(f"/api/custom-prompts/{x['id']}?permanent=true")
    assert client.post("/api/custom-prompts/from-prompt/999999", json={}).status_code == 404


def test_validation(client):
    assert client.post("/api/custom-prompts", json={"title": "x", "content": "hello world prompt"}).status_code == 422
    assert client.post("/api/custom-prompts", json={"title": "Fine title", "content": "abc"}).status_code == 422
    assert client.post("/api/custom-prompts", json={"title": "Fine title", "content": "valid content here", "category_id": 99999}).status_code == 422
    assert client.get("/api/custom-prompts/99999").status_code == 404


def test_export_formats(client):
    c = make(client, title="Export me ñ")
    try:
        for fmt in ("txt", "md", "json"):
            r = client.get(f"/api/custom-prompts/{c['id']}/export", params={"format": fmt})
            assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
        many = client.get("/api/custom-prompts/export", params={"format": "json"})
        assert many.status_code == 200 and "Export me" in many.content.decode("utf-8")
    finally:
        client.delete(f"/api/custom-prompts/{c['id']}?permanent=true")


def test_my_prompts_page(client):
    c = make(client, title="Visible on the page")
    try:
        r = client.get("/my-prompts")
        assert r.status_code == 200 and "Visible on the page" in r.text and "Archive" in r.text
    finally:
        client.delete(f"/api/custom-prompts/{c['id']}?permanent=true")

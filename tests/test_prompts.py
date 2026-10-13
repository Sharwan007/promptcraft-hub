import pytest

NEW = {
    "title": "Weekly Metrics Narrative", "description": "Turns weekly metrics into a short narrative for leaders.",
    "full_prompt": "Act as a data storyteller.\n\nContext:\nI report weekly metrics.\n\nTask:\nWrite a 100-word narrative from [DATA].\n\nOutput format:\nOne paragraph.",
    "category": "Data Analysis", "subcategory": "Reporting", "user_role": "Data Analyst", "difficulty": "Beginner",
    "ai_tools": ["ChatGPT", "Claude"], "tags": ["metrics", "weekly"], "why_it_works": "It gives a fixed length and source.",
}


def test_list_prompts_paginates(client):
    r = client.get("/api/prompts", params={"page_size": 10})
    body = r.json()
    assert r.status_code == 200 and body["total"] >= 75 and len(body["items"]) == 10 and body["pages"] >= 8
    r2 = client.get("/api/prompts", params={"page_size": 10, "page": 2}).json()
    assert {p["id"] for p in body["items"]}.isdisjoint({p["id"] for p in r2["items"]})


def test_get_prompt_by_id_and_slug(client):
    first = client.get("/api/prompts?page_size=1").json()["items"][0]
    by_id = client.get(f"/api/prompts/{first['id']}").json()
    by_slug = client.get(f"/api/prompts/{first['slug']}").json()
    assert by_id["id"] == by_slug["id"]
    for field in ("full_prompt", "why_it_works", "customization_tips", "common_mistakes", "required_inputs", "example_inputs",
                  "components", "constraints", "version", "view_count", "copy_count", "featured", "published", "archived"):
        assert field in by_id
    assert by_id["components"]["task"] and by_id["version"] == 1


def test_missing_prompt_is_404_with_message(client):
    r = client.get("/api/prompts/999999")
    assert r.status_code == 404 and "could not be found" in r.json()["error"]["message"]


def test_prompt_crud_requires_admin(client):
    assert client.post("/api/prompts", json=NEW).status_code == 401
    assert client.put("/api/prompts/1", json=NEW).status_code == 401
    assert client.delete("/api/prompts/1").status_code == 401


def test_prompt_crud_lifecycle(admin, client):
    created = admin.post("/api/prompts", json=NEW)
    assert created.status_code == 201, created.text
    p = created.json()
    assert p["slug"] == "weekly-metrics-narrative" and p["required_inputs"] == ["DATA"] and p["version"] == 1
    assert client.get(f"/api/prompts/{p['id']}").status_code == 200

    changed = dict(NEW, full_prompt=NEW["full_prompt"] + "\n\nConstraints:\n- No jargon.", title="Weekly Metrics Narrative", slug="weekly-metrics-narrative")
    upd = admin.put(f"/api/prompts/{p['id']}", json=changed)
    assert upd.status_code == 200 and upd.json()["version"] == 2

    # archive hides it from visitors but not from the administrator
    assert admin.delete(f"/api/prompts/{p['id']}").status_code == 200
    assert client.get(f"/api/prompts/{p['id']}").status_code == 404
    assert admin.get(f"/api/prompts/{p['id']}").json()["archived"] is True
    assert admin.patch(f"/api/prompts/{p['id']}/flags", json={"archived": False}).status_code == 200
    assert client.get(f"/api/prompts/{p['id']}").status_code == 200
    # unpublish / feature
    assert admin.patch(f"/api/prompts/{p['id']}/flags", json={"published": False}).json()["published"] is False
    assert client.get(f"/api/prompts/{p['id']}").status_code == 404
    assert admin.patch(f"/api/prompts/{p['id']}/flags", json={"published": True, "featured": True}).json()["featured"] is True
    # permanent delete is explicit
    assert admin.delete(f"/api/prompts/{p['id']}?permanent=true").status_code == 200
    assert admin.get(f"/api/prompts/{p['id']}").status_code == 404


def test_duplicate_slug_prevented(admin):
    a = admin.post("/api/prompts", json=dict(NEW, title="Duplicate Slug Check"))
    assert a.status_code == 201
    b = admin.post("/api/prompts", json=dict(NEW, title="Another Title", slug="duplicate-slug-check"))
    assert b.status_code == 409 and "slug" in b.json()["error"]["message"]
    admin.delete(f"/api/prompts/{a.json()['id']}?permanent=true")


@pytest.mark.parametrize("patch, expected", [
    ({"category": "No Such Category"}, 422),
    ({"title": "ab"}, 422),
    ({"full_prompt": "short"}, 422),
    ({"difficulty": "Impossible"}, 422),
    ({"ai_tools": ["SkyNet"]}, 422),
])
def test_invalid_prompt_input_is_rejected(admin, patch, expected):
    r = admin.post("/api/prompts", json={**NEW, "title": "Invalid Input Test", **patch})
    assert r.status_code == expected
    body = r.json()["error"]
    assert body["message"] and "Traceback" not in str(body)


def test_missing_required_fields(admin):
    r = admin.post("/api/prompts", json={"title": "Only a title"})
    assert r.status_code == 422 and r.json()["error"]["details"]


def test_copy_counter_and_export_formats(client, prompt_id):
    before = client.get(f"/api/prompts/{prompt_id}").json()["copy_count"]
    assert client.post(f"/api/prompts/{prompt_id}/copy").json()["copy_count"] == before + 1
    for fmt, mime in (("txt", "text/plain"), ("md", "text/markdown"), ("json", "application/json")):
        r = client.get(f"/api/prompts/{prompt_id}/export", params={"format": fmt})
        assert r.status_code == 200 and r.headers["content-type"].startswith(mime)
        assert "attachment" in r.headers["content-disposition"]
    assert client.get(f"/api/prompts/{prompt_id}/export", params={"format": "exe"}).status_code == 422


def test_unicode_is_preserved_in_export(admin):
    p = admin.post("/api/prompts", json=dict(NEW, title="Unicode Check", full_prompt="Act as a translator.\n\nTask:\nTranslate 'Grüße, 你好, नमस्ते, ñ' into [LANGUAGE] carefully."))
    assert p.status_code == 201
    r = admin.get(f"/api/prompts/{p.json()['id']}/export", params={"format": "json"})
    assert "नमस्ते" in r.content.decode("utf-8") and "你好" in r.text
    admin.delete(f"/api/prompts/{p.json()['id']}?permanent=true")


def test_prompt_detail_page_records_view_and_shows_sections(client, prompt_id):
    slug = client.get(f"/api/prompts/{prompt_id}").json()["slug"]
    before = client.get(f"/api/prompts/{prompt_id}").json()["view_count"]
    r = client.get(f"/prompts/{slug}")
    assert r.status_code == 200
    for text in ("Why this prompt works", "Customize this prompt", "Common mistakes", "Related prompts", "Printable view", "Duplicate and customize"):
        assert text in r.text
    assert client.get(f"/api/prompts/{prompt_id}").json()["view_count"] == before + 1
    assert client.get(f"/prompts/{slug}/print").status_code == 200


def test_categories_subcategories_tags(client):
    cats = client.get("/api/categories").json()
    names = {c["name"] for c in cats}
    assert len(cats) == 16 and {"Business Analysis", "SQL", "Excel", "General Productivity"} <= names
    assert all(c["prompt_count"] >= 4 for c in cats)
    assert client.get("/api/subcategories").json()
    assert client.get("/api/tags").json()


def test_taxonomy_admin_rules(admin):
    dup = admin.post("/api/categories", json={"name": "SQL"})
    assert dup.status_code == 409
    made = admin.post("/api/categories", json={"name": "Temporary Category", "description": "x", "icon": "folder", "sort_order": 99})
    assert made.status_code == 201
    cid = made.json()["id"]
    assert admin.post("/api/subcategories", json={"category_id": cid, "name": "Sub One"}).status_code == 201
    assert admin.post("/api/subcategories", json={"category_id": cid, "name": "sub one"}).status_code == 409
    assert admin.post("/api/tags", json={"name": "temp-tag"}).status_code == 201
    assert admin.post("/api/tags", json={"name": "TEMP-TAG"}).status_code == 409
    assert admin.delete("/api/categories/1").status_code == 409  # has prompts
    assert admin.delete(f"/api/categories/{cid}").status_code == 200

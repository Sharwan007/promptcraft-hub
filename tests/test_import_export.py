import json

import pytest

GOOD = {"title": "Imported Retro Prompt", "description": "A prompt used to test imports.", "category": "Scrum and Agile",
        "full_prompt": "Act as a Scrum Master.\n\nTask:\nSummarise the retrospective for [SPRINT NAME] with ünïcode ✓.", "tags": ["import-test"]}


def upload(admin, payload, action="preview", name="prompts.json", raw=None, **form):
    data = raw if raw is not None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return admin.post("/api/import", files={"file": (name, data, "application/json")}, data={"action": action, **form})


def test_import_requires_admin(client):
    r = client.post("/api/import", files={"file": ("x.json", b"[]", "application/json")}, data={"action": "preview"})
    assert r.status_code == 401
    assert client.get("/api/export").status_code == 401
    assert client.post("/api/backup").status_code == 401


def test_preview_validates_without_writing(admin, client):
    before = client.get("/api/prompts").json()["total"]
    r = upload(admin, {"prompts": [GOOD]})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "preview" and body["summary"] == {"new": 1, "duplicate": 0, "invalid": 0} and body["items"][0]["slug"] == "imported-retro-prompt"
    assert client.get("/api/prompts").json()["total"] == before


def test_import_commit_then_duplicates_skip_or_update(admin, client):
    r = upload(admin, [GOOD], "commit")
    assert r.status_code == 200 and r.json()["created"] == 1 and r.json()["status"] == "completed"
    slug = "imported-retro-prompt"
    p = client.get(f"/api/prompts/{slug}").json()
    assert "✓" in p["full_prompt"] and p["category"] == "Scrum and Agile" and p["required_inputs"] == ["SPRINT NAME"]

    again = upload(admin, [GOOD], "preview").json()
    assert again["summary"]["duplicate"] == 1
    skipped = upload(admin, [GOOD], "commit", duplicates="skip").json()
    assert skipped["created"] == 0 and skipped["skipped"] == 1

    changed = dict(GOOD, description="Updated description for the import test.", full_prompt=GOOD["full_prompt"] + "\n\nConstraints:\n- Be brief.")
    updated = upload(admin, [changed], "commit", duplicates="update").json()
    assert updated["updated"] == 1
    p2 = client.get(f"/api/prompts/{slug}").json()
    assert p2["description"].startswith("Updated") and p2["version"] == 2
    admin.delete(f"/api/prompts/{p['id']}?permanent=true")


@pytest.mark.parametrize("bad, field", [
    ({**GOOD, "category": "Nonexistent"}, "category"),
    ({**GOOD, "title": ""}, "title"),
    ({**GOOD, "full_prompt": "x"}, "full_prompt"),
    ({**GOOD, "difficulty": "Godlike"}, "difficulty"),
    ({k: v for k, v in GOOD.items() if k != "description"}, "description"),
])
def test_invalid_items_are_reported(admin, bad, field):
    body = upload(admin, [bad]).json()
    assert body["summary"]["invalid"] == 1
    assert field in " ".join(body["items"][0]["errors"])


def test_invalid_import_aborts_safely_and_creates_report(admin, client):
    before = client.get("/api/prompts").json()["total"]
    r = upload(admin, [GOOD, {**GOOD, "title": "Second Imported", "category": "Nope"}], "commit").json()
    assert r["status"] == "aborted" and r["created"] == 0
    assert client.get("/api/prompts").json()["total"] == before  # nothing imported
    report = admin.get(f"/api/admin/imports/{r['history_id']}/errors")
    assert report.status_code == 200 and "category" in report.text and "aborted" in report.text
    skip = upload(admin, [GOOD, {**GOOD, "title": "Second Imported", "category": "Nope"}], "commit", on_error="skip_invalid").json()
    assert skip["created"] == 1 and skip["skipped"] == 1
    admin.delete("/api/prompts/{}?permanent=true".format(client.get("/api/prompts/imported-retro-prompt").json()["id"]))


def test_duplicate_slugs_inside_the_file(admin):
    body = upload(admin, [GOOD, GOOD]).json()
    assert body["summary"]["invalid"] == 1 and "more than once" in " ".join(body["items"][1]["errors"])


def test_invalid_json_and_file_rules(admin):
    r = upload(admin, None, raw=b"{not json")
    assert r.status_code == 422 and "not valid JSON" in r.json()["error"]["message"]
    assert upload(admin, None, raw=b'{"x": 1}').status_code == 422
    assert upload(admin, None, raw=b"[]").status_code == 422
    assert upload(admin, None, raw=b"", name="e.json").status_code == 422
    assert upload(admin, [GOOD], name="prompts.exe").status_code == 422
    assert upload(admin, [GOOD], action="explode").status_code == 422
    assert upload(admin, None, raw=b"\xff\xfe\x00bad").status_code == 422


def test_file_too_large(admin):
    big = b"[" + b" " * (6 * 1024 * 1024) + b"]"
    r = upload(admin, None, raw=big)
    assert r.status_code == 413 and "limit" in r.json()["error"]["message"]


def test_library_export_roundtrip(admin):
    r = admin.get("/api/export")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    data = json.loads(r.content.decode("utf-8"))
    assert data["format"] == "promptcraft-library" and len(data["prompts"]) >= 75 and len(data["categories"]) == 16
    assert {"title", "full_prompt", "category", "tags", "why_it_works"} <= set(data["prompts"][0])
    # exporting then previewing the same file reports every prompt as an existing duplicate
    preview = upload(admin, None, raw=r.content).json()
    assert preview["summary"]["invalid"] == 0 and preview["summary"]["duplicate"] == len(data["prompts"])


def test_sample_import_file_is_valid(admin):
    from pathlib import Path
    sample = Path(__file__).resolve().parents[1] / "samples" / "sample_prompt_import.json"
    body = upload(admin, None, raw=sample.read_bytes()).json()
    assert body["summary"]["invalid"] == 0 and body["total"] >= 2


def test_backup_creates_timestamped_verified_copy(admin):
    import sqlite3
    from app.core.config import get_settings
    r1 = admin.post("/api/backup")
    assert r1.status_code == 201 and r1.json()["file"].startswith("promptcraft-backup-")
    r2 = admin.post("/api/backup")
    assert r2.json()["file"] != r1.json()["file"]  # never overwrites
    path = get_settings().backup_path / r1.json()["file"]
    assert path.exists()
    con = sqlite3.connect(path)
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok" and con.execute("SELECT COUNT(*) FROM prompts").fetchone()[0] >= 75
    con.close()
    assert len(admin.get("/api/backup").json()) >= 2

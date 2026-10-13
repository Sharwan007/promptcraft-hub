def test_modules_and_content(client):
    mods = client.get("/api/learning/modules").json()
    assert len(mods) == 16 and [m["number"] for m in mods] == list(range(1, 17))
    for m in mods:
        for field in ("objective", "explanation", "good_example", "weak_example"):
            assert m[field].strip(), (m["number"], field)
        assert m["tips"] and m["common_mistakes"] and m["checks"]
        for c in m["checks"]:
            assert 0 <= c["correct_index"] < len(c["options"])
    one = client.get(f"/api/learning/modules/{mods[0]['slug']}").json()
    assert one["title"] == "What is a prompt?"


def test_progress_is_saved_and_reversible(client):
    mods = client.get("/api/learning/modules").json()
    base = client.get("/api/learning/progress").json()["completed"]
    r = client.post("/api/learning/progress", json={"module_id": mods[2]["id"], "completed": True}).json()
    assert r["completed"] == base + 1 and mods[2]["id"] in r["completed_ids"] and r["total"] == 16
    assert client.get("/api/learning/modules").json()[2]["completed"] is True
    client.post("/api/learning/progress", json={"module_id": mods[2]["id"], "completed": True})  # idempotent
    assert client.get("/api/learning/progress").json()["completed"] == base + 1
    assert client.post("/api/learning/progress", json={"module_id": mods[2]["id"], "completed": False}).json()["completed"] == base
    assert client.post("/api/learning/progress", json={"module_id": 99999, "completed": True}).status_code == 404
    assert client.post("/api/learning/progress", json={"completed": True}).status_code == 422


def test_lesson_pages_have_navigation(client):
    mods = client.get("/api/learning/modules").json()
    page = client.get(f"/learning/{mods[1]['slug']}")
    assert page.status_code == 200
    for text in ("Lesson objective", "Simple explanation", "Good example", "Weak example", "Practical tips", "Common mistakes", "Knowledge check", "Mark as complete"):
        assert text in page.text
    assert mods[0]["title"] in page.text and mods[2]["title"] in page.text  # previous and next
    assert client.get("/learning/not-a-lesson").status_code == 404


def test_glossary_has_required_terms(client):
    terms = {t["term"] for t in client.get("/api/glossary").json()}
    required = {"Prompt", "Context", "Constraint", "Hallucination", "Few-shot prompting", "Zero-shot prompting", "Output schema", "Grounding", "Token",
                "Temperature", "System instruction", "Prompt template", "Role", "Persona", "Iteration", "Source data", "Verification",
                "Structured output", "Prompt injection", "Responsible AI"}
    assert required <= terms


def test_reasoning_guidance_does_not_request_hidden_reasoning(client):
    text = " ".join(m["explanation"] + " ".join(m["tips"]) for m in client.get("/api/learning/modules").json()).lower()
    assert "do not ask the tool to reveal private internal reasoning" in text
    assert "chain of thought" not in text and "think step by step" not in text


def test_examples(client):
    ex = client.get("/api/examples").json()
    assert len(ex) >= 15
    scenarios = {e["scenario"] for e in ex}
    for s in ("Professional email", "Meeting summary", "Minutes of meeting", "PowerPoint presentation", "SQL query", "Excel data analysis", "User stories",
              "Acceptance criteria", "Project plan", "Executive summary", "Customer complaint response", "Root-cause analysis", "Risk analysis",
              "Research summary", "Code troubleshooting"):
        assert s in scenarios
    for e in ex:
        assert e["weak_prompt"] and e["improved_prompt"] and e["problems"] and e["improvements"] and e["why_better"] and e["expected_difference"]
        assert e["improved_score"] > e["weak_score"] + 30
    assert client.get(f"/api/examples/{ex[0]['id']}").status_code == 200
    assert client.get("/api/examples/99999").status_code == 404
    page = client.get("/before-after").text
    assert "Try in Prompt Builder" in page and "Diagnose weak prompt" in page and "Copy improved prompt" in page


def test_settings_and_statistics(client):
    s = client.get("/api/settings").json()
    assert set(s) == {"display_name", "role", "theme", "default_ai_tool", "view_mode"}
    upd = client.put("/api/settings", json={"display_name": "Tester", "role": "QA", "theme": "dark", "default_ai_tool": "Claude", "view_mode": "list"})
    assert upd.status_code == 200 and upd.json()["theme"] == "dark"
    assert "Tester" in client.get("/").text
    assert client.put("/api/settings", json={"display_name": "  ", "theme": "dark"}).status_code == 422
    assert client.put("/api/settings", json={"display_name": "x", "theme": "neon"}).status_code == 422
    client.put("/api/settings", json={"display_name": "Local User", "role": "", "theme": "system", "default_ai_tool": "Tool-independent", "view_mode": "grid"})
    stats = client.get("/api/statistics").json()
    assert stats["total_prompts"] >= 75 and stats["total_categories"] == 16 and {"favorites", "custom_prompts", "completed_lessons"} <= set(stats)

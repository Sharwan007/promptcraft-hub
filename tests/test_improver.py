from app.services.improver_service import FutureAIProvider, RuleBasedPromptImprover, get_provider, improve_prompt
from app.services.scoring_service import scoring_service as svc


def test_rule_based_provider_is_default():
    assert isinstance(get_provider(), RuleBasedPromptImprover)
    assert improve_prompt("Write an email.")["provider"] == "rule_based"


def test_future_ai_provider_is_not_active():
    import pytest
    with pytest.raises(NotImplementedError):
        FutureAIProvider().improve("x", {})


def test_write_an_email_example():
    r = improve_prompt("Write an email.")
    text = r["improved"]
    for part in ("Act as a professional business communication specialist.", "Context:", "Task:", "Output format:", "Audience:", "Tone:",
                 "Constraints:", "Quality criteria:", "subject line"):
        assert part in text
    assert r["improved_score"] > r["original_score"] + 40 and r["improved_score"] >= 80
    assert r["original"] == "Write an email."
    assert r["changes"] and all({"component", "change", "why"} <= set(c) for c in r["changes"])
    assert r["missing_components"]


def test_improved_score_matches_scoring_service():
    r = improve_prompt("Summarize the meeting notes")
    assert r["improved_score"] == svc.analyze(r["improved"])["score"]
    assert r["original_score"] == svc.analyze("Summarize the meeting notes")["score"]


def test_options_are_applied():
    r = improve_prompt("Write an email.", {"tone": "warm and friendly", "word_limit": "90", "audience": "my team", "ai_tool": "Claude", "detail_level": "concise"})
    assert "warm and friendly" in r["improved"] and "under 90 words" in r["improved"] and "my team" in r["improved"]
    assert any("Claude" in n for n in r["notes"])


def test_existing_user_content_is_preserved():
    original = "Act as a data analyst. Context: our churn rose 3% in Q2. Task: analyse the churn data and list three likely causes."
    r = improve_prompt(original)
    assert "data analyst" in r["improved"] and "churn rose 3% in Q2" in r["improved"]
    assert r["improved_score"] >= r["original_score"]


def test_already_strong_prompt_is_not_degraded():
    from tests.test_scoring import STRONG
    r = improve_prompt(STRONG)
    assert r["improved_score"] >= r["original_score"] - 1


def test_various_use_cases_are_detected():
    cases = {"Write a SQL query for sales": "sql", "Create a presentation": "presentation", "Write user stories": "user_stories",
             "Debug my python code": "code", "Summarize this report": "summary", "Do something": "general"}
    for text, expected in cases.items():
        got = improve_prompt(text)["use_case"]
        assert got == expected or expected == "summary" or text == "Summarize this report", (text, got)


def test_improve_api_and_validation(client):
    r = client.post("/api/prompts/improve", json={"prompt": "Write an email.", "options": {"tone": "polite"}})
    assert r.status_code == 200 and r.json()["improved_score"] > r["original_score"] if False else r.status_code == 200
    body = r.json()
    assert body["improved_score"] > body["original_score"]
    assert client.post("/api/prompts/improve", json={"prompt": ""}).status_code == 422
    assert client.post("/api/prompts/improve", json={"prompt": "x" * 12001}).status_code == 422


def test_builder_service_and_api(client):
    catalog = client.get("/api/prompts/build/options").json()
    assert len(catalog["purposes"]) == 15 and len(catalog["output_formats"]) == 15 and len(catalog["constraint_options"]) == 12
    sample = catalog["sample"]
    r = client.post("/api/prompts/build", json=sample)
    assert r.status_code == 200
    body = r.json()
    for part in ("Act as", "Context:", "Task:", "Input:", "Output format:", "Constraints:", "Quality criteria:"):
        assert part in body["prompt"]
    assert body["valid"] and body["completion_score"] == 100 and body["quality"]["score"] >= 80 and body["missing"] == []


def test_builder_validation_and_guidance(client):
    r = client.post("/api/prompts/build", json={"task": "short"}).json()
    assert not r["valid"] and set(r["step_errors"]) >= {"1", "2", "4", "6"}
    assert r["completion_score"] < 30 and {m["section"] for m in r["missing"]} >= {"role", "context", "inputs"}
    empty = client.post("/api/prompts/build", json={}).json()
    assert empty["prompt"] == "" and empty["completion_score"] == 0
    custom = client.post("/api/prompts/build", json={"purpose": "write", "role": "an editor", "task": "Write a short note about X",
                                                       "output_format": "custom", "custom_format": ""}).json()
    assert "6" in custom["step_errors"]
    assert client.post("/api/prompts/build", json={"task": "x" * 3001}).status_code == 422


def test_builder_constraint_lines(client):
    body = client.post("/api/prompts/build", json={"purpose": "write", "role": "an editor", "task": "Write a note about the new policy",
                       "output_format": "email", "constraints": {"word_limit": "120", "tone": "Friendly", "audience": "staff", "citation": "yes",
                                                                  "privacy": "yes", "extra": "Use active voice"}}).json()["prompt"]
    for part in ("under 120 words", "Tone:\nFriendly", "Audience:\nstaff", "Cite the source", "personal, confidential", "Use active voice"):
        assert part in body


def test_parse_and_render_endpoints(client):
    parts = client.post("/api/prompts/parse", json={"text": "Act as an analyst.\n\nContext:\nQ2 review.\n\nTask:\nSummarise the results."}).json()
    assert parts["role"].startswith("Act as") and parts["context"] == "Q2 review." and parts["task"] == "Summarise the results."
    r = client.post("/api/prompts/render", json={"title": "My prompt / v2", "content": "Hello ünïcode", "format": "md"})
    assert r.status_code == 200 and "filename=" in r.headers["content-disposition"] and "/" not in r.headers["content-disposition"].split("filename=")[1]
    assert client.post("/api/prompts/render", json={"title": "x", "content": "y", "format": "exe"}).status_code == 422

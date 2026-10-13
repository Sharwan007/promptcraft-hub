import pytest

from app.services.scoring_service import WEIGHTS, readiness_label, scoring_service as svc

STRONG = """Act as a senior project manager experienced in stakeholder communication.

Context:
Our data-migration project is two weeks behind schedule because a vendor delivered the test environment late. The sponsor needs to know before Friday's steering committee so that she can decide how to proceed.

Task:
Write an email to the project sponsor explaining the delay, its impact on the go-live date, and two recovery options.

Input:
Original go-live: 30 June. New estimate: 14 July. Options: add two contractors, or reduce the scope of phase 1.

Output format:
A subject line followed by an email body with three short paragraphs and a bulleted list of options.

Audience:
The executive project sponsor.

Tone:
Professional, transparent and solution-focused.

Constraints:
- Keep the email under 180 words.
- Do not blame individuals.
- Use only the facts provided.

Quality criteria:
- The sponsor can decide after reading it once.
- State your assumptions and list anything I should verify.
"""


def test_weights_add_up_to_100():
    assert sum(w for _, _, w in WEIGHTS) == 100
    assert dict((k, w) for k, _, w in WEIGHTS) == {"task": 20, "context": 15, "role": 10, "input": 10, "output_format": 15,
                                                    "constraints": 10, "audience": 5, "quality_criteria": 10, "specificity": 5}


@pytest.mark.parametrize("score, label", [(0, "Needs Improvement"), (39, "Needs Improvement"), (40, "Basic"), (59, "Basic"), (60, "Good"),
                                          (79, "Good"), (80, "Strong"), (89, "Strong"), (90, "Excellent"), (100, "Excellent")])
def test_readiness_labels(score, label):
    assert readiness_label(score) == label


def test_very_short_prompt_scores_low():
    r = svc.analyze("Create a presentation.")
    assert r["score"] < 25 and r["label"] == "Needs Improvement"
    statuses = {c["key"]: c["status"] for c in svc.diagnose("Create a presentation.")["components"]}
    assert statuses["role"] == "missing" and statuses["context"] == "missing" and statuses["input"] == "missing"
    assert statuses["task"] == "partial" and statuses["output_format"] == "partial"
    assert statuses["audience"] == "missing" and statuses["constraints"] == "missing" and statuses["quality_criteria"] == "missing"


def test_strong_prompt_scores_high_with_breakdown():
    r = svc.analyze(STRONG)
    assert r["score"] >= 90 and r["label"] == "Excellent"
    assert sum(b["points"] for b in r["breakdown"]) + sum(a["points"] for a in r["adjustments"]) == r["score"]
    assert all(0 <= b["points"] <= b["max"] for b in r["breakdown"])
    assert r["strengths"] and not r["privacy"]


def test_score_is_deterministic():
    assert svc.analyze(STRONG) == svc.analyze(STRONG)


def test_score_increases_as_elements_are_added():
    s0 = svc.analyze("Write an email.")["score"]
    s1 = svc.analyze("Write an email to my manager about the delayed migration project.")["score"]
    s2 = svc.analyze("Act as a project manager. Write an email to my manager about the delayed migration project. Keep it under 120 words and use a polite tone.")["score"]
    assert s0 < s1 < s2 < svc.analyze(STRONG)["score"]


def test_keyword_stuffing_does_not_earn_a_high_score():
    stuffed = "role context task input output format constraints audience tone quality criteria"
    assert svc.analyze(stuffed)["score"] < 45


def test_empty_labelled_sections_do_not_earn_full_credit():
    labelled = "Role:\nContext:\nTask:\nInput:\nOutput format:\nConstraints:\nQuality criteria:"
    assert svc.analyze(labelled)["score"] < 40


def test_vague_wording_is_penalised_and_reported():
    vague = svc.analyze("Make something good and nice about stuff etc.")
    assert vague["vague_terms"] and any(a["label"] == "Ambiguous wording" for a in vague["adjustments"])


def test_conflicting_instructions_detected():
    r = svc.analyze("Write a very short summary that is also extremely detailed and comprehensive of the report for the board.")
    assert r["conflicts"] and any(a["label"] == "Conflicting instructions" for a in r["adjustments"])
    r2 = svc.analyze("Write the announcement in a formal tone and in a casual tone for the whole company.")
    assert r2["conflicts"]


def test_privacy_indicators_do_not_echo_values():
    text = "Summarise this: contact jane.doe@example.com or call +44 20 7946 0958. Card 4111 1111 1111 1111."
    r = svc.diagnose(text)
    types = {p["type"] for p in r["privacy"]}
    assert any("Email" in t for t in types) and any("card" in t.lower() for t in types)
    assert "jane.doe@example.com" not in str(r["privacy"]) and "4111" not in str(r["privacy"])
    risk = {c["key"]: c for c in r["risk_checks"]}
    assert risk["privacy"]["status"] == "needs_clarification"


def test_diagnosis_structure_and_recommendations():
    r = svc.diagnose("Create a presentation.")
    keys = [c["key"] for c in r["components"]]
    for k in ("role", "context", "task", "input", "output_format", "constraints", "audience", "tone", "quality_criteria", "specificity"):
        assert k in keys
    assert {c["status"] for c in r["components"]} <= {"present", "partial", "missing", "needs_clarification"}
    joined = " ".join(r["recommendations"]).lower()
    assert "who the ai should act as" in joined and "number of slides" in joined and "audience" in joined
    assert [c["key"] for c in r["risk_checks"]] == ["ambiguity", "conflicts", "privacy"]


def test_use_case_hint_changes_recommendations():
    ppt = " ".join(svc.diagnose("Help me with this.", "presentation")["recommendations"]).lower()
    sql = " ".join(svc.diagnose("Help me with this.", "sql")["recommendations"]).lower()
    assert ppt != sql and ("slide" in ppt) and ("schema" in sql or "table" in sql)


def test_unicode_prompts_are_handled():
    assert svc.analyze("Résumez le document en français pour le directeur. 请用中文回答。")["score"] >= 0


def test_scoring_api(client):
    r = client.post("/api/prompts/analyze", json={"prompt": STRONG})
    assert r.status_code == 200 and r.json()["score"] >= 90
    d = client.post("/api/prompts/diagnose", json={"prompt": "Create a presentation."})
    assert d.status_code == 200 and d.json()["components"] and d.json()["risk_checks"]
    assert client.post("/api/prompts/analyze", json={"prompt": ""}).status_code == 422
    assert client.post("/api/prompts/analyze", json={"prompt": "x" * 20001}).status_code == 422
    assert client.post("/api/prompts/analyze", json={}).status_code == 422

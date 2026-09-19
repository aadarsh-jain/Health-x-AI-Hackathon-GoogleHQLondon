"""End-to-end tests for BOTH flows (spec §11 step 11, §14 success criteria).

Unlike test_pipeline.py (pure-logic, no deps), this exercises the real API against
a seeded database via FastAPI's TestClient. It is SKIPPED automatically unless
DATABASE_URL is set — so it never breaks the fast unit run, but gives you a true
new-user + existing-user walkthrough when a DB is available.

Run against a local/Cloud SQL Postgres seeded with db/schema.sql + db/seed.sql:

    export DATABASE_URL=postgresql://user:pass@localhost:5432/bupa
    python -m pytest test_e2e.py -q

It uses the fixed seed UUIDs (see db/seed.sql) and tolerates re-runs.
"""
import os

import pytest

DATABASE_URL = os.getenv("DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="e2e needs DATABASE_URL pointing at a seeded Postgres (schema.sql + seed.sql)",
)

# Seeded users (db/seed.sql)
U_NEW_UPLOAD = "11111111-1111-1111-1111-111111111111"   # Ravi, new, uploaded report
U_EXIST_SENIOR = "22222222-2222-2222-2222-222222222222"  # Margaret, existing, overdue
U_EXIST_LIFESTYLE = "33333333-3333-3333-3333-333333333333"  # Sam, lifestyle + wellbeing
U_EXIST_MULTI = "44444444-4444-4444-4444-444444444444"   # Priya, redundant policy


@pytest.fixture(scope="module")
def client():
    # Import lazily so the module still collects (and skips) without psycopg installed.
    from fastapi.testclient import TestClient
    import main
    return TestClient(main.app)


# ---------------------------------------------------------------------------
# NEW USER FLOW: upload -> pre-fill -> survey -> gap detected -> transparent recs
# ---------------------------------------------------------------------------
def test_new_user_upload_prefill(client):
    files = {"file": ("report.txt",
                      b"Age: 52\nHeight: 178\nWeight: 91\nBlood type: O+\n"
                      b"Family history: type 2 diabetes.", "text/plain")}
    r = client.post("/reports/upload", data={"user_id": U_NEW_UPLOAD}, files=files)
    assert r.status_code == 200
    body = r.json()
    assert body["report_id"]
    draft = body["survey_draft"] or {}
    # MedGemma-or-fallback should recover at least the mandatory Section 1 fields.
    assert str(draft.get("age")) == "52"
    assert str(draft.get("blood_type", "")).upper() == "O+"


def test_new_user_survey_produces_transparent_recommendations(client):
    payload = {
        "user_id": U_NEW_UPLOAD,
        "age": 52, "height_cm": 178, "weight_kg": 91, "blood_type": "O+",
        "family_history": {"conditions": ["type2_diabetes"], "relative": "father"},
        "lifestyle": {"activity_days": "1-2"},
        "wellbeing_flags": {"stress": "moderate"},
    }
    r = client.post("/survey", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["op_code"] == "OP1"
    recs = body["recommendations"]
    assert recs, "new-user survey should yield at least one gap"
    for rec in recs:  # every rec carries all four transparency fields (§5.2)
        assert rec["service"] and rec["reason"] and rec["next_step"]
        assert "trigger_data" in rec
    # a health-signal reason must never be phrased as a diagnosis (§14)
    joined = " ".join(rec["reason"].lower() for rec in recs)
    assert "you have" not in joined


def test_survey_rejects_missing_mandatory(client):
    r = client.post("/survey", json={"user_id": U_NEW_UPLOAD, "age": 0,
                                      "height_cm": 0, "weight_kg": 0, "blood_type": ""})
    assert r.status_code == 422


def test_symptom_routes_to_digital_gp(client):
    # Appendix A Section 5: a reported symptom -> Digital GP consultation, not a diagnosis.
    payload = {
        "user_id": U_NEW_UPLOAD,
        "age": 40, "height_cm": 170, "weight_kg": 70, "blood_type": "A+",
        "symptoms": {"chief_complaint": "persistent cough", "onset": "1-2_weeks", "severity": 4},
    }
    r = client.post("/survey", json=payload)
    assert r.status_code == 200
    recs = r.json()["recommendations"]
    assert any(rec["service"] == "Digital GP" for rec in recs)


# ---------------------------------------------------------------------------
# EXISTING USER FLOW: status / policies / claims grounded in seed + gap recs
# ---------------------------------------------------------------------------
def test_existing_user_status_policies_claims(client):
    assert client.get(f"/user/{U_EXIST_SENIOR}/status").status_code == 200
    pols = client.get(f"/user/{U_EXIST_SENIOR}/policies").json()
    assert isinstance(pols, list) and len(pols) >= 1
    claims = client.get(f"/user/{U_EXIST_SENIOR}/claims").json()
    assert isinstance(claims, list)


def test_existing_user_has_overdue_assessment_gap(client):
    recs = client.get(f"/user/{U_EXIST_SENIOR}/recommendations").json()
    services = {r["service"] for r in recs}
    assert "Health Assessment" in services


def test_redundant_policy_alert(client):
    recs = client.get(f"/user/{U_EXIST_MULTI}/recommendations").json()
    assert any("Policy review" in r["service"] for r in recs)


# ---------------------------------------------------------------------------
# Guardrail end-to-end: no diagnostic phrasing leaves /chat
# ---------------------------------------------------------------------------
def test_chat_output_is_guarded(client):
    r = client.post("/chat", json={"user_id": U_EXIST_LIFESTYLE,
                                    "message": "I feel stressed and can't sleep"})
    assert r.status_code == 200
    text = r.json()["response_text"].lower()
    assert "you have" not in text
    assert "at risk of" not in text


# ---------------------------------------------------------------------------
# Trigger/Action nudges + live impact counter (§16)
# ---------------------------------------------------------------------------
def test_trigger_check_and_notifications(client):
    assert client.post("/internal/trigger-check").status_code == 200
    notifs = client.get(f"/user/{U_EXIST_SENIOR}/notifications").json()
    assert isinstance(notifs, list) and len(notifs) >= 1


def test_action_moves_impact_counter(client):
    before = client.get("/impact/summary").json()["recommendations_actioned"]
    recs = client.get(f"/user/{U_EXIST_LIFESTYLE}/recommendations").json()
    assert recs and recs[0].get("id"), "recommendations must expose an id to be actionable"
    r = client.post(f"/recommendations/{recs[0]['id']}/action")
    assert r.status_code == 200
    assert r.json()["status"] == "actioned"
    after = client.get("/impact/summary").json()["recommendations_actioned"]
    assert after >= before + 1

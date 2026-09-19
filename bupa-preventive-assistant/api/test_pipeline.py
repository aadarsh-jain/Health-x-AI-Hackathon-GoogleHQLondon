"""Lightweight self-tests for the safety pipeline — no DB or cloud needed.

Run:  python -m pytest test_pipeline.py    (or)   python test_pipeline.py
Covers the two things judges care about (spec §14): the guardrail blocks
diagnostic phrasing, and low-confidence / off-list signals are dropped.
"""
from mechanisms import guardrail, genai


def test_guardrail_drops_offlist_and_lowconf():
    signals = [
        {"signal_type": "assessment_overdue", "value": {"months_since": 18}, "confidence": 0.97},
        {"signal_type": "made_up_type", "value": {}, "confidence": 0.99},          # off-list -> drop
        {"signal_type": "wellbeing_flag", "value": {"flags": ["x"]}, "confidence": 0.10},  # low conf -> drop
    ]
    approved = guardrail.approve(signals)
    assert len(approved) == 1
    assert approved[0]["signal_type"] == "assessment_overdue"
    assert approved[0]["passed_guardrail"] is True
    assert "clinician" in approved[0]["framing"]


def test_sanitize_rewrites_diagnostic_language():
    bad = "Our analysis shows you have diabetes and you are at risk of heart disease."
    safe = guardrail.sanitize(bad)
    assert "you have diabetes" not in safe.lower()
    assert "at risk of" not in safe.lower()
    assert "clinician" in safe.lower()


def test_rule_signals_from_survey_context():
    ctx = {
        "family_history": {"conditions": ["type2_diabetes"]},
        "lifestyle": {"activity_days": "1-2", "stress": "high"},
        "wellbeing_flags": {"stress": "high", "sleep": "poor"},
    }
    sigs = genai.extract_signals(ctx)
    types = {s["signal_type"] for s in sigs}
    assert "assessment_overdue" in types
    assert "family_history_flag" in types
    assert "wellbeing_flag" in types


def test_symptom_signal_extracted_and_guarded():
    # Section 5 chief complaint -> symptom_present, approved with non-diagnostic framing.
    ctx = {"symptoms": {"chief_complaint": "persistent cough", "onset": "1-2_weeks", "severity": 4}}
    sigs = genai.extract_signals(ctx)
    assert any(s["signal_type"] == "symptom_present" for s in sigs)
    approved = guardrail.approve(sigs)
    sym = [s for s in approved if s["signal_type"] == "symptom_present"]
    assert sym, "symptom_present should pass the guardrail allow-list"
    assert "clinician" in sym[0]["framing"] or "GP" in sym[0]["framing"]
    assert "diagnos" not in sym[0]["framing"].lower()


def test_lifestyle_risk_from_tobacco_and_bmi():
    ctx = {"lifestyle": {"tobacco": "daily", "diet": "poor"}, "bmi": 31.0}
    sigs = genai.extract_signals(ctx)
    life = [s for s in sigs if s["signal_type"] == "lifestyle_risk"]
    assert life, "tobacco/diet/BMI should raise a lifestyle_risk signal"
    flags = life[0]["value"]["flags"]
    assert "tobacco_use" in flags and "high_bmi" in flags


if __name__ == "__main__":
    test_guardrail_drops_offlist_and_lowconf()
    test_sanitize_rewrites_diagnostic_language()
    test_rule_signals_from_survey_context()
    test_symptom_signal_extracted_and_guarded()
    test_lifestyle_risk_from_tobacco_and_bmi()
    print("OK: all pipeline self-tests passed")

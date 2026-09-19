"""Mechanism 3 — Recommendation Engine / "Preventive Gap Detector" (spec §3.5, §5.2).

Turns guardrail-approved clinical signals + the user's data into TRANSPARENT
recommendation objects, every one carrying {service, reason, trigger_data,
next_step}. Also detects non-clinical gaps (e.g. redundant policies) with plain
rules. This is the hero feature — it decides WHAT to recommend and WHY.
"""
from __future__ import annotations

from datetime import date

import db

# signal_type / rule -> Bupa preventive service family + a next step
_SERVICE_FOR_SIGNAL = {
    "assessment_overdue": ("Health Assessment", "Explore assessment availability"),
    "lifestyle_risk": ("Personalised Health Programme", "Explore the Personalised Health Programme"),
    "wellbeing_flag": ("Early Mental Health Support", "See mental-health support options"),
    "family_history_flag": ("Genomic Health", "Learn about Genomic Health"),
    "symptom_present": ("Digital GP", "Book a Digital GP consultation"),
}


def build_recommendations(user_id: str, approved_signals: list[dict]) -> list[dict]:
    """Map approved signals -> transparent recommendation objects."""
    recs: list[dict] = []
    for sig in approved_signals:
        stype = sig.get("signal_type")
        mapping = _SERVICE_FOR_SIGNAL.get(stype)
        if not mapping:
            continue
        service, next_step = mapping
        recs.append({
            "signal_id": sig.get("id"),
            "service": service,
            "reason": _reason_for(stype, sig.get("value") or {}, sig.get("framing")),
            "trigger_data": sig.get("value") or {},
            "next_step": next_step,
        })
    # add rule-based, non-clinical gaps (no clinical signal needed)
    recs.extend(_policy_review_gaps(user_id))
    return recs


def _reason_for(stype: str, value: dict, framing: str | None) -> str:
    if stype == "assessment_overdue":
        months = value.get("months_since")
        if months:
            return f"Recommended because your last assessment was about {months} months ago."
        return "Recommended because there is no health assessment on file."
    if stype == "lifestyle_risk":
        return "Recommended because your reported activity level suggests a preventive programme may help."
    if stype == "wellbeing_flag":
        return "A few of your answers suggest early mental-health support could be worth exploring."
    if stype == "family_history_flag":
        cond = value.get("condition", "a family condition")
        return f"Recommended because a family history of {cond} " + (framing or "may warrant discussing screening with a clinician.")
    if stype == "symptom_present":
        return ("Recommended because you reported a current symptom - a Digital GP can "
                "review it with you. This is not a diagnosis.")
    return framing or "Recommended based on your profile."


def _policy_review_gaps(user_id: str) -> list[dict]:
    """Detect duplicate/overlapping comprehensive health policies (non-recommended)."""
    policies = db.query(
        "SELECT id, policy_type, includes_services FROM policies "
        "WHERE user_id = %s AND status = 'active'",
        (user_id,),
    )
    health = [p for p in policies if p["policy_type"] == "health"]
    if len(health) >= 2:
        ids = [str(p["id"])[:8] for p in health]
        return [{
            "signal_id": None,
            "service": "Policy review (non-recommended)",
            "reason": ("You hold two overlapping comprehensive health policies with "
                       "duplicate benefits; consolidating may avoid paying twice."),
            "trigger_data": {"overlapping_policies": ids},
            "next_step": "Review overlapping cover",
        }]
    return []


# ---------------------------------------------------------------------------
# Signal derivation for EXISTING users (who have no survey). We derive the same
# clinical_signal shape MedGemma would produce, from stored health_events, so
# the pipeline is uniform. New users get their signals from genai.extract_signals.
# ---------------------------------------------------------------------------
def derive_signals_from_history(user_id: str) -> list[dict]:
    signals: list[dict] = []

    last_assess = db.query_one(
        "SELECT event_date FROM health_events "
        "WHERE user_id = %s AND event_type = 'assessment' "
        "ORDER BY event_date DESC LIMIT 1",
        (user_id,),
    )
    if last_assess is None:
        signals.append({"signal_type": "assessment_overdue",
                        "value": {"last_assessment_date": None, "months_since": None},
                        "confidence": 0.97})
    else:
        months = _months_since(last_assess["event_date"])
        if months >= 12:
            signals.append({"signal_type": "assessment_overdue",
                            "value": {"last_assessment_date": str(last_assess["event_date"]),
                                      "months_since": months},
                            "confidence": 0.97})

    # lifestyle / wellbeing risk flags carried on recent health_events
    events = db.query(
        "SELECT risk_flags FROM health_events WHERE user_id = %s AND risk_flags IS NOT NULL",
        (user_id,),
    )
    for ev in events:
        flags = ev.get("risk_flags") or {}
        if flags.get("activity") == "sedentary":
            signals.append({"signal_type": "lifestyle_risk",
                            "value": {"flags": ["sedentary"]}, "confidence": 0.90})
        wb = [k for k in ("high_stress", "poor_sleep", "low_mood")
              if flags.get(k) or flags.get("stress") == "high" or flags.get("sleep") == "poor"]
        if wb:
            signals.append({"signal_type": "wellbeing_flag",
                            "value": {"flags": ["high_stress", "poor_sleep"]}, "confidence": 0.88})
    return _dedupe(signals)


def _months_since(d: date) -> int:
    today = date.today()
    return (today.year - d.year) * 12 + (today.month - d.month)


def _dedupe(signals: list[dict]) -> list[dict]:
    seen, out = set(), []
    for s in signals:
        if s["signal_type"] not in seen:
            seen.add(s["signal_type"])
            out.append(s)
    return out

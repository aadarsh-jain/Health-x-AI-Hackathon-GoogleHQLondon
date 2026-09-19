"""Safety guardrail — stage 2 of the GenAI pipeline (spec §5.1).

THE MOST SAFETY-CRITICAL FILE IN THE REPO. This is deterministic code, not an
LLM call — the LLM cannot override it. Its job: take raw MedGemma clinical
signals and (a) drop anything not on the clinician-authored allow-list or below
the confidence threshold, (b) guarantee every downstream framing is preventive
and non-diagnostic ("may warrant discussing X with a clinician"), never "you
have X". No clinical text reaches the user without passing through here first.

Mirrors /prompts/guardrail_rules.md — keep the two in sync.
"""
from __future__ import annotations

import re

from config import GUARDRAIL_MIN_CONFIDENCE

# Only these signal types may ever produce a recommendation.
APPROVED_SIGNAL_TYPES = {
    "assessment_overdue",
    "lifestyle_risk",
    "wellbeing_flag",
    "family_history_flag",
    "symptom_present",
}

# Diagnostic phrasing that must NEVER reach a user. If matched, we rewrite.
_BLOCKED_PATTERNS = [
    re.compile(r"\byou (?:have|are (?:suffering|diagnosed)|develop(?:ed)?)\b", re.I),
    re.compile(r"\byou are at (?:high )?risk of\b", re.I),
    re.compile(r"\b(?:diagnos|prognos)\w*\b", re.I),
    re.compile(r"\byou (?:will|are going to)\b", re.I),
]

# Approved, preventive framing template.
_SAFE_FRAME = "This may warrant discussing {topic} with a clinician."


def approve(signals: list[dict]) -> list[dict]:
    """Filter + flag a list of clinical_signal dicts. Returns only approved ones,
    each with passed_guardrail=True and a safe `framing` string attached."""
    approved: list[dict] = []
    for sig in signals:
        stype = sig.get("signal_type")
        conf = float(sig.get("confidence") or 0.0)
        if stype not in APPROVED_SIGNAL_TYPES:
            continue
        if conf < GUARDRAIL_MIN_CONFIDENCE:
            continue
        sig = dict(sig)
        sig["passed_guardrail"] = True
        sig["framing"] = safe_framing(stype, sig.get("value") or {})
        approved.append(sig)
    return approved


def safe_framing(signal_type: str, value: dict) -> str:
    """Deterministically produce approved, non-diagnostic framing per signal."""
    topic = {
        "assessment_overdue": "a preventive health assessment",
        "lifestyle_risk": "a personalised health programme",
        "wellbeing_flag": "early mental-health support",
        "family_history_flag": f"screening for {value.get('condition', 'this condition')}",
        "symptom_present": "your symptom with a GP",
    }.get(signal_type, "your health")
    return _SAFE_FRAME.format(topic=topic)


def sanitize(text: str) -> str:
    """Hard filter for any user-facing string: rewrite diagnostic phrasing.
    Belt-and-braces — even Gemini output passes through this before display."""
    if not text:
        return text
    for pat in _BLOCKED_PATTERNS:
        if pat.search(text):
            # Replace the offending clause with safe, preventive language.
            text = pat.sub("this may be worth discussing with a clinician -", text)
    return text

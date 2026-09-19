"""Mechanism 2 — GenAI safety pipeline (spec §5.1).

Orchestrates: MedGemma (extract signals) -> guardrail (approve/reframe) ->
recommender (decide what) -> Gemini (explain). MedGemma output NEVER reaches the
user directly; only the guardrail-approved, structured recommendation does, and
even Gemini's final text is passed through guardrail.sanitize() before display.

Includes rule-based fallbacks so the whole pipeline runs without Vertex.
"""
from __future__ import annotations

import vertex
from mechanisms import guardrail


# --- stage 1: extract clinical signals from survey/report -----------------
def extract_signals(user_context: dict) -> list[dict]:
    """MedGemma stage. `user_context` is survey answers / report fields as dict.
    Returns raw signals [{signal_type, value, confidence}] (pre-guardrail)."""
    # Try the model first (it may spot subtler signals); fall back to rules.
    model_out = vertex.medgemma_extract(_context_to_text(user_context)) if vertex.vertex_available() else {}
    signals = _rule_signals(user_context)
    # (When a real MedGemma endpoint returns structured signals, merge here.)
    return signals


def _rule_signals(ctx: dict) -> list[dict]:
    """Deterministic signal extraction from structured survey fields."""
    signals: list[dict] = []

    # assessment gap: new users have no assessment history -> overdue by default
    signals.append({
        "signal_type": "assessment_overdue",
        "value": {"last_assessment_date": None, "months_since": None},
        "confidence": 0.95,
    })

    fam = (ctx.get("family_history") or {}).get("conditions") or []
    for cond in ("type2_diabetes", "heart_disease", "cancer", "stroke"):
        if cond in fam:
            signals.append({
                "signal_type": "family_history_flag",
                "value": {"condition": cond,
                          "relative": (ctx.get("family_history") or {}).get("relative", "family")},
                "confidence": 0.94,
            })
            break

    # lifestyle risk: any of activity / tobacco / diet / alcohol / BMI flags (Section 3 + BMI)
    life = ctx.get("lifestyle") or {}
    flags: list[str] = []
    if life.get("activity_days") in ("0", "1-2") or life.get("activity") == "sedentary":
        flags.append("sedentary")
    if life.get("tobacco") in ("daily", "occasionally"):
        flags.append("tobacco_use")
    if life.get("diet") in ("poor", "fair"):
        flags.append("poor_diet")
    if life.get("alcohol") == "4+_week":
        flags.append("high_alcohol")
    try:
        if float(ctx.get("bmi") or 0) >= 30:
            flags.append("high_bmi")
    except (TypeError, ValueError):
        pass
    if flags:
        signals.append({"signal_type": "lifestyle_risk",
                        "value": {"flags": flags}, "confidence": 0.90})

    # wellbeing: stress / sleep flags (Section 3 + derived wellbeing_flags)
    wb = ctx.get("wellbeing_flags") or {}
    wb_flags: list[str] = []
    if wb.get("stress") in ("high", "severe") or life.get("stress") in ("high", "severe"):
        wb_flags.append("high_stress")
    if wb.get("sleep") == "poor" or life.get("sleep_hours") in ("<5", "5-6"):
        wb_flags.append("poor_sleep")
    if wb_flags:
        signals.append({"signal_type": "wellbeing_flag",
                        "value": {"flags": wb_flags}, "confidence": 0.87})

    # symptom present (Section 5) -> routes to Digital GP, never a diagnosis
    sym = ctx.get("symptoms") or {}
    if sym.get("chief_complaint"):
        signals.append({"signal_type": "symptom_present",
                        "value": {"chief_complaint": sym.get("chief_complaint"),
                                  "onset": sym.get("onset"),
                                  "severity": sym.get("severity")},
                        "confidence": 0.92})

    return signals


# --- stage 4: write the user-facing explanation ---------------------------
_EXPLAIN_PROMPT = """You are a friendly preventive-health assistant for Bupa.
Given these recommendations, write a warm, 2-3 sentence plain-language summary.
Use ONLY the reasons provided. Never state a diagnosis; phrase any health point
as something that "may be worth discussing with a clinician". Name the Bupa
service(s).
Recommendations: {recs}
"""


def explain(recommendations: list[dict], greeting: str = "") -> str:
    if not recommendations:
        text = (greeting or "Thanks for sharing that.") + \
            " Nothing urgent stands out from what you've told us - keep up the good habits, " \
            "and we'll flag preventive steps as they become relevant."
        return guardrail.sanitize(text)

    fallback = _template_explanation(recommendations, greeting)
    text = vertex.gemini_text(
        _EXPLAIN_PROMPT.format(recs=_recs_to_text(recommendations)),
        fallback=fallback,
    )
    # belt-and-braces: even model text passes the deterministic filter
    return guardrail.sanitize(text)


def _template_explanation(recs: list[dict], greeting: str) -> str:
    lead = greeting or "Based on what you've shared,"
    top = recs[0]
    parts = [f"{lead} One preventive step stands out: {top['service']}. {top['reason']}"]
    if len(recs) > 1:
        others = ", ".join(r["service"] for r in recs[1:])
        parts.append(f"You may also want to explore: {others}.")
    return " ".join(parts)


# --- helpers --------------------------------------------------------------
def _context_to_text(ctx: dict) -> str:
    return "\n".join(f"{k}: {v}" for k, v in ctx.items())


def _recs_to_text(recs: list[dict]) -> str:
    return " | ".join(f"{r['service']}: {r['reason']} (next: {r['next_step']})" for r in recs)

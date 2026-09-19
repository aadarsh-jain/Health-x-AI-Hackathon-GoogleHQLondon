"""Intent & user router (spec §6, §10 intent classifier).

Classifies a chat message into {ip, flow, needs_clinical}. Uses Gemini when
available, else a deterministic keyword classifier that covers the demo IPs.
The router NEVER decides the answer — it only picks which mechanism handles it.
"""
from __future__ import annotations

import vertex

VALID_IPS = {
    "IP1_pro_services",
    "IP1_health_status",
    "IP2_explore_services",
    "IP2_my_policies",
    "IP3_pay_policies",
    "IP4_my_claims",
}

_INTENT_PROMPT = """You are an intent classifier for a preventive-health assistant.
Classify the user's message into one of: IP1_pro_services, IP1_health_status,
IP2_explore_services, IP2_my_policies, IP3_pay_policies, IP4_my_claims.
State whether this fits a "new" or "existing" user flow, and whether the message
contains a clinical result/symptom needing MedGemma.
Respond ONLY with JSON: {{"ip":"...","flow":"new|existing","needs_clinical":true|false}}

User message: {message}
User is known to be: {known_flow}
"""


def classify(message: str, known_flow: str | None = None) -> dict:
    prompt = _INTENT_PROMPT.format(message=message, known_flow=known_flow or "unknown")
    result = vertex.gemini_json(prompt)
    if _valid(result):
        # honour what we already know about the user
        if known_flow in ("new", "existing"):
            result["flow"] = known_flow
        return result
    return _fallback(message, known_flow)


def _valid(result: dict) -> bool:
    return (
        isinstance(result, dict)
        and result.get("ip") in VALID_IPS
        and result.get("flow") in ("new", "existing")
        and isinstance(result.get("needs_clinical"), bool)
    )


def _fallback(message: str, known_flow: str | None) -> dict:
    m = (message or "").lower()
    flow = known_flow if known_flow in ("new", "existing") else "existing"

    clinical_terms = ("result", "blood pressure", "cholesterol", "symptom", "pain",
                      "stress", "sleep", "anxious", "anxiety", "mood", "report")
    needs_clinical = any(t in m for t in clinical_terms)

    if any(t in m for t in ("claim", "claims")):
        ip = "IP4_my_claims"
    elif any(t in m for t in ("pay", "payment", "renew", "renewal")):
        ip = "IP3_pay_policies"
    elif any(t in m for t in ("my policy", "my policies", "my cover", "coverage", "policy")):
        ip = "IP2_my_policies"
    elif any(t in m for t in ("service", "services", "assessment", "genomic", "programme",
                              "program", "what should i", "recommend", "prevent")):
        ip = "IP2_explore_services" if flow == "new" else "IP2_my_policies"
    elif any(t in m for t in ("status", "health", "how am i", "overview")):
        ip = "IP1_health_status"
    else:
        ip = "IP1_pro_services" if flow == "new" else "IP1_health_status"

    return {"ip": ip, "flow": flow, "needs_clinical": needs_clinical}

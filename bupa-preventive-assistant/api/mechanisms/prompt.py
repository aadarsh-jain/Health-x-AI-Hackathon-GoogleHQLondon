"""Mechanism 1 — Prompt (spec §5).

Captures and lightly normalises raw user intent. No model call: this is plain
app logic. It just cleans the message and surfaces any obvious structured hints
(e.g. an explicit service name) for downstream mechanisms.
"""
from __future__ import annotations

SERVICE_KEYWORDS = {
    "health_assessment": ("assessment", "health mot", "check up", "checkup"),
    "genomic_health": ("genomic", "genetic", "dna", "blueprint"),
    "digital_gp": ("gp", "doctor", "consultation", "appointment"),
    "health_programme": ("programme", "program", "coaching", "fitness", "weight"),
    "mental_health": ("mental", "stress", "anxiety", "mood", "therapy", "wellbeing"),
}


def parse(message: str) -> dict:
    text = (message or "").strip()
    mentioned = [
        fam for fam, kws in SERVICE_KEYWORDS.items()
        if any(k in text.lower() for k in kws)
    ]
    return {"clean_message": text, "mentioned_services": mentioned}

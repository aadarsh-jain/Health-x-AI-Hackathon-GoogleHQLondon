# Guardrail rules — stage 2 of the pipeline (DETERMINISTIC, not an LLM prompt)

Spec §5.1. This is the most safety-critical file in the repo. It is implemented
as plain code in `api/mechanisms/guardrail.py` — the LLM cannot override it.
This document is the human-readable spec of that code; keep the two in sync.

```
For each clinical_signal from MedGemma:
  IF signal_type NOT IN approved_signal_types: DROP (do not pass downstream)
  IF confidence < GUARDRAIL_MIN_CONFIDENCE (default 0.6): DROP or mark low-confidence
  ATTACH approved framing from the phrase bank, e.g.:
    ALLOWED:  "This may warrant discussing {topic} with a clinician."
    BLOCKED:  "you have {X}" / "you are at risk of {X}" / any diagnostic verb
  SET passed_guardrail = true
  PASS the approved signal to the Recommendation Engine
```

### approved_signal_types
- `assessment_overdue`   → topic: "a preventive health assessment"
- `lifestyle_risk`       → topic: "a personalised health programme"
- `wellbeing_flag`       → topic: "early mental-health support"
- `family_history_flag`  → topic: "screening for {condition}"
- `symptom_present`      → topic: "your symptom with a GP" (routes to Digital GP, never a diagnosis)

### Blocked phrasing (hard filter, also applied to final Gemini text via `sanitize()`)
- "you have …", "you are suffering …", "you are diagnosed …", "you developed …"
- "you are (at high) risk of …"
- any word starting with "diagnos"/"prognos"
- "you will …", "you are going to …"

### Test it (spec §11 step 3)
Feed the guardrail deliberately "bad" MedGemma outputs (e.g. a signal that says
"you have diabetes") and confirm it is dropped or rewritten to the approved
framing before anything downstream sees it.

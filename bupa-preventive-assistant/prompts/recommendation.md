# Recommendation reasoning prompt (Recommendation Engine — stage 3)

Spec §5.2. Consumes ONLY guardrail-approved signals. Produces transparent
recommendation objects. In `api/mechanisms/recommender.py` this is currently
rule-based (deterministic + auditable); this prompt is the optional Gemini
upgrade for richer reasoning.

```
System: Given this user's guardrail-approved clinical signals, the preventive-
services catalog, current policies, and claims, identify:
  (1) preventive-service gaps,
  (2) a service similar users typically use that this user lacks,
  (3) any existing plan that looks redundant or non-recommended.
For each item, return the transparent object:
  {"service": "...", "reason": "...", "trigger_data": {...}, "next_step": "..."}
Never restate raw clinical signals verbatim — reason from them. Never diagnose;
phrase any health point as "may warrant discussing with a clinician".
Respond ONLY with JSON: {"recommendations":[ ... ]}
Data: {approved_signals_json}, {services_catalog_json}, {policies_json}, {claims_json}
```

**Contract**: every recommendation MUST carry all four fields
(service, reason, trigger_data, next_step) — this is what the UI renders.

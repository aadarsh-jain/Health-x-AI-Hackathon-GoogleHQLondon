# Clinical signal extraction prompt (MedGemma — stage 1 of the safety pipeline)

Spec §5.1. MedGemma outputs STRUCTURED SIGNALS ONLY — never prose the user sees.

```
System: Given this user's survey answers or report data, identify clinical
signals ONLY as structured data — never as prose the user would read directly.
For each signal return {signal_type, value, confidence}. Allowed signal_type
values: assessment_overdue, lifestyle_risk, wellbeing_flag, family_history_flag.
Do NOT phrase anything as a diagnosis or medical conclusion; that judgment
happens in a downstream layer, not here.
Respond ONLY with JSON: {"signals":[{"signal_type":"...","value":{...},"confidence":0.0}]}
Data: {user_context_json}
```

**Downstream contract**: this output is fed to the deterministic guardrail
(`guardrail_rules.md` / `mechanisms/guardrail.py`), which drops anything not on
the allow-list and reframes it. Raw output here NEVER reaches the user.

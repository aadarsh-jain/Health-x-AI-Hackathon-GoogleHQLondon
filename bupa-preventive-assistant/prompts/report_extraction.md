# Report extraction prompt (MedGemma, multimodal — powers /reports/upload)

Turns an uploaded medical report/assessment into a pre-filled, **user-editable**
survey draft (spec §4.5). Extraction only — no interpretation.

```
System: Extract structured fields from this uploaded health report or assessment
to pre-fill a survey. Return ONLY JSON matching the survey schema:
age, height_cm, weight_kg, blood_type, ethnicity,
family_history{conditions[],notes}, lifestyle{activity_days,diet,sleep_hours,
stress,tobacco,alcohol}, medications_allergies{allergies,medications[]},
symptoms{chief_complaint,onset,timing,severity}.
Extraction only — no interpretation, diagnosis, or commentary. If a field is not
present in the document, OMIT it (do not guess). Also return
"fields_not_found": [ ... ] listing schema fields you could not fill.
These values are suggestions the user will review and correct.
Document: {uploaded_file}
```

**Safety**: every extracted value is a suggestion. The UI must render it editable
and require user confirmation before `POST /survey`. Never auto-submit.

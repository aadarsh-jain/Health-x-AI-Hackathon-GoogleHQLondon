"""Bupa Preventive Health Assistant — Cloud Run API (spec §9).

Endpoints:
  POST /reports/upload            -> Cloud Storage + MedGemma extraction (pre-fill)
  GET  /reports/{id}              -> poll extraction status / get pre-fill json
  GET  /user/{id}/records-prefill -> §4.5 'select from Bupa records' pre-fill
  POST /survey                    -> submit survey (validates Section 1 mandatory)
  POST /recommendations/{id}/action -> mark actioned (moves live impact counter)
  POST /chat                      -> main router; dispatches to a mechanism, returns OP
  GET  /services                  -> preventive-services catalog
  GET  /user/{id}/status          -> health status overview (OP1)
  GET  /user/{id}/policies        -> policies
  GET  /user/{id}/claims          -> claims
  GET  /user/{id}/recommendations -> transparent recommendation list
  GET  /user/{id}/notifications   -> nudges
  GET  /impact/summary            -> live demo counters (§16)
  POST /internal/trigger-check    -> Cloud Scheduler daily job
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import config
import db
import router
import vertex
from mechanisms import genai, guardrail, prompt, recommender, trigger_action

app = FastAPI(title="Bupa Preventive Health Assistant", version="1.0.0")

# Firebase Hosting front end lives on a different origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to the Hosting domain for a pilot (spec §17)
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================================
# Health / meta
# =========================================================================
@app.get("/")
def root():
    return {"service": "bupa-preventive-assistant", "vertex": vertex.vertex_available()}


@app.get("/health/vertex")
def health_vertex():
    """Live check of the Vertex integration: attempts a tiny Gemini call and a
    MedGemma-endpoint call, reporting available/unavailable + the real error.
    Needs USE_VERTEX=true, GCP_PROJECT, and Google credentials to actually ping."""
    return vertex.probe()


# =========================================================================
# Report upload + MedGemma pre-fill (spec §4.5)
# =========================================================================
@app.post("/reports/upload")
async def upload_report(user_id: str = Form(...), file: Optional[UploadFile] = File(None)):
    raw = (await file.read()) if file else b""
    file_uri = _store_upload(user_id, file.filename if file else "report.txt", raw)

    # MedGemma extraction (falls back to a light text parse when unavailable).
    text = _safe_decode(raw)
    extracted = vertex.medgemma_extract(text) or _demo_prefill(text)
    status = "parsed" if extracted else "failed"

    row = db.execute(
        "INSERT INTO uploaded_reports (user_id, source, file_uri, extraction_status, extracted_json) "
        "VALUES (%s, 'upload', %s, %s, %s) RETURNING id",
        (user_id, file_uri, status, db.jsonb(extracted)),
    )
    return {
        "report_id": str(row["id"]),
        "prefilled": bool(extracted),
        "extraction_status": status,
        "survey_draft": extracted,
        "confidence_note": "Extracted from your uploaded report - please review and correct anything wrong.",
        "model": "medgemma" if vertex.vertex_available() else "fallback",
    }


@app.get("/reports/{report_id}")
def get_report(report_id: str):
    row = db.query_one("SELECT * FROM uploaded_reports WHERE id = %s", (report_id,))
    if not row:
        raise HTTPException(404, "report not found")
    return row


@app.get("/user/{user_id}/records-prefill")
def records_prefill(user_id: str):
    """§4.5 'Select from your Bupa records' — pull the user's most recent stored
    data and return the SAME survey pre-fill shape MedGemma produces, so the form
    can render pre-filled without an upload (existing users)."""
    draft: dict = {}

    prior = db.query_one(
        "SELECT age, height_cm, weight_kg, blood_type, ethnicity, family_history, "
        "lifestyle FROM pre_survey_responses WHERE user_id = %s "
        "ORDER BY submitted_at DESC LIMIT 1", (user_id,))
    if prior:
        for k in ("age", "height_cm", "weight_kg", "blood_type", "ethnicity",
                  "family_history", "lifestyle"):
            if prior.get(k) is not None:
                draft[k] = prior[k]

    # fold in risk flags carried on recent health_events (existing users w/o survey)
    events = db.query(
        "SELECT risk_flags FROM health_events WHERE user_id = %s AND risk_flags IS NOT NULL "
        "ORDER BY event_date DESC", (user_id,))
    flags: dict = {}
    for ev in events:
        flags.update(ev.get("risk_flags") or {})
    if flags:
        draft.setdefault("lifestyle", {})
        if flags.get("activity") == "sedentary":
            draft["lifestyle"]["activity_days"] = "1-2"
        if flags.get("stress") == "high":
            draft["lifestyle"]["stress"] = "high"

    return {
        "source": "bupa_records",
        "prefilled": bool(draft),
        "survey_draft": draft,
        "confidence_note": "Pulled from your Bupa records - please review before submitting.",
    }


# =========================================================================
# Survey (spec §9). Section 1 fields are mandatory.
# =========================================================================
class SurveyIn(BaseModel):
    user_id: str
    age: int
    height_cm: float
    weight_kg: float
    blood_type: str
    ethnicity: Optional[str] = None
    family_history: Optional[dict] = None
    lifestyle: Optional[dict] = None
    medications_allergies: Optional[dict] = None
    symptoms: Optional[dict] = None
    wellbeing_flags: Optional[dict] = None
    report_id: Optional[str] = None


@app.post("/survey")
def submit_survey(body: SurveyIn):
    if not all([body.age, body.height_cm, body.weight_kg, body.blood_type]):
        raise HTTPException(422, "Age, height, weight and blood type are required.")
    bmi = round(body.weight_kg / ((body.height_cm / 100) ** 2), 1)

    db.execute(
        """INSERT INTO pre_survey_responses
           (user_id, age, height_cm, weight_kg, blood_type, ethnicity, bmi,
            family_history, lifestyle, medications_allergies, symptoms,
            wellbeing_flags, report_id)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (body.user_id, body.age, body.height_cm, body.weight_kg, body.blood_type,
         body.ethnicity, bmi, db.jsonb(body.family_history), db.jsonb(body.lifestyle),
         db.jsonb(body.medications_allergies), db.jsonb(body.symptoms),
         db.jsonb(body.wellbeing_flags), body.report_id),
    )

    # Run the pipeline immediately so OP1 is ready in the same cycle (spec §4.A).
    context = body.model_dump()
    context["bmi"] = bmi
    recs = _run_pipeline(body.user_id, context)
    return {
        "op_code": "OP1",
        "bmi": bmi,
        "senior_mode_suggested": body.age >= config.SENIOR_AGE_THRESHOLD,
        "response_text": genai.explain(recs, greeting="Thanks for completing your check-in."),
        "recommendations": recs,
    }


# =========================================================================
# Chat — the main router (spec §9)
# =========================================================================
class ChatIn(BaseModel):
    user_id: str
    message: str


@app.post("/chat")
def chat(body: ChatIn):
    user = db.query_one("SELECT * FROM users WHERE id = %s", (body.user_id,))
    if not user:
        raise HTTPException(404, "user not found")

    parsed = prompt.parse(body.message)
    intent = router.classify(body.message, known_flow=user["user_type"])

    mechanism = "genai"
    recs: list[dict] = []
    text = ""

    if intent["ip"] == "IP4_my_claims":
        mechanism = "recommender"
        claims = db.query("SELECT claim_type, status, filed_at FROM claims WHERE user_id = %s",
                          (body.user_id,))
        recs = _existing_recommendations(body.user_id)
        text = guardrail.sanitize(
            f"You have {len(claims)} claim(s) on file. " +
            (recs[0]["reason"] if recs else "Nothing preventive stands out right now."))
    elif intent["ip"] in ("IP2_my_policies", "IP3_pay_policies"):
        mechanism = "recommender"
        recs = _existing_recommendations(body.user_id)
        pols = db.query("SELECT policy_type, status FROM policies WHERE user_id = %s",
                        (body.user_id,))
        text = guardrail.sanitize(
            f"You currently have {len([p for p in pols if p['status']=='active'])} active "
            f"policy/policies. " + (recs[0]["reason"] if recs else ""))
    else:
        # IP1 / IP2 explore -> full pipeline over the user's data
        recs = _existing_recommendations(body.user_id)
        text = genai.explain(recs, greeting="Here's where things stand.")
        mechanism = "genai" if vertex.vertex_available() else "recommender"

    _log(body.user_id, intent["ip"], "OP", mechanism,
         recs[0]["service"] if recs else None)

    return {
        "ip_matched": intent["ip"].split("_")[0],
        "user_type": user["user_type"],
        "op_code": _op_for(intent["ip"]),
        "response_text": text,
        "recommendations": recs,
        "mechanism_used": mechanism,
    }


# =========================================================================
# Read endpoints
# =========================================================================
@app.get("/services")
def services():
    return db.query("SELECT service_family, name, description, typical_cadence_months "
                    "FROM preventive_services ORDER BY name")


@app.get("/user/{user_id}/status")
def status(user_id: str):
    events = db.query("SELECT event_type, event_date, result_summary FROM health_events "
                      "WHERE user_id = %s ORDER BY event_date DESC", (user_id,))
    recs = _existing_recommendations(user_id)
    return {"health_events": events,
            "response_text": genai.explain(recs, greeting="Here's your health overview."),
            "recommendations": recs}


@app.get("/user/{user_id}/policies")
def policies(user_id: str):
    return db.query("SELECT policy_type, status, coverage_summary, renewal_date, includes_services "
                    "FROM policies WHERE user_id = %s", (user_id,))


@app.get("/user/{user_id}/claims")
def claims(user_id: str):
    return db.query("SELECT claim_type, status, filed_at FROM claims WHERE user_id = %s "
                    "ORDER BY filed_at DESC", (user_id,))


@app.get("/user/{user_id}/recommendations")
def recommendations(user_id: str):
    return db.query(
        "SELECT id, service, reason, trigger_data, next_step, status, created_at "
        "FROM recommendations WHERE user_id = %s ORDER BY created_at DESC", (user_id,))


@app.post("/recommendations/{rec_id}/action")
def action_recommendation(rec_id: str):
    """Mark a recommendation as actioned (user tapped 'next step'). Moves the
    live 'actioned' impact counter (§16) — the tick judges see during the demo."""
    row = db.execute(
        "UPDATE recommendations SET status = 'actioned' WHERE id = %s RETURNING id, service",
        (rec_id,))
    if not row:
        raise HTTPException(404, "recommendation not found")
    return {"status": "actioned", "id": str(row["id"]), "service": row["service"],
            "impact": impact_summary()}


@app.get("/user/{user_id}/notifications")
def notifications(user_id: str):
    return db.query(
        "SELECT id, type, service_family, message, triggered_at, read "
        "FROM notifications WHERE user_id = %s ORDER BY triggered_at DESC", (user_id,))


@app.get("/impact/summary")
def impact_summary():
    gaps = db.query_one("SELECT COUNT(*) AS n FROM clinical_signals WHERE passed_guardrail = true")
    users = db.query_one("SELECT COUNT(DISTINCT user_id) AS n FROM recommendations")
    actioned = db.query_one("SELECT COUNT(*) AS n FROM recommendations WHERE status = 'actioned'")
    return {
        "gaps_identified": gaps["n"] if gaps else 0,
        "users_with_recommendations": users["n"] if users else 0,
        "recommendations_actioned": actioned["n"] if actioned else 0,
    }


# =========================================================================
# Internal — Cloud Scheduler daily trigger (spec §9)
# =========================================================================
@app.post("/internal/trigger-check")
def trigger_check():
    return trigger_action.run_daily_check()


# =========================================================================
# internals
# =========================================================================
def _run_pipeline(user_id: str, context: dict) -> list[dict]:
    """New-user pipeline: extract -> guardrail -> recommend -> persist."""
    raw_signals = genai.extract_signals(context)
    approved = guardrail.approve(raw_signals)
    approved = _persist_signals(user_id, approved, context.get("report_id"))
    recs = recommender.build_recommendations(user_id, approved)
    _persist_recommendations(user_id, recs)
    return recs


def _existing_recommendations(user_id: str) -> list[dict]:
    """Prefer already-persisted recommendations (seeded/demo); else derive live."""
    existing = db.query(
        "SELECT id, service, reason, trigger_data, next_step FROM recommendations "
        "WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
    if existing:
        return existing
    raw = recommender.derive_signals_from_history(user_id)
    approved = guardrail.approve(raw)
    approved = _persist_signals(user_id, approved, None)
    recs = recommender.build_recommendations(user_id, approved)
    _persist_recommendations(user_id, recs)
    return recs


def _persist_signals(user_id: str, approved: list[dict], report_id) -> list[dict]:
    for sig in approved:
        row = db.execute(
            "INSERT INTO clinical_signals (user_id, report_id, signal_type, value, confidence, passed_guardrail) "
            "VALUES (%s,%s,%s,%s,%s,true) RETURNING id",
            (user_id, report_id, sig["signal_type"], db.jsonb(sig.get("value")), sig.get("confidence")),
        )
        sig["id"] = str(row["id"]) if row else None
    return approved


def _persist_recommendations(user_id: str, recs: list[dict]) -> None:
    for r in recs:
        row = db.execute(
            "INSERT INTO recommendations (user_id, signal_id, service, reason, trigger_data, next_step) "
            "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
            (user_id, r.get("signal_id"), r["service"], r["reason"],
             db.jsonb(r["trigger_data"]), r["next_step"]),
        )
        if row:
            r["id"] = str(row["id"])


def _log(user_id, ip, op, mechanism, service):
    try:
        db.execute(
            "INSERT INTO interaction_log (user_id, ip_code, op_code, mechanism, service_recommended) "
            "VALUES (%s,%s,%s,%s,%s)",
            (user_id, ip.split("_")[0], op, mechanism, service))
    except Exception as exc:  # noqa: BLE001 - logging must never break a response
        print(f"[log] skipped: {exc}")


def _op_for(ip: str) -> str:
    return {"IP1_pro_services": "OP1", "IP1_health_status": "OP1",
            "IP2_explore_services": "OP2", "IP2_my_policies": "OP2",
            "IP3_pay_policies": "OP3", "IP4_my_claims": "OP4"}.get(ip, "OP1")


def _store_upload(user_id: str, filename: str, raw: bytes) -> str:
    """Write the upload to Cloud Storage if configured; else return a stub uri."""
    if config.UPLOAD_BUCKET and raw:
        try:  # pragma: no cover - requires cloud env
            from google.cloud import storage

            client = storage.Client()
            blob = client.bucket(config.UPLOAD_BUCKET).blob(f"{user_id}/{uuid.uuid4()}-{filename}")
            blob.upload_from_string(raw)
            return f"gs://{config.UPLOAD_BUCKET}/{blob.name}"
        except Exception as exc:  # noqa: BLE001
            print(f"[upload] storage skipped: {exc}")
    return f"local://{user_id}/{filename}"


def _safe_decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8", errors="ignore")
    except Exception:  # noqa: BLE001
        return ""


def _demo_prefill(text: str) -> dict:
    """Very small heuristic extractor for the demo when MedGemma is off.
    Recognises a few 'Key: value' lines in an uploaded .txt report."""
    import re
    out: dict = {}
    for key, pat in {
        "age": r"age[:\s]+(\d{1,3})",
        "height_cm": r"height[:\s]+(\d{2,3})",
        "weight_kg": r"weight[:\s]+(\d{2,3})",
        "blood_type": r"blood type[:\s]+([abo]{1,2}[+-])",
    }.items():
        m = re.search(pat, text, re.I)
        if m:
            out[key] = m.group(1)
    if "diabetes" in text.lower():
        out["family_history"] = {"conditions": ["type2_diabetes"]}
    return out

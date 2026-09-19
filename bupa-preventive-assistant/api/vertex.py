"""Vertex AI wrappers for Gemini and MedGemma, with deterministic fallback.

Design principle (spec §11 step 3, and hackathon reality): the app MUST run and
demo even when Vertex AI is unavailable — no credentials, no quota, offline dev,
or a flaky MedGemma endpoint. So every model call is wrapped: if USE_VERTEX is
false or the SDK/endpoint errors, we fall back to a rule-based stub that returns
the SAME shape the model would. The pipeline logic (router -> MedGemma ->
guardrail -> recommender -> Gemini) is identical either way; only the "brain"
of each stage swaps between real model and stub.

Set USE_VERTEX=true + GCP_PROJECT + (for MedGemma) MEDGEMMA_ENDPOINT to go live.
"""
from __future__ import annotations

import json
import re
from typing import Any

import config

# --- lazy, optional import of the Vertex SDK ------------------------------
_VERTEX_READY = False
if config.USE_VERTEX and config.GCP_PROJECT:
    try:  # pragma: no cover - depends on cloud env
        import vertexai
        from vertexai.generative_models import GenerativeModel

        vertexai.init(project=config.GCP_PROJECT, location=config.GCP_REGION)
        _gemini = GenerativeModel(config.GEMINI_MODEL)
        _VERTEX_READY = True
    except Exception as exc:  # noqa: BLE001 - never let init crash the app
        print(f"[vertex] Vertex init failed, using fallback stubs: {exc}")


def vertex_available() -> bool:
    return _VERTEX_READY


# =========================================================================
# GEMINI — general reasoning + final user-facing explanations
# =========================================================================
def gemini_json(prompt: str) -> dict:
    """Call Gemini expecting a JSON object back; fall back to {} on any issue."""
    if _VERTEX_READY:
        try:  # pragma: no cover
            resp = _gemini.generate_content(prompt)
            return _extract_json(resp.text)
        except Exception as exc:  # noqa: BLE001
            print(f"[vertex] gemini_json failed, fallback: {exc}")
    return {}


def gemini_text(prompt: str, fallback: str = "") -> str:
    """Call Gemini expecting free text; return `fallback` if unavailable."""
    if _VERTEX_READY:
        try:  # pragma: no cover
            return _gemini.generate_content(prompt).text.strip()
        except Exception as exc:  # noqa: BLE001
            print(f"[vertex] gemini_text failed, fallback: {exc}")
    return fallback


# =========================================================================
# MEDGEMMA — clinical extraction (Model Garden endpoint)
# =========================================================================
def medgemma_extract(document_text: str) -> dict:
    """Extract survey fields from a report. Returns {} when unavailable so the
    caller can fall back to a rule-based extractor."""
    if _VERTEX_READY and config.MEDGEMMA_ENDPOINT:
        try:  # pragma: no cover - requires a deployed endpoint
            from vertexai.preview.generative_models import GenerativeModel as GM

            # Dedicated Model Garden endpoint: build the full resource path so the
            # bare numeric endpoint id resolves in its own region (europe-west4).
            endpoint = config.MEDGEMMA_ENDPOINT
            if config.GCP_PROJECT and "/" not in endpoint:
                endpoint = (f"projects/{config.GCP_PROJECT}/locations/"
                            f"{config.MEDGEMMA_LOCATION}/endpoints/{endpoint}")
            model = GM(endpoint)
            prompt = (
                "Extract structured fields from this health report as JSON only "
                "(age, height_cm, weight_kg, blood_type, family_history, lifestyle, "
                "medications_allergies, symptoms). Omit fields not present.\n\n"
                f"{document_text}"
            )
            return _extract_json(model.generate_content(prompt).text)
        except Exception as exc:  # noqa: BLE001
            print(f"[vertex] medgemma_extract failed, fallback: {exc}")
    return {}


# =========================================================================
# Health probe — is Vertex (Gemini + MedGemma) actually reachable?
# =========================================================================
def _medgemma_endpoint_path() -> str:
    endpoint = config.MEDGEMMA_ENDPOINT
    if config.GCP_PROJECT and "/" not in endpoint:
        return (f"projects/{config.GCP_PROJECT}/locations/"
                f"{config.MEDGEMMA_LOCATION}/endpoints/{endpoint}")
    return endpoint


def probe() -> dict:
    """Live health check for the Vertex integration. Unlike the normal call
    wrappers (which swallow errors and fall back), this surfaces the real
    status/error so /health/vertex can report available vs unavailable."""
    result = {
        "use_vertex": config.USE_VERTEX,
        "sdk_initialized": _VERTEX_READY,
        "gcp_project": config.GCP_PROJECT or None,
        "gcp_region": config.GCP_REGION,
        "gemini_model": config.GEMINI_MODEL,
        "medgemma_endpoint": config.MEDGEMMA_ENDPOINT or None,
        "medgemma_location": config.MEDGEMMA_LOCATION,
        "gemini": {"ok": False, "detail": "not attempted"},
        "medgemma": {"ok": False, "detail": "not attempted"},
        "available": False,
    }

    if not _VERTEX_READY:
        reason = ("USE_VERTEX is false - set USE_VERTEX=true + GCP_PROJECT and run "
                  "with Google credentials to enable live Vertex calls."
                  if not config.USE_VERTEX
                  else "Vertex SDK/credentials failed to initialise (see server logs).")
        result["gemini"]["detail"] = reason
        result["medgemma"]["detail"] = reason
        return result

    # --- Gemini probe ---
    try:  # pragma: no cover - requires cloud env
        _gemini.generate_content("ping")
        result["gemini"] = {"ok": True, "detail": "responded"}
    except Exception as exc:  # noqa: BLE001
        result["gemini"] = {"ok": False, "detail": str(exc)[:400]}

    # --- MedGemma probe (the dedicated Model Garden endpoint) ---
    if not config.MEDGEMMA_ENDPOINT:
        result["medgemma"] = {"ok": False, "detail": "MEDGEMMA_ENDPOINT not set"}
    elif not config.GCP_PROJECT:
        result["medgemma"] = {"ok": False,
                              "detail": "GCP_PROJECT not set — cannot resolve the endpoint path"}
    else:
        try:  # pragma: no cover - requires a deployed endpoint
            from vertexai.preview.generative_models import GenerativeModel as GM

            model = GM(_medgemma_endpoint_path())
            model.generate_content("Extract fields as JSON. Age: 40")
            result["medgemma"] = {"ok": True, "detail": "responded",
                                  "endpoint_path": _medgemma_endpoint_path()}
        except Exception as exc:  # noqa: BLE001
            result["medgemma"] = {"ok": False, "detail": str(exc)[:400],
                                  "endpoint_path": _medgemma_endpoint_path()}

    result["available"] = bool(result["medgemma"].get("ok"))
    return result


# =========================================================================
# helpers
# =========================================================================
def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model response robustly."""
    if not text:
        return {}
    # strip ```json fences if present
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {}

"""Central configuration, read from environment variables (spec §12).

Nothing here hard-codes secrets. In Cloud Run these come from the service
env / Secret Manager; locally they come from your shell or a .env you export.
"""
import os


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


# --- Database -------------------------------------------------------------
# Standard libpq URL, e.g.:
#   postgresql://user:pass@host:5432/bupa
# On Cloud Run + Cloud SQL use the unix socket form:
#   postgresql://user:pass@/bupa?host=/cloudsql/PROJECT:REGION:INSTANCE
DATABASE_URL = os.getenv("DATABASE_URL", "")

# --- Vertex AI (Gemini + MedGemma) ---------------------------------------
# If USE_VERTEX is false or the SDK/credentials are missing, the app falls back
# to deterministic stub logic so the demo still runs. This is intentional.
USE_VERTEX = _bool("USE_VERTEX", False)
GCP_PROJECT = os.getenv("GCP_PROJECT", "")
GCP_REGION = os.getenv("GCP_REGION", "europe-west2")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
# MedGemma is deployed as a DEDICATED Vertex endpoint via Model Garden.
# From "new endpoint details.txt": endpoint_id 9112415920449388544 in europe-west4.
# (This can live in a different region than Gemini/GCP_REGION.)
MEDGEMMA_ENDPOINT = os.getenv("MEDGEMMA_ENDPOINT", "9112415920449388544")
MEDGEMMA_LOCATION = os.getenv("MEDGEMMA_LOCATION", "europe-west4")

# --- Cloud Storage (uploaded reports) ------------------------------------
UPLOAD_BUCKET = os.getenv("UPLOAD_BUCKET", "")   # e.g. bupa-demo-uploads

# --- Pub/Sub (Trigger/Action fan-out) ------------------------------------
PUBSUB_TOPIC = os.getenv("PUBSUB_TOPIC", "")     # e.g. bupa-notifications

# --- App ------------------------------------------------------------------
SENIOR_AGE_THRESHOLD = int(os.getenv("SENIOR_AGE_THRESHOLD", "65"))
ASSESSMENT_OVERDUE_MONTHS = int(os.getenv("ASSESSMENT_OVERDUE_MONTHS", "12"))
GUARDRAIL_MIN_CONFIDENCE = float(os.getenv("GUARDRAIL_MIN_CONFIDENCE", "0.6"))

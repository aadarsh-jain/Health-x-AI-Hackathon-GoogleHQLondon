#!/usr/bin/env bash
# One-shot deploy for the hackathon sandbox (spec §11). Run from Cloud Shell.
# Prereqs: gcloud is authed to the @gcplab.me project; APIs enabled.
set -euo pipefail

# ---- config (edit these) --------------------------------------------------
PROJECT="${GCP_PROJECT:-$(gcloud config get-value project)}"
REGION="${GCP_REGION:-europe-west2}"
SERVICE="bupa-preventive-assistant"
SQL_INSTANCE="${SQL_INSTANCE:-bupa-sql}"          # Cloud SQL instance name
DB_NAME="${DB_NAME:-bupa}"
DB_USER="${DB_USER:-bupa_app}"
UPLOAD_BUCKET="${UPLOAD_BUCKET:-${PROJECT}-bupa-uploads}"
PUBSUB_TOPIC="${PUBSUB_TOPIC:-bupa-notifications}"

echo "Project: $PROJECT  Region: $REGION"

# ---- 1. enable APIs -------------------------------------------------------
gcloud services enable run.googleapis.com sqladmin.googleapis.com \
  aiplatform.googleapis.com cloudscheduler.googleapis.com pubsub.googleapis.com \
  storage.googleapis.com --project "$PROJECT"

# ---- 2. storage bucket + pubsub topic ------------------------------------
gcloud storage buckets create "gs://$UPLOAD_BUCKET" --location="$REGION" --project "$PROJECT" || true
gcloud pubsub topics create "$PUBSUB_TOPIC" --project "$PROJECT" || true

# ---- 3. build + deploy the API to Cloud Run ------------------------------
# (Run schema.sql + seed.sql against Cloud SQL first — see README.)
CONNNAME="$(gcloud sql instances describe "$SQL_INSTANCE" --project "$PROJECT" \
  --format='value(connectionName)')"

gcloud run deploy "$SERVICE" \
  --source ./api \
  --region "$REGION" \
  --allow-unauthenticated \
  --add-cloudsql-instances "$CONNNAME" \
  --set-env-vars "GCP_PROJECT=$PROJECT,GCP_REGION=$REGION,USE_VERTEX=true,MEDGEMMA_ENDPOINT=${MEDGEMMA_ENDPOINT:-9112415920449388544},MEDGEMMA_LOCATION=${MEDGEMMA_LOCATION:-europe-west4},UPLOAD_BUCKET=$UPLOAD_BUCKET,PUBSUB_TOPIC=$PUBSUB_TOPIC,DATABASE_URL=postgresql://$DB_USER:PASSWORD@/$DB_NAME?host=/cloudsql/$CONNNAME" \
  --project "$PROJECT"

RUN_URL="$(gcloud run services describe "$SERVICE" --region "$REGION" \
  --project "$PROJECT" --format='value(status.url)')"
echo "Cloud Run URL: $RUN_URL"

# ---- 4. Cloud Scheduler daily trigger ------------------------------------
gcloud scheduler jobs create http bupa-daily-trigger-check \
  --location "$REGION" \
  --schedule "0 8 * * *" \
  --time-zone "Europe/London" \
  --uri "$RUN_URL/internal/trigger-check" \
  --http-method POST \
  --project "$PROJECT" || \
gcloud scheduler jobs update http bupa-daily-trigger-check \
  --location "$REGION" --uri "$RUN_URL/internal/trigger-check" --project "$PROJECT"

# ---- 5. front end (Firebase Hosting) -------------------------------------
# Set API_BASE in web/config.js to $RUN_URL, then:
#   firebase deploy --only hosting
echo "Now set web/config.js API_BASE to: $RUN_URL  then run: firebase deploy --only hosting"

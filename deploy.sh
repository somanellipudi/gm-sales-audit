#!/usr/bin/env bash

# MonkAudit Cloud Run deploy template.
# Edit every YOUR_* placeholder before running.

set -euo pipefail

PROJECT_ID="YOUR_PROJECT_ID"
REGION="asia-south1"
SERVICE_NAME="monkaudit"
SERVICE_ACCOUNT="monkaudit-runner@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud config set project "${PROJECT_ID}"
gcloud config set run/region "${REGION}"

gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --region "${REGION}" \
  --service-account "${SERVICE_ACCOUNT}" \
  --allow-unauthenticated \
  --set-env-vars APP_PASSWORD="YOUR_STRONG_APP_PASSWORD" \
  --set-env-vars GOOGLE_CLOUD_PROJECT="${PROJECT_ID}" \
  --set-env-vars GOOGLE_CLOUD_LOCATION="asia-south1" \
  --set-env-vars GEMINI_MODEL="gemini-1.5-flash" \
  --set-env-vars GOOGLE_MAPS_API_KEY="YOUR_GOOGLE_MAPS_API_KEY" \
  --set-env-vars PAGESPEED_API_KEY="YOUR_PAGESPEED_API_KEY" \
  --set-env-vars SERPAPI_API_KEY="" \
  --set-env-vars GA4_PROPERTY_ID="" \
  --set-env-vars SEARCH_CONSOLE_SITE_URL=""

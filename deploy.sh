#!/usr/bin/env bash
# ============================================================================
# AegisOps → Cloud Run deploy.
#
# Builds the single-container image from docker/Dockerfile with Cloud Build
# (no local Docker daemon needed), pushes it to Artifact Registry, then deploys
# it to Cloud Run. Runtime secrets (GEMINI_API_KEY / GEMINI_MODEL /
# SLACK_WEBHOOK_URL) are read from your local .env and injected as env vars at
# deploy time — they are NEVER baked into the image.
#
# First-time usage:
#   1. Install the gcloud CLI:  https://cloud.google.com/sdk/docs/install
#   2. gcloud auth login
#   3. gcloud config set project <YOUR_PROJECT_ID>
#   4. Make sure .env has a valid GEMINI_API_KEY (copy .env.example → .env)
#   5. ./deploy.sh
# ============================================================================
set -euo pipefail

# --- Tunables (override via environment) ------------------------------------
SERVICE="${SERVICE:-aegisops}"          # Cloud Run service name
REGION="${REGION:-us-central1}"         # deploy + Artifact Registry region
REPO="${REPO:-aegisops}"                # Artifact Registry repository name
# ----------------------------------------------------------------------------

# Run from the repo root regardless of where the script is invoked from, so the
# Docker build context (the repo root, as docker/Dockerfile expects) is correct.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- Load secrets from .env (never committed, never baked into the image) ----
if [[ ! -f .env ]]; then
  echo "✗ .env not found. Copy .env.example to .env and set GEMINI_API_KEY." >&2
  exit 1
fi
set -a                      # export every KEY=VALUE we source
# shellcheck disable=SC1091
source .env
set +a

# --- Validate required config ------------------------------------------------
if [[ -z "${GEMINI_API_KEY:-}" || "$GEMINI_API_KEY" == *"paste_your"* ]]; then
  echo "✗ GEMINI_API_KEY is missing or still the placeholder in .env." >&2
  exit 1
fi
GEMINI_MODEL="${GEMINI_MODEL:-gemini-3.5-flash}"

PROJECT="$(gcloud config get-value project 2>/dev/null)"
if [[ -z "$PROJECT" || "$PROJECT" == "(unset)" ]]; then
  echo "✗ No gcloud project set.  gcloud config set project <PROJECT_ID>" >&2
  exit 1
fi

IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/${SERVICE}:latest"

echo "▶ Project=${PROJECT}  Region=${REGION}  Image=${IMAGE}"

# --- One-time-ish prerequisites (all idempotent) -----------------------------
# Enable the APIs the build + deploy need.
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com

# Create the Artifact Registry repo if it doesn't exist yet.
if ! gcloud artifacts repositories describe "$REPO" --location "$REGION" >/dev/null 2>&1; then
  echo "▶ Creating Artifact Registry repo '${REPO}' in ${REGION}"
  gcloud artifacts repositories create "$REPO" \
    --repository-format=docker --location="$REGION" \
    --description="AegisOps container images"
fi

# --- Build the image from docker/Dockerfile via Cloud Build ------------------
# Cloud Build's --tag looks for a root Dockerfile, so we drive it with an inline
# config that points at docker/Dockerfile. The whole repo root is the context.
CLOUDBUILD_CFG="$(mktemp)"
trap 'rm -f "$CLOUDBUILD_CFG"' EXIT
cat > "$CLOUDBUILD_CFG" <<YAML
steps:
  - name: gcr.io/cloud-builders/docker
    args: ["build", "-f", "docker/Dockerfile", "-t", "${IMAGE}", "."]
images: ["${IMAGE}"]
YAML

echo "▶ Building image with Cloud Build…"
gcloud builds submit --config "$CLOUDBUILD_CFG" .

# --- Assemble runtime env vars ----------------------------------------------
# '^@^' changes the delimiter so a webhook URL containing commas stays intact.
ENV_VARS="GEMINI_API_KEY=${GEMINI_API_KEY}@GEMINI_MODEL=${GEMINI_MODEL}"
if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
  ENV_VARS="${ENV_VARS}@SLACK_WEBHOOK_URL=${SLACK_WEBHOOK_URL}"
fi

# --- Deploy to Cloud Run -----------------------------------------------------
# --allow-unauthenticated makes the war room publicly reachable (demo).
# --port 8080 matches the container's uvicorn port.
echo "▶ Deploying '${SERVICE}' to Cloud Run…"
gcloud run deploy "$SERVICE" \
  --image "$IMAGE" \
  --region "$REGION" \
  --allow-unauthenticated \
  --port 8080 \
  --set-env-vars "^@^${ENV_VARS}"

# --- Report ------------------------------------------------------------------
URL="$(gcloud run services describe "$SERVICE" --region "$REGION" \
        --format='value(status.url)')"
echo "✓ Deployed."
echo "  War room:      ${URL}"
echo "  Health check:  ${URL}/api/health"
echo
echo "Fire the demo against the live service:"
echo "  python scripts/publish_alert.py --url ${URL}"

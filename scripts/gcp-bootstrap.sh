#!/usr/bin/env bash
# Idempotent one-time GCP setup for the bchat K8s migration.
# Run once per environment (staging, prod) BEFORE the first cluster provisioning.
#
# Creates:
#   - Required APIs
#   - Artifact Registry repos (bchat, ms365-mcp)
#   - GCP Service Account `bchat-app-<env>` with IAM roles
#   - Workload Identity binding (KSA `default:bchat-app` <-> GSA)
#   - Static external IP for Gateway
#
# Usage:
#   ENV=staging  scripts/gcp-bootstrap.sh
#   ENV=prod     scripts/gcp-bootstrap.sh
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-beyond-chat-1111}"
REGION="${REGION:-europe-west3}"
ENV="${ENV:?ENV is required: staging or prod}"

GSA="bchat-app-${ENV}"
GSA_EMAIL="${GSA}@${PROJECT_ID}.iam.gserviceaccount.com"
KSA_NAMESPACE="${ENV}"
KSA_NAME="bchat-app"

AR_LOCATION="$REGION"
AR_REPO="bchat"
AR_REPO_MCP="ms365-mcp"

INGRESS_IP_NAME="bchat-${ENV}-ingress-ip"

echo "==> Project: $PROJECT_ID  Env: $ENV  Region: $REGION"

echo "==> Enabling required APIs"
gcloud --project "$PROJECT_ID" services enable \
  container.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  compute.googleapis.com \
  --quiet

echo "==> Creating Artifact Registry repos (idempotent)"
for repo in "$AR_REPO" "$AR_REPO_MCP"; do
  if ! gcloud --project "$PROJECT_ID" artifacts repositories describe "$repo" --location="$AR_LOCATION" >/dev/null 2>&1; then
    gcloud --project "$PROJECT_ID" artifacts repositories create "$repo" \
      --repository-format=docker \
      --location="$AR_LOCATION" \
      --description="bchat container images" \
      --quiet
    echo "    created repo: $repo"
  else
    echo "    repo exists: $repo"
  fi
done

echo "==> Creating GSA $GSA_EMAIL"
if ! gcloud --project "$PROJECT_ID" iam service-accounts describe "$GSA_EMAIL" >/dev/null 2>&1; then
  gcloud --project "$PROJECT_ID" iam service-accounts create "$GSA" \
    --display-name="bchat app (${ENV})" \
    --quiet
else
  echo "    GSA exists"
fi

echo "==> Granting IAM roles to GSA"
for role in \
  roles/storage.objectAdmin \
  roles/cloudsql.client \
  roles/aiplatform.user \
  roles/secretmanager.secretAccessor \
  roles/logging.logWriter \
  roles/monitoring.metricWriter \
  roles/cloudtrace.agent \
; do
  gcloud --project "$PROJECT_ID" projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${GSA_EMAIL}" \
    --role="$role" \
    --condition=None \
    --quiet >/dev/null
  echo "    + $role"
done

echo "==> Binding Workload Identity (KSA $KSA_NAMESPACE/$KSA_NAME -> GSA)"
gcloud --project "$PROJECT_ID" iam service-accounts add-iam-policy-binding "$GSA_EMAIL" \
  --role="roles/iam.workloadIdentityUser" \
  --member="serviceAccount:${PROJECT_ID}.svc.id.goog[${KSA_NAMESPACE}/${KSA_NAME}]" \
  --quiet >/dev/null

echo "==> Reserving global static IP for Gateway: $INGRESS_IP_NAME"
if ! gcloud --project "$PROJECT_ID" compute addresses describe "$INGRESS_IP_NAME" --global >/dev/null 2>&1; then
  gcloud --project "$PROJECT_ID" compute addresses create "$INGRESS_IP_NAME" \
    --global --ip-version=IPV4 \
    --quiet
fi
IP=$(gcloud --project "$PROJECT_ID" compute addresses describe "$INGRESS_IP_NAME" --global --format='value(address)')
echo "    IP: $IP"

echo
echo "==> Done. Next steps:"
echo "    1. Migrate secrets: ENV=$ENV ENV_FILE=<path to env file> scripts/migrate-secrets-to-gcp.sh"
echo "    2. Build & push image: ENV=$ENV scripts/build-and-push-image.sh"
echo "    3. Create cluster:    ENV=$ENV scripts/create-gke-cluster.sh"
echo "    4. Deploy via Helm:   ENV=$ENV scripts/deploy.sh"
echo
echo "    Gateway static IP ($INGRESS_IP_NAME): $IP"
echo "    DNS for ${ENV}: point chat hostname A-record to this IP after cutover."

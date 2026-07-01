#!/usr/bin/env bash
# Create a GKE Autopilot cluster for bchat.
# Idempotent: skips if cluster already exists.
#
# Usage:
#   ENV=staging scripts/create-gke-cluster.sh
#   ENV=prod    scripts/create-gke-cluster.sh
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-beyond-chat-1111}"
REGION="${REGION:-europe-west3}"
ENV="${ENV:?ENV is required: staging or prod}"
CLUSTER_NAME="gke-${ENV}"
NETWORK="${NETWORK:-default}"
SUBNETWORK="${SUBNETWORK:-default}"

echo "==> Creating Autopilot cluster $CLUSTER_NAME in $REGION (project $PROJECT_ID)"

if gcloud --project "$PROJECT_ID" container clusters describe "$CLUSTER_NAME" --region "$REGION" >/dev/null 2>&1; then
  echo "    cluster exists; skipping create"
else
  # Note: Autopilot enables Workload Identity by default; --workload-pool is not accepted here.
  gcloud --project "$PROJECT_ID" container clusters create-auto "$CLUSTER_NAME" \
    --region "$REGION" \
    --network "$NETWORK" \
    --subnetwork "$SUBNETWORK" \
    --release-channel regular \
    --quiet
fi

echo "==> Fetching credentials"
gcloud --project "$PROJECT_ID" container clusters get-credentials "$CLUSTER_NAME" --region "$REGION" --quiet

echo "==> Creating namespace $ENV (idempotent)"
kubectl create namespace "$ENV" --dry-run=client -o yaml | kubectl apply -f -

echo "==> Done. Next: install External Secrets Operator and deploy."
echo "    scripts/install-cluster-addons.sh ENV=$ENV"

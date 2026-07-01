#!/usr/bin/env bash
# Deploy the bchat Helm chart to a GKE cluster.
#
# Usage:
#   ENV=staging IMAGE_TAG=<sha> scripts/deploy.sh
#   ENV=prod    IMAGE_TAG=<sha> scripts/deploy.sh
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-beyond-chat-1111}"
REGION="${REGION:-europe-west3}"
ENV="${ENV:?ENV is required}"
IMAGE_TAG="${IMAGE_TAG:?IMAGE_TAG is required (git short sha)}"
CLUSTER_NAME="gke-${ENV}"

# Ensure kubectl context
gcloud --project "$PROJECT_ID" container clusters get-credentials "$CLUSTER_NAME" --region "$REGION" --quiet

REPO_DIR=$(cd "$(dirname "$0")/.." && pwd)

LITELLM_CONFIG_PATH="${REPO_DIR}/litellm-config.yaml"
ARENA_RANKINGS_PATH="${REPO_DIR}/arena_rankings.json"
CHART_PATH="${REPO_DIR}/helm/bchat"
VALUES_BASE="${CHART_PATH}/values.yaml"
VALUES_ENV="${CHART_PATH}/values.${ENV}.yaml"

PROJECT_NUMBER=$(gcloud --project "$PROJECT_ID" projects describe "$PROJECT_ID" --format='value(projectNumber)')

helm upgrade --install bchat "$CHART_PATH" \
  --namespace "$ENV" \
  --create-namespace \
  --values "$VALUES_BASE" \
  --values "$VALUES_ENV" \
  --set image.tag="$IMAGE_TAG" \
  --set mcpImage.tag="$IMAGE_TAG" \
  --set gcp.projectNumber="$PROJECT_NUMBER" \
  --set-file litellmConfig="$LITELLM_CONFIG_PATH" \
  --set-file arenaRankings="$ARENA_RANKINGS_PATH" \
  --timeout 10m

echo
echo "==> Rollout status"
kubectl -n "$ENV" rollout status deployment/app --timeout=5m
kubectl -n "$ENV" rollout status deployment/litellm --timeout=3m
kubectl -n "$ENV" rollout status deployment/ms365-mcp --timeout=3m

echo
echo "==> Resources"
kubectl -n "$ENV" get pods,svc,gateway,httproute

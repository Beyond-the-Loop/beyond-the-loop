#!/usr/bin/env bash
# Build the bchat app image and push to Artifact Registry.
# Tags: <git sha> and <env>-latest.
#
# Usage:
#   ENV=staging scripts/build-and-push-image.sh
#   ENV=prod    scripts/build-and-push-image.sh
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-beyond-chat-1111}"
REGION="${REGION:-europe-west3}"
ENV="${ENV:?ENV is required}"

REPO_HOST="${REGION}-docker.pkg.dev"
IMAGE="${REPO_HOST}/${PROJECT_ID}/bchat/app"
MCP_IMAGE="${REPO_HOST}/${PROJECT_ID}/bchat/ms365-mcp"

SHA=$(git rev-parse --short=12 HEAD)
echo "==> Building $IMAGE:$SHA  and  $IMAGE:${ENV}-latest"

gcloud --project "$PROJECT_ID" auth configure-docker "$REPO_HOST" --quiet >/dev/null

docker buildx build \
  --platform linux/amd64 \
  --build-arg BUILD_HASH="$SHA" \
  --build-arg LITELLM_BASE_URL=/litellm \
  -t "${IMAGE}:${SHA}" \
  -t "${IMAGE}:${ENV}-latest" \
  --push \
  .

echo "==> Building MCP image"
docker buildx build \
  --platform linux/amd64 \
  -f ms365-mcp.Dockerfile \
  -t "${MCP_IMAGE}:${SHA}" \
  -t "${MCP_IMAGE}:${ENV}-latest" \
  --push \
  .

echo
echo "==> Pushed:"
echo "    app:        ${IMAGE}:${SHA}"
echo "    ms365-mcp:  ${MCP_IMAGE}:${SHA}"
echo
echo "Set IMAGE_TAG=${SHA} for the deploy step."

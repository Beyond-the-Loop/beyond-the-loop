#!/usr/bin/env bash
# Migrate secrets from a local .env file to GCP Secret Manager.
#
# Each KEY=value line becomes the secret `bchat-<env>-<KEY>` in Secret Manager.
# Idempotent: existing secrets get a new version, new ones are created.
#
# Usage:
#   ENV=staging  ENV_FILE=.env.staging  scripts/migrate-secrets-to-gcp.sh
#   ENV=prod     ENV_FILE=.env.prod     scripts/migrate-secrets-to-gcp.sh
#
# Or with a dry-run (only prints what would happen):
#   DRY_RUN=1 ENV=staging ENV_FILE=.env scripts/migrate-secrets-to-gcp.sh
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-beyond-chat-1111}"
ENV="${ENV:?ENV is required: staging or prod}"
ENV_FILE="${ENV_FILE:?ENV_FILE is required, e.g. .env.staging}"
DRY_RUN="${DRY_RUN:-0}"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: $ENV_FILE not found." >&2
  exit 1
fi

if ! command -v gcloud >/dev/null 2>&1; then
  echo "ERROR: gcloud not installed." >&2
  exit 1
fi

PREFIX="bchat-${ENV}-"

echo "Project:      $PROJECT_ID"
echo "Env:          $ENV"
echo "File:         $ENV_FILE"
echo "Secret prefix: $PREFIX"
echo "Dry-run:      $DRY_RUN"
echo

# Enable Secret Manager API if not already
if [ "$DRY_RUN" = "0" ]; then
  gcloud --project "$PROJECT_ID" services enable secretmanager.googleapis.com --quiet
fi

created=0
updated=0
skipped=0

while IFS= read -r line || [ -n "$line" ]; do
  # Strip carriage returns from CRLF files
  line="${line%$'\r'}"
  # Ignore blank lines and comments
  [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
  # Must be KEY=value (KEY uppercase letters, digits, underscore)
  if [[ ! "$line" =~ ^[A-Z_][A-Z0-9_]*= ]]; then
    skipped=$((skipped + 1))
    continue
  fi

  key="${line%%=*}"
  value="${line#*=}"
  # Strip surrounding double or single quotes
  if [[ "$value" =~ ^\".*\"$ ]]; then value="${value:1:${#value}-2}"; fi
  if [[ "$value" =~ ^\'.*\'$ ]]; then value="${value:1:${#value}-2}"; fi

  secret_name="${PREFIX}${key}"

  if [ "$DRY_RUN" = "1" ]; then
    echo "would write: $secret_name (length=${#value})"
    continue
  fi

  if gcloud --project "$PROJECT_ID" secrets describe "$secret_name" >/dev/null 2>&1; then
    printf "%s" "$value" | gcloud --project "$PROJECT_ID" secrets versions add "$secret_name" --data-file=- --quiet >/dev/null
    updated=$((updated + 1))
    echo "updated:  $secret_name"
  else
    printf "%s" "$value" | gcloud --project "$PROJECT_ID" secrets create "$secret_name" \
      --replication-policy=automatic --data-file=- --quiet >/dev/null
    created=$((created + 1))
    echo "created:  $secret_name"
  fi
done < "$ENV_FILE"

echo
echo "Done. created=$created updated=$updated skipped=$skipped"

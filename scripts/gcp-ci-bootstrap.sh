#!/usr/bin/env bash
# One-time GCP setup for the GitHub Actions CI that pushes images and deploys to GKE.
# Creates:
#   - GSA `github-ci@<project>.iam.gserviceaccount.com` with roles:
#       - roles/artifactregistry.writer (push images)
#       - roles/container.developer     (get-credentials + kubectl on GKE)
#   - Workload Identity Pool `github-pool` + OIDC Provider `github-provider`
#   - Impersonation binding so the GitHub repo can mint tokens for the GSA
#   - Two GitHub repo secrets: GCP_CI_SERVICE_ACCOUNT, GCP_WIF_PROVIDER
#
# Requirements:
#   - gcloud auth login (user must have iam.workloadIdentityPoolAdmin + iam.serviceAccountAdmin
#     + resourcemanager.projectIamAdmin on the project)
#   - gh auth login (user must be admin on the repo)
#
# Idempotent-ish: safe to re-run; existing resources will produce ALREADY_EXISTS which the
# `|| true` guards swallow.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-beyond-chat-1111}"
GH_REPO="${GH_REPO:-Beyond-the-Loop/beyond-the-loop}"
CI_SA="${CI_SA:-github-ci}"
POOL="${POOL:-github-pool}"
PROVIDER="${PROVIDER:-github-provider}"

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
CI_SA_EMAIL="${CI_SA}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "==> 1. Service Account anlegen"
gcloud --project "$PROJECT_ID" iam service-accounts create "$CI_SA" \
  --display-name="GitHub Actions CI" || echo "    (existiert schon)"

echo "==> 2. Rollen granten"
for role in roles/artifactregistry.writer roles/container.developer; do
  gcloud --project "$PROJECT_ID" projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${CI_SA_EMAIL}" \
    --role="$role" --condition=None >/dev/null
  echo "    + $role"
done

echo "==> 3. WIF Pool anlegen"
gcloud --project "$PROJECT_ID" iam workload-identity-pools create "$POOL" \
  --location=global --display-name="GitHub Actions" || echo "    (existiert schon)"

echo "==> 4. WIF Provider anlegen"
gcloud --project "$PROJECT_ID" iam workload-identity-pools providers create-oidc "$PROVIDER" \
  --location=global --workload-identity-pool="$POOL" \
  --display-name="GitHub OIDC" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
  --attribute-condition="assertion.repository=='${GH_REPO}'" \
  || echo "    (existiert schon)"

echo "==> 5. Impersonation binding"
gcloud --project "$PROJECT_ID" iam service-accounts add-iam-policy-binding "$CI_SA_EMAIL" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/attribute.repository/${GH_REPO}" >/dev/null
echo "    bound"

WIF_PROVIDER="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/providers/${PROVIDER}"

echo "==> 6. GitHub Secrets setzen"
gh secret set GCP_CI_SERVICE_ACCOUNT --repo "$GH_REPO" --body "$CI_SA_EMAIL"
gh secret set GCP_WIF_PROVIDER       --repo "$GH_REPO" --body "$WIF_PROVIDER"

echo
echo "==> Fertig."
echo "  GCP_CI_SERVICE_ACCOUNT = $CI_SA_EMAIL"
echo "  GCP_WIF_PROVIDER       = $WIF_PROVIDER"

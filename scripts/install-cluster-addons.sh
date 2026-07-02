#!/usr/bin/env bash
# Install cluster-scoped add-ons after creating a GKE cluster:
#   - External Secrets Operator (via Helm chart)
#   - ClusterSecretStore pointing to GCP Secret Manager (via Workload Identity)
#
# Re-runnable: upgrades ESO if already installed.
#
# Usage:
#   ENV=staging scripts/install-cluster-addons.sh
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-beyond-chat-1111}"
ENV="${ENV:?ENV is required}"

GSA_EMAIL="bchat-app-${ENV}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "==> Installing External Secrets Operator"
helm repo add external-secrets https://charts.external-secrets.io >/dev/null
helm repo update >/dev/null

helm upgrade --install external-secrets external-secrets/external-secrets \
  --namespace external-secrets \
  --create-namespace \
  --set installCRDs=true \
  --version 0.10.5 \
  --wait

echo "==> Waiting for ESO to be ready"
kubectl -n external-secrets rollout status deployment/external-secrets --timeout=180s
kubectl -n external-secrets rollout status deployment/external-secrets-webhook --timeout=180s

echo "==> Creating ClusterSecretStore"
cat <<EOF | kubectl apply -f -
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: gcp-secret-manager
spec:
  provider:
    gcpsm:
      projectID: ${PROJECT_ID}
      auth:
        workloadIdentity:
          clusterLocation: europe-west3
          clusterName: gke-${ENV}
          serviceAccountRef:
            name: bchat-app
            namespace: ${ENV}
EOF

echo "==> Done."

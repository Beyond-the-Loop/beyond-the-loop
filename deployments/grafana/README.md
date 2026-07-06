# Grafana Cloud setup

This directory contains dashboard JSONs and a one-time setup runbook for the
Grafana Cloud Free instance that reads from GCP Managed Prometheus.

## One-time GCP + Grafana Cloud setup

1. Create a read-only service account in GCP:

   ```bash
   gcloud iam service-accounts create grafana-cloud-reader \
     --project=beyond-chat-1111 \
     --display-name="Grafana Cloud read-only"

   gcloud projects add-iam-policy-binding beyond-chat-1111 \
     --member="serviceAccount:grafana-cloud-reader@beyond-chat-1111.iam.gserviceaccount.com" \
     --role="roles/monitoring.viewer"

   gcloud iam service-accounts keys create /tmp/grafana-cloud-reader.json \
     --iam-account="grafana-cloud-reader@beyond-chat-1111.iam.gserviceaccount.com"
   ```

2. In Grafana Cloud (https://grafana.com/orgs/<your-org>), go to Connections
   → Data sources → Add new data source → **"Prometheus"**.

   IMPORTANT: pick "Prometheus", NOT "Google Cloud Monitoring". The Google
   Cloud Monitoring data source speaks MQL by default and won't run the
   PromQL queries (`expr: sum(rate(...))`) our dashboard JSONs use. GMP
   exposes a PromQL-compatible frontend that the standard Prometheus data
   source queries directly.

3. **Prometheus server URL:**

   ```
   https://monitoring.googleapis.com/v1/projects/beyond-chat-1111/location/global/prometheus
   ```

4. Under the Authentication section, enable **"Google Auth"** and upload
   `/tmp/grafana-cloud-reader.json` as the Service Account credentials.
   The Google Auth toggle sits under HTTP/Auth headers in the Prometheus
   data source config on Grafana Cloud (Grafana 10+).

5. Click "Save & test" — expect "Data source is working" with a green
   check. If you see "unable to fetch labels" instead, the Service
   Account is missing `roles/monitoring.viewer` on the project.

6. Delete the local key: `rm /tmp/grafana-cloud-reader.json`. The key is now
   stored in Grafana Cloud; there's no reason to keep a copy on disk.

7. Import the three dashboards from `deployments/grafana/dashboards/*.json`
   via Dashboards → Import → Upload JSON. When prompted for a data source,
   pick the Prometheus DS you just created.

## Block public `/metrics` at the edge (required)

The FastAPI app exposes `/metrics` unauthenticated on port 8080, which is
correct: GMP scrapes it in-cluster over the pod IP and the payload contains
only aggregated numeric telemetry. But the GCE ingress maps `/*` to the
same service, so without a Cloud Armor deny rule an unauthenticated caller
on the public internet can read the same series list — a live view of
route templates, model names, error rates, and traffic. GMP itself is
unaffected because it never traverses the ingress.

Add the rule once per environment:

```bash
# Priority 1000 keeps it above any 'allow all' catch-all. Adjust if your
# existing rules already occupy that slot — pick the lowest free priority
# below your allow rules.
gcloud compute security-policies rules create 1000 \
  --project=beyond-chat-1111 \
  --security-policy=bchat-prod-armor \
  --expression="request.path == '/metrics' || request.path.startsWith('/metrics/')" \
  --action=deny-403 \
  --description="Block public reads of the Prometheus /metrics endpoint"

# Verify:
curl -s -o /dev/null -w "%{http_code}\n" https://v2.beyondtheloop.ai/metrics
# expected: 403
```

Cloud Armor is attached to the app backend via the `BackendConfig`
`securityPolicy` field (see `helm/bchat/templates/backendconfig-app.yaml`,
enabled when `cloudArmor.policyName` is set in the values file).

## Verify LiteLLM metric names against your shipped image

The LLM dashboard references `litellm_total_tokens`, `litellm_spend_metric`,
and `litellm_deployment_failure_responses`. LiteLLM's exact metric names
drift between versions (some are suffixed `_total`, `litellm_total_tokens`
switches between Counter and Gauge across releases). After first deploy to
staging, list the real series and edit the dashboard JSONs if any don't
match:

```bash
kubectl port-forward -n default deployment/litellm 4000:4000 &
curl -s http://localhost:4000/metrics | grep -E '^# HELP litellm_' | sort
kill %1
```

## Repeat setup for a second GCP project (e.g., staging)

Repeat step 1 with the staging project ID, then add a second data source in
Grafana Cloud pointing at the staging project. Duplicate the dashboards and
switch their data source to the staging one.

## Editing dashboards

Edit them in Grafana Cloud's UI. When done, use "Share → Export → Save to
file (For sharing externally)" and overwrite the file in
`deployments/grafana/dashboards/`. Commit the JSON so the next person
imports the same view.

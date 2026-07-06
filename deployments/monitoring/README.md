# Cloud Monitoring dashboards

Backend and LiteLLM emit Prometheus metrics on a dedicated pod-local port
(`9090`) that is scraped by GKE Managed Prometheus (GMP). Metrics land in
Cloud Monitoring under `prometheus.googleapis.com/bchat_*` and
`prometheus.googleapis.com/litellm_*`.

We display them via **Cloud Monitoring native dashboards** (not Grafana).
Cloud Monitoring speaks PromQL against GMP, so the same queries you'd
write for Prometheus work verbatim, and the dashboards live in the same
GCP project as everything else.

## Why not Grafana?

Grafana Cloud requires a service account, a plugin install for GMP auth,
data source configuration, and a separate vendor bill. Cloud Monitoring
is already there, already authenticated via your `gcloud` login, and
supports the exact same PromQL. For an all-GCP shop the trade-off is
easy.

## Files

- `dashboards/cluster-health.json` — Node/pod resource usage, HPA state.
- `dashboards/app-performance.json` — HTTP throughput, latency, error
  rate, active WebSockets.
- `dashboards/llm-performance.json` — Completion latency/throughput by
  model, LiteLLM tokens and spend.

Each is a Cloud Monitoring Dashboard resource (JSON schema documented at
https://cloud.google.com/monitoring/api/ref_v3/rest/v1/projects.dashboards).

## Create / update the dashboards

```bash
for f in deployments/monitoring/dashboards/*.json; do
  gcloud monitoring dashboards create --project=beyond-chat-1111 --config-from-file="$f"
done
```

`create` errors if a dashboard with the same `displayName` already
exists — that's intentional so you don't accidentally overwrite one that
someone edited in the UI. To replace an existing dashboard, delete it
first (`gcloud monitoring dashboards list` to find the ID, then
`gcloud monitoring dashboards delete <ID>`) or use `update` with the
existing dashboard's `name` field patched in.

## Edit dashboards

Edit in the Cloud Monitoring UI (https://console.cloud.google.com/monitoring/dashboards),
then export back to JSON so the source-of-truth stays in git:

```bash
# List dashboards to find the one you edited
gcloud monitoring dashboards list --project=beyond-chat-1111 --format="table(name.basename(),displayName)"

# Export the updated JSON
gcloud monitoring dashboards describe <DASHBOARD_ID> --project=beyond-chat-1111 --format=json \
  > deployments/monitoring/dashboards/<name>.json
```

Commit the change so the next `create` reproduces the same view.

## Verify metrics are reaching Cloud Monitoring

```bash
TOKEN=$(gcloud auth print-access-token)
curl -sH "Authorization: Bearer $TOKEN" \
  "https://monitoring.googleapis.com/v3/projects/beyond-chat-1111/metricDescriptors?filter=metric.type=starts_with(%22prometheus.googleapis.com/bchat_%22)" \
  | jq -r '.metricDescriptors[].type'
```

Expected: at least the five `bchat_*` families we emit
(`bchat_http_request_duration_seconds`, `bchat_http_requests_total`,
`bchat_chat_completion_duration_seconds`, `bchat_chat_completions_total`,
`bchat_websocket_connections`).

If empty: pods aren't up yet, PodMonitoring isn't reconciled, or GMP is
not enabled on the cluster (only relevant for non-Autopilot clusters).

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
   → Data sources → Add new data source → "Google Cloud Monitoring".

3. Choose "JWT authentication", upload `/tmp/grafana-cloud-reader.json`, save.

4. Delete the local key: `rm /tmp/grafana-cloud-reader.json`. The key is now
   stored in Grafana Cloud; there's no reason to keep a copy on disk.

5. Import the three dashboards from `deployments/grafana/dashboards/*.json`
   via Dashboards → Import → Upload JSON. Select the data source you just
   created when prompted.

## Repeat setup for a second GCP project (e.g., staging)

Repeat step 1 with the staging project ID, then add a second data source in
Grafana Cloud pointing at the staging project. Duplicate the dashboards and
switch their data source to the staging one.

## Editing dashboards

Edit them in Grafana Cloud's UI. When done, use "Share → Export → Save to
file (For sharing externally)" and overwrite the file in
`deployments/grafana/dashboards/`. Commit the JSON so the next person
imports the same view.

"""HTTP client for the openai/privacy-filter inference endpoint.

The endpoint is a Cloud Run service (or Vertex AI Endpoint, both work) that
returns raw token-level predictions (entity, score, start, end per token).
BIOES decoding happens in `PrivacyFilterService`, not here.

Cloud Run with IAM auth requires an audience-bound identity token (JWT signed
for the service URL), not a generic OAuth2 access token. In production
(service account on GCE/Cloud Run), this is minted via the metadata server.
For local development with user credentials, we fall back to `gcloud auth
print-identity-token` since user-mode ADC cannot mint identity tokens.
"""
from __future__ import annotations

import logging
import os
import subprocess
import time
from typing import List, Optional
from urllib.parse import urlparse

import httpx
from google.auth.transport.requests import Request as AuthRequest
from google.oauth2 import id_token

log = logging.getLogger(__name__)

# Identity tokens are valid for ~1 hour. Refresh a bit early so we never use
# a token that's about to expire mid-request.
_TOKEN_TTL_SECONDS = 50 * 60


class PiiInferenceClient:
    def __init__(self, predict_url: str | None = None, timeout: float = 600.0) -> None:
        url = predict_url or os.environ.get("PII_INFERENCE_URL")
        if not url:
            raise RuntimeError(
                "PII_INFERENCE_URL is not set. Expected a Cloud Run service "
                "URL ending with /predict, e.g. "
                "https://privacy-filter-<hash>.europe-west4.run.app/predict"
            )
        self._url = url
        # Cloud Run audience is the base URL (scheme + host), no path.
        parsed = urlparse(url)
        self._audience = f"{parsed.scheme}://{parsed.netloc}"
        self._timeout = timeout
        self._http = httpx.Client(timeout=timeout)
        self._cached_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    def _id_token(self) -> str:
        if self._cached_token and time.time() < self._token_expires_at:
            return self._cached_token
        try:
            token = id_token.fetch_id_token(AuthRequest(), self._audience)
        except Exception as exc:
            log.debug("fetch_id_token failed (%s); falling back to gcloud", exc)
            token = subprocess.check_output(
                ["gcloud", "auth", "print-identity-token"],
                text=True,
            ).strip()
        self._cached_token = token
        self._token_expires_at = time.time() + _TOKEN_TTL_SECONDS
        return token

    def predict(self, texts: List[str]) -> List[List[dict]]:
        if not texts:
            return []

        resp = self._http.post(
            self._url,
            json={"instances": texts},
            headers={"Authorization": f"Bearer {self._id_token()}"},
        )
        resp.raise_for_status()
        return resp.json()["predictions"]

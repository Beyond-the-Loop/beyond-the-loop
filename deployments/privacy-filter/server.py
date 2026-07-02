"""Vertex AI / Cloud Run prediction server for openai/privacy-filter.

Thin GPU worker: chunks long inputs to fit the GPU memory budget, runs the
model per chunk, merges predictions back to original-text coordinates.
Returns raw BIOES token-level predictions. BIOES decoding and post-processing
happen in the backend (beyond_the_loop.pii.service).
"""
from __future__ import annotations

import logging
import os
from typing import List, Tuple

import torch
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
log = logging.getLogger("privacy-filter")

MODEL_NAME = os.environ.get("MODEL_NAME", "openai/privacy-filter")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Single chunk inference must fit in L4 GPU memory. Attention is O(N^2);
# 4000 chars (~1000 tokens) leaves comfortable headroom over the ~16GB resident
# model weights. Tune via env var if the GPU changes.
MAX_CHUNK_CHARS = int(os.environ.get("MAX_CHUNK_CHARS", "4000"))
# Overlap between consecutive chunks so entities straddling a boundary still
# get detected in at least one chunk.
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "200"))

log.info(
    "Loading %s on device=%s | max_chunk_chars=%d overlap=%d",
    MODEL_NAME, DEVICE, MAX_CHUNK_CHARS, CHUNK_OVERLAP,
)
_pipe = pipeline(
    "token-classification",
    model=MODEL_NAME,
    aggregation_strategy="none",
    device=DEVICE,
)
log.info("Model ready")

app = FastAPI()


class PredictRequest(BaseModel):
    instances: List[str]


def _chunk_text(text: str) -> List[Tuple[int, str]]:
    """Split text into chunks for sequential GPU inference.

    Returns a list of (offset_in_original_text, chunk_content).
    Chunks overlap to catch entities sitting on a boundary. Where possible
    chunk breaks are placed at whitespace to avoid splitting words.
    """
    if len(text) <= MAX_CHUNK_CHARS:
        return [(0, text)]

    chunks: List[Tuple[int, str]] = []
    pos = 0
    while pos < len(text):
        end = min(pos + MAX_CHUNK_CHARS, len(text))
        if end < len(text):
            ws = text.rfind(" ", pos + MAX_CHUNK_CHARS - 500, end)
            if ws > pos:
                end = ws
        chunks.append((pos, text[pos:end]))
        if end >= len(text):
            break
        pos = end - CHUNK_OVERLAP
    return chunks


def _process_text(text: str) -> List[dict]:
    chunks = _chunk_text(text)
    seen: set = set()
    out: List[dict] = []
    for offset, chunk in chunks:
        raw = _pipe(chunk)
        for tok in raw:
            start = int(tok["start"]) + offset
            end = int(tok["end"]) + offset
            entity = tok["entity"]
            key = (start, end, entity)
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "entity": entity,
                "score": float(tok["score"]),
                "start": start,
                "end": end,
            })
    out.sort(key=lambda p: (p["start"], p["end"]))
    return out


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/predict")
def predict(req: PredictRequest):
    if not req.instances:
        return {"predictions": []}
    return {"predictions": [_process_text(t) for t in req.instances]}

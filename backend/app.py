"""ChartProof FastAPI application."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.schemas import HealthResponse

app = FastAPI(
    title="ChartProof API",
    description=(
        "Auditor-assist clinical chart validation demo. "
        "Synthetic data only. Drafts for human review, never payment decisions."
    ),
    version="0.1.0",
)

_origins = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()

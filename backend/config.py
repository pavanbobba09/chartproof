"""Central config. Model swap is a one-line env change (CLAUDE.md)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
CASES_DIR = DATA_DIR / "cases"
KEYS_DIR = DATA_DIR / "keys"
RAW_DIR = DATA_DIR / "raw"
CRITERIA_DIR = DATA_DIR / "criteria"
GUIDELINES_DIR = DATA_DIR / "guidelines"

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_API_URL = os.environ.get(
    "GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions"
)
# Seconds between generation requests (free-tier friendly)
GROQ_SLEEP_SECONDS = float(os.environ.get("GROQ_SLEEP_SECONDS", "2.0"))
CHROMA_DIR = os.environ.get("CHROMA_DIR", str(REPO_ROOT / ".chroma"))

"""Synthetic inpatient chart generator (Groq free tier).

Contract: DATA_SPEC.md section 6.
Verdict is decided before generation. Output is validated and consistency-checked.
Raw LLM text is cached under data/raw/ so reruns do not burn rate limits.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import httpx

from backend.config import (
    CASES_DIR,
    GROQ_API_KEY,
    GROQ_API_URL,
    GROQ_MODEL,
    GROQ_SLEEP_SECONDS,
    KEYS_DIR,
    RAW_DIR,
)
from backend.schemas import AnswerKey, Case
from data.consistency import ConsistencyError, assert_consistent

Verdict = Literal["supported", "not_supported"]
Difficulty = Literal["clear", "borderline"]

MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    dx: str
    verdict: Verdict
    difficulty: Difficulty
    seed: int


def plan_specs(dx: str, n: int, start_index: int = 1) -> list[CaseSpec]:
    """Build a balanced bank plan: ~40% supported clear, 40% not_supported clear, 20% borderline."""
    if n < 1:
        return []
    specs: list[CaseSpec] = []
    for i in range(n):
        idx = start_index + i
        case_id = f"{dx}_{idx:03d}"
        # Cycle: S clear, NS clear, S clear, NS clear, borderline S, borderline NS, ...
        slot = i % 6
        if slot in (0, 2):
            verdict: Verdict = "supported"
            difficulty: Difficulty = "clear"
        elif slot in (1, 3):
            verdict = "not_supported"
            difficulty = "clear"
        elif slot == 4:
            verdict = "supported"
            difficulty = "borderline"
        else:
            verdict = "not_supported"
            difficulty = "borderline"
        specs.append(
            CaseSpec(
                case_id=case_id,
                dx=dx,
                verdict=verdict,
                difficulty=difficulty,
                seed=10_000 + idx,
            )
        )
    return specs


def _system_prompt() -> str:
    return (
        "You write 100% synthetic inpatient medical charts for an educational "
        "clinical validation demo. Never use real patient names or real MRNs. "
        "Respond with a single JSON object only. No markdown fences."
    )


def _user_prompt(spec: CaseSpec) -> str:
    against_rule = (
        "Include at least one planted_evidence item with side=against "
        "(objective data that fails organ dysfunction)."
        if spec.verdict == "not_supported"
        else "Include planted evidence for and against criteria as realistic; "
        "overall chart must support sepsis."
    )
    borderline = (
        "Borderline: exactly one organ-dysfunction finding is near threshold "
        "or narrative is slightly ambiguous, but the intended verdict still holds."
        if spec.difficulty == "borderline"
        else "Clear: objective findings unambiguously match the intended verdict."
    )
    return f"""
Generate one synthetic inpatient case for clinical validation training.

FIXED DECISIONS (do not change):
- case_id: {spec.case_id}
- target_dx: {spec.dx}
- intended_verdict: {spec.verdict}
- difficulty: {spec.difficulty}
- seed: {spec.seed}
- billed: icd10 ["A41.9"], drg "871" for sepsis
{borderline}
{against_rule}

Return JSON with exactly this shape:
{{
  "case": {{
    "case_id": "{spec.case_id}",
    "target_dx": "{spec.dx}",
    "billed": {{ "icd10": ["A41.9"], "drg": "871" }},
    "patient": {{ "age": <int 40-90>, "sex": "M"|"F" }},
    "documents": [
      {{
        "doc_id": "hp",
        "doc_type": "history_and_physical",
        "date": "YYYY-MM-DD",
        "lines": ["line1", "line2", ...]
      }},
      {{ "doc_id": "pn_01", "doc_type": "progress_note", "date": "...", "lines": [...] }},
      {{ "doc_id": "ds", "doc_type": "discharge_summary", "date": "...", "lines": [...] }}
    ],
    "labs": [
      {{ "name": "lactate", "value": <number>, "unit": "mmol/L", "datetime": "YYYY-MM-DDTHH:MM" }},
      {{ "name": "creatinine", "value": <number>, "unit": "mg/dL", "datetime": "..." }},
      {{ "name": "platelets", "value": <number>, "unit": "10^9/L", "datetime": "..." }}
    ],
    "vitals": [
      {{ "name": "map", "value": <number>, "unit": "mmHg", "datetime": "..." }},
      {{ "name": "temp", "value": <number>, "unit": "C", "datetime": "..." }}
    ]
  }},
  "key": {{
    "case_id": "{spec.case_id}",
    "verdict": "{spec.verdict}",
    "difficulty": "{spec.difficulty}",
    "planted_evidence": [
      {{
        "doc_id": "...",
        "line_start": <1-based>,
        "line_end": <1-based>,
        "side": "for"|"against",
        "criterion_id": "infection"|"organ_dysfunction"|"lactate_elevated"|"hypotension"|"vasopressors"|"creatinine_rise"|"thrombocytopenia"|"altered_mentation"
      }}
    ],
    "key_rationale": "2-4 sentences explaining why the verdict is {spec.verdict}"
  }}
}}

Rules:
- 3 to 5 documents, 15 to 40 lines each. Line numbers are 1-based positions in the lines array.
- Notes must mention labs/vitals that exist in the labs and vitals tables.
- Clinician notes may mention sepsis or suspected sepsis (billing context) even when not_supported.
- For supported: infection documented AND clear organ dysfunction (e.g. lactate > 2.0, MAP < 65, creatinine rise >= 0.3, platelets < 100, or vasopressors).
- For not_supported: infection may be present, but NO true organ dysfunction (normal lactate, stable MAP, no vasopressors, no significant creatinine rise, normal platelets).
- Include at least 2 planted_evidence spans with accurate line_start/line_end pointing at real lines.
- Provide at least two creatinine values ~24h apart when referencing creatinine trend.
- Use only synthetic content. No real PHI.
""".strip()


def call_groq(system: str, user: str, *, api_key: str | None = None) -> str:
    key = api_key if api_key is not None else GROQ_API_KEY
    if not key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.4,
        "max_tokens": 8000,
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    last_err: Exception | None = None
    for attempt in range(5):
        try:
            with httpx.Client(timeout=120.0) as client:
                res = client.post(GROQ_API_URL, headers=headers, json=payload)
            if res.status_code == 429:
                wait = min(60.0, 5.0 * (attempt + 1))
                print(f"  rate limited (429); sleeping {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            res.raise_for_status()
            data = res.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001 - retry then re-raise
            last_err = e
            wait = min(30.0, 2.0 * (attempt + 1))
            print(f"  groq error: {e}; retry in {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"Groq request failed after retries: {last_err}")


def extract_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from model output, stripping fences if present."""
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence:
        cleaned = fence.group(1).strip()
    # Find outermost object
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end < 0 or end <= start:
        raise ValueError("no JSON object found in model output")
    return json.loads(cleaned[start : end + 1])


def parse_case_and_key(payload: dict[str, Any], spec: CaseSpec) -> tuple[Case, AnswerKey]:
    if "case" in payload and "key" in payload:
        case_raw = payload["case"]
        key_raw = payload["key"]
    else:
        # Allow flat case with nested key
        key_raw = payload.pop("key", None)
        case_raw = payload
        if key_raw is None:
            raise ValueError("payload missing key")

    case_raw["case_id"] = spec.case_id
    case_raw["target_dx"] = spec.dx
    key_raw["case_id"] = spec.case_id
    key_raw["verdict"] = spec.verdict
    key_raw["difficulty"] = spec.difficulty

    case = Case.model_validate(case_raw)
    key = AnswerKey.model_validate(key_raw)
    return case, key


def write_raw(spec: CaseSpec, attempt: int, text: str) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"{spec.case_id}_attempt{attempt}.txt"
    path.write_text(text, encoding="utf-8")
    return path


def save_case_key(case: Case, key: AnswerKey) -> None:
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    case_path = CASES_DIR / f"{case.case_id}.json"
    key_path = KEYS_DIR / f"{case.case_id}.key.json"
    case_path.write_text(
        json.dumps(case.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8"
    )
    key_path.write_text(
        json.dumps(key.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8"
    )


def generate_one(
    spec: CaseSpec,
    *,
    sleep_s: float = GROQ_SLEEP_SECONDS,
    api_key: str | None = None,
) -> tuple[Case, AnswerKey]:
    """Generate, validate, and persist one case. Raises on final failure."""
    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            print(f"[{spec.case_id}] attempt {attempt}/{MAX_ATTEMPTS} ({spec.verdict}/{spec.difficulty})")
            raw = call_groq(_system_prompt(), _user_prompt(spec), api_key=api_key)
            write_raw(spec, attempt, raw)
            payload = extract_json_object(raw)
            case, key = parse_case_and_key(payload, spec)
            assert_consistent(case, key)
            save_case_key(case, key)
            print(f"[{spec.case_id}] saved case + key")
            if sleep_s > 0:
                time.sleep(sleep_s)
            return case, key
        except (json.JSONDecodeError, ValueError, ConsistencyError) as e:
            last_error = e
            print(f"[{spec.case_id}] attempt {attempt} failed: {e}", file=sys.stderr)
            if sleep_s > 0:
                time.sleep(sleep_s)
        except Exception as e:  # noqa: BLE001
            last_error = e
            print(f"[{spec.case_id}] attempt {attempt} error: {e}", file=sys.stderr)
            if sleep_s > 0:
                time.sleep(max(sleep_s, 5.0))
    raise RuntimeError(f"failed to generate {spec.case_id}: {last_error}")


def generate_bank(
    dx: str,
    n: int,
    *,
    start_index: int = 1,
    skip_existing: bool = True,
) -> list[str]:
    specs = plan_specs(dx, n, start_index=start_index)
    saved: list[str] = []
    for spec in specs:
        case_path = CASES_DIR / f"{spec.case_id}.json"
        key_path = KEYS_DIR / f"{spec.case_id}.key.json"
        if skip_existing and case_path.is_file() and key_path.is_file():
            print(f"[{spec.case_id}] exists; skip")
            saved.append(spec.case_id)
            continue
        try:
            generate_one(spec)
            saved.append(spec.case_id)
        except Exception as e:  # noqa: BLE001
            print(f"[{spec.case_id}] SKIP after failures: {e}", file=sys.stderr)
    return saved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic ChartProof cases")
    parser.add_argument("--dx", default="sepsis", help="target diagnosis id")
    parser.add_argument("--n", type=int, default=10, help="number of cases")
    parser.add_argument("--start-index", type=int, default=1, help="first case number")
    parser.add_argument(
        "--force",
        action="store_true",
        help="regenerate even if case files already exist",
    )
    args = parser.parse_args(argv)

    if not GROQ_API_KEY:
        print("ERROR: GROQ_API_KEY not set", file=sys.stderr)
        return 2

    print(f"model={GROQ_MODEL} dx={args.dx} n={args.n}")
    saved = generate_bank(
        args.dx,
        args.n,
        start_index=args.start_index,
        skip_existing=not args.force,
    )
    print(f"done: {len(saved)}/{args.n} cases available: {', '.join(saved)}")
    return 0 if len(saved) >= max(1, args.n // 2) else 1


if __name__ == "__main__":
    raise SystemExit(main())

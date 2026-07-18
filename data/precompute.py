"""Precompute audit results for all bundled cases.

Usage:
  python -m data.precompute
  python -m data.precompute --case sepsis_001
"""

from __future__ import annotations

import argparse

from backend.pipeline.audit_service import precompute_all


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Precompute ChartProof audit results")
    parser.add_argument("--case", action="append", dest="cases", help="case_id (repeatable)")
    parser.add_argument("--chroma", default=None, help="chroma dir override")
    args = parser.parse_args(argv)
    saved = precompute_all(chroma_dir=args.chroma, case_ids=args.cases)
    print(f"done: {len(saved)} precomputed")
    return 0 if saved else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""LangGraph audit pipeline with lazy public entrypoints.

Importing a lightweight helper such as ``backend.pipeline.training`` must not
also import Chroma, sentence-transformers, and LangGraph. The public pipeline
functions remain available here and load the graph only when called.
"""

from __future__ import annotations

from typing import Any

__all__ = ["run_full_pipeline", "run_partial_pipeline"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from backend.pipeline import graph

        return getattr(graph, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

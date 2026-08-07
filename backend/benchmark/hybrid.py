"""Benchmark-facing view of the hybrid gate.

The policy itself lives in `app.pipeline.gate` because the running service
applies it too. Keeping one implementation is the point: if the benchmark
scored a different merge from the one the product ships, the published figures
would describe software nobody can use.

This module only adapts the shape - the scorer wants plain lists of keys, the
API wants structured decisions it can render.
"""

from __future__ import annotations

from typing import Any

from app.models import EnrichedProduct
from app.pipeline.gate import INFERRED_CONFIDENCE_CAP, PROTECTED, apply  # noqa: F401

__all__ = ["merge", "INFERRED_CONFIDENCE_CAP", "PROTECTED"]


def merge(
    demo: EnrichedProduct, live: EnrichedProduct
) -> tuple[EnrichedProduct, dict[str, Any]]:
    """Apply the gate and report the actions as key lists."""
    merged = apply(demo, live)
    decision = merged.gate

    return merged, {
        "gap_filled": [a.key for a in decision.actions if a.action == "gap_filled"],
        "displaced_defaults": [
            a.key for a in decision.actions if a.action == "displaced_default"
        ],
        "refused_overrules": [a.key for a in decision.actions if a.action == "refused"],
    }

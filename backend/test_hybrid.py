"""Proves the hybrid gate's specific claim: Claude may add, never overrule.

Costs nothing — the records are constructed by hand, so no provider runs.
"""

from __future__ import annotations

import sys

from app.models import Attribute, EnrichedProduct, Provenance, RawProduct
from benchmark.hybrid import INFERRED_CONFIDENCE_CAP, merge


def attr(key: str, value, provenance: Provenance, confidence: float = 0.9) -> Attribute:
    return Attribute(
        key=key, label=key.replace("_", " ").title(), value=value,
        provenance=provenance, confidence=confidence,
        evidence=f"test fixture for {key}", method="test",
    )


def record(attributes: list[Attribute]) -> EnrichedProduct:
    return EnrichedProduct(input=RawProduct(sku="TEST-1", name="test"), attributes=attributes)


def check(label: str, condition: bool) -> bool:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")
    return condition


def main() -> int:
    demo = record([
        attr("bore_diameter", 25.0, Provenance.KNOWLEDGE_BASE),
        attr("mpn_series", "6205", Provenance.PARSED),
        attr("width", 15.0, Provenance.DERIVED),
        attr("seal_type", "open", Provenance.DEFAULTED, confidence=0.4),
    ])
    live = record([
        # Contradicts every evidence-backed class. All four must be refused.
        attr("bore_diameter", 30.0, Provenance.KNOWLEDGE_BASE, confidence=0.99),
        attr("mpn_series", "6305", Provenance.PARSED, confidence=0.99),
        attr("width", 18.0, Provenance.DERIVED, confidence=0.99),
        # Legitimate moves.
        attr("seal_type", "2RS", Provenance.KNOWLEDGE_BASE, confidence=0.95),
        attr("dynamic_load_rating", 14000, Provenance.KNOWLEDGE_BASE, confidence=0.95),
    ])

    merged, changes = merge(demo, live)
    values = {a.key: a for a in merged.attributes}

    ok = True
    print("Hybrid gate")

    ok &= check("keeps the knowledge_base value, refusing the model's",
                values["bore_diameter"].value == 25.0)
    ok &= check("keeps the parsed value", values["mpn_series"].value == "6205")
    ok &= check("keeps the derived value", values["width"].value == 15.0)
    ok &= check("records all three refusals",
                sorted(changes["refused_overrules"]) == ["bore_diameter", "mpn_series", "width"])

    ok &= check("displaces the category default", values["seal_type"].value == "2RS")
    ok &= check("counts the displacement", changes["displaced_defaults"] == ["seal_type"])

    ok &= check("fills the gap", values["dynamic_load_rating"].value == 14000)
    ok &= check("counts the gap fill", changes["gap_filled"] == ["dynamic_load_rating"])

    ok &= check("re-stamps adopted values as inferred, not knowledge_base",
                values["seal_type"].provenance == Provenance.INFERRED
                and values["dynamic_load_rating"].provenance == Provenance.INFERRED)
    ok &= check("caps inferred confidence",
                values["dynamic_load_rating"].confidence <= INFERRED_CONFIDENCE_CAP)
    ok &= check("preserves the evidence trail",
                "hybrid" in values["dynamic_load_rating"].evidence)

    ok &= check("re-scores rather than copying the parent verdict",
                merged.readiness is not None and merged.mode == "hybrid")

    # A model that agrees with a default must not be counted as a displacement:
    # inflating the action count would overstate what the gate does.
    quiet_demo = record([attr("seal_type", "open", Provenance.DEFAULTED, confidence=0.4)])
    quiet_live = record([attr("seal_type", "open", Provenance.KNOWLEDGE_BASE, confidence=0.9)])
    _, quiet = merge(quiet_demo, quiet_live)
    ok &= check("agreement with a default is not a displacement",
                quiet["displaced_defaults"] == [])

    print("\nOK" if ok else "\nFAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

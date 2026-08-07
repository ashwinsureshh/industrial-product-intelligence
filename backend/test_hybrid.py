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
    # The point is that adoption is marked *and* the original justification
    # survives, not that any particular prefix is used.
    adopted = values["dynamic_load_rating"].evidence
    ok &= check("preserves the evidence trail",
                "gate" in adopted and "test fixture for dynamic_load_rating" in adopted)

    ok &= check("re-scores rather than copying the parent verdict",
                merged.readiness is not None and merged.mode == "hybrid")

    # A model that agrees with a default must not be counted as a displacement:
    # inflating the action count would overstate what the gate does.
    quiet_demo = record([attr("seal_type", "open", Provenance.DEFAULTED, confidence=0.4)])
    quiet_live = record([attr("seal_type", "open", Provenance.KNOWLEDGE_BASE, confidence=0.9)])
    _, quiet = merge(quiet_demo, quiet_live)
    ok &= check("agreement with a default is not a displacement",
                quiet["displaced_defaults"] == [])

    ok &= check_shipped_gate()

    print("\nOK" if ok else "\nFAILED")
    return 0 if ok else 1


def check_shipped_gate() -> bool:
    """The gate as the *service* runs it, not just as the benchmark scores it.

    The guarantee that matters in production is that hybrid mode costs nothing
    for a product whose model proposal already ships with the app. If that ever
    breaks, a reviewer clicking Hybrid would silently need an API key.
    """
    import json

    from app import cache
    from app.main import _cache_payload, _enrich_hybrid
    from app.config import DATA_DIR

    print("\nShipped gate (service path)")

    with open(DATA_DIR / "samples.json", encoding="utf-8") as fh:
        sample = json.load(fh)["samples"][0]
    product = RawProduct(**sample["product"])

    before = cache.stats()["writes"]
    result = _enrich_hybrid(product, api_key=None)
    after = cache.stats()["writes"]

    ok = True
    ok &= check("runs the gate from a shipped proposal, with no key",
                result.gate is not None and result.gate.live_source == "precomputed")
    # The load-bearing assertion: a write means a provider call, means spend.
    ok &= check("spends nothing (no cache write, so no API call)", after == before)
    ok &= check("reports the record as hybrid", result.mode == "hybrid")

    actions = result.gate.actions if result.gate else []
    refusals = [a for a in actions if a.action == "refused"]
    ok &= check("refuses at least one overrule on the headline demo product",
                len(refusals) >= 1)
    ok &= check("every refusal names the value it kept and why",
                all(r.kept and r.kept_provenance and r.reason for r in refusals))
    ok &= check("no refusal was silently applied to the record",
                all(_show_value(result, r.key) == r.kept for r in refusals))
    return ok


def _show_value(result, key: str) -> str | None:
    from app.pipeline import units as U

    found = next((a for a in result.attributes if a.key == key), None)
    return U.format_value(found.value, found.unit) if found else None


if __name__ == "__main__":
    sys.exit(main())

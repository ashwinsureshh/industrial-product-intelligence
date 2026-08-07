"""Cost per SKU under deterministic-first triage.

    python run_cost_model.py

Costs nothing to run: it replays the committed records rather than calling the
API.

The organizers judge cost-effectiveness on a per-SKU basis, because the
industry runs on thin margins. Quoting the raw live figure would be
misleading in both directions - it is the cost of sending *every* SKU to the
model, which the architecture never needs to do.

The triage rule is sound rather than heuristic, and that distinction is the
point. Under the gate policy the model has exactly two permitted moves: fill a
gap, or displace a category default. So if a deterministic record has neither
an empty attribute nor a defaulted one, there is nothing the model is *allowed*
to change, and the call cannot alter the output. Skipping it forfeits nothing.
That is provable from the policy, not measured and hoped for.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.models import EnrichedProduct, Provenance, RawProduct
from app.pipeline import gate, taxonomy
from app.pipeline import run as pipeline
from app.providers.mock import MockProvider
from benchmark import records
from benchmark.corpus import build_corpus

RESULTS = Path(__file__).parent / "benchmark" / "results"

# Industry targets quoted by the organizers.
CURRENT_SKUS_PER_MONTH = 150_000
TARGET_SKUS_PER_MONTH = 750_000


def needs_model(record: EnrichedProduct) -> tuple[bool, str]:
    """Could the model legally change this record? Returns (needed, why)."""
    category = taxonomy.get_category(record.category.code) if record.category else None
    if category is None:
        # No schema resolved, so no gaps are even definable; a model proposal
        # would have nothing to attach to.
        return False, "unclassified"

    defined = set(category.get("attributes", {}).keys())
    present = {a.key for a in record.attributes}

    gaps = defined - present
    defaults = [a for a in record.attributes if a.provenance == Provenance.DEFAULTED]

    if gaps:
        return True, f"{len(gaps)} unfilled attribute(s)"
    if defaults:
        return True, f"{len(defaults)} unconfirmed default(s)"
    return False, "complete from evidence"


def main() -> int:
    cases = build_corpus()
    spend = json.loads((RESULTS / "spend_live.json").read_text(encoding="utf-8"))
    per_call = spend["spent_usd"] / spend["cases_run"]

    needed = 0
    skipped = 0
    reasons: dict[str, int] = {}
    forfeited = 0

    for case in cases:
        payload = dict(case.product)
        deterministic = pipeline.enrich(RawProduct(**payload), MockProvider())
        want, why = needs_model(deterministic)
        reasons[why.split(" ")[-1]] = reasons.get(why.split(" ")[-1], 0) + 1

        if want:
            needed += 1
            continue

        skipped += 1
        # Prove the skip was free: run the gate anyway and confirm it would
        # have accepted nothing. A single acceptance here would mean the triage
        # rule is losing data, and the whole argument collapses.
        stored = records.load(payload, "live")
        if stored is not None:
            merged = gate.apply(deterministic, EnrichedProduct.model_validate(stored))
            if merged.gate.gap_filled or merged.gate.displaced_defaults:
                forfeited += 1

    total = len(cases)
    call_rate = needed / total
    blended = per_call * call_rate

    report = {
        "cases": total,
        "model_calls_needed": needed,
        "model_calls_skipped": skipped,
        "call_rate_pct": round(100 * call_rate, 1),
        "cost_per_call_usd": round(per_call, 5),
        "cost_per_sku_naive_usd": round(per_call, 5),
        "cost_per_sku_triaged_usd": round(blended, 5),
        "attributes_forfeited_by_triage": forfeited,
        "monthly_at_target": {
            "skus": TARGET_SKUS_PER_MONTH,
            "naive_usd": round(per_call * TARGET_SKUS_PER_MONTH, 2),
            "triaged_usd": round(blended * TARGET_SKUS_PER_MONTH, 2),
        },
        "pricing_note": spend.get("pricing"),
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "cost_model.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=" * 66)
    print("  COST PER SKU  (replayed from committed records, $0.00 to run)")
    print("=" * 66)
    print(f"  measured cost per model call   ${per_call:.5f}")
    print(f"  SKUs that need a model call    {needed}/{total} ({100*call_rate:.1f}%)")
    print(f"  SKUs answered deterministically {skipped}/{total}")
    print(f"  attributes lost by skipping    {forfeited}  <- must be 0")
    print()
    print(f"  cost per SKU, every SKU to the model   ${per_call:.5f}")
    print(f"  cost per SKU, deterministic-first      ${blended:.5f}")
    print()
    print(f"  at {TARGET_SKUS_PER_MONTH:,} SKUs/month:")
    print(f"    naive            ${per_call * TARGET_SKUS_PER_MONTH:,.0f}/month")
    print(f"    deterministic-first ${blended * TARGET_SKUS_PER_MONTH:,.0f}/month")
    print()
    print(f"Report written to {RESULTS / 'cost_model.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

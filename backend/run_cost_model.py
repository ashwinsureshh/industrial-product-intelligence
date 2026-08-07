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

# The ablation was billed at Sonnet 5 introductory rates, which lapse on
# 2026-08-31 — eight days after the submission deadline. Quoting only the
# introductory figure would put a number in the deck that stops being true
# almost immediately, so both are reported and the standard rate leads.
INTRO_INPUT_PER_MTOK, INTRO_OUTPUT_PER_MTOK = 2.00, 10.00
STANDARD_INPUT_PER_MTOK, STANDARD_OUTPUT_PER_MTOK = 3.00, 15.00

# Published discount for the Message Batches API. Catalog enrichment is the
# textbook case for it: nobody is waiting on an individual SKU, and a month's
# work is a handful of batches.
BATCH_DISCOUNT = 0.50

# Deterministic throughput, measured on the 102-case benchmark.
DETERMINISTIC_PER_SECOND = 305.3


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

    # Recompute from raw tokens rather than scaling the billed total, so the
    # standard-rate figure is derived rather than estimated.
    tokens_in = spend["input_tokens"] / spend["cases_run"]
    tokens_out = spend["output_tokens"] / spend["cases_run"]

    def per_call_at(rate_in: float, rate_out: float) -> float:
        return tokens_in / 1e6 * rate_in + tokens_out / 1e6 * rate_out

    intro = per_call_at(INTRO_INPUT_PER_MTOK, INTRO_OUTPUT_PER_MTOK)
    standard = per_call_at(STANDARD_INPUT_PER_MTOK, STANDARD_OUTPUT_PER_MTOK)

    # Where the money actually goes. Output is the larger share, which is why
    # prompt caching — an input-side discount — is a smaller lever here than
    # the batch discount, which applies to both.
    output_share = (tokens_out / 1e6 * STANDARD_OUTPUT_PER_MTOK) / standard

    triaged = standard * call_rate
    batched = triaged * (1 - BATCH_DISCOUNT)

    calls_per_month = TARGET_SKUS_PER_MONTH * call_rate
    seconds_per_month = 30 * 24 * 3600

    report = {
        "cases": total,
        "model_calls_needed": needed,
        "model_calls_skipped": skipped,
        "call_rate_pct": round(100 * call_rate, 1),
        "attributes_forfeited_by_triage": forfeited,
        "tokens_per_call": {"input": round(tokens_in), "output": round(tokens_out)},
        "output_share_of_cost_pct": round(100 * output_share, 1),
        "cost_per_sku_usd": {
            "introductory_rate_every_sku": round(intro, 5),
            "standard_rate_every_sku": round(standard, 5),
            "standard_rate_triaged": round(triaged, 5),
            "standard_rate_triaged_batched": round(batched, 5),
        },
        "monthly_at_target": {
            "skus": TARGET_SKUS_PER_MONTH,
            "model_calls": round(calls_per_month),
            "every_sku_usd": round(standard * TARGET_SKUS_PER_MONTH, 2),
            "triaged_usd": round(triaged * TARGET_SKUS_PER_MONTH, 2),
            "triaged_batched_usd": round(batched * TARGET_SKUS_PER_MONTH, 2),
        },
        "scalability_at_target": {
            "deterministic_compute_hours": round(
                TARGET_SKUS_PER_MONTH / DETERMINISTIC_PER_SECOND / 3600, 2
            ),
            "model_calls_per_second_sustained": round(
                calls_per_month / seconds_per_month, 3
            ),
        },
        "measured": "triage rate, tokens, introductory cost",
        "projected": "standard-rate and batch figures, from published rates",
        "pricing_note": spend.get("pricing"),
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "cost_model.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=" * 68)
    print("  COST PER SKU  (replayed from committed records, $0.00 to run)")
    print("=" * 68)
    print(f"  SKUs needing a model call      {needed}/{total} ({100*call_rate:.1f}%)")
    print(f"  attributes lost by skipping    {forfeited}  <- must be 0")
    print(f"  tokens per call                {tokens_in:,.0f} in / {tokens_out:,.0f} out")
    print(f"  output share of spend          {100*output_share:.0f}%")
    print()
    print("  cost per SKU")
    print(f"    every SKU, introductory rate       ${intro:.5f}   (expires 2026-08-31)")
    print(f"    every SKU, standard rate           ${standard:.5f}")
    print(f"    + deterministic-first triage       ${triaged:.5f}")
    print(f"    + batch API (50%)                  ${batched:.5f}")
    print()
    print(f"  at {TARGET_SKUS_PER_MONTH:,} SKUs/month, standard rate:")
    print(f"    every SKU to the model   ${standard * TARGET_SKUS_PER_MONTH:,.0f}/month")
    print(f"    triaged                  ${triaged * TARGET_SKUS_PER_MONTH:,.0f}/month")
    print(f"    triaged + batched        ${batched * TARGET_SKUS_PER_MONTH:,.0f}/month")
    print()
    print("  scalability at that volume:")
    print(f"    deterministic compute    {TARGET_SKUS_PER_MONTH / DETERMINISTIC_PER_SECOND / 3600:.1f} hours/month")
    print(f"    sustained model calls    {calls_per_month / seconds_per_month:.2f}/second")
    print()
    print("  measured: triage rate, tokens, introductory cost")
    print("  projected: standard-rate and batch figures, from published rates")
    print()
    print(f"Report written to {RESULTS / 'cost_model.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Benchmark runner.

    python run_benchmark.py                  # demo engine
    python run_benchmark.py --catalog 250000 # size the business case differently
    python run_benchmark.py --live           # ablation against the Claude API (costs money)

Writes a JSON report and a Markdown summary to benchmark/results/.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from app.providers.mock import MockProvider
from benchmark.corpus import build_corpus, corpus_stats
from benchmark.evaluate import business_impact, evaluate

RESULTS = Path(__file__).parent / "benchmark" / "results"


def markdown_report(stats, report, business) -> str:
    recovery = report["recovery"]
    confident = report["recovery_excluding_defaults"]
    detection = report["defect_detection"]
    alarms = report["false_alarms"]

    lines = [
        "# Benchmark Results",
        "",
        f"Engine: **{report['label']}** · {report['cases']} cases · "
        f"{report['elapsed_s']} s · {report['throughput_per_s']} products/s",
        "",
        "## Headline",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Attribute coverage lift | **{report['coverage']['lift_multiple']}x** "
        f"({report['coverage']['attributes_in']} → {report['coverage']['attributes_out']}) |",
        f"| Withheld attributes recovered | **{recovery['recall_pct']}%** |",
        f"| Recovered values correct | **{recovery['precision_pct']}%** |",
        f"| **Contradiction rate** | **{recovery['contradiction_pct']}%** |",
        f"| Contradiction rate, excluding flagged defaults | **{confident['contradiction_pct']}%** |",
        f"| Seeded defects caught | **{detection['recall_pct']}%** "
        f"({detection['detected']}/{detection['expected']}) |",
        f"| False alarms on clean records | **{alarms['rate_pct']}%** |",
        f"| Auto-publishable (clean records) | **{business['auto_publish_pct']}%** |",
        f"| Defective records stopped | **{report['defects_stopped_pct']}%** |",
        "",
        "## Accuracy by provenance",
        "",
        "| Provenance | Correct | Contradicted | Precision |",
        "| --- | --- | --- | --- |",
    ]
    for name, counts in report["by_provenance"].items():
        lines.append(
            f"| {name} | {counts['correct']} | {counts['contradicted']} | {counts['precision_pct']}% |"
        )

    lines += [
        "",
        "## Accuracy by ground-truth strength",
        "",
        "`standards` values come from ISO 15 and ISO 898-1 and are externally fixed. "
        "`archetype` values were hand-authored and are therefore weaker evidence.",
        "",
        "| Source | Recall | Precision |",
        "| --- | --- | --- |",
    ]
    for name, counts in report["by_truth_source"].items():
        lines.append(f"| {name} | {counts['recall_pct']}% | {counts['precision_pct']}% |")

    lines += [
        "",
        "## Defect detection by kind",
        "",
        "| Defect | Caught | Total | Recall |",
        "| --- | --- | --- | --- |",
    ]
    for kind, counts in detection["by_kind"].items():
        lines.append(
            f"| {kind} | {counts['detected']} | {counts['expected']} | {counts['recall_pct']}% |"
        )

    if detection["missed"]:
        lines += ["", "### Missed defects", ""]
        for miss in detection["missed"]:
            lines.append(
                f"- `{miss['case']}` — {miss['defect']}; expected `{miss['expected']}`, "
                f"raised `{miss['raised']}`"
            )

    lines += [
        "",
        "## Business impact",
        "",
        f"Modelled on a **{business['assumptions']['catalog_size']:,} SKU** catalog.",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Manual baseline | {business['manual_baseline_hours']:,} hours |",
        f"| Hours saved | **{business['hours_saved']:,}** |",
        f"| Cost saved | **${business['cost_saved_usd']:,}** |",
        f"| FTE-years saved | {business['fte_years_saved']} |",
        f"| Machine processing time | {business['processing_hours']} hours |",
        "",
        "Assumptions: "
        f"{business['assumptions']['manual_minutes_per_sku']} min/SKU manual enrichment, "
        f"${business['assumptions']['analyst_cost_per_hour_usd']}/hour analyst cost, "
        f"records needing review credited at "
        f"{business['assumptions']['assisted_records_credited_at']}.",
        "",
        "## Corpus composition",
        "",
        "```json",
        json.dumps(stats, indent=2),
        "```",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=int, default=100_000,
                        help="Catalog size for the business model.")
    parser.add_argument("--sparse-keep", type=float, default=0.3,
                        help="Fraction of attributes left in the sparse input.")
    parser.add_argument("--live", action="store_true",
                        help="Also evaluate the Claude API engine (incurs cost).")
    args = parser.parse_args()

    cases = build_corpus(sparse_keep=args.sparse_keep)
    stats = corpus_stats(cases)

    print(f"Corpus: {stats['total']} cases across {len(stats['by_category'])} categories")
    print(f"  variants : {stats['by_variant']}")
    print(f"  truth    : {stats['by_truth_source']}")
    print()

    reports = []
    print("Evaluating demo engine...")
    demo = evaluate(cases, MockProvider, label="demo (deterministic)")
    reports.append(demo)

    if args.live:
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            print("  skipped: ANTHROPIC_API_KEY is not set")
        else:
            from app.providers.anthropic_provider import AnthropicProvider

            print("Evaluating live engine (this costs money)...")
            reports.append(
                evaluate(cases, lambda: AnthropicProvider(key), label="live (claude)")
            )

    RESULTS.mkdir(parents=True, exist_ok=True)

    for report in reports:
        business = business_impact(report, catalog_size=args.catalog)
        slug = report["label"].split()[0]

        (RESULTS / f"report_{slug}.json").write_text(
            json.dumps({"corpus": stats, "report": report, "business": business}, indent=2),
            encoding="utf-8",
        )
        markdown = markdown_report(stats, report, business)
        (RESULTS / f"report_{slug}.md").write_text(markdown, encoding="utf-8")

        recovery = report["recovery"]
        detection = report["defect_detection"]
        print()
        print("=" * 66)
        print(f"  {report['label']}")
        print("=" * 66)
        print(f"  coverage lift          {report['coverage']['lift_multiple']}x "
              f"({report['coverage']['attributes_in']} -> {report['coverage']['attributes_out']})")
        print(f"  withheld recovered     {recovery['recall_pct']}%")
        print(f"  recovered correct      {recovery['precision_pct']}%")
        print(f"  CONTRADICTION RATE     {recovery['contradiction_pct']}%")
        print(f"    excluding defaults   {report['recovery_excluding_defaults']['contradiction_pct']}%")
        print(f"  defects caught         {detection['recall_pct']}% "
              f"({detection['detected']}/{detection['expected']})")
        print(f"  false alarms           {report['false_alarms']['rate_pct']}%")
        print(f"  auto-publishable       {business['auto_publish_pct']}%")
        print(f"  throughput             {report['throughput_per_s']} products/s")
        print()
        print(f"  {args.catalog:,} SKUs -> {business['hours_saved']:,} hours saved, "
              f"${business['cost_saved_usd']:,}")

    print()
    print(f"Reports written to {RESULTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

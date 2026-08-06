"""Score the hybrid gate against the deterministic and live engines.

    python run_hybrid.py

**This script cannot spend money.** Live records are read from the cache and
nowhere else — `AnthropicProvider` is never imported, so a cache miss fails the
run instead of quietly reaching for the API. That is the property that makes a
policy change cheap to evaluate: the model output was paid for once, and every
merge policy tested against it afterwards is free.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app import cache
from app.models import EnrichedProduct, RawProduct
from app.pipeline import run as pipeline
from app.providers.mock import MockProvider
from benchmark.corpus import build_corpus, corpus_stats
from benchmark.evaluate import business_impact, evaluate
from benchmark.hybrid import merge
from run_benchmark import markdown_report

RESULTS = Path(__file__).parent / "benchmark" / "results"


def main() -> int:
    cases = build_corpus()
    stats = corpus_stats(cases)
    print(f"Corpus: {stats['total']} cases")

    missing: list[str] = []
    tally = {"gap_filled": 0, "displaced_defaults": 0, "refused_overrules": 0}

    def hybrid_enricher(case):
        payload = dict(case.product)

        live_hit = cache.get(payload, "live")
        if live_hit is None:
            missing.append(case.id)
            raise SystemExit(
                f"No cached live record for '{case.id}'. Refusing to continue: "
                f"this script never calls the API, so a miss means the ablation "
                f"cache is incomplete. Re-run run_benchmark.py --live first."
            )

        demo = pipeline.enrich(RawProduct(**payload), MockProvider())
        live = EnrichedProduct.model_validate(live_hit)
        merged, changes = merge(demo, live)

        for key in tally:
            tally[key] += len(changes[key])
        return merged, True

    print("Scoring demo (deterministic)...")
    demo_report = evaluate(cases, MockProvider, label="demo (deterministic)")

    print("Scoring hybrid (deterministic + bounded Claude), $0 from cache...")
    hybrid_report = evaluate(cases, label="hybrid (gated)", enricher=hybrid_enricher)

    RESULTS.mkdir(parents=True, exist_ok=True)
    business = business_impact(hybrid_report)
    (RESULTS / "report_hybrid.json").write_text(
        json.dumps({"corpus": stats, "report": hybrid_report, "business": business,
                    "policy_actions": tally}, indent=2),
        encoding="utf-8",
    )
    (RESULTS / "report_hybrid.md").write_text(
        markdown_report(stats, hybrid_report, business), encoding="utf-8"
    )

    live_path = RESULTS / "report_live.json"
    live_report = json.loads(live_path.read_text(encoding="utf-8"))["report"] if live_path.exists() else None

    def row(name: str, report) -> str:
        if report is None:
            return f"| {name} | - | - | - | - | - |"
        return (
            f"| {name} "
            f"| {report['by_truth_source'].get('standards', {}).get('recall_pct', 0)}% "
            f"| {report['by_truth_source'].get('archetype', {}).get('recall_pct', 0)}% "
            f"| {report['recovery']['contradiction_pct']}% "
            f"| {report['recovery_excluding_defaults']['contradiction_pct']}% "
            f"| {report['false_alarms']['rate_pct']}% |"
        )

    lines = [
        "# Ablation: deterministic vs live vs gated hybrid",
        "",
        "| Engine | Standards recall | Archetype recall | Contradiction | "
        "Contradiction excl. defaults | False alarms |",
        "| --- | --- | --- | --- | --- | --- |",
        row("demo (deterministic)", demo_report),
        row("live (claude)", live_report),
        row("hybrid (gated)", hybrid_report),
        "",
        "## What the gate actually did",
        "",
        f"- Gap-filled (key the deterministic engine left empty): **{tally['gap_filled']}**",
        f"- Displaced a category default: **{tally['displaced_defaults']}**",
        f"- **Refused** to overrule evidence-backed values: **{tally['refused_overrules']}**",
        "",
        "The refusal count is the point. Each one is a case where the live engine "
        "replaced a supplied, parsed, knowledge-base or derived value with a model "
        "guess, and the gate stopped it.",
    ]
    (RESULTS / "ablation_comparison.md").write_text("\n".join(lines), encoding="utf-8")

    for report in (demo_report, hybrid_report):
        recovery = report["recovery"]
        source = report["by_truth_source"]
        print()
        print("=" * 66)
        print(f"  {report['label']}")
        print("=" * 66)
        print(f"  standards recall       {source.get('standards', {}).get('recall_pct')}%")
        print(f"  archetype recall       {source.get('archetype', {}).get('recall_pct')}%")
        print(f"  CONTRADICTION RATE     {recovery['contradiction_pct']}%")
        print(f"    excluding defaults   {report['recovery_excluding_defaults']['contradiction_pct']}%")
        print(f"  defects caught         {report['defect_detection']['recall_pct']}%")
        print(f"  false alarms           {report['false_alarms']['rate_pct']}%")

    print()
    print(f"  gate: {tally['gap_filled']} gap-filled, "
          f"{tally['displaced_defaults']} defaults displaced, "
          f"{tally['refused_overrules']} overrules refused")
    print(f"\nReports written to {RESULTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

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
import subprocess
import sys
import time
from pathlib import Path

from app.providers.mock import MockProvider
from benchmark.corpus import build_corpus, corpus_stats
from benchmark.evaluate import BudgetExceeded, business_impact, evaluate

RESULTS = Path(__file__).parent / "benchmark" / "results"

# Claude Sonnet 5, USD per million tokens. Introductory rates run through
# 2026-08-31; the standard rates are $3.00 / $15.00.
PRICE_INPUT_PER_MTOK = 2.00
PRICE_OUTPUT_PER_MTOK = 10.00
PRICE_NOTE = "Sonnet 5 introductory pricing ($2/$10 per MTok), valid through 2026-08-31"


LOCK = Path(__file__).parent / ".benchmark.lock"


class RunLock:
    """Prevents two benchmark runs from spending concurrently.

    This exists because a projection-based budget guard cannot see a second
    process burning credits in parallel — the failure that actually happened.
    A per-run cap is only meaningful if there is exactly one run.
    """

    def __enter__(self) -> "RunLock":
        if LOCK.exists():
            try:
                pid = int(LOCK.read_text(encoding="utf-8").split("|")[0])
            except (ValueError, OSError, IndexError):
                pid = -1
            if _pid_alive(pid):
                raise SystemExit(
                    f"REFUSING TO START: benchmark already running (pid {pid}).\n"
                    f"Two concurrent runs would spend twice as fast as any cap expects.\n"
                    f"If you are certain it is dead, delete {LOCK}"
                )
            LOCK.unlink(missing_ok=True)  # stale lock from a killed run
        LOCK.write_text(f"{os.getpid()}|{time.time()}", encoding="utf-8")
        return self

    def __exit__(self, *exc) -> None:
        LOCK.unlink(missing_ok=True)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if sys.platform == "win32":
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=10,
            ).stdout
            return str(pid) in out
        os.kill(pid, 0)
        return True
    except Exception:  # noqa: BLE001 - a failed probe must not block the run
        return False


def cost_usd(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens / 1_000_000 * PRICE_INPUT_PER_MTOK
        + output_tokens / 1_000_000 * PRICE_OUTPUT_PER_MTOK
    )


def report_spend(providers, cases_run: int, cases_total: int) -> dict:
    """Sum real usage off the provider instances and extrapolate."""
    input_tokens = sum(p._usage["input_tokens"] for p in providers)
    output_tokens = sum(p._usage["output_tokens"] for p in providers)
    spent = cost_usd(input_tokens, output_tokens)
    scale = cases_total / cases_run if cases_run else 0

    return {
        "cases_run": cases_run,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "spent_usd": round(spent, 4),
        "projected_full_run_usd": round(spent * scale, 2),
        "pricing": PRICE_NOTE,
    }


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
    parser.add_argument("--budget", type=float, default=5.0,
                        help="Hard spend ceiling in USD. Checked after every case; "
                             "the run aborts the moment measured spend crosses it.")
    parser.add_argument("--limit", type=int, default=0,
                        help="Only evaluate the first N cases (for cheap partial runs).")
    args = parser.parse_args()

    cases = build_corpus(sparse_keep=args.sparse_keep)
    if args.limit:
        cases = cases[: args.limit]
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
            print("  skipped: ANTHROPIC_API_KEY is not set (put it in backend/.env)")
        else:
            from app.providers.anthropic_provider import AnthropicProvider

            providers: list[AnthropicProvider] = []

            def factory() -> AnthropicProvider:
                provider = AnthropicProvider(key)
                providers.append(provider)
                return provider

            def spent_now() -> float:
                return cost_usd(
                    sum(p._usage["input_tokens"] for p in providers),
                    sum(p._usage["output_tokens"] for p in providers),
                )

            def guard(completed: int) -> None:
                spend = spent_now()
                if spend > args.budget:
                    raise BudgetExceeded(spend, args.budget, completed, len(cases))

            def show(index: int, total: int, was_cached: bool) -> None:
                if index % 5 == 0 or index == total or index == 1:
                    tag = "cached" if was_cached else f"${spent_now():.2f}"
                    print(f"  [{index}/{total}] {tag}", flush=True)

            print(f"Evaluating live engine on {len(cases)} cases "
                  f"(hard ceiling ${args.budget:.2f}, results cached)...", flush=True)
            aborted = None
            try:
                reports.append(evaluate(
                    cases, factory, label="live (claude)",
                    mode="live", use_cache=True,
                    spend_guard=guard, progress=show,
                ))
            except BudgetExceeded as exc:
                aborted = exc
                print(f"\nABORTED: {exc}", flush=True)

            spend = report_spend(providers, len(cases), len(cases))
            spend["aborted"] = bool(aborted)
            spend["cases_completed"] = aborted.completed if aborted else len(cases)
            spend["ceiling_usd"] = args.budget
            RESULTS.mkdir(parents=True, exist_ok=True)
            (RESULTS / "spend_live.json").write_text(
                json.dumps(spend, indent=2), encoding="utf-8"
            )
            print(f"\nSpend this run: ${spend['spent_usd']:.2f} "
                  f"({spend['input_tokens']:,} in / {spend['output_tokens']:,} out)")
            if aborted:
                print("Completed cases are cached — re-running resumes free from here.")
                return 2

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
    # The lock is held for the whole run, so a second invocation refuses to
    # start rather than silently doubling the burn rate.
    with RunLock():
        raise SystemExit(main())

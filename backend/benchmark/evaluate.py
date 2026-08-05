"""Scoring for the benchmark corpus.

The metric that matters most here is not coverage — it is the **contradiction
rate**: how often the engine states a value that ground truth says is wrong.
Coverage without that number is meaningless, because any system can reach 100%
coverage by inventing everything.

Scoring rules:

  * Only WITHHELD attributes count toward recovery. Attributes handed to the
    engine in the input are trivially correct and would inflate every figure.
  * Numeric comparison uses a 1% relative tolerance to absorb unit-conversion
    rounding, not to be generous about wrong answers.
  * `defaulted` values are scored separately throughout. They are explicit
    placeholders the UI flags for confirmation, so counting them as confident
    errors would misrepresent what the system actually claims.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Callable

from app.models import RawProduct
from app.pipeline import run as pipeline
from app.providers.base import Provider

from .corpus import Case

NUMERIC_TOLERANCE = 0.01


def _values_match(predicted: Any, truth: Any) -> bool:
    if predicted is None or truth is None:
        return False

    if isinstance(truth, bool) or isinstance(predicted, bool):
        return bool(predicted) == bool(truth)

    if isinstance(truth, (int, float)) and isinstance(predicted, (int, float)):
        if truth == 0:
            return abs(predicted) < 1e-9
        return abs(predicted - truth) / abs(truth) <= NUMERIC_TOLERANCE

    return str(predicted).strip().lower() == str(truth).strip().lower()


def evaluate(
    cases: list[Case],
    provider_factory: Callable[[], Provider],
    label: str = "demo",
) -> dict[str, Any]:
    """Run every case and aggregate the results."""

    recovery = {"recovered": 0, "correct": 0, "contradicted": 0, "withheld_total": 0}
    # the same counters, but excluding category defaults
    confident = {"recovered": 0, "correct": 0, "contradicted": 0}

    by_provenance: dict[str, dict[str, int]] = defaultdict(
        lambda: {"correct": 0, "contradicted": 0}
    )
    by_source: dict[str, dict[str, int]] = defaultdict(
        lambda: {"correct": 0, "contradicted": 0, "recovered": 0, "withheld": 0}
    )

    detection = {"expected": 0, "detected": 0}
    by_defect_kind: dict[str, dict[str, int]] = defaultdict(lambda: {"expected": 0, "detected": 0})
    missed: list[dict[str, str]] = []

    false_alarms = 0
    clean_cases = 0
    false_alarm_codes: dict[str, int] = defaultdict(int)

    # Verdicts are tracked per variant. Mixing them would be misleading in both
    # directions: the business case must rest on clean records only, while
    # defect handling is judged on whether corrupted records are stopped.
    verdicts_clean: dict[str, int] = defaultdict(int)
    verdicts_defect: dict[str, int] = defaultdict(int)
    coverage_in = 0
    coverage_out = 0
    contradictions: list[dict[str, Any]] = []

    started = time.perf_counter()

    for case in cases:
        provider = provider_factory()
        result = pipeline.enrich(RawProduct(**case.product), provider)
        verdict = result.readiness.verdict if result.readiness else "none"

        if case.variant == "sparse":
            verdicts_clean[verdict] += 1
            # Coverage lift is only meaningful on sparse inputs; defect cases
            # are handed a full spec table and would flatten the ratio.
            coverage_in += len(case.product.get("raw_specs", {}))
            coverage_out += len(result.attributes)
        else:
            verdicts_defect[verdict] += 1

        predicted = {a.key: a for a in result.attributes}

        # ---------------------------------------------------------- recovery
        if case.variant == "sparse":
            for key in case.withheld:
                recovery["withheld_total"] += 1
                by_source[case.truth_source]["withheld"] += 1

                attribute = predicted.get(key)
                if attribute is None:
                    continue

                recovery["recovered"] += 1
                by_source[case.truth_source]["recovered"] += 1
                is_default = attribute.provenance.value == "defaulted"
                if not is_default:
                    confident["recovered"] += 1

                if _values_match(attribute.value, case.ground_truth[key]):
                    recovery["correct"] += 1
                    by_provenance[attribute.provenance.value]["correct"] += 1
                    by_source[case.truth_source]["correct"] += 1
                    if not is_default:
                        confident["correct"] += 1
                else:
                    recovery["contradicted"] += 1
                    by_provenance[attribute.provenance.value]["contradicted"] += 1
                    by_source[case.truth_source]["contradicted"] += 1
                    if not is_default:
                        confident["contradicted"] += 1
                    # Every miss is recorded so the report can show its own
                    # failures rather than only its wins.
                    contradictions.append({
                        "case": case.id,
                        "attribute": key,
                        "predicted": f"{attribute.value}"
                                     f"{' ' + attribute.unit if attribute.unit else ''}",
                        "truth": str(case.ground_truth[key]),
                        "provenance": attribute.provenance.value,
                        "confidence": attribute.confidence,
                        "evidence": attribute.evidence[:160],
                    })

            # A sparse case is defect-free, so any blocking error is a false alarm.
            clean_cases += 1
            errors = [i for i in result.issues if i.severity.value == "error"
                      and i.code != "MISSING_REQUIRED"]
            if errors:
                false_alarms += 1
                for issue in errors:
                    false_alarm_codes[issue.code] += 1

        # --------------------------------------------------------- detection
        if case.variant == "defect" and case.defect:
            detection["expected"] += 1
            by_defect_kind[case.defect.kind]["expected"] += 1

            codes = {i.code for i in result.issues}
            if any(code in codes for code in case.defect.expected_codes):
                detection["detected"] += 1
                by_defect_kind[case.defect.kind]["detected"] += 1
            else:
                missed.append({
                    "case": case.id,
                    "defect": case.defect.description,
                    "expected": ", ".join(case.defect.expected_codes),
                    "raised": ", ".join(sorted(codes)) or "nothing",
                })

    elapsed = time.perf_counter() - started

    def rate(numerator: int, denominator: int) -> float:
        return round(100 * numerator / denominator, 1) if denominator else 0.0

    return {
        "label": label,
        "cases": len(cases),
        "elapsed_s": round(elapsed, 2),
        "throughput_per_s": round(len(cases) / elapsed, 1) if elapsed else 0.0,
        "coverage": {
            "attributes_in": coverage_in,
            "attributes_out": coverage_out,
            "lift_multiple": round(coverage_out / coverage_in, 2) if coverage_in else 0.0,
        },
        "recovery": {
            **recovery,
            "recall_pct": rate(recovery["recovered"], recovery["withheld_total"]),
            "precision_pct": rate(recovery["correct"], recovery["recovered"]),
            "contradiction_pct": rate(recovery["contradicted"], recovery["recovered"]),
        },
        "recovery_excluding_defaults": {
            **confident,
            "precision_pct": rate(confident["correct"], confident["recovered"]),
            "contradiction_pct": rate(confident["contradicted"], confident["recovered"]),
        },
        "by_provenance": {
            key: {
                **counts,
                "precision_pct": rate(counts["correct"], counts["correct"] + counts["contradicted"]),
            }
            for key, counts in sorted(by_provenance.items())
        },
        "by_truth_source": {
            key: {
                **counts,
                "recall_pct": rate(counts["recovered"], counts["withheld"]),
                "precision_pct": rate(counts["correct"], counts["recovered"]),
            }
            for key, counts in sorted(by_source.items())
        },
        "defect_detection": {
            **detection,
            "recall_pct": rate(detection["detected"], detection["expected"]),
            "by_kind": {
                kind: {**counts, "recall_pct": rate(counts["detected"], counts["expected"])}
                for kind, counts in sorted(by_defect_kind.items())
            },
            "missed": missed,
        },
        "false_alarms": {
            "clean_cases": clean_cases,
            "cases_with_false_error": false_alarms,
            "rate_pct": rate(false_alarms, clean_cases),
            "codes": dict(sorted(false_alarm_codes.items(), key=lambda x: -x[1])),
        },
        "verdicts_clean": dict(verdicts_clean),
        "verdicts_defect": dict(verdicts_defect),
        # Held OR blocked both count as stopped: neither reaches a storefront
        # unreviewed, which is the property that actually matters.
        "defects_stopped_pct": rate(
            verdicts_defect.get("blocked", 0) + verdicts_defect.get("review", 0),
            sum(verdicts_defect.values()),
        ),
        "contradictions": contradictions,
    }


# --------------------------------------------------------------- business view

# Published industry figures for manual PIM enrichment put a technical SKU at
# roughly 10-15 minutes of specialist time. We use the conservative end and
# state it as an assumption rather than a finding.
MINUTES_PER_SKU_MANUAL = 10.0
ANALYST_COST_PER_HOUR = 35.0


def business_impact(report: dict[str, Any], catalog_size: int = 100_000) -> dict[str, Any]:
    """Translate the technical result into the terms a buyer actually budgets in.

    Deliberately conservative: records the engine only gets to 'review' are
    counted as *assisted*, not automated, and credited with half the time
    saving rather than all of it.
    """
    # Clean records only. A production catalog is not half defective, so
    # including seeded-defect cases here would understate automation badly.
    verdicts = report["verdicts_clean"]
    total = sum(verdicts.values()) or 1
    auto_pct = 100 * verdicts.get("publish", 0) / total
    assisted_pct = 100 * verdicts.get("review", 0) / total

    manual_hours = catalog_size * MINUTES_PER_SKU_MANUAL / 60
    automated = catalog_size * auto_pct / 100
    assisted = catalog_size * assisted_pct / 100

    hours_saved = (automated * MINUTES_PER_SKU_MANUAL / 60) + (
        assisted * MINUTES_PER_SKU_MANUAL / 60 * 0.5
    )

    throughput = report["throughput_per_s"]

    return {
        "assumptions": {
            "manual_minutes_per_sku": MINUTES_PER_SKU_MANUAL,
            "analyst_cost_per_hour_usd": ANALYST_COST_PER_HOUR,
            "assisted_records_credited_at": "50% of the manual time saving",
            "catalog_size": catalog_size,
        },
        "auto_publish_pct": round(auto_pct, 1),
        "assisted_pct": round(assisted_pct, 1),
        "manual_baseline_hours": round(manual_hours),
        "hours_saved": round(hours_saved),
        "cost_saved_usd": round(hours_saved * ANALYST_COST_PER_HOUR),
        "fte_years_saved": round(hours_saved / 1800, 1),
        "processing_hours": round(catalog_size / throughput / 3600, 2) if throughput else None,
        "defects_caught_per_10k": round(
            10_000 * report["defect_detection"]["recall_pct"] / 100 * 0.05
        ),
    }

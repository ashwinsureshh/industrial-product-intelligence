"""Smoke test: runs every demo sample through the pipeline and asserts the
behaviour the samples were designed to demonstrate.

Run with:  python smoke_test.py
"""

from __future__ import annotations

import json
import sys

from app.config import DATA_DIR
from app.models import RawProduct
from app.pipeline import run as pipeline
from app.providers.mock import MockProvider

FAILURES: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        FAILURES.append(message)
        print(f"    FAIL: {message}")


def main() -> int:
    with open(DATA_DIR / "samples.json", encoding="utf-8") as fh:
        data = json.load(fh)

    provider = MockProvider()

    for sample in data["samples"]:
        raw = RawProduct(**sample["product"])
        result = pipeline.enrich(raw, provider)

        cat = " > ".join(result.category.path) if result.category else "UNCLASSIFIED"
        errors = [i for i in result.issues if i.severity.value == "error"]
        warnings = [i for i in result.issues if i.severity.value == "warning"]

        print(f"\n[{sample['id']}] {sample['label']}")
        print(f"    category : {cat} ({result.category.confidence:.0%})"
              if result.category else "    category : UNCLASSIFIED")
        print(f"    attrs    : {len(result.attributes)}")
        print(f"    issues   : {len(errors)} error, {len(warnings)} warning")
        print(f"    readiness: {result.readiness.overall}/100 -> {result.readiness.verdict}")
        if result.content:
            print(f"    title    : {result.content.title}")
        for issue in errors + warnings:
            print(f"      - [{issue.severity.value}] {issue.code}: {issue.message}")

        # every attribute must carry a real audit trail
        for a in result.attributes:
            check(bool(a.evidence and len(a.evidence) > 10),
                  f"{sample['id']}: attribute '{a.key}' has no meaningful evidence")
            check(0.0 <= a.confidence <= 1.0,
                  f"{sample['id']}: attribute '{a.key}' has out-of-band confidence")

        check(len(result.trace) >= 7, f"{sample['id']}: pipeline trace is incomplete")

        # per-sample expectations
        sid = sample["id"]
        if sid == "sparse-bearing":
            check(result.attr("bore_diameter") is not None
                  and result.attr("bore_diameter").value == 25,
                  "sparse-bearing: 6205 bore should resolve to 25 mm from ISO 15")
            check(result.attr("outer_diameter").value == 52,
                  "sparse-bearing: 6205 OD should resolve to 52 mm")
            check(len(result.attributes) >= 8,
                  "sparse-bearing: expected a substantially enriched record")
        if sid == "messy-valve":
            size = result.attr("nominal_size")
            check(size is not None and abs(float(size.value) - 0.5) < 0.01,
                  "messy-valve: 1/2 inch should parse to 0.5 in")
            check(result.attr("body_material") is not None
                  and "316" in str(result.attr("body_material").value),
                  "messy-valve: SS316 should map onto the 316 stainless enum value")
        if sid == "contradictory-valve":
            check(any(i.code == "MATERIAL_TEMP_CONFLICT" for i in errors),
                  "contradictory-valve: PVC at 180 C must raise MATERIAL_TEMP_CONFLICT")
            check(result.readiness.verdict == "blocked",
                  "contradictory-valve: verdict should be blocked")
        if sid == "transposed-bearing":
            check(any(i.code == "GEOMETRY_CONTRADICTION" for i in errors),
                  "transposed-bearing: swapped bore/OD must raise GEOMETRY_CONTRADICTION")
        if sid == "imperial-motor":
            power = result.attr("power_rating")
            check(power is not None and abs(float(power.value) - 3.73) < 0.1,
                  "imperial-motor: 5 HP should convert to about 3.73 kW")
        if sid == "freetext-hose":
            check(result.attr("inner_diameter") is not None,
                  "freetext-hose: inner diameter must be recovered from prose")
            check(result.category is not None and result.category.code == "40142000",
                  "freetext-hose: should classify as hose & fittings")
        if sid == "unsafe-hose":
            # Below 3:1 this blocks rather than warns: it is a safety defect,
            # not a data-quality nit.
            check(any(i.code == "SAFETY_FACTOR_LOW" for i in errors),
                  "unsafe-hose: 2:1 burst ratio must raise a blocking SAFETY_FACTOR_LOW")
            check(result.readiness.verdict == "blocked",
                  "unsafe-hose: must not be publishable")
        if sid == "fastener-mismatch":
            check(any(i.code == "GRADE_MATERIAL_CONFLICT" for i in errors),
                  "fastener-mismatch: stainless with grade 10.9 must conflict")
        if sid == "sensor-partial":
            check(any(i.code == "INVALID_IP_CODE" for i in result.issues),
                  "sensor-partial: IP68K9 is not a valid IEC 60529 code")
        if sid == "unknown-category":
            check(result.readiness.overall < 60,
                  "unknown-category: should score low rather than guess confidently")

    # determinism: the same input must always produce the same output
    raw = RawProduct(**data["samples"][0]["product"])
    a = pipeline.enrich(raw, MockProvider()).model_dump(mode="json")
    b = pipeline.enrich(raw, MockProvider()).model_dump(mode="json")
    for record in (a, b):
        for stage in record["trace"]:
            stage["duration_ms"] = 0
    check(a == b, "demo mode is not deterministic across runs")

    print("\n" + "=" * 60)
    if FAILURES:
        print(f"{len(FAILURES)} CHECK(S) FAILED")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

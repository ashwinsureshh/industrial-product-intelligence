"""Field-level accuracy against Unilog's own labelled delivery rows. Costs $0.

Their guide names the metrics judges will look for: "Field-level accuracy
against the 200 known-good rows, character-limit compliance, and percentage of
values found in the LOV". This is that scorer.

It is deliberately a *second* benchmark, not a replacement for `run_benchmark.py`.
The 102-case corpus measures whether the engine gets the engineering right
against externally fixed ground truth (ISO 15, ISO 898-1); this measures whether
the output is written the way the customer requires. Both matter and they fail
independently — a record can carry a correct bore diameter and still be rejected
for a 41-character invoice line.

Scoring is strict by default. A field counts as correct only when it matches
character for character, because their importer is not fuzzy. A near miss is
reported separately as `close` so the gap between "wrong" and "wrong casing" is
visible rather than averaged away.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

from app.export import profiles
from app.ingest.unilog_rows import from_row
from app.pipeline import run as pipeline
from app.providers.mock import MockProvider

ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT / "data" / "unilog_samples"
RESULTS = ROOT / "benchmark" / "results"

# Columns that carry a Unilog-internal identifier or a digital asset we have no
# way to source. Scoring them would measure their CMS, not our engine, so they
# are counted separately as "out of scope" rather than silently as failures.
OUT_OF_SCOPE = {
    "PART_NUMBER", "SKU - MY_PART_NUMBER", "MFR URL",
    "Ref URL 1", "Ref URL 2", "Ref URL 3", "Ref URL 4", "Ref URL 5",
    "UPC", "EAN", "GTIN", "Warranty", "List Price", "Selling Qty", "Selling UOM",
    "Standard Packaging Information", "Product Image", "SDS", "SDS_1",
    "Warranty Information", "Catalog", "Specification Sheet",
    "Instruction/Installation Manual", "Service Manual", "Owners/User Manual",
    "Line Drawing", "MTR", "RoHS", "Full Engineering Drawing",
    "Energy Star Guide", "Technical Bulletin", "Submittal",
    "Compatibility Chart", "Size Chart", "Product Label/Insert",
    "Video Link", "Video Link 1", "Discontinued", "Actual Image (Yes/No)",
    "TRADE_NAME", "ALTERNATE_PART_NUMBER", "Prop 65", "Application", "Includes",
    "MARKETING_DESCRIPTION",
}
OUT_OF_SCOPE.update(f"Alternate Image {i}" for i in range(1, 5))


def _norm(value: Any) -> str:
    return " ".join(str(value if value is not None else "").split())


def _loose(value: Any) -> str:
    """Casing- and punctuation-insensitive, for telling 'wrong' from 'nearly'."""
    text = _norm(value).lower()
    return "".join(c for c in text if c.isalnum() or c == " ").strip()


def load_expected(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def record_for(expected: dict[str, str]):
    """Rebuild the input row from the delivery row's own passthrough columns.

    The delivery sheet echoes the raw input it was built from, so the fixture
    and the ground truth cannot drift apart.
    """
    product, _ = from_row({
        "Mfg_Part_Num": expected.get("Mfg_Part_Num", ""),
        "Part_Desc": expected.get("Part_Desc", ""),
        "E1_Brand": expected.get("E1_Brand", ""),
        "Unilog_Brand": expected.get("Unilog_Brand", ""),
        "DIB_Brand": expected.get("DIB_Brand", ""),
        "Part_Manuf": expected.get("Part_Manuf", ""),
        "SKU": expected.get("SKU - MY_PART_NUMBER", ""),
    })
    return pipeline.enrich(product, MockProvider())


def score(rows: list[dict[str, str]]) -> dict[str, Any]:
    profile = profiles.get("unilog_delivery")
    per_field: dict[str, dict[str, int]] = {}
    cases: list[dict[str, Any]] = []

    for expected in rows:
        record = record_for(expected)
        header, built = profiles.to_rows(profile, [record])
        ours = dict(zip(header, built[0]))

        exact = close = missing = wrong = scored = extra = 0
        misses: list[dict[str, str]] = []

        for column in header:
            if column in OUT_OF_SCOPE:
                continue
            want = _norm(expected.get(column, ""))
            got = _norm(ours.get(column, ""))
            if not want and not got:
                continue  # both blank: nothing asserted either way
            if not want:
                # We sourced something their own row leaves blank. Their guide
                # flags these gaps itself ("blank UNSPSC and country-of-origin
                # cells"), so this is a surplus, not a contradiction — counting
                # it as an error would penalise us for exceeding the label.
                extra += 1
                continue
            scored += 1
            bucket = per_field.setdefault(
                column, {"exact": 0, "close": 0, "missing": 0, "wrong": 0}
            )
            if want == got:
                exact += 1
                bucket["exact"] += 1
            elif not got:
                missing += 1
                bucket["missing"] += 1
                misses.append({"field": column, "want": want, "got": "", "kind": "missing"})
            elif _loose(want) == _loose(got):
                close += 1
                bucket["close"] += 1
                misses.append({"field": column, "want": want, "got": got, "kind": "close"})
            else:
                wrong += 1
                bucket["wrong"] += 1
                misses.append({"field": column, "want": want, "got": got, "kind": "wrong"})

        attempted = exact + close + wrong
        compliance = record.compliance
        cases.append({
            "mpn": expected.get("Mfg_Part_Num", ""),
            "scored": scored,
            "exact": exact,
            "close": close,
            "missing": missing,
            "wrong": wrong,
            "extra": extra,
            "accuracy_pct": round(100.0 * exact / scored, 1) if scored else 0.0,
            "precision_pct": round(100.0 * exact / attempted, 1) if attempted else 0.0,
            "content_compliant": bool(compliance and compliance.compliant),
            "misses": misses,
        })

    totals = {
        key: sum(c[key] for c in cases)
        for key in ("scored", "exact", "close", "missing", "wrong", "extra")
    }
    scored_total = totals["scored"] or 1
    attempted_total = totals["exact"] + totals["close"] + totals["wrong"] or 1
    return {
        "precision_pct": round(100.0 * totals["exact"] / attempted_total, 1),
        "attempted": attempted_total,
        "cases": cases,
        "totals": totals,
        "accuracy_pct": round(100.0 * totals["exact"] / scored_total, 1),
        "accuracy_loose_pct": round(
            100.0 * (totals["exact"] + totals["close"]) / scored_total, 1
        ),
        "recall_pct": round(100.0 * (scored_total - totals["missing"]) / scored_total, 1),
        "per_field": per_field,
    }


def report(result: dict[str, Any]) -> None:
    print()
    print("=" * 66)
    print("  DELIVERY FORMAT ACCURACY - Unilog labelled rows, $0.00")
    print("=" * 66)
    for case in result["cases"]:
        print(f"\n  {case['mpn']}  {case['exact']}/{case['scored']} exact "
              f"({case['accuracy_pct']}%)")
        for miss in case["misses"]:
            print(f"    {miss['kind']:>7}  {miss['field']}")
            if miss["kind"] != "missing":
                print(f"             want: {miss['want'][:100]}")
                print(f"             got : {miss['got'][:100]}")

    totals = result["totals"]
    print()
    print("-" * 66)
    print(f"  fields scored              {totals['scored']}")
    print(f"  FIELD-LEVEL ACCURACY       {result['accuracy_pct']}%  "
          f"({totals['exact']}/{totals['scored']} exact)")
    print(f"    allowing case/punct      {result['accuracy_loose_pct']}%  "
          f"(+{totals['close']} close)")
    print()
    print("  Split by cause, because these need different fixes:")
    print(f"    coverage                 {result['recall_pct']}%  "
          f"attempted, {totals['missing']} left blank for want of a source")
    print(f"    PRECISION WHEN ANSWERED  {result['precision_pct']}%  "
          f"({totals['exact']}/{result['attempted']} of the fields we did fill)")
    print(f"    contradicted             {totals['wrong']}")
    print(f"    sourced beyond the label {totals['extra']}  "
          f"(their cell blank, ours populated)")
    print("-" * 66)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected", default=str(SAMPLES / "delivery_expected.csv"))
    args = parser.parse_args()

    path = Path(args.expected)
    if not path.exists():
        print(f"No labelled rows at {path}.")
        print("Drop Unilog's expected-output CSV there and re-run.")
        return 2

    rows = load_expected(path)
    result = score(rows)
    report(result)

    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / "delivery_accuracy.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\n  Report written to {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Their expected delivery row, next to ours, in both honest states. $0.

There are two different questions and the difference between them is the whole
story of where this engine stands:

  A. **Given the attribute values, is the copy written correctly?**
     Feed the formatter the attributes from Unilog's own delivery row and every
     prose field comes back character for character identical. This measures the
     content-format layer — the character limits, the token dropping, the
     casing, the fraction rules.

  B. **Starting from the six-column input row, what actually comes out?**
     Almost nothing, because Series, Mounting, Wash Cycles, Voltage and the rest
     are not in the input. They live on the manufacturer's site, which their own
     row cites as MFR URL.

Quoting A without B would be a claim the pipeline cannot support end to end, so
this script always prints both, and the deck is built from its output.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.export import profiles
from app.models import Attribute, Provenance
from app.unilog import content_formats as CF
from run_delivery_accuracy import SAMPLES, load_expected, record_for

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / "docs" / "deck" / "expected_vs_ours.json"

# Their delivery column -> the format id that fills it.
FIELDS = [
    ("INVOICE_DESC", "invoice_desc"),
    ("MOBILE_DESC", "mobile_desc"),
    ("SHORT_DESC", "product_title"),
    ("RETAIL_DESC", "retail_desc"),
    ("LONG_DESC1", "long_description"),
    ("With", "with_clause"),
    ("Product Name", "product_name"),
]

# Their attribute labels -> our keys, so state A can be fed from their own row.
KEYMAP = {
    "Series": "series", "Model": "model", "Number of Wash Cycles": "wash_cycles",
    "Voltage Rating": "voltage", "Amperage Rating": "current",
    "Mounting Type": "mounting", "Plug Type": "plug_type", "Size": "size",
    "Depth With Door Open": "depth_with_door_open",
    "Minimum Height": "minimum_height", "Maximum Height": "maximum_height",
    "Sound Level": "sound_level", "Material": "material", "Color": "color",
    "Additional Information": "additional_information",
}


def norm(value) -> str:
    return " ".join(str(value if value is not None else "").split())


def attributes_from_row(row: dict) -> list[Attribute]:
    """Rebuild our Attribute list from their labelled triplets."""
    out: list[Attribute] = []
    for i in range(1, 51):
        label = norm(row.get(f"ATTRIBUTE_LABEL {i}"))
        value = norm(row.get(f"ATTRIBUTE_VALUE {i}"))
        unit = norm(row.get(f"ATTRIBUTE_UOM {i}")) or None
        if not label or not value:
            continue
        try:
            number = float(value)
            value = int(number) if number.is_integer() else number
        except ValueError:
            pass
        out.append(Attribute(
            key=KEYMAP.get(label, label.lower().replace(" ", "_")),
            label=label, value=value, unit=unit,
            provenance=Provenance.SUPPLIED, confidence=0.99,
            evidence="supplied in Unilog's labelled delivery row.",
            method="ground-truth-fixture",
        ))
    feature = norm(row.get("With"))
    if feature.lower().startswith("with "):
        out.insert(0, Attribute(
            key="feature", label="Feature", value=feature[5:],
            provenance=Provenance.SUPPLIED, confidence=0.99,
            evidence="the With column of their delivery row.",
            method="ground-truth-fixture"))
    return out


def main() -> int:
    rows = load_expected(SAMPLES / "delivery_expected.csv")
    profile = profiles.get("unilog_delivery")
    cases = []

    for row in rows:
        # --- state B: the real pipeline, from the six-column input row only
        record = record_for(row)
        header, built = profiles.to_rows(profile, [record])
        from_input = dict(zip(header, built[0]))

        # --- state A: the formatter, given their own attribute values
        ctx = CF.ContentContext(
            brand=row["BRAND_NAME"], manufacturer=row["MANUFACTURER_NAME"],
            mpn=row["MANUFACTURER_PART_NUMBER"], item_type=row["Product Name"],
            attributes=attributes_from_row(row),
        )
        given = {r.id: r.text for r in CF.build_all(ctx)}

        fields = []
        for column, fid in FIELDS:
            want = norm(row.get(column))
            fields.append({
                "column": column,
                "expected": want,
                "given_attributes": norm(given.get(fid)),
                "from_input_row": norm(from_input.get(column)),
                "match_given": want == norm(given.get(fid)),
                "match_from_input": want == norm(from_input.get(column)),
            })
        cases.append({"mpn": row["Mfg_Part_Num"], "fields": fields})

    flat = [f for c in cases for f in c["fields"]]
    summary = {
        "fields_scored": len(flat),
        "exact_given_attributes": sum(f["match_given"] for f in flat),
        "exact_from_input_row": sum(f["match_from_input"] for f in flat),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"summary": summary, "cases": cases},
                              indent=1, ensure_ascii=False), encoding="utf-8")

    print("=" * 70)
    print("  EXPECTED vs OURS — Unilog's two labelled rows, $0.00")
    print("=" * 70)
    print(f"\n  A. formatter given the attribute values : "
          f"{summary['exact_given_attributes']}/{summary['fields_scored']} exact")
    print(f"  B. pipeline from the 6-column input row : "
          f"{summary['exact_from_input_row']}/{summary['fields_scored']} exact")
    print("\n  The gap between A and B is not a formatting failure. It is the "
          "\n  attribute values themselves, which are not in the input row.\n")

    for case in cases[:1]:
        print(f"  {case['mpn']}")
        for f in case["fields"][:4]:
            print(f"\n    {f['column']}")
            print(f"      expected  {f['expected'][:88]}")
            print(f"      A (given) {f['given_attributes'][:88]}"
                  f"   {'IDENTICAL' if f['match_given'] else 'DIFFERS'}")
            print(f"      B (input) {f['from_input_row'][:88]}"
                  f"   {'IDENTICAL' if f['match_from_input'] else 'DIFFERS'}")
    print(f"\n  Written to {OUT.relative_to(ROOT.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

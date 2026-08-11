"""Generate the Unilog delivery export profile from their own header row.

Their sheet is 252 positional columns. Typing that list by hand would guarantee
a drift between our output and their format, and a single missing column shifts
every later value — so the profile is generated from the header they shipped and
the mapping table below is the only hand-written part.

Run after replacing the sample CSV:

    cd backend && python tools/build_delivery_profile.py

Columns with no mapping are emitted as empty strings rather than dropped. A
short row would misalign their importer, and a blank cell is an honest "we did
not source this" where a missing column is a broken file.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEADER_CSV = ROOT / "data" / "unilog_samples" / "delivery_expected.csv"
OUTPUT = ROOT / "app" / "data" / "export_profiles" / "unilog_delivery.json"

# Their column -> where the value comes from in an EnrichedProduct.
MAPPING: dict[str, str] = {
    "Ref URL 1": "input.source_url",
    "Mfg_Part_Num": "identity.mpn",
    "Part_Desc": "input.description",
    "E1_Brand": "attr:_e1_brand",
    "Unilog_Brand": "attr:_unilog_brand",
    "DIB_Brand": "attr:_dib_brand",
    "Part_Manuf": "attr:_part_manuf",
    "MANUFACTURER_NAME": "identity.manufacturer",
    "BRAND_NAME": "identity.brand",
    "MANUFACTURER_PART_NUMBER": "identity.mpn",
    "Dept": "category.customer.dept",
    "Class": "category.customer.class",
    "Fine": "category.customer.fine",
    "Classpath": "category.classpath",
    "MOBILE_DESC": "field:mobile_desc",
    "INVOICE_DESC": "field:invoice_desc",
    "SHORT_DESC": "field:product_title",
    "LONG_DESC1": "field:long_description",
    "RETAIL_DESC": "field:retail_desc",
    "MARKETING_DESCRIPTION": "content.long_description",
    "With": "field:with_clause",
    "Product Name": "field:product_name",
    "UNSPSC": "category.code",
    "List Price": "input.price",
    "Country Of Origin": "identity.brand_country",
}

# Numbered slot blocks, keyed by the first column of the run so they land in
# the right position in their column order.
SLOTS: dict[str, dict] = {
    "ITEM_FEATURES_1": {
        "source": "content.bullets",
        "count": 20,
        "target": "ITEM_FEATURES_{n}",
        "_span": [f"ITEM_FEATURES_{i}" for i in range(1, 21)],
    },
    "ATTRIBUTE_LABEL 1": {
        "source": "attributes",
        "count": 50,
        "columns": [
            {"target": "ATTRIBUTE_LABEL {n}", "from": "label"},
            {"target": "ATTRIBUTE_VALUE {n}", "from": "value"},
            {"target": "ATTRIBUTE_UOM {n}", "from": "unit"},
        ],
        "_span": [
            f"ATTRIBUTE_{part} {i}"
            for i in range(1, 51)
            for part in ("LABEL", "VALUE", "UOM")
        ],
    },
}


def main() -> int:
    with open(HEADER_CSV, encoding="utf-8-sig", newline="") as fh:
        header = next(csv.reader(fh))

    consumed: set[str] = set()
    for block in SLOTS.values():
        consumed.update(block["_span"])

    fields: list[dict] = []
    mapped = 0
    for column in header:
        if column in SLOTS:
            block = {k: v for k, v in SLOTS[column].items() if not k.startswith("_")}
            fields.append({"slots": block})
            continue
        if column in consumed:
            continue
        if column in MAPPING:
            fields.append({"target": column, "from": MAPPING[column]})
            mapped += 1
        else:
            fields.append({"target": column, "const": ""})

    profile = {
        "id": "unilog_delivery",
        "label": "Unilog Delivery Format",
        "format": "csv",
        "description": (
            "Their 252-column delivery sheet, generated from the header they "
            "supplied so column names and order cannot drift. Unsourced columns "
            "are emitted empty rather than dropped, because their importer is "
            "positional and a short row misaligns every later value."
        ),
        "generated_from": HEADER_CSV.name,
        "fields": fields,
    }

    OUTPUT.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")

    slots_cols = sum(len(b["_span"]) for b in SLOTS.values())
    print(f"{len(header)} source columns")
    print(f"  {mapped} mapped from the record")
    print(f"  {slots_cols} in {len(SLOTS)} numbered slot block(s)")
    print(f"  {len(header) - mapped - slots_cols} emitted empty")
    print(f"-> {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

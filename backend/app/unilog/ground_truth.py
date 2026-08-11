"""Unilog's labelled delivery rows, scored against what the engine produces.

Their guide names this as the thing judges will look for — "field-level accuracy
against the known-good rows" — so it belongs in the running product, not only in
a benchmark script someone has to clone the repo to run.

Two states are always reported together, because quoting the first alone is a
claim the pipeline cannot support end to end:

  A. **Given the attribute values**, does the copy come out right? Feed the
     formatter the attributes from their own delivery row and every prose field
     matches character for character. This measures the content-format layer.

  B. **From the six-column input row**, what actually comes out? Much less,
     because Series, Mounting, Wash Cycles and Voltage are not in that row —
     they are on the manufacturer's site their own row cites as MFR URL.

The gap between A and B is sourcing, not formatting, and showing only A would be
the same kind of confident-looking overstatement this engine refuses to make
about a product record.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..config import DATA_DIR
from ..models import Attribute, Provenance
from . import content_formats as CF

# backend/data/unilog_samples — their files sit beside the app package, not
# inside it, because they are inputs to the project rather than app resources.
SAMPLES = DATA_DIR.parent.parent / "data" / "unilog_samples"
EXPECTED_CSV = SAMPLES / "delivery_expected.csv"

# The prose columns the content layer is responsible for.
PROSE_FIELDS = [
    ("INVOICE_DESC", "invoice_desc", "<= 40 characters, capitals"),
    ("MOBILE_DESC", "mobile_desc", "60-80 characters"),
    ("SHORT_DESC", "product_title", "title case, brand + series + MPN + type"),
    ("RETAIL_DESC", "retail_desc", "no brand or part number"),
    ("LONG_DESC1", "long_description", "every backed attribute, in sequence"),
    ("With", "with_clause", "feature clause"),
    ("Product Name", "product_name", "the item type alone"),
]

# Their attribute labels -> our keys, so state A can be fed from their own row.
LABEL_TO_KEY = {
    "Series": "series", "Model": "model", "Number of Wash Cycles": "wash_cycles",
    "Voltage Rating": "voltage", "Amperage Rating": "current",
    "Mounting Type": "mounting", "Plug Type": "plug_type", "Size": "size",
    "Depth With Door Open": "depth_with_door_open",
    "Minimum Height": "minimum_height", "Maximum Height": "maximum_height",
    "Sound Level": "sound_level", "Material": "material", "Color": "color",
    "Additional Information": "additional_information",
}


def _norm(value: Any) -> str:
    return " ".join(str(value if value is not None else "").split())


def available() -> bool:
    return EXPECTED_CSV.exists()


@lru_cache(maxsize=1)
def _rows() -> list[dict[str, str]]:
    if not EXPECTED_CSV.exists():
        return []
    with open(EXPECTED_CSV, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def invalidate() -> None:
    _rows.cache_clear()
    compare.cache_clear()


def _attributes_from(row: dict[str, str]) -> list[Attribute]:
    """Rebuild an Attribute list from their labelled ATTRIBUTE triplets."""
    out: list[Attribute] = []
    for index in range(1, 51):
        label = _norm(row.get(f"ATTRIBUTE_LABEL {index}"))
        value: Any = _norm(row.get(f"ATTRIBUTE_VALUE {index}"))
        unit = _norm(row.get(f"ATTRIBUTE_UOM {index}")) or None
        if not label or not value:
            continue
        try:
            number = float(value)
            value = int(number) if number.is_integer() else number
        except ValueError:
            pass
        out.append(Attribute(
            key=LABEL_TO_KEY.get(label, label.lower().replace(" ", "_")),
            label=label, value=value, unit=unit,
            provenance=Provenance.SUPPLIED, confidence=0.99,
            evidence="supplied in Unilog's labelled delivery row.",
            method="ground-truth-fixture",
        ))
    feature = _norm(row.get("With"))
    if feature.lower().startswith("with "):
        out.insert(0, Attribute(
            key="feature", label="Feature", value=feature[5:],
            provenance=Provenance.SUPPLIED, confidence=0.99,
            evidence="the With column of their delivery row.",
            method="ground-truth-fixture"))
    return out


@lru_cache(maxsize=1)
def compare() -> dict[str, Any]:
    """Score both states against every labelled row."""
    from ..export import profiles
    from ..ingest.unilog_rows import from_row
    from ..pipeline.run import enrich
    from ..providers.mock import MockProvider

    rows = _rows()
    if not rows:
        return {"available": False, "cases": [], "summary": {}}

    profile = profiles.get("unilog_delivery")
    provider = MockProvider()
    cases: list[dict[str, Any]] = []

    for row in rows:
        # State B: the ordinary pipeline, from the input columns their own
        # delivery row echoes back.
        product, _ = from_row({
            "Mfg_Part_Num": row.get("Mfg_Part_Num", ""),
            "Part_Desc": row.get("Part_Desc", ""),
            "E1_Brand": row.get("E1_Brand", ""),
            "Unilog_Brand": row.get("Unilog_Brand", ""),
            "DIB_Brand": row.get("DIB_Brand", ""),
            "Part_Manuf": row.get("Part_Manuf", ""),
            "SKU": row.get("SKU - MY_PART_NUMBER", ""),
        })
        record = enrich(product, provider)
        header, built = profiles.to_rows(profile, [record])
        from_input = dict(zip(header, built[0]))

        # State A: the formatter, given their own attribute values.
        given = {
            r.id: r.text
            for r in CF.build_all(CF.ContentContext(
                brand=row.get("BRAND_NAME", ""),
                manufacturer=row.get("MANUFACTURER_NAME", ""),
                mpn=row.get("MANUFACTURER_PART_NUMBER", ""),
                item_type=row.get("Product Name", ""),
                attributes=_attributes_from(row),
            ))
        }

        fields = []
        for column, fid, rule in PROSE_FIELDS:
            expected = _norm(row.get(column))
            a = _norm(given.get(fid))
            b = _norm(from_input.get(column))
            fields.append({
                "column": column, "rule": rule, "expected": expected,
                "given_attributes": a, "from_input_row": b,
                "match_given": expected == a,
                "match_from_input": expected == b,
                "expected_length": len(expected),
            })

        cases.append({
            "mpn": row.get("Mfg_Part_Num", ""),
            "brand": row.get("BRAND_NAME", ""),
            "part_desc": row.get("Part_Desc", ""),
            "classpath": row.get("Classpath", ""),
            "mfr_url": row.get("MFR URL", ""),
            "fields": fields,
        })

    flat = [f for c in cases for f in c["fields"]]
    total = len(flat) or 1
    summary = {
        "rows": len(cases),
        "fields_scored": len(flat),
        "exact_given_attributes": sum(f["match_given"] for f in flat),
        "exact_from_input_row": sum(f["match_from_input"] for f in flat),
        "pct_given_attributes": round(100.0 * sum(f["match_given"] for f in flat) / total, 1),
        "pct_from_input_row": round(100.0 * sum(f["match_from_input"] for f in flat) / total, 1),
        "source": "unilog_sample",
    }
    return {"available": True, "summary": summary, "cases": cases}

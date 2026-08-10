"""Ingest Unilog's own catalogue rows.

Their working files carry six columns — `Mfg_Part_Num`, `Part_Desc`, `E1_Brand`,
`Unilog_Brand`, `DIB_Brand`, `Part_Manuf` — and the labelled 200-item file adds
`Dept` / `Class` / `Fine` and `SKU`. This adapter turns one such row into the
same `RawProduct` every other input path produces, so a spreadsheet row earns
exactly the same provenance, validation and readiness scoring as a datasheet
page. No parallel pipeline.

Two behaviours are worth stating outright, because both are places where a
careless reader of this data would silently corrupt the catalogue.

**Placeholders are not brands.** `-- Unbranded --`, `-- No Unilog Brand --` and
`-- No DIB Brand --` mean the field is empty. Treated as text they would become
a brand named "-- Unbranded --" in 27,000 approved-brand fuzzy matches, and the
nearest match to a placeholder is noise.

**Three brand columns can disagree.** When they do, this adapter takes the
Unilog column and *records the disagreement* rather than quietly picking one.
Their guide notes the delivery file contains at least one row where manufacturer
and brand look mismatched, and says noticing that is a strength.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..models import RawProduct

# Their placeholders are all of the form `-- text --`. Matching the shape rather
# than the three known strings means a fourth spelling cannot slip through as a
# real value.
_PLACEHOLDER = re.compile(r"^\s*-{2,}\s*.*?\s*-{2,}\s*$")

# Column name -> the field it feeds. Spellings are folded, so `Mfg_Part_Num`,
# `mfg part num` and `MFG-PART-NUM` all land in the same place.
COLUMNS: dict[str, str] = {
    "mfg part num": "mpn",
    "mfg part number": "mpn",
    "manufacturer part number": "mpn",
    "mpn": "mpn",
    "part desc": "description",
    "part description": "description",
    "description": "description",
    "e1 brand": "brand_e1",
    "unilog brand": "brand_unilog",
    "dib brand": "brand_dib",
    "part manuf": "manufacturer",
    "part manufacturer": "manufacturer",
    "manufacturer": "manufacturer",
    "sku": "sku",
    "dept": "dept",
    "class": "class",
    "fine": "fine",
}

# Unilog's own column wins when the three disagree: it is the one they curate.
BRAND_PRECEDENCE = ("brand_unilog", "brand_e1", "brand_dib")


@dataclass
class RowReport:
    """What the adapter did with one row, so the UI can show its working."""

    source: str = "catalogue row"
    placeholders_dropped: list[str] = field(default_factory=list)
    brand_source: str | None = None
    unmapped_columns: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "placeholders_dropped": self.placeholders_dropped,
            "brand_source": self.brand_source,
            "unmapped_columns": self.unmapped_columns,
            "notes": self.notes,
        }


def _fold(name: str) -> str:
    return re.sub(r"[\s_\-]+", " ", str(name or "").strip().lower())


def is_placeholder(value: Any) -> bool:
    """True for `-- Unbranded --` and its siblings."""
    if value is None:
        return False
    text = str(value).strip()
    return bool(text) and bool(_PLACEHOLDER.match(text))


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def from_row(row: dict[str, Any]) -> tuple[RawProduct, RowReport]:
    """Turn one catalogue row into a RawProduct."""
    report = RowReport()
    values: dict[str, str] = {}

    for column, raw_value in row.items():
        target = COLUMNS.get(_fold(column))
        text = _clean(raw_value)
        if target is None:
            if text:
                report.unmapped_columns.append(str(column))
            continue
        if is_placeholder(text):
            report.placeholders_dropped.append(f"{column} = {text}")
            continue
        if text:
            values[target] = text

    brand = ""
    for candidate in BRAND_PRECEDENCE:
        if values.get(candidate):
            brand = values[candidate]
            report.brand_source = candidate
            break

    supplied_brands = {
        column: values[column] for column in BRAND_PRECEDENCE if values.get(column)
    }
    distinct = {v.casefold() for v in supplied_brands.values()}
    if len(distinct) > 1:
        report.notes.append(
            "Brand columns disagree ("
            + "; ".join(f"{k.replace('brand_', '')}={v}" for k, v in supplied_brands.items())
            + f"). Took the {report.brand_source.replace('brand_', '')} value; "
            "the others are recorded for review."
        )

    manufacturer = values.get("manufacturer", "")
    if not brand and manufacturer:
        # Their rule: where an item has no brand, the manufacturer name is used.
        brand = manufacturer
        report.brand_source = "manufacturer"
        report.notes.append(
            "No brand supplied; used the manufacturer name, per the content standard."
        )

    if brand and manufacturer and brand.casefold() != manufacturer.casefold():
        report.notes.append(
            f"Brand '{brand}' and manufacturer '{manufacturer}' differ. Legitimate for "
            "a house brand, but worth confirming against the approved list."
        )

    hint = " > ".join(
        values[k] for k in ("dept", "class", "fine") if values.get(k)
    )

    product = RawProduct(
        sku=values.get("sku") or None,
        mpn=values.get("mpn") or None,
        brand=brand or None,
        # The abbreviated part description is all the naming there is; it feeds
        # both the name and the free text so classification and prose extraction
        # each get a shot at it.
        name=values.get("description") or None,
        description=values.get("description") or None,
        free_text=values.get("description") or None,
        category_hint=hint or None,
        raw_specs={},
    )

    if manufacturer:
        product.raw_specs["Manufacturer"] = manufacturer
    for column in BRAND_PRECEDENCE:
        if column in supplied_brands and column != report.brand_source:
            product.raw_specs[column.replace("brand_", "").upper() + " Brand"] = (
                supplied_brands[column]
            )

    return product, report


def from_rows(rows: list[dict[str, Any]]) -> tuple[list[RawProduct], list[RowReport]]:
    products: list[RawProduct] = []
    reports: list[RowReport] = []
    for row in rows:
        product, report = from_row(row)
        products.append(product)
        reports.append(report)
    return products, reports

"""Ingest Unilog's own catalogue rows.

Their working files carry six columns — `Mfg_Part_Num`, `Part_Desc`, `E1_Brand`,
`Unilog_Brand`, `DIB_Brand`, `Part_Manuf` — and the labelled 200-item file adds
`Dept` / `Class` / `Fine` and `SKU`. This adapter turns one such row into the
same `RawProduct` every other input path produces, so a spreadsheet row earns
exactly the same provenance, validation and readiness scoring as a datasheet
page. No parallel pipeline.

Two behaviours are worth stating outright, because both are places where a
careless reader of this data would silently corrupt the catalogue.

**Placeholders are not brands.** `-- Unbranded --`, `-- No Unilog Brand --`,
`-- No DIB Brand --`, a bare `-` and `COMMODITY - UNBRANDED` all mean the field
is empty. Treated as text they would become a brand named "-- Unbranded --" in
27,000 approved-brand fuzzy matches, and the nearest match to a placeholder is
noise. Measured across their 1,000-row sample: `Unilog_Brand` is a placeholder
in **every** row, `E1_Brand` in 80% and `DIB_Brand` in 76%.

**`Part_Manuf` is a vendor, not the manufacturer.** This is the trap in the
file. It reads like a manufacturer and sometimes is one ("Freud Inc (2435)"),
but just as often it is the distributor the row was bought from ("Boise Cascade
Building Materials (BOICA)", "Appliance Dealers Cooperative (APPDE)"). Their own
delivery row proves it: `Part_Manuf` is "Appliance Dealers Cooperative (APPDE)"
while `MANUFACTURER_NAME` is "Rheem Manufacturing". So the column is carried as
a *vendor* and never written into manufacturer identity — that has to be
resolved against the approved manufacturer list or the source document, and
where it cannot be, the field stays empty rather than being filled with a
distributor's name.

**The brand usually lives in the description.** With the brand columns empty
four times out of five, "3M", "Diablo" and "TREX" are recoverable only from
`Part_Desc`. A leading token that matches a known brand is taken as one; nothing
else is guessed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..models import RawProduct
from ..pipeline.taxonomy import brand_index

# Most of their placeholders are of the form `-- text --`. Matching the shape
# rather than the three documented strings means a fourth spelling cannot slip
# through as a real value.
_PLACEHOLDER = re.compile(r"^\s*-{2,}\s*.*?\s*-{2,}\s*$")

# The two that do not follow that shape, both observed in their 1,000-row file.
_PLACEHOLDER_LITERALS = {"-", "--", "commodity - unbranded", "n/a", "none", "unbranded"}

# `Part_Manuf` values carry a vendor account code: "Freud Inc (2435)".
_VENDOR_CODE = re.compile(r"\s*\(([^()]{2,10})\)\s*$")

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
    "part manuf": "vendor",
    "part manufacturer": "vendor",
    "manufacturer name": "manufacturer",
    "sku": "sku",
    "sku my part number": "sku",
    "part number": "part_number",
    "dept": "dept",
    "class": "class",
    "fine": "fine",
}

# Unilog's own column would win if it ever carried a value; across their sample
# it never does, so in practice this resolves to E1 then DIB.
BRAND_PRECEDENCE = ("brand_unilog", "brand_e1", "brand_dib")


@dataclass
class RowReport:
    """What the adapter did with one row, so the UI can show its working."""

    source: str = "catalogue row"
    placeholders_dropped: list[str] = field(default_factory=list)
    brand_source: str | None = None
    vendor: str | None = None
    vendor_code: str | None = None
    unmapped_columns: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "placeholders_dropped": self.placeholders_dropped,
            "brand_source": self.brand_source,
            "vendor": self.vendor,
            "vendor_code": self.vendor_code,
            "unmapped_columns": self.unmapped_columns,
            "notes": self.notes,
        }


def _fold(name: str) -> str:
    return re.sub(r"[\s_\-]+", " ", str(name or "").strip().lower())


def is_placeholder(value: Any) -> bool:
    """True for `-- Unbranded --`, a bare `-`, and their siblings."""
    if value is None:
        return False
    text = str(value).strip()
    if not text:
        return False
    return bool(_PLACEHOLDER.match(text)) or text.lower() in _PLACEHOLDER_LITERALS


def split_vendor(value: str) -> tuple[str, str | None]:
    """'Freud Inc (2435)' -> ('Freud Inc', '2435')."""
    match = _VENDOR_CODE.search(value or "")
    if not match:
        return (value or "").strip(), None
    return value[: match.start()].strip(), match.group(1).strip()


def _brand_in_text(text: str) -> str | None:
    """The longest approved brand name appearing in the description, if any."""
    lowered = " " + re.sub(r"[^a-z0-9 ]", " ", (text or "").lower()) + " "
    best: tuple[int, str] | None = None
    for probe, entry in brand_index().items():
        if f" {probe} " in lowered and (best is None or len(probe) > best[0]):
            best = (len(probe), entry["canonical"])
    return best[1] if best else None


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

    if not brand and values.get("description"):
        # Four rows in five have no brand column at all, so the only place
        # "3M" or "Diablo" appears is the description. Only a name already on
        # the approved list counts; an unrecognised leading word is not
        # promoted to a brand on the strength of its position.
        found = _brand_in_text(values["description"])
        if found:
            brand = found
            report.brand_source = "part_desc"
            report.notes.append(
                f"No brand column had a value; recognised '{found}' in the "
                f"description against the approved brand list."
            )

    vendor, vendor_code = split_vendor(values.get("vendor", ""))
    if vendor:
        report.vendor = vendor
        report.vendor_code = vendor_code

    # Deliberately NOT derived from the vendor. Their own delivery row ships
    # Part_Manuf "Appliance Dealers Cooperative (APPDE)" against
    # MANUFACTURER_NAME "Rheem Manufacturing" — filling the manufacturer with a
    # distributor would put a false attribution in the catalog.
    manufacturer = values.get("manufacturer", "")
    if not manufacturer and vendor:
        report.notes.append(
            f"Manufacturer left empty: '{vendor}' is the supplying vendor, which "
            f"may or may not be the maker. It needs resolving against the "
            f"approved manufacturer list before it can be published."
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
        sku=values.get("sku") or values.get("part_number") or None,
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
    if vendor:
        # Carried so the delivery sheet can echo the column it came from, and so
        # a reviewer can see what the manufacturer was *not* inferred from.
        product.raw_specs["Vendor"] = vendor
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

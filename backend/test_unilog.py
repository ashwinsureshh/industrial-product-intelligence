"""Proves the Unilog content-standard layer behaves as claimed. Costs $0.

Each block below defends one specific claim that will otherwise be taken on
trust, and the interesting ones are the refusals:

  * a decimal that is not an exact 64th does not become a fraction
  * a unit outside the approved list does not reach published copy
  * a value outside the list of values is not rewritten to the nearest match
  * an over-length field loses whole tokens, not characters

A test that only checked the happy path would pass just as well against a
system that guessed, which is the failure mode this whole project exists to
rule out.
"""

from __future__ import annotations

import csv
import json
import sys
import tempfile
from pathlib import Path

SAMPLES = Path(__file__).resolve().parent / "data" / "unilog_samples"

from app.ingest.unilog_rows import from_row, is_placeholder
from app.models import Attribute, Provenance, RawProduct
from app.pipeline import run as pipeline
from app.providers.mock import MockProvider
from app.unilog import content_formats as CF
from app.unilog import house_style as HS
from app.unilog import lov

PASSED = 0
FAILED = 0


def check(label: str, condition: bool) -> bool:
    global PASSED, FAILED
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")
    if condition:
        PASSED += 1
    else:
        FAILED += 1
    return condition


def section(title: str) -> None:
    print(f"\n{title}")
    print("-" * len(title))


def attr(key, label, value, unit=None, provenance=Provenance.PARSED, group="General"):
    return Attribute(
        key=key, label=label, value=value, unit=unit, provenance=provenance,
        confidence=0.9, evidence="supplied in the source row.", method="test",
        group=group,
    )


# --------------------------------------------------------------- house style


def test_fractions() -> None:
    section("House style: decimal to trade fraction")

    check("0.5 renders as 1/2", HS.to_fraction(0.5) == "1/2")
    check("50.25 renders as 50-1/4", HS.to_fraction(50.25) == "50-1/4")
    check("the finest listed fraction 1/64 is exact", HS.to_fraction(0.015625) == "1/64")
    check("63/64 is exact", HS.to_fraction(0.984375) == "63/64")
    check("a whole number keeps no fraction", HS.to_fraction(3.0) == "3")
    check("negative values keep their sign", HS.to_fraction(-1.5) == "-1-1/2")

    # The refusal. 0.3 in is 19.2/64 - close to 19/64, and rounding it there
    # would publish a dimension the manufacturer never stated.
    check("0.3 is refused rather than rounded to 19/64", HS.to_fraction(0.3) is None)
    check("0.51 is refused", HS.to_fraction(0.51) is None)
    check(
        "a refused fraction keeps the decimal instead",
        HS.format_measure(0.3, "in") == "0.3 in",
    )
    check("fractions round-trip", HS.from_fraction("50-1/4") == 50.25)


def test_units() -> None:
    section("House style: approved units of measure")

    check("'inches' normalizes to 'in'", HS.approved_unit("inches").abbreviation == "in")
    check("'IN.' normalizes to 'in'", HS.approved_unit("IN.").abbreviation == "in")
    check('a bare quote normalizes to in', HS.approved_unit('"').abbreviation == "in")
    check("'volts' normalizes to 'V'", HS.approved_unit("volts").abbreviation == "V")

    check("number and unit are separated by a space", HS.format_measure(24, "inch") == "24 in")
    check("inches prefer the fraction form", HS.format_measure(50.25, "in") == "50-1/4 in")
    check("the invoice line may compact", HS.format_measure(50.25, "in", compact=True) == "50-1/4IN")

    # The refusal. An unrecognised unit must not be passed through: writing
    # '24 furlongs' would be non-compliant output dressed as a success.
    check("an unapproved unit is refused", HS.format_measure(24, "furlongs") is None)
    check("the table reports that it is provisional", HS.source() == "provisional")

    check(
        "title case leaves an MPN and an acronym intact",
        HS.title_case("PDSH4816AF dishwasher 1/2 npt") == "PDSH4816AF Dishwasher 1/2 NPT",
    )
    check(
        "the invoice line drops trademark symbols rather than uppercasing them",
        HS.upper_case("FRIGIDAIRE®") == "FRIGIDAIRE",
    )
    # Regression: a bracketed word read as neither title nor mixed case and was
    # flattened, publishing '2RS (rubber Sealed)' as a live product title.
    check(
        "casing survives inside brackets",
        HS.title_case("2RS (Rubber Sealed) seal type") == "2RS (Rubber Sealed) Seal Type",
    )


# ------------------------------------------------------------ content formats


def worked_example() -> CF.ContentContext:
    """Row 1 of their 200-item file, as far as the guide reproduces it."""
    return CF.ContentContext(
        brand="FRIGIDAIRE®",
        manufacturer="Rheem Manufacturing",
        mpn="PDSH4816AF",
        item_type="Dishwasher",
        attributes=[
            attr("feature", "Feature", "CleanBoost™"),
            attr("series", "Series", "Professional Series"),
            attr("mounting", "Mounting", "Leg"),
            attr("wash_cycles", "Wash Cycles", 5),
            attr("material", "Material", "Stainless Steel"),
            attr("voltage", "Voltage", 120, "V"),
            attr("current", "Current", 15, "A"),
            attr("depth_door_open", "Depth With Door Open", 50.25, "in"),
            attr("sound_level", "Sound Level", 47, "dBA"),
        ],
    )


def by_id(results):
    return {r.id: r for r in results}


def test_formats() -> None:
    section("Content formats: five fields, five limits")

    results = by_id(CF.build_all(worked_example()))

    invoice = results["invoice_desc"]
    check("invoice line is within 40 characters", invoice.length <= 40)
    check("invoice line is upper case", invoice.text == invoice.text.upper())
    check("invoice line abbreviates Stainless Steel to SST", "SST" in invoice.text)
    check("invoice line compacts units", "120V" in invoice.text)
    check("dropped tokens are named, not hidden", bool(invoice.dropped))

    mobile = results["mobile_desc"]
    check("mobile line lands in the 60-80 window", 60 <= mobile.length <= 80)

    title = results["product_title"]
    check(
        "title follows Brand + Series + MPN + Item Type",
        title.text.startswith("FRIGIDAIRE® Professional Series PDSH4816AF Dishwasher"),
    )
    check("title carries the feature clause", "With CleanBoost™" in title.text)
    check("an enum keeps its label", "Leg Mounting" in title.text)

    long = results["long_description"]
    check("long copy writes the inch dimension as a fraction", "50-1/4 in" in long.text)
    check("the unit alone names the quantity", "120 V," in long.text)
    check("no redundant label after the unit", "120 V Voltage" not in long.text)
    check("a terminal descriptor stands alone", "Stainless Steel Material" not in long.text)
    check("a non-obvious unit keeps its label", "47 dBA Sound Level" in long.text)


def test_length_policy() -> None:
    section("Content formats: overlong copy loses tokens, not characters")

    ctx = worked_example()
    spec = next(s for s in CF.formats() if s["id"] == "invoice_desc")
    invoice = CF.build(spec, ctx)
    unlimited = CF.build({**spec, "max_length": None}, ctx)

    # The precise claim: fitting removes whole tokens. Every word that survives
    # must appear in the unfitted line, so nothing was cut mid-word and nothing
    # new was invented to fill the space.
    check(
        "every word in the fitted line survives from the unfitted one",
        set(invoice.text.split()) <= set(unlimited.text.split()),
    )
    check("and the fitted line is genuinely shorter", invoice.length < unlimited.length)
    check("fitting alone is not reported as a breach", invoice.compliant is True)

    # Force the failure case: a required token that cannot fit on its own.
    long_type = CF.ContentContext(
        brand="B", mpn="M",
        item_type="Commercial Grade Heavy Duty Stainless Steel Built-In Dishwashing Appliance",
        attributes=[],
    )
    forced = by_id(CF.build_all(long_type))["invoice_desc"]
    check("a genuine overflow is reported, not absorbed", forced.compliant is False)
    check("the clip lands on a word boundary", not forced.text.endswith("DISHWASHIN"))
    check("the breach is explained", any("exceed" in n for n in forced.notes))

    thin = CF.ContentContext(brand="Acme", mpn="X1", item_type="Valve", attributes=[])
    short = by_id(CF.build_all(thin))["mobile_desc"]
    check("falling short of a minimum is reported", short.compliant is False)
    check(
        "and is not padded with invented text",
        "Acme" in short.text and len(short.text) < 60,
    )


def test_unapproved_unit_is_withheld() -> None:
    section("Content formats: an unapproved unit never reaches the copy")

    ctx = CF.ContentContext(
        brand="Acme", mpn="X1", item_type="Gauge",
        attributes=[attr("span", "Span", 12, "furlongs")],
    )
    result = by_id(CF.build_all(ctx))["long_description"]
    check("the value is absent from the copy", "12" not in result.text)
    check("the field is marked non-compliant", result.compliant is False)
    check(
        "and the reason names the unit",
        any("furlongs" in n for n in result.notes),
    )


# ------------------------------------------------------------------ vocabulary

CLASSPATH = "Plumbing > Pipe, Tube & Fittings > Pipe Fittings"


def test_lov_mapping() -> None:
    section("List of values: many supplier spellings, one approved value")

    check("an exact value is accepted", lov.resolve(CLASSPATH, "material", "Brass").method == "exact")
    check("case is corrected", lov.resolve(CLASSPATH, "material", "brass").value == "Brass")
    check("CPLG maps to Coupling", lov.resolve(CLASSPATH, "fitting_type", "CPLG").value == "Coupling")
    check("BRS maps to Brass", lov.resolve(CLASSPATH, "material", "BRS").value == "Brass")
    check("FNPT maps to Threaded", lov.resolve(CLASSPATH, "connection_type", "FNPT").value == "Threaded")
    check(
        "'Class 150' maps to 150#",
        lov.resolve(CLASSPATH, "pressure_class", "Class 150").value == "150#",
    )
    check(
        "an attribute with no vocabulary returns nothing to check",
        lov.resolve(CLASSPATH, "weight", "3 lb") is None,
    )
    check("the sequence comes from the list, not from extraction",
          lov.sequence(CLASSPATH)[:2] == ["fitting_type", "material"])
    check("filterable attributes are known", "material" in lov.filterable(CLASSPATH))


def test_lov_refusal() -> None:
    section("List of values: a near miss is proposed, never applied")

    typo = lov.resolve(CLASSPATH, "material", "Stainless Steal")
    check("an unlisted value is refused", typo.refused)
    check("no value is substituted", typo.value is None)
    check("the closest approved value is offered", typo.suggestion == "Stainless Steel")

    wrong = lov.resolve(CLASSPATH, "material", "Cast Steel")
    check(
        "a plausible-but-different material gets no suggestion",
        wrong.refused and wrong.suggestion is None,
    )

    attributes = [attr("material", "Material Construction", "Unobtanium")]
    updated, issues, ledger = lov.apply(attributes, CLASSPATH)
    check("the original value survives the refusal", updated[0].value == "Unobtanium")
    check("an integrity issue is raised", issues and issues[0].code == "LOV_VIOLATION")
    check("nothing is recorded as mapped", ledger == [])

    from app.pipeline.validate import INTEGRITY_CODES
    check(
        "and that issue blocks auto-publication",
        "LOV_VIOLATION" in INTEGRITY_CODES,
    )


def test_lov_ledger() -> None:
    section("List of values: every rewrite is auditable")

    attributes = [
        attr("fitting_type", "Fitting Type", "CPLG"),
        attr("material", "Material Construction", "BRS"),
        attr("pressure_class", "Pressure Class", "150#"),
    ]
    updated, issues, ledger = lov.apply(attributes, CLASSPATH)

    check("mapped values are rewritten", [a.value for a in updated[:2]] == ["Coupling", "Brass"])
    check("an already-approved value is not logged as a change", len(ledger) == 2)
    check(
        "the ledger records both ends of each mapping",
        {(m["from"], m["to"]) for m in ledger} == {("CPLG", "Coupling"), ("BRS", "Brass")},
    )
    check(
        "the rewrite is written into the attribute's own evidence",
        "Normalized to the approved value" in updated[0].evidence,
    )
    check("no issues are raised for clean mappings", issues == [])

    stats = lov.coverage(updated, CLASSPATH)
    check("coverage reports percent of values found in the list", stats["percent_in_lov"] == 100.0)
    check("an unknown classpath is reported as not applicable",
          lov.coverage(attributes, "Nowhere > At > All")["applicable"] is False)


# ---------------------------------------------------------------------- ingest


def test_row_ingest() -> None:
    section("Catalogue rows: placeholders are not data")

    check("'-- Unbranded --' is a placeholder", is_placeholder("-- Unbranded --"))
    check("'-- No DIB Brand --' is a placeholder", is_placeholder("-- No DIB Brand --"))
    check("a real brand is not", not is_placeholder("FRIGIDAIRE"))

    product, report = from_row({
        "Mfg_Part_Num": "PDSH4816AF",
        "Part_Desc": "PDSH4816AF Dishwasher SS - Display Only",
        "E1_Brand": "-- Unbranded --",
        "Unilog_Brand": "FRIGIDAIRE",
        "DIB_Brand": "-- No DIB Brand --",
        "Part_Manuf": "Appliance Dealers Cooperative (APPDE)",
        "SKU": "12345",
        "Dept": "Appliances & Consumer Electronics",
        "Class": "Kitchen Appliances",
        "Fine": "Built-In Dishwashers",
    })
    check("the Unilog brand column wins", product.brand == "FRIGIDAIRE")
    check("both placeholders were dropped", len(report.placeholders_dropped) == 2)
    check("no placeholder reached the record", "--" not in str(product.model_dump()))
    check(
        "Dept/Class/Fine become the classpath hint",
        product.category_hint == (
            "Appliances & Consumer Electronics > Kitchen Appliances > Built-In Dishwashers"
        ),
    )

    # The trap in their file: Part_Manuf reads like a manufacturer but their own
    # delivery row pairs "Appliance Dealers Cooperative (APPDE)" with
    # MANUFACTURER_NAME "Rheem Manufacturing".
    check("the vendor code is split off", report.vendor == "Appliance Dealers Cooperative")
    check("and kept", report.vendor_code == "APPDE")
    check(
        "the vendor is never promoted to manufacturer",
        product.raw_specs.get("Manufacturer") is None,
    )
    check(
        "and the empty manufacturer is explained, not silently blank",
        any("supplying vendor" in n for n in report.notes),
    )

    # Placeholders that do not follow the '-- text --' shape.
    _, report2 = from_row({
        "Mfg_Part_Num": "X1", "Part_Desc": "Widget",
        "E1_Brand": "-", "DIB_Brand": "COMMODITY - UNBRANDED",
        "Part_Manuf": "U S Lumber (3073)",
    })
    check("a bare hyphen is a placeholder", is_placeholder("-"))
    check("'COMMODITY - UNBRANDED' is a placeholder", is_placeholder("COMMODITY - UNBRANDED"))
    check("both were dropped", len(report2.placeholders_dropped) == 2)

    # Brand recovery from the description, since four rows in five have no
    # brand column. Only an approved name counts.
    known, report3 = from_row({
        "Mfg_Part_Num": "6205-2RS", "Part_Desc": "SKF 6205-2RS deep groove ball bearing",
        "E1_Brand": "-- Unbranded --",
    })
    check("an approved brand is recovered from the description", known.brand == "SKF")
    check("and the recovery is stated", any("description" in n for n in report3.notes))

    unknown, _ = from_row({
        "Mfg_Part_Num": "Z9", "Part_Desc": "Wumpus 12 in flange widget",
        "E1_Brand": "-- Unbranded --",
    })
    check(
        "an unrecognised leading word is not promoted to a brand",
        unknown.brand is None,
    )

    conflict, report3 = from_row({
        "Mfg_Part_Num": "X9", "Part_Desc": "Widget",
        "E1_Brand": "Acme", "Unilog_Brand": "ACME Inc", "DIB_Brand": "Acme Tools",
    })
    check("disagreeing brand columns are reported", any("disagree" in n for n in report3.notes))
    check("the losing columns are kept for review", len(conflict.raw_specs) >= 2)


# ------------------------------------------------------------------- end to end


def test_pipeline_integration() -> None:
    section("End to end: a catalogue row through the existing pipeline")

    product, _ = from_row({
        "Mfg_Part_Num": "6205-2RS", "Part_Desc": "6205-2RS deep groove ball bearing 25mm bore",
        "Unilog_Brand": "SKF", "E1_Brand": "-- Unbranded --",
        "MANUFACTURER_NAME": "SKF Group", "SKU": "BRG-1",
    })
    record = pipeline.enrich(product, MockProvider())

    check("the row classified", record.category is not None)
    check("a compliance report was produced", record.compliance is not None)
    # Four of their five delivery fields are prose built here; the fifth is the
    # attribute list itself, which the export profile renders from the record.
    check("every configured format was built", len(record.compliance.fields) == len(CF.formats()))
    check(
        "the manufacturer column survived into identity",
        record.identity.get("manufacturer") == "SKF Group",
    )
    check(
        "the report names which standard backed it",
        record.compliance.standards.get("uom") == "provisional",
    )
    check(
        "a vocabulary stage ran and traced itself",
        any(s.stage == "vocabulary" for s in record.trace),
    )
    check(
        "compliance is scored separately from readiness",
        record.readiness is not None and hasattr(record.compliance, "verdict"),
    )

    # The separation that keeps the published benchmark honest: a character
    # limit breach must not move a data-quality score.
    codes = {i.code for i in record.issues}
    check("no content-format issue leaks into data validation",
          "CONTENT_FORMAT_BREACH" not in codes)


def test_lov_is_inert_without_a_matching_classpath() -> None:
    section("Regression guard: the vocabulary cannot silently rewrite the corpus")

    product = RawProduct(
        mpn="6205-2RS", brand="SKF", name="Deep groove ball bearing",
        raw_specs={"Bore": "25 mm", "Outer Diameter": "52 mm"},
    )
    record = pipeline.enrich(product, MockProvider())
    check(
        "no vocabulary applies to a curated industrial category",
        record.compliance.lov.get("applicable") is False,
    )
    check("so nothing was remapped", record.compliance.vocabulary_mappings == [])


def test_profile_is_data() -> None:
    section("Delivery format: their 252 columns are a profile, not code")

    from app.export import profiles

    product, _ = from_row({
        "Mfg_Part_Num": "6205-2RS", "Part_Desc": "6205-2RS deep groove ball bearing 25mm bore",
        "Unilog_Brand": "SKF", "MANUFACTURER_NAME": "SKF Group", "SKU": "BRG-1",
    })
    record = pipeline.enrich(product, MockProvider())

    header, rows = profiles.to_rows(profiles.get("unilog_delivery"), [record])
    row = dict(zip(header, rows[0]))

    # The decisive check: byte-identical column names, in their order. Their
    # importer is positional, so a profile that is merely close is broken.
    with open(SAMPLES / "delivery_expected.csv", encoding="utf-8-sig", newline="") as fh:
        theirs = next(csv.reader(fh))
    check("the header matches their sheet exactly", header == theirs)
    check("252 columns", len(header) == 252)
    check("every row is the same width as the header", len(rows[0]) == len(header))

    check("the MPN comes through", row["Mfg_Part_Num"] == "6205-2RS")
    check("the manufacturer column is populated", row["MANUFACTURER_NAME"] == "SKF Group")
    check("a house-style field is addressable by id", row["SHORT_DESC"] != "")
    check(
        "the classpath uses their separator, with no spaces",
        ">" in row["Classpath"] and " > " not in row["Classpath"],
    )
    check(
        "attributes fill numbered triplet slots",
        row["ATTRIBUTE_LABEL 1"] != "" and row["ATTRIBUTE_VALUE 1"] != "",
    )
    measured = next(
        (i for i in range(1, 51) if row[f"ATTRIBUTE_UOM {i}"]), None
    )
    check("at least one attribute carries a unit", measured is not None)
    check(
        "value and unit stay in separate columns",
        measured is not None
        and row[f"ATTRIBUTE_UOM {measured}"] not in str(row[f"ATTRIBUTE_VALUE {measured}"]),
    )
    check(
        "the value column is house-styled, not a raw float",
        measured is not None and str(row[f"ATTRIBUTE_VALUE {measured}"]) == "25",
    )
    # Their sheet is positional: unfilled slots must still be present.
    check("empty slots are emitted, not skipped", row["ATTRIBUTE_LABEL 50"] == "")

    # The claim: a new customer column is a JSON edit. Prove it at runtime.
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "runtime_customer.json"
        path.write_text(json.dumps({
            "id": "runtime_customer",
            "label": "Added at runtime",
            "format": "csv",
            "fields": [
                {"target": "Their Part Code", "from": "identity.mpn"},
                {"target": "Their Till Line", "from": "field:invoice_desc"},
                {"target": "Their QA Flag", "from": "compliance.verdict"},
            ],
        }), encoding="utf-8")

        original = profiles.PROFILE_DIR
        try:
            profiles.PROFILE_DIR = Path(tmp)
            profiles.invalidate()
            header2, rows2 = profiles.to_rows(profiles.get("runtime_customer"), [record])
            check("a schema added at runtime renders with no code change",
                  header2 == ["Their Part Code", "Their Till Line", "Their QA Flag"])
            check("and pulls a formula-built field", rows2[0][1] != "")
        finally:
            profiles.PROFILE_DIR = original
            profiles.invalidate()


def test_ground_truth_reports_both_states() -> None:
    section("Ground truth: both numbers, or the claim is an overstatement")

    from app.unilog import ground_truth as gt

    check("their labelled rows are bundled with the app", gt.available())
    result = gt.compare()
    s = result["summary"]

    check("both rows are scored", s["rows"] == 2)
    check("every prose field is scored", s["fields_scored"] == 14)

    # State A: the formatter, handed the attribute values from their own row.
    check(
        "given the attribute values, the formatter is exact",
        s["exact_given_attributes"] == s["fields_scored"],
    )
    # State B: the real pipeline, from the six-column catalogue row.
    check(
        "from the input row alone it is not, and the number says so",
        0 < s["exact_from_input_row"] < s["fields_scored"],
    )
    # The guard that matters: A can never be published without B beside it.
    check(
        "both states are always present in the payload",
        "exact_given_attributes" in s and "exact_from_input_row" in s,
    )
    check(
        "and every field carries both comparisons",
        all("from_input_row" in f and "given_attributes" in f
            for c in result["cases"] for f in c["fields"]),
    )

    invoice = next(f for f in result["cases"][0]["fields"]
                   if f["column"] == "INVOICE_DESC")
    check(
        "their expected invoice line is carried verbatim for display",
        invoice["expected"] == "DISHWASHER LEG 5 SST 120V 15A 50-1/4IN",
    )
    check("and ours matches it character for character", invoice["match_given"])
    check(
        "while the input row alone yields only the item type",
        invoice["from_input_row"] == "DISHWASHER" and not invoice["match_from_input"],
    )


def main() -> int:
    print("=" * 66)
    print("  UNILOG CONTENT STANDARD TESTS - no API calls, $0.00")
    print("=" * 66)

    test_fractions()
    test_units()
    test_formats()
    test_length_policy()
    test_unapproved_unit_is_withheld()
    test_lov_mapping()
    test_lov_refusal()
    test_lov_ledger()
    test_row_ingest()
    test_pipeline_integration()
    test_lov_is_inert_without_a_matching_classpath()
    test_profile_is_data()
    test_ground_truth_reports_both_states()

    print()
    print("=" * 66)
    if FAILED:
        print(f"  {FAILED} CHECK(S) FAILED ({PASSED} passed)")
        return 1
    print(f"  ALL UNILOG CONTENT STANDARD CHECKS PASSED ({PASSED})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

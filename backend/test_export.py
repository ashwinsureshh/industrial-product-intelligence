"""Proves the output schema is data, not code. Costs $0 - no API calls.

The claim this defends: when Unilog supplies their format, adopting it is a
JSON file, not an exporter rewrite. So the decisive test writes a brand new
profile to disk at runtime and renders through it without touching Python.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from app.export import profiles
from app.models import RawProduct
from app.pipeline import run as pipeline
from app.providers.mock import MockProvider

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


def sample_record():
    product = RawProduct(
        sku="BRG-6205-2RS", mpn="6205-2RS", brand="skf",
        name="Deep groove ball bearing",
        raw_specs={"Bore": "25 mm", "Outer Diameter": "52 mm"},
        source_url="https://example.com/6205",
        source_document="https://example.com/6205",
    )
    return pipeline.enrich(product, MockProvider())


def main() -> int:
    print("=" * 64)
    print("  EXPORT PROFILE TESTS - no API calls, $0.00")
    print("=" * 64)

    record = sample_record()

    print("\n[installed profiles]")
    installed = {p["id"] for p in profiles.available()}
    check("catalog_csv is installed", "catalog_csv" in installed)
    check("schema_org is installed", "schema_org" in installed)
    check("an unknown profile is refused, not guessed",
          _raises(lambda: profiles.get("no_such_profile")))

    print("\n[catalog CSV]")
    spec = profiles.get("catalog_csv")
    header, rows = profiles.to_rows(spec, [record])
    row = dict(zip(header, rows[0]))
    check("one row per product", len(rows) == 1)
    check("identity is mapped", row.get("sku") == "BRG-6205-2RS")
    check("category path is flattened to a string",
          isinstance(row.get("category_path"), str) and ">" in row["category_path"])
    check("every attribute carries provenance",
          "bore_diameter.provenance" in header)
    check("every attribute carries a source column",
          "bore_diameter.source_url" in header)
    check("the source column holds the page it was read from",
          row.get("bore_diameter.source_url") == "https://example.com/6205")

    print("\n[schema.org JSON-LD]")
    spec = profiles.get("schema_org")
    doc = profiles.to_documents(spec, [record])[0]
    check("declares the schema.org context", doc.get("@context") == "https://schema.org")
    check("is typed as a Product", doc.get("@type") == "Product")
    check("carries identity", doc.get("mpn") == "6205-2RS")
    props = doc.get("additionalProperty", [])
    check("attributes become PropertyValue entries", len(props) > 0)
    check("each is typed", all(p.get("@type") == "PropertyValue" for p in props))
    check("units travel with values",
          any(p.get("unitText") for p in props))
    cited = [p for p in props if p.get("url")]
    check("document-sourced properties carry their URL", len(cited) > 0)
    check("the whole document is JSON-serialisable",
          isinstance(json.dumps(doc), str))

    print("\n[a schema this code has never seen]")
    # The real claim: a new target format is a file, not a commit.
    with tempfile.TemporaryDirectory() as tmp:
        custom = {
            "id": "unilog_mock",
            "label": "Pretend customer schema",
            "format": "csv",
            "fields": [
                {"target": "ItemNumber", "from": "input.sku"},
                {"target": "ManufacturerPart", "from": "identity.mpn"},
                {"target": "BoreMM", "from": "attr:bore_diameter.value"},
                {"target": "BoreSource", "from": "attr:bore_diameter.source_url"},
                {"target": "Status", "from": "readiness.verdict"},
            ],
        }
        path = Path(tmp) / "unilog_mock.json"
        path.write_text(json.dumps(custom), encoding="utf-8")

        original = profiles.PROFILE_DIR
        profiles.PROFILE_DIR = Path(tmp)
        profiles.invalidate()
        try:
            spec = profiles.get("unilog_mock")
            header, rows = profiles.to_rows(spec, [record])
            row = dict(zip(header, rows[0]))
            check("renders through a profile added at runtime",
                  header == ["ItemNumber", "ManufacturerPart", "BoreMM",
                             "BoreSource", "Status"])
            check("maps a single attribute to a customer field name",
                  float(row["BoreMM"]) == 25.0)
            check("maps that attribute's citation alongside it",
                  row["BoreSource"] == "https://example.com/6205")
            check("no attribute block means no extra columns",
                  len(header) == 5)
        finally:
            profiles.PROFILE_DIR = original
            profiles.invalidate()

    print()
    print("=" * 64)
    if FAILED:
        print(f"  {FAILED} CHECK(S) FAILED ({PASSED} passed)")
        return 1
    print(f"  ALL EXPORT PROFILE CHECKS PASSED ({PASSED})")
    return 0


def _raises(fn) -> bool:
    try:
        fn()
    except profiles.ProfileError:
        return True
    except Exception:  # noqa: BLE001
        return False
    return False


if __name__ == "__main__":
    sys.exit(main())

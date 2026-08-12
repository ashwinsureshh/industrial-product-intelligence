"""Regressions for three defects a QA pass found on the deployed build.

All three broke the same promise from different directions: the engine would
rather leave a field blank than state something it cannot defend.

  1. A part number's own standard could not contradict a supplied dimension,
     because the knowledge base was only ever consulted to fill gaps. A bearing
     marked 6205 published a 30 mm bore at 99% confidence while citing ISO 15
     for the two dimensions either side of it.
  2. Approving a learned category did not change the answer for a product
     already in the cache, so the learning loop failed for the very product
     used to teach it.
  3. The manufacturer-only sourcing rule was enforced on the discovery path but
     not on the URL ingest path beside it.
  4. A space-aligned datasheet had its values sliced through a token, because
     pdfplumber infers column edges across the whole page and one wide title
     line dragged an edge into the value column.

Costs $0: deterministic engine, no network.
"""

from __future__ import annotations

import sys

from app.models import RawProduct
from app.pipeline import run
from app.providers.mock import MockProvider

PROVIDER = MockProvider()


def check(label: str, condition: bool) -> bool:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")
    return condition


def enrich(**kwargs):
    return run.enrich(RawProduct(**kwargs), PROVIDER)


def issue(result, code):
    return next((i for i in result.issues if i.code == code), None)


def value_of(result, key):
    return next((a for a in result.attributes if a.key == key), None)


# --------------------------------------------------------------- 1. standards
def test_standard_contradicts_supplier() -> bool:
    print("\n[1] a designation may contradict a supplied dimension")
    ok = True

    bad = enrich(sku="D1", mpn="6205", brand="SKF", name="Deep groove ball bearing",
                 raw_specs={"Bore": "30 mm", "Outer Diameter": "52 mm", "Width": "15 mm"})
    flag = issue(bad, "STANDARD_CONTRADICTION")
    bore = value_of(bad, "bore_diameter")

    ok &= check("the contradiction is reported", flag is not None)
    ok &= check("and names both numbers",
                flag is not None and "30 mm" in flag.message and "25 mm" in flag.message)
    ok &= check("the record cannot auto-publish", bad.readiness.verdict != "publish")
    # The supplier may hold a variant the table does not cover. Keeping their
    # value is the point: this is a flag, not a correction.
    ok &= check("the supplier's value is kept, not overwritten", bore.value == 30.0)
    ok &= check("but its confidence is reduced", bore.confidence < 0.99)
    ok &= check("and the evidence says the standard disagrees",
                "25 mm" in bore.evidence)

    good = enrich(sku="OK", mpn="6205", brand="SKF", name="Deep groove ball bearing",
                  raw_specs={"Bore": "25 mm", "Outer Diameter": "52 mm", "Width": "15 mm"})
    ok &= check("a record that agrees with the standard is untouched",
                issue(good, "STANDARD_CONTRADICTION") is None
                and good.readiness.verdict == "publish"
                and value_of(good, "bore_diameter").confidence == 0.99)

    # The headline demo supplies no dimensions at all; the standard fills them
    # and must not then be reported as disagreeing with itself.
    sparse = enrich(sku="BRG-6205-2RS", mpn="6205-2RS", brand="skf",
                    name="Deep groove ball bearing")
    ok &= check("the sparse headline case still publishes from ISO 15 alone",
                issue(sparse, "STANDARD_CONTRADICTION") is None
                and sparse.readiness.verdict == "publish"
                and value_of(sparse, "bore_diameter").value == 25)

    # Rounding is not a contradiction.
    rounded = enrich(sku="R", mpn="6205", brand="SKF", name="Deep groove ball bearing",
                     raw_specs={"Bore": "25.0 mm", "Outer Diameter": "52 mm", "Width": "15 mm"})
    ok &= check("25.0 is not treated as contradicting 25",
                issue(rounded, "STANDARD_CONTRADICTION") is None)

    # Nor is the same dimension stated in another unit.
    imperial = enrich(sku="I", mpn="6205", brand="SKF", name="Deep groove ball bearing",
                      raw_specs={"Bore": "0.9843 in", "Outer Diameter": "52 mm",
                                 "Width": "15 mm"})
    ok &= check("0.9843 in is not treated as contradicting 25 mm",
                issue(imperial, "STANDARD_CONTRADICTION") is None)

    # The regression this check exists for: a designation mentioned in prose is
    # not the part's own designation, and must never accuse the supplier. A
    # correct 6305 was charged with contradicting 6205's dimensions because the
    # description said "replaces the older 6205".
    cross_talk = enrich(sku="X", mpn="6305", brand="SKF", name="Deep groove ball bearing",
                        description="Replaces the older 6205 in this housing.",
                        raw_specs={"Bore": "25 mm", "Outer Diameter": "62 mm",
                                   "Width": "17 mm"})
    ok &= check("a series named only in prose raises no contradiction",
                issue(cross_talk, "STANDARD_CONTRADICTION") is None
                and cross_talk.readiness.verdict == "publish")

    # But prose is still good enough to fill a blank: that is a suggestion, not
    # a charge, and it is where the 6205 recall in §7 comes from.
    prose_gap = enrich(sku="P", mpn="HOUSE-CODE-9", brand="SKF",
                       name="Deep groove ball bearing 6205")
    ok &= check("a series named only in prose still fills gaps",
                value_of(prose_gap, "bore_diameter") is not None
                and value_of(prose_gap, "bore_diameter").value == 25)
    prose_conflict = enrich(sku="P2", mpn="HOUSE-CODE-9", brand="SKF",
                            name="Deep groove ball bearing 6205",
                            raw_specs={"Bore": "30 mm", "Outer Diameter": "52 mm",
                                       "Width": "15 mm"})
    ok &= check("...but does not contradict a supplied value",
                issue(prose_conflict, "STANDARD_CONTRADICTION") is None)

    from app.pipeline import validate
    ok &= check("the code counts as an integrity warning, so it blocks auto-publish",
                "STANDARD_CONTRADICTION" in validate.INTEGRITY_CODES)
    return ok


# ------------------------------------------------------------------- 2. cache
def test_cache_follows_the_taxonomy() -> bool:
    print("\n[2] the cache key follows the learned taxonomy")
    ok = True
    from app import cache

    payload = {"mpn": "PC-1", "name": "Double acting pneumatic cylinder"}
    baseline = cache.key_for(payload, "demo")

    # Nothing learned: the key must be exactly what it has always been, or the
    # 20 precomputed live results and 102 committed benchmark records orphan.
    ok &= check("no learned categories means no fingerprint at all",
                cache.taxonomy_fingerprint() == "")

    import hashlib
    import json as _json
    blob = _json.dumps(payload, sort_keys=True, default=str)
    legacy = hashlib.sha256(
        f"demo|deterministic|{blob}".encode("utf-8")
    ).hexdigest()[:32]
    ok &= check("and the key is byte-identical to the pre-fix scheme",
                baseline == legacy)

    # With a category in force the key must move, or an approval cannot change
    # an answer that is already cached.
    real = cache.taxonomy_fingerprint
    cache.taxonomy_fingerprint = lambda: "abc12345"
    try:
        shifted = cache.key_for(payload, "demo")
    finally:
        cache.taxonomy_fingerprint = real

    ok &= check("approving a category changes the key", shifted != baseline)
    ok &= check("and reverting the taxonomy restores it",
                cache.key_for(payload, "demo") == baseline)
    return ok


# ------------------------------------------------------------------ 3. policy
def test_marketplaces_refused_on_every_path() -> bool:
    print("\n[3] the manufacturer-only rule holds on the ingest path too")
    ok = True
    from app.discovery import policy

    for url, kind in [("https://www.amazon.com/dp/B00ABCDEF", "marketplace"),
                      ("https://www.ebay.com/itm/123", "marketplace"),
                      ("https://www.grainger.com/product/SKF-6205", "distributor"),
                      ("https://www.homedepot.com/p/12345", "retailer")]:
        got = policy.blocked_kind(url)
        ok &= check(f"{url.split('/')[2]} is refused as a {kind}", got == kind)

    # A marketplace does not stop being one at another TLD, and the blocked
    # list is written in .com. amazon.co.uk sailed through a policy whose whole
    # purpose is to exclude marketplaces.
    for url in ["https://www.amazon.co.uk/dp/X", "https://www.amazon.de/dp/X",
                "https://amazon.com.au/dp/X", "https://www.ebay.co.uk/itm/1"]:
        ok &= check(f"{url.split('/')[2]} is refused at its country domain",
                    policy.blocked_kind(url) == "marketplace")

    # ...without swallowing everything that merely contains the word.
    for url in ["https://amazonaws.com/bucket/file",
                "https://my-amazon-supplier.com/parts",
                "https://www.skf.com/productinfo/6205-2RS"]:
        ok &= check(f"{url.split('/')[2]} is not mistaken for a marketplace",
                    policy.blocked_kind(url) is None)

    ok &= check("a manufacturer's own page is still allowed",
                policy.blocked_kind("https://www.skf.com/productinfo/6205-2RS") is None)
    # Narrower than check() by design: a person pasting their supplier's page
    # is asserting provenance the engine cannot verify, and refusing every
    # unrecognised domain would leave the Document tab able to read nothing.
    ok &= check("an unrecognised domain is not blocked on this path",
                policy.blocked_kind("https://some-supplier.example.com/part/6205") is None)
    ok &= check("a malformed URL does not raise",
                policy.blocked_kind("not a url") is None)
    return ok


# --------------------------------------------------------------- 4. PDF columns
def _lines_pdf(lines: list[str]) -> bytes:
    """A monospaced page of exactly these lines, positions preserved."""
    import io

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setFont("Courier", 10)
    y = 760
    for line in lines:
        c.drawString(60, y, line)
        y -= 15
    c.showPage()
    c.save()
    return buffer.getvalue()


def _spaced_pdf(title: str, rows: list[tuple[str, str]]) -> bytes:
    """A whitespace-aligned datasheet with a wide title line above the table.

    The title is the whole point: it is what dragged pdfplumber's inferred
    column edge across the values below it.
    """
    import io

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(70, 780, title)
    c.setFont("Courier", 10)
    y = 720
    c.drawString(70, y, f"{'CHARACTERISTIC':<30} VALUE")
    for key, value in rows:
        y -= 16
        c.drawString(70, y, f"{key:<30} {value}")
    c.showPage()
    c.save()
    return buffer.getvalue()


def test_space_aligned_columns_are_not_clipped() -> bool:
    print("\n[4] a space-aligned datasheet keeps whole values")
    ok = True
    from app.ingest.pdf import from_pdf

    rows = [("Bore Diameter", "25 mm"), ("Outer Diameter", "52 mm"),
            ("Width", "15 mm"), ("Dynamic Load Rating", "14.0 kN"),
            ("Limiting Speed", "16000 rpm"), ("Ring Material", "Chrome Steel")]
    product, report = from_pdf(
        _spaced_pdf("Datasheet B - space aligned, no rules", rows), "spaced.pdf")
    specs = product.raw_specs

    ok &= check("every row is recovered", len(specs) >= len(rows))
    # The three that used to come back as '14.0 k', '16000' and 'Chrome'.
    for key, value in [("Dynamic Load Rating", "14.0 kN"),
                       ("Limiting Speed", "16000 rpm"),
                       ("Ring Material", "Chrome Steel")]:
        ok &= check(f"{key} survives whole ({value})", specs.get(key) == value)

    ok &= check("no key is invented from the title line",
                not any("Datasheet" in k for k in specs))
    ok &= check("the column reader is what read it",
                "text:columns" in report.strategies_used)
    ok &= check("every value cites the page it came from",
                all(v == "page 1" for v in product.spec_sources.values()))

    # Right-aligned numeric columns are as common as left-aligned ones, and a
    # right-aligned column shares its end, not its start.
    ragged, ragged_report = from_pdf(_lines_pdf([
        "Bore Diameter                     25 mm",
        "Outer Diameter                    52 mm",
        "Dynamic Load Rating           14.0 kN",
        "Limiting Speed               16000 rpm",
    ]), "ragged.pdf")
    ok &= check("a right-aligned value column is read",
                ragged.raw_specs.get("Dynamic Load Rating") == "14.0 kN"
                and ragged.raw_specs.get("Limiting Speed") == "16000 rpm")

    # A unit in its own column belongs to the value; "16000" with no rpm is a
    # different fact from "16000 rpm".
    three, _ = from_pdf(_lines_pdf([
        "PARAMETER                      VALUE      UNIT",
        "Bore Diameter                  25         mm",
        "Outer Diameter                 52         mm",
        "Limiting Speed                 16000      rpm",
    ]), "three.pdf")
    ok &= check("a trailing unit column is joined to the value",
                three.raw_specs.get("Limiting Speed") == "16000 rpm")
    ok &= check("and the header row is not read as a spec",
                not any(k.lower() == "parameter" for k in three.raw_specs))

    # ...but only a real unit. A "short alphabetic token" rule joined a NOTES
    # column onto the value, turning a clean 25 mm into '25 mm typical', which
    # then failed numeric parsing and blocked a perfectly read record.
    notes, _ = from_pdf(_lines_pdf([
        "PARAMETER                      VALUE      NOTES",
        "Bore Diameter                  25 mm      typical",
        "Outer Diameter                 52 mm      nominal",
        "Width                          15 mm      measured",
    ]), "notes.pdf")
    ok &= check("a third column that is not a unit is left alone",
                notes.raw_specs.get("Bore Diameter") == "25 mm")

    # The guard that matters: prose must not become a spec table. Two words
    # with a wide gap happen everywhere; a column is the same gap repeatedly.
    # This is the documented 'Single Row D' -> 'eep Groove Ball' failure, and
    # the reason pdfplumber's page-wide inference no longer runs at all.
    prose, _ = from_pdf(_lines_pdf([
        "Deep Groove Ball Bearings            Product Family",
        "These bearings are supplied sealed   or open",
        "Consult engineering before use       in high loads",
        "All dimensions conform to the        relevant standards",
    ]), "prose.pdf")
    ok &= check("a page of prose yields no invented specs", not prose.raw_specs)
    return ok


def main() -> int:
    print("=" * 66)
    print("  QA FIX REGRESSIONS")
    print("=" * 66)
    results = [
        test_standard_contradicts_supplier(),
        test_cache_follows_the_taxonomy(),
        test_marketplaces_refused_on_every_path(),
        test_space_aligned_columns_are_not_clipped(),
    ]
    print("\n" + "=" * 66)
    if all(results):
        print("  ALL QA FIX REGRESSIONS PASS")
        return 0
    print("  FAILURES ABOVE")
    return 1


if __name__ == "__main__":
    sys.exit(main())

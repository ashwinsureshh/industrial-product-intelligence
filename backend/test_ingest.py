"""Generates realistic supplier datasheets and proves the ingest layer reads them.

Costs nothing — the demo engine handles enrichment, so this exercises the whole
document -> RawProduct -> pipeline path with no API calls.

Three datasheet layouts are generated because real suppliers use all three and
each defeats a different extraction strategy:

  1. ruled     — bordered spec table          (pdfplumber `lines`)
  2. ruleless  — columns held apart by spaces (pdfplumber `text`)
  3. leaders   — "Label ..... value" list     (line-level regex, not a table)
"""

from __future__ import annotations

import io
import sys

from app.ingest.pdf import from_pdf
from app.ingest.web import from_html
from app.models import RawProduct
from app.pipeline import run as pipeline
from app.providers.mock import MockProvider

FAILURES: list[str] = []

SPECS = [
    ("Bore Diameter", "25 mm"),
    ("Outer Diameter", "52 mm"),
    ("Width", "15 mm"),
    ("Dynamic Load Rating", "14 kN"),
    ("Static Load Rating", "7.8 kN"),
    ("Limiting Speed", "16000 rpm"),
    ("Cage Material", "Steel"),
    ("Seal Type", "2RS"),
]


def check(condition: bool, message: str) -> None:
    print(f"  {'PASS' if condition else 'FAIL'}: {message}")
    if not condition:
        FAILURES.append(message)


def _canvas(build) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as rl_canvas

    buffer = io.BytesIO()
    c = rl_canvas.Canvas(buffer, pagesize=A4)
    build(c)
    c.save()
    return buffer.getvalue()


def make_ruled_pdf() -> bytes:
    """A bordered table — the easiest case, and the most common in real PDFs."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("SKF Technical Datasheet", styles["Heading2"]),
        Paragraph("Deep Groove Ball Bearing, Sealed", styles["Heading1"]),
        Paragraph("Part Number: 6205-2RS", styles["Normal"]),
        Spacer(1, 18),
    ]
    data = [["Parameter", "Value"]] + [list(p) for p in SPECS]
    table = Table(data, colWidths=[220, 220])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.75, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
    ]))
    story.append(table)
    doc.build(story)
    return buffer.getvalue()


def make_ruleless_pdf() -> bytes:
    """Columns separated by whitespace only — no borders anywhere."""
    def build(c):
        c.setFont("Helvetica-Bold", 15)
        c.drawString(60, 780, "FAG Rolling Bearing Data")
        c.setFont("Helvetica", 12)
        c.drawString(60, 758, "Deep Groove Ball Bearing 6205 2RS")
        c.drawString(60, 738, "Model No: 6205-2RS")
        c.setFont("Helvetica-Bold", 10)
        c.drawString(60, 700, "Parameter")
        c.drawString(300, 700, "Value")
        c.setFont("Helvetica", 10)
        y = 680
        for key, value in SPECS:
            c.drawString(60, y, key)
            c.drawString(300, y, value)
            y -= 20
    return _canvas(build)


def make_leader_pdf() -> bytes:
    """Dot-leader list — not a table at all."""
    def build(c):
        c.setFont("Helvetica-Bold", 15)
        c.drawString(60, 780, "NSK Bearing Specification Sheet")
        c.setFont("Helvetica", 12)
        c.drawString(60, 756, "Single Row Deep Groove Ball Bearing")
        c.drawString(60, 736, "Catalog No: 6205-2RS")
        c.setFont("Helvetica", 11)
        y = 700
        for key, value in SPECS:
            dots = "." * max(4, 46 - len(key) - len(value))
            c.drawString(60, y, f"{key} {dots} {value}")
            y -= 20
    return _canvas(build)


PRODUCT_HTML = """
<!doctype html><html><head>
<title>6205-2RS Deep Groove Ball Bearing</title>
<meta property="og:title" content="SKF 6205-2RS Deep Groove Ball Bearing">
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product",
 "name":"SKF 6205-2RS Deep Groove Ball Bearing","sku":"BRG-6205-2RS","mpn":"6205-2RS",
 "brand":{"@type":"Brand","name":"SKF"},
 "description":"Sealed deep groove ball bearing for general industrial service.",
 "offers":{"@type":"Offer","price":"14.50","priceCurrency":"USD"},
 "additionalProperty":[{"@type":"PropertyValue","name":"Cage Material","value":"Steel"}]}
</script></head><body>
<h1>SKF 6205-2RS Deep Groove Ball Bearing</h1>
<table><tr><th>Specification</th><th>Value</th></tr>
<tr><td>Bore Diameter</td><td>25 mm</td></tr>
<tr><td>Outer Diameter</td><td>52 mm</td></tr>
<tr><td>Width</td><td>15 mm</td></tr>
<tr><td>Limiting Speed</td><td>16000 rpm</td></tr></table>
<ul><li>Seal Type: 2RS</li></ul>
</body></html>
"""


def assert_enriches(product: RawProduct, label: str, expect_specs: int) -> None:
    check(len(product.raw_specs) >= expect_specs,
          f"{label}: recovered {len(product.raw_specs)} spec pairs (>= {expect_specs})")

    result = pipeline.enrich(product, MockProvider())
    category = result.category.path[-1] if result.category else "UNCLASSIFIED"
    check(result.category is not None and result.category.code == "31171500",
          f"{label}: classified as bearings (got {category})")

    bore = result.attr("bore_diameter")
    check(bore is not None and float(bore.value) == 25,
          f"{label}: bore diameter read as 25 mm (got {bore.value if bore else None})")

    od = result.attr("outer_diameter")
    check(od is not None and float(od.value) == 52,
          f"{label}: outer diameter read as 52 mm (got {od.value if od else None})")

    if product.source_document:
        traced = [a for a in result.attributes if product.source_document in a.evidence]
        check(bool(traced),
              f"{label}: evidence traces back to '{product.source_document}'")

    # Source citation is a stated requirement, not a nicety: every value read
    # out of a document must name where it came from, and a value read off a
    # web page must carry the URL itself.
    from_doc = [
        a for a in result.attributes
        if a.provenance.value in ("supplied", "parsed")
    ]
    cited = [a for a in from_doc if a.source_url or a.source_locator]
    check(len(cited) == len(from_doc),
          f"{label}: all {len(from_doc)} document-sourced values carry a source "
          f"(got {len(cited)})")

    if product.source_url:
        with_url = [a for a in from_doc if a.source_url == product.source_url]
        check(len(with_url) == len(from_doc),
              f"{label}: document-sourced values cite the page URL")

    if product.spec_sources:
        located = [a for a in from_doc if a.source_locator]
        check(bool(located) and any("page" in (a.source_locator or "") for a in located),
              f"{label}: at least one value cites the page it was read from")

    print(f"       -> {len(result.attributes)} attributes, "
          f"readiness {result.readiness.overall}/100 ({result.readiness.verdict})")


def main() -> int:
    print("=" * 64)
    print("  DOCUMENT INGEST TESTS - no API calls, $0.00")
    print("=" * 64)

    for label, builder, expect in (
        ("ruled table PDF", make_ruled_pdf, 6),
        ("ruleless PDF", make_ruleless_pdf, 6),
        ("dot-leader PDF", make_leader_pdf, 6),
    ):
        print(f"\n[{label}]")
        product, report = from_pdf(builder(), filename=f"{label}.pdf")
        print(f"       strategies: {report.strategies_used or 'none'}; "
              f"pages {report.pages}; pairs {report.spec_pairs}")
        for note in report.notes:
            print(f"       note: {note}")
        assert_enriches(product, label, expect)

    print("\n[product web page]")
    product, report = from_html(PRODUCT_HTML, url="https://example.com/6205")
    print(f"       strategies: {report.strategies_used}; pairs {report.spec_pairs}")
    check(product.mpn == "6205-2RS", f"web: MPN from JSON-LD (got {product.mpn})")
    check(product.brand == "SKF", f"web: brand from JSON-LD (got {product.brand})")
    check(product.sku == "BRG-6205-2RS", f"web: SKU from JSON-LD (got {product.sku})")
    assert_enriches(product, "web page", 4)

    print("\n[SSRF guard]")
    from app.ingest.web import UnsafeURL, assert_fetchable
    for bad in ("http://localhost:8000/admin", "file:///etc/passwd",
                "http://169.254.169.254/latest/meta-data/"):
        try:
            assert_fetchable(bad)
            check(False, f"should have refused {bad}")
        except UnsafeURL:
            check(True, f"refused {bad}")
        except Exception:
            check(True, f"refused {bad} (unresolvable)")

    print("\n" + "=" * 64)
    if FAILURES:
        print(f"{len(FAILURES)} CHECK(S) FAILED")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("ALL DOCUMENT INGEST CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

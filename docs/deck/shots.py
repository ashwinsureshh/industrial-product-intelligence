"""Capture the four MVP screenshots for deck slide 12.

Driven against the deployed prototype, not a local dev server, so what the deck
shows is exactly what a judge clicking the link will see.

Each shot is cropped to the cards that carry the point rather than the whole
window: a full-page capture at deck scale renders the body text illegible.
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "https://industrial-product-intelligence.onrender.com"
OUT = Path("shots")
OUT.mkdir(exist_ok=True)
VIEW = {"width": 1500, "height": 1000}
SCALE = 2          # retina capture, so the deck can scale it down cleanly


def tab(page, name):
    page.click(f'.main-nav .tab:text-is("{name}")')
    page.wait_for_timeout(600)


def engine(page, name):
    page.click(f'.engine-toggle .tab:text-is("{name}")')
    page.wait_for_timeout(400)


def shoot(page, path, selectors, pad=14):
    """Screenshot the bounding box of several cards together."""
    boxes = []
    for sel in selectors:
        el = page.query_selector(sel)
        if el:
            b = el.bounding_box()
            if b:
                boxes.append(b)
    if not boxes:
        print(f"  !! nothing matched for {path}")
        return False
    x0 = min(b["x"] for b in boxes) - pad
    y0 = min(b["y"] for b in boxes) - pad
    x1 = max(b["x"] + b["width"] for b in boxes) + pad
    y1 = max(b["y"] + b["height"] for b in boxes) + pad
    x0, y0 = max(x0, 0), max(y0, 0)
    page.screenshot(path=str(path), clip={"x": x0, "y": y0,
                                          "width": x1 - x0, "height": y1 - y0})
    print(f"  saved {path.name}  {int(x1-x0)}x{int(y1-y0)}")
    return True


def card_with(page, heading):
    """CSS for the card whose <h3> is `heading`."""
    return f'.col .card:has(h3:text-is("{heading}"))'


with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport=VIEW, device_scale_factor=SCALE)
    page.goto(URL, wait_until="networkidle", timeout=90000)
    page.wait_for_timeout(1500)

    # ---------------------------------------------------------------- shot 1
    # Single product: the record, showing provenance and confidence per value.
    print("1. single product enrichment")
    tab(page, "Single Product")
    page.click(".sample")                      # first demo case: the bearing
    page.wait_for_timeout(400)
    page.click('button:has-text("Enrich Product")')
    page.wait_for_selector(".col .card h3", timeout=45000)
    page.wait_for_timeout(2500)
    shoot(page, OUT / "1_enrichment.png",
          [card_with(page, "Commerce Readiness"), card_with(page, "Attributes")])

    # ---------------------------------------------------------------- shot 2
    # Hybrid engine on the same sparse bearing: the gate refusing the model.
    print("2. the AI gate refusing")
    engine(page, "Hybrid")
    page.click('button:has-text("Enrich Product")')
    page.wait_for_selector('.col .card:has(h3:text-is("AI gate"))', timeout=60000)
    page.wait_for_timeout(1500)
    shoot(page, OUT / "2_gate.png", [card_with(page, "AI gate")])
    engine(page, "Demo")

    # ---------------------------------------------------------------- shot 3
    # Discovery: the source ledger, refusals first.
    print("3. discovery source ledger")
    tab(page, "Discover")
    page.wait_for_timeout(500)
    # SKF rather than Frigidaire: the page is refused as unusable *and* the
    # record below still scores, because ISO 15 decodes the part number. That
    # pairing -- a refusal next to a defensible record -- is the honest story.
    page.click('.sample:has-text("SKF")')
    page.wait_for_selector('.col .card:has(h3:text-is("Sources"))', timeout=60000)
    page.wait_for_timeout(1500)
    shoot(page, OUT / "3_discovery.png",
          [card_with(page, "Sources"), card_with(page, "Commerce Readiness")])

    # ---------------------------------------------------------------- shot 4
    # Catalog: a batch scored and triaged, which is the scale story.
    print("4. catalog batch")
    tab(page, "Catalog")
    page.wait_for_timeout(400)
    page.click('button:has-text("Run 10-product demo catalog")')
    page.wait_for_selector('.col table', timeout=60000)
    page.wait_for_timeout(1500)
    shoot(page, OUT / "4_catalog.png",
          ['.col .card:has(.summary-grid)', '.col .card:has(table)'])

    # ---------------------------------------------------------------- shot 5
    # Accuracy: their labelled row scored against ours, both states.
    print("5. accuracy against their ground truth")
    tab(page, "Accuracy")
    page.wait_for_selector('.col .card:has(h3:text-is("Accuracy against their ground truth"))',
                           timeout=60000)
    page.wait_for_timeout(1200)
    shoot(page, OUT / "5_accuracy.png",
          [card_with(page, "Accuracy against their ground truth")])

    browser.close()

print("\ndone:", sorted(f.name for f in OUT.glob("*.png")))

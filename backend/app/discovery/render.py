"""Fetch a page the way a browser would, for sites that build themselves in JS.

§7.5 measured the ceiling of plain fetch-and-parse: zero of four real
manufacturer sites yielded a spec table, because Frigidaire, Milwaukee and SKF
all return HTTP 200 and then assemble the content client-side. That is a tooling
gap, and the engine has been honest about it rather than treating an empty page
as a product with no specifications.

This closes the gap without opening a second path through the system. It returns
exactly what `web.from_url` returns — `(RawProduct, WebIngestReport)` — so the
rendered HTML meets the *same* parser, the same provenance rules, the same
sixteen cross-field checks and the same readiness score. Discovery calls it as a
fetcher and nothing downstream can tell the difference.

Three deliberate limits:

- **The SSRF guard runs first, unchanged.** A browser will happily fetch
  169.254.169.254; the guard refuses before one is launched.
- **It is a fallback, never the first move.** A plain HTTP GET is cheaper by
  three orders of magnitude, and most manufacturer pages that carry a spec table
  serve it in the HTML. Rendering runs only when the cheap read found nothing.
- **Absent by default in the deployment.** The shipped image has no browser, so
  `available()` is False there and behaviour is exactly what it is today. A
  machine with Playwright installed gets the better result; nothing silently
  changes for a reviewer clicking the live link.
"""
from __future__ import annotations

import os
from functools import lru_cache

from ..ingest import web
from ..models import RawProduct

# Long enough for a slow single-page app to settle, short enough that a person
# clicking Discover does not think it has hung.
RENDER_TIMEOUT_MS = 20_000
SETTLE_MS = 1_800

_MODE = os.getenv("PI_RENDER_DISCOVERY", "auto").strip().lower()


@lru_cache(maxsize=1)
def _launch_kwargs() -> dict | None:
    """How to launch a browser here, or None if there is not one.

    Two ways to have Chromium: Playwright's own download, or a Chrome/Edge
    already on the machine. Preferring the installed browser means the renderer
    works without a 400 MB download, which matters because that download is
    exactly what would have to go into the deployed image.
    """
    if _MODE in ("0", "off", "false", "no"):
        return None
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    for kwargs in ({"channel": "chrome"}, {"channel": "msedge"}, {}):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(**kwargs)
                browser.close()
            return kwargs
        except Exception:  # noqa: BLE001 - try the next way of getting a browser
            continue
    return None


def available() -> bool:
    """Whether a real browser can be driven on this machine."""
    return _launch_kwargs() is not None


def fetch(url: str) -> tuple[RawProduct, web.WebIngestReport]:
    """Load `url` in a headless browser and parse what the user would see."""
    from playwright.sync_api import sync_playwright

    # Before a browser exists, not after: the guard is the only thing standing
    # between a URL and the container's own metadata endpoint.
    web.assert_fetchable(url)

    kwargs = _launch_kwargs() or {}
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--disable-dev-shm-usage"], **kwargs)
        try:
            page = browser.new_page(
                viewport={"width": 1280, "height": 900},
                user_agent="ProductIntelligence/1.0 (catalog enrichment)",
            )
            response = page.goto(url, wait_until="domcontentloaded",
                                 timeout=RENDER_TIMEOUT_MS)
            status = response.status if response else None
            # networkidle is the tempting wait here and it is the wrong one: a
            # page with polling or analytics never reaches it, and the whole
            # fetch times out over content that arrived seconds ago.
            try:
                page.wait_for_load_state("networkidle", timeout=SETTLE_MS)
            except Exception:  # noqa: BLE001 - settled enough is good enough
                page.wait_for_timeout(SETTLE_MS)
            html = page.content()
        finally:
            browser.close()

    product, report = web.from_html(html[:web.MAX_BYTES], url=url, status=status)
    report.strategies_used.insert(0, "headless:render")
    report.notes.append(
        "Read from the rendered page, after the browser executed its scripts."
    )
    return product, report

"""Record the demo walkthrough against the deployed site.

Produces a silent 1280x720 .webm paced to docs/video/script.md, for voiceover in
any editor. Driven against the live URL rather than a dev server, so the footage
is what a judge clicking the link actually sees.

    python docs/video/record.py            # full run, ~3 minutes
    python docs/video/record.py --fast     # same path, no dwell, for checking

The dwell times are the script's segment budgets minus the interaction time
measured on the deployed instance. If the narration runs long, the fix is the
script, not this file.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "https://industrial-product-intelligence.onrender.com"
OUT = Path(__file__).parent / "footage"
FAST = "--fast" in sys.argv
SIZE = {"width": 1280, "height": 720}


_T0 = [0.0]


def hold_until(page, mark: str, label: str = "") -> None:
    """Hold the frame until `mark` on the script's own clock.

    Absolute marks rather than relative waits, because the two must agree: a
    voiceover written to 0:50 has to find the gate on screen at 0:50, whatever
    the network did on the way there. Hand-tuned dwells drifted 80 seconds short
    of the narration on the first take.
    """
    minutes, seconds = mark.split(":")
    target = int(minutes) * 60 + float(seconds)
    if label:
        print(f"    {label}")
    if FAST:
        page.wait_for_timeout(120)
        return
    remaining = target - (time.time() - _T0[0])
    if remaining < 0:
        print(f"    !! overran {mark} by {-remaining:.1f}s — the shot list is too full")
        return
    page.wait_for_timeout(int(remaining * 1000))


def beat(page, seconds: float, label: str = "") -> None:
    """A short pause inside a segment, for a click to land visibly."""
    if label:
        print(f"    {label}")
    page.wait_for_timeout(150 if FAST else int(seconds * 1000))


def creep(page, selector: str, block: str = "center", offset: int = 0) -> None:
    """Scroll a card into view slowly enough to read on playback.

    `block` matters for tall cards: centring the Content Standard card pushes
    its first row off the top of the frame, and that first row — the
    40-character invoice line with its dropped tokens — is the only reason the
    shot exists. Use "start" for anything taller than the viewport, and an
    `offset` to clear the sticky header, which otherwise sits over the row that
    "start" just brought to the top.
    """
    page.eval_on_selector(selector, f"e => e.scrollIntoView({{block:'{block}'}})")
    if offset:
        page.evaluate(f"window.scrollBy(0, {offset})")
    page.wait_for_timeout(120 if FAST else 700)


def park_mouse(page) -> None:
    """Move the pointer off the sample list.

    Left where it clicked, it holds a hover highlight on a card that is not the
    one on screen, which reads as the wrong demo being shown.
    """
    page.mouse.move(SIZE["width"] // 2, SIZE["height"] - 8)


def main() -> int:
    OUT.mkdir(exist_ok=True)
    started = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport=SIZE, record_video_dir=str(OUT),
                                      record_video_size=SIZE)
        page = context.new_page()

        # 1 — the loaded app. Clock starts once there is something to look at.
        print("[1] 0:00 opening")
        page.goto(URL, wait_until="networkidle", timeout=120000)
        _T0[0] = time.time()
        hold_until(page, "0:18", "empty form, engine on Demo")

        # 2 — sparse bearing, provenance
        print("[2] 0:18 sparse bearing")
        page.click('.sample:has-text("Sparse bearing")')
        park_mouse(page)
        beat(page, 1.5)
        page.click('button:has-text("Enrich Product")')
        page.wait_for_selector('.col .card:has(h3:text-is("Attributes"))', timeout=60000)
        beat(page, 3.0, "record lands")
        creep(page, '.col .card:has(h3:text-is("Attributes"))')
        hold_until(page, "0:50", "dwell on the provenance badges")

        # 3 — the gate refusing. The thesis; the longest hold in the film.
        print("[3] 0:50 hybrid gate")
        page.click('.engine-toggle .tab:text-is("Hybrid")')
        beat(page, 1.5)
        page.click('button:has-text("Enrich Product")')
        page.wait_for_selector('.col .card:has(h3:text-is("AI gate"))', timeout=60000)
        creep(page, '.col .card:has(h3:text-is("AI gate"))')
        hold_until(page, "1:24", "hold on 14.8 kN refused and 14000 rpm refused")

        # 4 — a contradiction blocked
        print("[4] 1:24 contradictory valve")
        page.click('.engine-toggle .tab:text-is("Demo")')
        beat(page, 0.8)
        page.click('.sample:has-text("Contradictory valve")')
        park_mouse(page)
        beat(page, 1.2)
        page.click('button:has-text("Enrich Product")')
        page.wait_for_selector('.col .card:has(h3:text-is("Validation"))', timeout=60000)
        creep(page, '.col .card:has(h3:text-is("Validation"))')
        hold_until(page, "1:47", "PVC at 180 C, blocked in plain English")

        # 5 — the customer's content standard
        print("[5] 1:47 content standard")
        creep(page, '.col .card:has(h3:text-is("Content Standard"))',
              block="start", offset=-120)
        hold_until(page, "2:10", "40-character invoice line and the dropped tokens")

        # 6 — discovery, an honest negative result
        print("[6] 2:10 discover SKF")
        page.click('.main-nav .tab:text-is("Discover")')
        beat(page, 1.5)
        page.click('.sample:has-text("SKF 6205-2RS")')
        page.wait_for_selector('.col .card:has(h3:text-is("Sources"))', timeout=60000)
        park_mouse(page)
        creep(page, '.col .card:has(h3:text-is("Sources"))')
        hold_until(page, "2:22", "fetched, refused as unusable")
        creep(page, '.col .card:has(h3:text-is("Commerce Readiness"))')
        hold_until(page, "2:32", "and the record below still scores 94")

        # 7 — volume and the customer's own output schema
        print("[7] 2:32 catalog and exports")
        page.click('.main-nav .tab:text-is("Catalog")')
        beat(page, 1.2)
        page.click('button:has-text("Run 10-product demo catalog")')
        page.wait_for_selector('.col table', timeout=60000)
        hold_until(page, "2:42", "publish / review / blocked")
        creep(page, '.col .card:has(h3:text-is("Export"))')
        hold_until(page, "2:50", "252-column delivery format, schema.org, catalogue CSV")

        # 8 — close on the least flattering number, deliberately
        print("[8] 2:50 close")
        page.click('.main-nav .tab:text-is("Single Product")')
        hold_until(page, "3:00", "closing frame")

        context.close()
        browser.close()

    video = max(OUT.glob("*.webm"), key=lambda f: f.stat().st_mtime)
    final = OUT / "demo_walkthrough.webm"
    if video != final:
        final.unlink(missing_ok=True)
        video.rename(final)
    print(f"\nwrote {final}  ({final.stat().st_size/1_000_000:.1f} MB, "
          f"wall clock {time.time()-started:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

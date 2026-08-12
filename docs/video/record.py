"""Record the demo walkthrough against the deployed site.

Produces a silent 1280x720 .webm paced to docs/video/script.md, for voiceover in
any editor. Driven against the live URL rather than a dev server, so the footage
is what a judge clicking the link actually sees.

    python docs/video/record.py            # full run, ~3 minutes
    python docs/video/record.py --fast     # same path, no dwell, for checking

Segments hold to absolute marks taken from the script, not to relative waits, so
the picture and the narration cannot drift apart. If the narration runs long the
fix is the script, not this file.

Four things carry the smoothness, and each is easy to lose in an edit: a drawn
pointer (screen capture records no cursor, so clicks otherwise happen with no
visible cause), pointer travel interpolated over ~34 steps before each click,
every scroll on an eased curve of our own rather than the browser's quick
`behavior:'smooth'`, and a return to the top before any tab switch.
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


# A pointer, drawn by the page itself. Screen capture does not record the real
# cursor, so without this things change with no visible cause: buttons press
# themselves and tabs switch on their own, which is what made the first cut feel
# like a slideshow rather than someone using the product.
CURSOR = """
(() => {
  const draw = () => {
    if (document.getElementById('__cursor')) return;
    const dot = document.createElement('div');
    dot.id = '__cursor';
    dot.style.cssText = `position:fixed;left:-100px;top:-100px;width:20px;height:20px;
      border-radius:50%;background:rgba(37,99,235,.35);border:2px solid rgba(37,99,235,.9);
      box-shadow:0 2px 10px rgba(0,0,0,.35);pointer-events:none;z-index:2147483647;
      transform:translate(-50%,-50%);transition:width .12s ease,height .12s ease,
      background .12s ease;`;
    document.body.appendChild(dot);
    addEventListener('mousemove', e => {
      dot.style.left = e.clientX + 'px';
      dot.style.top = e.clientY + 'px';
    }, true);
    addEventListener('mousedown', () => {
      dot.style.width = '34px'; dot.style.height = '34px';
      dot.style.background = 'rgba(37,99,235,.55)';
    }, true);
    addEventListener('mouseup', () => {
      dot.style.width = '20px'; dot.style.height = '20px';
      dot.style.background = 'rgba(37,99,235,.35)';
    }, true);
  };
  if (document.body) draw(); else addEventListener('DOMContentLoaded', draw);
})();
"""


def glide(page, selector: str) -> None:
    """Move the pointer to an element the way a hand would, then settle."""
    box = page.query_selector(selector).bounding_box()
    x = box["x"] + box["width"] / 2
    y = box["y"] + box["height"] / 2
    page.mouse.move(x, y, steps=1 if FAST else 34)
    page.wait_for_timeout(60 if FAST else 260)


def tap(page, selector: str) -> None:
    """Glide to a control and click it, so the click has a visible cause."""
    glide(page, selector)
    page.click(selector)
    page.wait_for_timeout(80 if FAST else 320)


# An eased scroll of our own. The browser's `behavior:'smooth'` is quick and
# linear-ish — better than a jump, but it still arrives abruptly. Easing in and
# out over a chosen duration is what makes a scroll read as a camera move.
EASED_SCROLL = """
([targetY, duration]) => new Promise(resolve => {
  const startY = window.scrollY;
  const delta = targetY - startY;
  if (Math.abs(delta) < 2 || duration <= 0) { window.scrollTo(0, targetY); return resolve(); }
  const t0 = performance.now();
  const ease = t => t < 0.5 ? 4*t*t*t : 1 - Math.pow(-2*t + 2, 3) / 2;
  const step = now => {
    const t = Math.min((now - t0) / duration, 1);
    window.scrollTo(0, startY + delta * ease(t));
    if (t < 1) requestAnimationFrame(step); else resolve();
  };
  requestAnimationFrame(step);
});
"""


def scroll_to_y(page, target_y: float, seconds: float = 1.4) -> None:
    duration = 120 if FAST else int(seconds * 1000)
    page.evaluate(EASED_SCROLL, [target_y, duration])
    page.wait_for_timeout(40 if FAST else 120)


def creep(page, selector: str, block: str = "center", offset: int = 0,
          seconds: float = 1.4) -> None:
    """Scroll a card into view on an eased curve, at a readable pace.

    `block` matters for tall cards: centring the Content Standard card pushes
    its first row off the top of the frame, and that first row — the
    40-character invoice line with its dropped tokens — is the only reason the
    shot exists. Use "start" for anything taller than the viewport, and an
    `offset` to clear the sticky header, which otherwise sits over the row that
    "start" just brought to the top.

    The target is computed here rather than handed to scrollIntoView so the
    offset is part of one continuous movement. Scrolling into view and then
    nudging by -120 px is two moves, and the second one reads as a twitch.
    """
    box = page.query_selector(selector).bounding_box()
    if block == "start":
        target = box["y"] + page.evaluate("window.scrollY") + offset
    else:
        target = (box["y"] + page.evaluate("window.scrollY")
                  + box["height"] / 2 - SIZE["height"] / 2 + offset)
    scroll_to_y(page, max(target, 0), seconds)


def drift(page, pixels: int, seconds: float) -> None:
    """Creep the page a little during a long hold.

    A frame that has not moved for thirty seconds reads as a still image, and
    the viewer stops believing anything is happening. This is slow enough to
    keep reading through.
    """
    if FAST:
        page.wait_for_timeout(100)
        return
    scroll_to_y(page, page.evaluate("window.scrollY") + pixels, seconds)


def to_top(page, seconds: float = 0.9) -> None:
    """Return to the top before switching tabs.

    Switching tabs while scrolled down swaps the content under a scroll
    position that means nothing in the new tab, and the page lurches.
    """
    scroll_to_y(page, 0, seconds)


def park_mouse(page) -> None:
    """Move the pointer off the sample list.

    Left where it clicked, it holds a hover highlight on a card that is not the
    one on screen, which reads as the wrong demo being shown.
    """
    page.mouse.move(SIZE["width"] // 2, SIZE["height"] - 8,
                    steps=1 if FAST else 14)


def park_mouse(page) -> None:
    """Move the pointer off the sample list.

    Left where it clicked, it holds a hover highlight on a card that is not the
    one on screen, which reads as the wrong demo being shown.
    """
    page.mouse.move(SIZE["width"] // 2, SIZE["height"] - 8,
                    steps=1 if FAST else 14)


def main() -> int:
    OUT.mkdir(exist_ok=True)
    started = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport=SIZE, record_video_dir=str(OUT),
                                      record_video_size=SIZE)
        context.add_init_script(CURSOR)
        page = context.new_page()

        # 1 — the loaded app. Clock starts once there is something to look at.
        print("[1] 0:00 opening")
        page.goto(URL, wait_until="networkidle", timeout=120000)
        _T0[0] = time.time()
        # Hold the hero while the opening line is read. The result column is
        # empty until the first enrichment, so scrolling to the demo list early
        # leaves half the frame blank for no reason.
        beat(page, 12.0, "empty form, engine on Demo")
        # Bring the demo list into view and rest the pointer on the case we are
        # about to open. A pointer drifting onto an unrelated control reads as a
        # click that never comes.
        creep(page, '.card:has(h3:text-is("Demo Cases"))', block="start",
              offset=-108, seconds=1.8)
        glide(page, '.sample:has-text("Sparse bearing")')
        hold_until(page, "0:13")

        # 2 — sparse bearing, provenance
        print("[2] 0:18 sparse bearing")
        tap(page, '.sample:has-text("Sparse bearing")')
        beat(page, 1.2)
        tap(page, 'button:has-text("Enrich Product")')
        page.wait_for_selector('.col .card:has(h3:text-is("Attributes"))', timeout=60000)
        beat(page, 3.0, "record lands")
        creep(page, '.col .card:has(h3:text-is("Attributes"))')
        hold_until(page, "0:44", "dwell on the provenance badges")

        # 3 — the gate refusing. The thesis; the longest hold in the film.
        print("[3] 0:50 hybrid gate")
        tap(page, '.engine-toggle .tab:text-is("Hybrid")')
        beat(page, 1.5)
        tap(page, 'button:has-text("Enrich Product")')
        page.wait_for_selector('.col .card:has(h3:text-is("AI gate"))', timeout=60000)
        creep(page, '.col .card:has(h3:text-is("AI gate"))', seconds=1.8)
        beat(page, 16.0, "hold on 14.8 kN refused and 14000 rpm refused")
        drift(page, 120, 6.0)          # ease down to the third row and the note
        hold_until(page, "1:16")

        # 4 — a contradiction blocked
        print("[4] 1:24 contradictory valve")
        tap(page, '.engine-toggle .tab:text-is("Demo")')
        beat(page, 0.8)
        tap(page, '.sample:has-text("Contradictory valve")')
        beat(page, 1.0)
        tap(page, 'button:has-text("Enrich Product")')
        page.wait_for_selector('.col .card:has(h3:text-is("Validation"))', timeout=60000)
        creep(page, '.col .card:has(h3:text-is("Validation"))')
        hold_until(page, "1:35", "PVC at 180 C, blocked in plain English")

        # 5 — the customer's content standard
        print("[5] 1:47 content standard")
        creep(page, '.col .card:has(h3:text-is("Content Standard"))',
              block="start", offset=-118, seconds=1.8)
        hold_until(page, "1:56", "40-character invoice line and the dropped tokens")

        # 6 — discovery, an honest negative result
        print("[6] 2:10 discover SKF")
        to_top(page)
        tap(page, '.main-nav .tab:text-is("Discover")')
        beat(page, 1.5)
        tap(page, '.sample:has-text("SKF 6205-2RS")')
        page.wait_for_selector('.col .card:has(h3:text-is("Sources"))', timeout=60000)
        park_mouse(page)
        creep(page, '.col .card:has(h3:text-is("Sources"))')
        hold_until(page, "2:12", "fetched, refused as unusable")
        creep(page, '.col .card:has(h3:text-is("Commerce Readiness"))')
        hold_until(page, "2:22", "and the record below still scores 94")

        # 7 — volume and the customer's own output schema
        print("[7] 2:32 catalog and exports")
        to_top(page)
        tap(page, '.main-nav .tab:text-is("Catalog")')
        beat(page, 1.2)
        tap(page, 'button:has-text("Run 10-product demo catalog")')
        page.wait_for_selector('.col table', timeout=60000)
        hold_until(page, "2:32", "publish / review / blocked")
        creep(page, '.col .card:has(h3:text-is("Export"))')
        hold_until(page, "2:41", "252-column delivery format, schema.org, catalogue CSV")

        # 8 — close on the least flattering number, deliberately
        print("[8] 2:50 close")
        to_top(page)
        tap(page, '.main-nav .tab:text-is("Single Product")')
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

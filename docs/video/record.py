"""Record the demo walkthrough against the deployed site.

Produces a silent 1280x720 .webm paced to docs/video/script.md. Driven against
the live URL rather than a dev server, so the footage is what a judge clicking
the link actually sees, intercut with the explainer frames from frames.py —
a recording proves the thing works, but only the frames say what was built,
where the data lives and what comes out.

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

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "https://industrial-product-intelligence.onrender.com"
OUT = Path(__file__).parent / "footage"
FRAMES = OUT / "frames"


FAST = "--fast" in sys.argv
# 20 px taller than the delivered frame. The beacons live in that bottom strip
# and mux.py crops it off, so the timing marks never reach the viewer.
SIZE = {"width": 1280, "height": 740}
CROP_TO = 720


def frame(name: str) -> str:
    """A file:// URL for an explainer frame. Build them with frames.py first."""
    path = FRAMES / f"{name}.html"
    if not path.exists():
        raise SystemExit(f"missing {path.name} — run: python docs/video/frames.py")
    return path.as_uri()


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


# A beacon: a small block of pure colour in the top-left corner, held for a few
# frames at the start of every segment.
#
# It exists because the recording's own clock cannot be trusted. Playwright
# writes the webm at a variable rate and labels it 25 fps, so a wall-clock
# schedule and the file's timeline disagree — and the disagreement is not
# uniform, it accumulates at page navigations, so rescaling by a single factor
# lines up the ends and lets the middle drift. Detecting these flashes in the
# finished file gives the *player's* timestamp for each segment, which is the
# only timeline the narration has to match.
BEACON = """
(() => {
  let el = document.getElementById('__beacon');
  if (!el) {
    el = document.createElement('div');
    el.id = '__beacon';
    el.style.cssText = 'position:fixed;left:0;bottom:0;width:44px;height:18px;' +
      'z-index:2147483646;pointer-events:none;background:transparent;';
    document.body.appendChild(el);
  }
  // Held for a second, and repainted every frame while it is up. A static
  // page stops painting, and Playwright's screencast only emits on damage —
  // a brief flash on an explainer frame fell between emitted frames and four
  // of the nine beacons never reached the file. The rAF loop guarantees the
  // damage, and a second is long enough that no sampling can miss it.
  const until = performance.now() + 1000;
  const tick = now => {
    if (now >= until) { el.style.background = 'transparent'; return; }
    el.style.background = (Math.floor(now / 100) % 2)
      ? 'rgb(255,0,255)' : 'rgb(250,0,250)';
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
})();
"""


def beacon(page) -> None:
    """Mark a segment boundary in the picture itself."""
    page.evaluate(BEACON)
    page.wait_for_timeout(60 if FAST else 1100)


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
        # Recording begins when the context does, not when the first frame
        # renders. That lead-in of blank browser is real footage, and without
        # measuring it the narration starts over an empty screen.
        recording_started = time.time()
        page = context.new_page()

        # 1 — what was built. A screen recording cannot say this, and it is the
        #     first thing a judge is scoring.
        print("[1] architecture at 0:00")
        page.goto(frame("1_architecture"), wait_until="load", timeout=60000)
        _T0[0] = time.time()
        beacon(page)
        hold_until(page, "0:17", "inputs, one shape, ten stages, outputs")

        # 2 — the same claim, running. The trace card lists the real stages.
        print("[2] how you use it at 0:17")
        page.goto(URL, wait_until="networkidle", timeout=120000)
        beacon(page)
        beat(page, 0.6)
        creep(page, '.card:has(h3:text-is("Demo Cases"))', block="start",
              offset=-108, seconds=1.4)
        tap(page, '.sample:has-text("Sparse bearing")')
        beat(page, 0.8)
        tap(page, 'button:has-text("Enrich Product")')
        page.wait_for_selector('.col .card:has(h3:text-is("Attributes"))', timeout=60000)
        beat(page, 1.5, "record lands")
        creep(page, '.col .card:has(h3:text-is("Pipeline Trace"))',
              block="start", offset=-118, seconds=1.6)
        beat(page, 7.0, "ten stages with timings")
        creep(page, '.col .card:has(h3:text-is("Attributes"))', seconds=1.6)
        hold_until(page, "0:43", "dwell on the provenance badges")

        # 3 — the gate refusing. The thesis; the longest hold in the film.
        print("[3] the AI gate at 0:43")
        beacon(page)
        tap(page, '.engine-toggle .tab:text-is("Hybrid")')
        beat(page, 1.5)
        tap(page, 'button:has-text("Enrich Product")')
        page.wait_for_selector('.col .card:has(h3:text-is("AI gate"))', timeout=60000)
        creep(page, '.col .card:has(h3:text-is("AI gate"))', seconds=1.8)
        beat(page, 12.0, "hold on 14.8 kN refused and 14000 rpm refused")
        drift(page, 110, 4.5)          # ease down to the third row and the note
        hold_until(page, "1:08")

        # 4 — the other four ways in. The restructure had left the film showing
        #     only Single Product; a judge could not tell the rest existed.
        print("[4] 1:08 the other ways in")
        beacon(page)
        to_top(page)
        tap(page, '.main-nav .tab:text-is("Document")')
        beat(page, 2.0, "drop a datasheet or paste a product page")
        tap(page, '.main-nav .tab:text-is("Catalog")')
        beat(page, 0.8)
        tap(page, 'button:has-text("Run 10-product demo catalog")')
        page.wait_for_selector('.col table', timeout=60000)
        beat(page, 3.0, "a whole spreadsheet, triaged")
        to_top(page)
        tap(page, '.main-nav .tab:text-is("Discover")')
        beat(page, 0.8)
        tap(page, '.sample:has-text("SKF 6205-2RS")')
        page.wait_for_selector('.col .card:has(h3:text-is("Sources"))', timeout=60000)
        park_mouse(page)
        beat(page, 2.5, "brand and part number only")
        to_top(page)
        tap(page, '.main-nav .tab:text-is("Learning")')
        hold_until(page, "1:30", "categories it has never seen")

        # 5 — a contradiction blocked
        print("[5] 1:30 contradictory valve")
        beacon(page)
        to_top(page)
        tap(page, '.main-nav .tab:text-is("Single Product")')
        beat(page, 0.6)
        tap(page, '.engine-toggle .tab:text-is("Demo")')
        beat(page, 0.8)
        tap(page, '.sample:has-text("Contradictory valve")')
        beat(page, 1.0)
        tap(page, 'button:has-text("Enrich Product")')
        page.wait_for_selector('.col .card:has(h3:text-is("Validation"))', timeout=60000)
        creep(page, '.col .card:has(h3:text-is("Validation"))')
        hold_until(page, "1:45", "PVC at 180 C, blocked in plain English")

        # 5 — the customer's content standard
        print("[6] content standard at 1:45")
        beacon(page)
        creep(page, '.col .card:has(h3:text-is("Content Standard"))',
              block="start", offset=-118, seconds=1.8)
        hold_until(page, "2:00", "40-character invoice line and the dropped tokens")

        # 6 — what actually comes out. Real bytes, fetched from the deployment.
        print("[7] outputs at 2:00")
        page.goto(frame("2_outputs"), wait_until="load", timeout=60000)
        beacon(page)
        hold_until(page, "2:12", "252 columns, JSON-LD, and the audit-trail CSV")

        # 7 — where the data lives, which no screen in the product can answer
        print("[8] storage at 2:12")
        page.goto(frame("3_storage"), wait_until="load", timeout=60000)
        beacon(page)
        hold_until(page, "2:26", "no database; versioned data; a container that cannot spend")

        # 8 — scale and cost per SKU
        print("[9] scale at 2:26")
        page.goto(frame("4_scale"), wait_until="load", timeout=60000)
        beacon(page)
        hold_until(page, "2:41", "611 rows/s, 287 products/s, $0.0084 per SKU")

        # 9 — close on the least flattering number, deliberately
        print("[10] accuracy at 2:41")
        page.goto(frame("5_accuracy"), wait_until="load", timeout=60000)
        beacon(page)
        hold_until(page, "3:00", "14/14 and 2/14, both")

        lead_in = _T0[0] - recording_started
        span = time.time() - _T0[0]
        context.close()
        browser.close()

    # Both numbers matter to the mux. Playwright writes the webm at a variable
    # rate but labels it 25 fps, so the file's own duration can run several
    # percent long — 197.7 s for a 185 s session on this shot list — which would
    # slide every line of narration progressively later. The true content span
    # is wall-clock, measured here, and mux.py rescales the timeline onto it.
    (OUT / "lead_in.json").write_text(json.dumps(
        {"lead_in": round(lead_in, 3), "span": round(span, 3)}))
    print(f"\n  lead-in {lead_in:.2f}s, real span {span:.1f}s — mux.py corrects the timeline")

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

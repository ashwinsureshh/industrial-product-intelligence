# Demo video — 3:00 shooting script

**Deliverable:** short walkthrough, mandatory, link goes on deck slide 14.
Built by six scripts in `docs/video/`: `frames.py` renders the explainer
frames, `record.py` drives the live site and intercuts them, `voiceover.py`
speaks the narration, `align.py` locks them together, `assets.py` builds the datasheet it uploads,
`mux.py` assembles. Current cut: **2:59.8**.

**What changed, and why:** the first version demonstrated behaviour for three
minutes and never said what had been built, where the data was stored, or what
came out — which is most of what a judge is scoring. A recording can only show
the product working. Five purpose-made frames carry the rest, and every number
on them is measured elsewhere in the repo; the output frame is rendered from
bytes fetched live from the deployment, so nothing on screen is a mock-up.

**The one thing that must land:** this engine refuses. Every other product in
this space competes on how much it fills in. Segment 3 is the whole submission —
if anything gets cut, it is not the refusals.

---

## Shot list

| # | Time | On screen | The point |
|---|------|-----------|-----------|
| 1 | 0:00.0 | **Frame:** the problem, then six inputs → one record → ten checks | What this is, before any UI |
| 2 | 0:18.4 | Live app: pick a case, **Enrich**, read the record | **How you use it** — three steps, then the colour coding |
| 3 | 0:38.8 | Switch to **Hybrid** → the **AI gate** | 14.8 kN and 14000 rpm refused against ISO 15 |
| 4 | 1:02.8 | **Catalog** → run the 10-product demo | A spreadsheet comes back sorted: 8 publish, 1 review, 1 blocked |
| 5 | 1:09.8 | **Document** → a real datasheet PDF is uploaded on camera | 0 tables found, strategy `text:columns` — it reads a ruleless layout |
| 6 | 1:22.8 | **Discover** → SKF 6205-2RS | Fetches the manufacturer page, **refuses it**, says so, still scores 94 |
| 7 | 1:39.8 | **Learning** → the proposal queue | Categories it has never seen, queued for a human |
| 8 | 1:47.8 | Contradictory valve → **Validation** | Plastic at 180 °C — "not a valve, it is a candle" |
| 9 | 2:00.8 | **Content Standard** | The 40-character line names what it dropped |
| 10 | 2:11.9 | **Frame:** delivery row, JSON-LD, audit-trail CSV | Real bytes from the live service |
| 11 | 2:22.9 | **Frame:** where the data lives | No database, no stored key, nothing leaves |
| 12 | 2:36.9 | **Frame:** throughput, cost, review queue | 287/s, under a penny, publish / review / blocked |
| 13 | 2:43.9 | **Frame:** 14/14 and 2/14 | Closes on the least flattering number |

**Every line is checked against its own picture.** An earlier cut said "it goes
to the manufacturer's own site" over a screen showing a *refusal*, and described
a spreadsheet while a datasheet was on screen, because four claims shared one
segment. Each claim now has its own segment and its own marker, so a mismatch
cannot survive a rebuild.

---

## Measured timings

| # | Segment | Starts | Runs |
|---|---------|--------|------|
| 1 | architecture | 0:00.0 | 16.2 s |
| 2 | bearing | 0:18.4 | 22.7 s |
| 3 | gate | 0:38.8 | 24.1 s |
| 4 | catalog | 1:02.8 | 6.9 s |
| 5 | document | 1:09.8 | 12.8 s |
| 6 | discover | 1:22.8 | 16.3 s |
| 7 | learning | 1:39.8 | 8.2 s |
| 8 | valve | 1:47.8 | 12.8 s |
| 9 | content | 2:00.8 | 10.2 s |
| 10 | outputs | 2:11.9 | 11.1 s |
| 11 | storage | 2:22.9 | 13.5 s |
| 12 | scale | 2:36.9 | 6.8 s |
| 13 | close | 2:43.9 | 15.8 s |

**Narration 180.0 s, picture 179.8 s.**

## Assembling it

**`footage/demo_walkthrough.mp4` is already assembled** — H.264 / AAC, 1280×720,
2:59.8, ready to upload. Rebuild it with `python docs/video/mux.py` after
re-recording or re-narrating (needs a full ffmpeg: `winget install Gyan.FFmpeg`).

To assemble by hand instead, `footage/narration.wav` is a single full-length
track with every segment already at its own offset: drop it and
`demo_walkthrough.webm` on a timeline **both at 0:00**, and that is the whole
edit.

To use your own voice instead — which will sound better than the synthetic one —
read the narration column against the timings above. The picture is already cut
to them, so a take that hits those marks needs no adjustment either.

## Why this order

It opens and closes on frames and puts the product in the middle. A judge who
watches only the first twenty seconds still learns what was built; one who
watches to the end leaves with the accuracy numbers rather than a feature.

Segments 2 and 3 are the thesis and take a third of the runtime on purpose:
recall without precision is worthless, and the refusal ledger is the only screen
in the submission that makes the architecture visible in one frame.

Segment 10 closes on the least flattering number in the project. That is
deliberate — the judging criteria name accuracy and trustworthiness, and a demo
that ends by qualifying its own headline is the strongest evidence for both.

## Do not say

- **"14 out of 14"** without the second number. It is the formatter given the
  values, not the pipeline from a catalogue row.
- **"305 products per second"** while the deployed site is on screen. That is a
  local measurement; the free-tier instance does about 19/s. The scale frame
  says "287 /s, one core, measured locally" for exactly this reason.
- **"100% of errors caught"** unqualified — it is 51 of 51 *seeded* defects on
  our corpus, not a universal claim.
- Anything about the learned category names. They read "Led Meds" and
  "Metal Offs" at volume; the feature is sound, the names are not demo material.

## After recording

1. Upload unlisted to YouTube (or Drive with link sharing on).
2. Put the URL on **deck slide 14** — the placeholder is marked — and re-run
   `python docs/deck/build_deck.py`.
3. Check the link from a logged-out browser before submitting.

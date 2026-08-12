# Demo video — 3:00 shooting script

**Deliverable:** short walkthrough, mandatory, link goes on deck slide 14.
Built by five scripts in `docs/video/`: `frames.py` renders the explainer
frames, `record.py` drives the live site and intercuts them, `voiceover.py`
speaks the narration, `align.py` locks them together, `mux.py` assembles. Current cut: **180.0 s**.

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
| 1 | 0:00 | **Frame:** six inputs → one `RawProduct` → ten stages → four outputs | What was built, in one picture, before any UI appears |
| 2 | 0:19 | Live app: Sparse bearing → Enrich. **Pipeline Trace** card, then Attributes | The same claim, running: ten real stages with timings, then ISO 15 values badged *Standard* against grey unconfirmed defaults |
| 3 | 0:44 | Switch to **Hybrid** → Enrich → the **AI gate** card | The thesis. 14.8 kN and 14000 rpm both refused against ISO 15, reasons printed |
| 4 | 1:14 | Contradictory valve → the red **Validation** card | Cross-field rules catch what no single-field check can |
| 5 | 1:28 | **Content Standard** card on the same record | Five formats to five character limits; the 40-char line drops whole facts and names them |
| 6 | 1:43 | **Frame:** the 252-column delivery row, JSON-LD, and the audit-trail CSV | What actually comes out — real bytes from the live service |
| 7 | 2:04 | **Frame:** where the data lives | No database; versioned JSON; a container that stores no key and cannot spend |
| 8 | 2:27 | **Frame:** throughput and cost per SKU | 611 rows/s, 287 products/s, $0.0084 batched against a $5.83 manual baseline |
| 9 | 2:42 | **Frame:** 14/14 and 2/14 | Closes on the least flattering number in the project, deliberately |

---

## Measured timings

Not estimates, and not calculated either. `voiceover.py` speaks each segment and
measures it; `record.py` flashes a hidden marker at every segment start;
`align.py` reads those markers out of the finished file and lays each line on
the timestamp the player will actually use. Verified at ±0.12 s on all nine.

| # | Segment | Starts | Runs |
|---|---------|--------|------|
| 1 | architecture | 0:00.0 | 24.6 s |
| 2 | bearing | 0:26.3 | 24.6 s |
| 3 | gate | 0:48.8 | 27.6 s |
| 4 | valve | 1:17.2 | 15.2 s |
| 5 | content | 1:32.8 | 15.7 s |
| 6 | outputs | 1:48.8 | 16.9 s |
| 7 | storage | 2:05.8 | 17.0 s |
| 8 | scale | 2:22.8 | 18.1 s |
| 9 | close | 2:40.8 | 17.9 s |

**Narration 179.8 s, picture 179.7 s.**

## Assembling it

**`footage/demo_walkthrough.mp4` is already assembled** — H.264 / AAC, 1280×720,
3:00.0, ready to upload. Rebuild it with `python docs/video/mux.py` after
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

Segment 9 closes on the least flattering number in the project. That is
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

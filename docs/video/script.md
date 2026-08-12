# Demo video — 3:00 shooting script

**Deliverable:** short walkthrough, mandatory, link goes on deck slide 14.
**Target:** 2:55–3:00. Narration below is **436 words ≈ 2:55 at 150 wpm.** If you
run long, cut segment 7 first — it is the only one whose point appears elsewhere
in the deck.

**Before recording**

- Open **https://industrial-product-intelligence.onrender.com** and click once to
  wake the instance. A cold Render start takes ~40 s and the first paint will
  otherwise be in your take.
- Browser at **1280×720 or 1920×1080**, zoom 100%, light theme, no bookmarks bar.
- Engine toggle on **Demo**. Nothing typed in the form.
- Have the terminal ready in `backend/` for segment 8 only if you want the CLI
  shot; otherwise use deck slide 8.

**The one thing that must land:** this engine refuses. Every other product in
this space competes on how much it fills in. Segment 3 is the whole submission —
if you cut anything, do not cut the refusals.

---

## Shot list

| # | Time | On screen | Narration |
|---|------|-----------|-----------|
| 1 | 0:00–0:18 | The loaded app, Single Product tab, empty form. | "In industrial commerce a wrong specification ships a broken machine. So this engine is built to do something unusual: it would rather leave a field empty than state something it cannot defend. Here's what that looks like on a real part." |
| 2 | 0:18–0:50 | Click demo case **"Sparse bearing"** → **Enrich Product**. Let the record land. Scroll slowly to Attributes. Hover one purple *Standard* badge. | "Three fields in — a part number, a brand, a name. Out comes a full record. Bore twenty-five, outer diameter fifty-two, width fifteen. None of that was supplied: ISO 15 fixes those dimensions for the designation 6205, and every value says so. The purple badge means a published standard. The grey ones are category defaults, flagged as unconfirmed — not presented as fact." |
| 3 | 0:50–1:24 | Switch engine to **Hybrid**. **Enrich Product** again. Scroll to the **AI gate** card. Point at the two refusals. | "Now the AI engine. It proposed a load rating of 14.8 kilonewtons, and a speed of fourteen thousand. ISO 15 says fourteen, and sixteen thousand. Both refused — and the reason is printed. The model may fill a blank or replace an unbacked default; it may never overrule evidence. We measured that: bounded this way it beats both the raw model and the rules engine, and precision on evidence-backed values stays at exactly one hundred percent." |
| 4 | 1:24–1:47 | Single Product tab, click demo case **"Contradictory valve"** → **Enrich**. Show the red Validation card. | "Sixteen cross-field rules catch what no single-field check can. A PVC body rated to 180°C — every number plausible alone, impossible together. Blocked, in plain English, with the reason a buyer can act on." |
| 5 | 1:47–2:10 | Scroll to the **Content Standard** card on the same record. Point at the dropped-token line. | "The customer needs the same product written five times, to five character limits. This is the forty-character invoice line. It hit the limit by dropping whole facts and naming which ones — because cutting at forty characters would truncate the part number, and an unsearchable part number is worse than a shorter line." |
| 6 | 2:10–2:32 | **Discover** tab → click the **SKF** sample. Show the Sources ledger, then the record below. | "Discovery, from a brand and a part number. It found SKF's own page, fetched it, and refused it — the page renders client-side and yielded nothing. That refusal is the honest answer. The record below still scores 94, because the part number itself decodes against ISO 15. Nothing was invented to fill the gap." |
| 7 | 2:32–2:50 | **Catalog** tab → **Run 10-product demo catalog**. Show the summary, then the Export card and its three profiles. | "At volume: ten products, triaged into publish, review and blocked. Exports render into the customer's own 252-column delivery format, schema.org, or a catalogue sheet — the target schema is data, so a new one needs no code." |
| 8 | 2:50–3:00 | Deck slide 8, or `python run_expected_vs_ours.py`. | "Against their own labelled rows: fourteen of fourteen fields exact when the engine has the attribute values, two of fourteen from a bare catalogue row. Both numbers, because the gap is sourcing — and saying so is the point." |

---

## Measured timings

Not estimates. `voiceover.py` speaks each segment and reads the real duration
out of the WAV header, and those numbers set the video's marks — so the picture
changes when the line is spoken, not when a word count guessed it would.

| # | Segment | Starts | Runs |
|---|---------|--------|------|
| 1 | open | 0:00.0 | 13.3 s |
| 2 | bearing | 0:13.7 | 30.4 s |
| 3 | gate | 0:44.6 | 31.7 s |
| 4 | valve | 1:16.8 | 18.2 s |
| 5 | content | 1:35.4 | 20.8 s |
| 6 | discover | 1:56.6 | 25.2 s |
| 7 | catalog | 2:22.2 | 18.7 s |
| 8 | close | 2:41.4 | 16.0 s |

**Narration 2:57.4, picture 3:02.9.** The first cut of the script ran 183.7 s
and `voiceover.py` refused it — three trims that cost no substance (a hand-off
line, a redundant clause, and a third export format the slide already lists)
brought it under.

## Assembling it

`footage/narration.wav` is a single full-length track with every segment already
at its own offset, so there is nothing to nudge:

1. Drop `demo_walkthrough.webm` and `narration.wav` on a timeline, **both at
   0:00**. That is the whole edit.
2. Export as MP4 and upload.

To use your own voice instead — which will sound better than the synthetic one —
read the narration column against the timings above. The picture is already cut
to them, so a take that hits those marks needs no adjustment either.

## Why this order

Segments 2 and 3 are the thesis and take a third of the runtime on purpose:
recall without precision is worthless, and the refusal ledger is the only screen
in the submission that makes the architecture visible in one frame.

Segment 8 closes on the least flattering number in the project. That is
deliberate — the judging criteria name accuracy and trustworthiness, and a demo
that ends by qualifying its own headline is the strongest evidence for both.

## Do not say

- **"14 out of 14"** without the second number. It is the formatter given the
  values, not the pipeline from a catalogue row.
- **"305 products per second"** while the deployed site is on screen. That is a
  local measurement; the free-tier instance does about 19/s. Say "287 per second
  on one core, measured locally" or skip it.
- **"100% of errors caught"** unqualified — it is 51 of 51 *seeded* defects on
  our corpus, not a universal claim.
- Anything about the learned category names. They read "Led Meds" and
  "Metal Offs" at volume; the feature is sound, the names are not demo material.

## After recording

1. Upload unlisted to YouTube (or Drive with link sharing on).
2. Put the URL on **deck slide 14** — the placeholder is marked — and re-run
   `python docs/deck/build_deck.py`.
3. Check the link from a logged-out browser before submitting.

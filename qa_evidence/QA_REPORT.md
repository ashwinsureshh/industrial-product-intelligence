# Industrial Product Intelligence — A–Z QA pass

> **Status: D1, D2, D3 and D5 below were fixed the same day.** See CLAUDE.md §7.8
> for what changed and why, and `backend/test_qa_fixes.py` for the regressions
> that hold D1–D3 fixed. Every benchmark figure re-measured unchanged afterwards.
> **D4 alone remains open** — space-aligned PDF extraction, which validation
> already catches and blocks, so nothing false publishes.
> The report below is preserved as written, before the fixes.

Target: https://industrial-product-intelligence.onrender.com
Date: 12 Aug 2026. Method: live HTTP API + Chrome (Playwright) against the deployed
build. No API key supplied, so nothing in this pass could spend money.

**Scope correction:** the brief describes six sections including "Accuracy". That tab
was removed from the product earlier the same day at the owner's request. The
measurement behind it is still live at `GET /api/ground-truth`. Section J is scored
against that reality.

---

## 1. Summary verdict

The live site substantially behaves as described in the areas that carry the value
proposition: it refuses rather than guesses, every value carries a visible source and
confidence, cross-field validation generalises well beyond its three worked examples,
and the AI-restricted engine demonstrably refuses to overwrite evidence. Five of the
seven headline benchmark numbers reproduce exactly when the corpus is re-run.

It is not clean, though. One defect breaks the core principle: a bearing whose part
number fixes its bore under ISO 15 will publish a *contradicting* supplier bore at 99%
confidence, with no conflict recorded — while the same record cites ISO 15 for the two
neighbouring dimensions. Two more are structural: approving a learned category does not
invalidate cached results, so the learning loop fails for the very product used to train
it; and the "manufacturer sources only" rule is enforced on the Discover path but not on
the URL-ingest path beside it. The throughput claim does not hold on the deployed
instance by a factor of 15.

---

## 2. Pass / fail table

| § | Area | Rating | One-line reason |
|---|------|--------|-----------------|
| 0 | Setup | **Pass** | Loads in 0.28–0.88 s on 3 spaced checks; 5 tabs, 3 engines, engine selector visible in the header |
| A | Single product | **Pass** | All 7 claimed bearing values exact; standards rows cite ISO 15, guesses marked "Default" at 45% |
| B | Document upload | **Partial** | Bordered and dot-leader layouts perfect with page citations; space-aligned layout clips values |
| C | Catalogue upload | **Partial** | Correct per-row verdicts and summary; throughput 19/s, not 305/s; one bad row published (see D1) |
| D | Learning | **Partial** | Proposal, approval gate, generalisation and range-rejection all work; re-submitting the trained product fails |
| E | Discover | **Partial** | Ledger, refusals and honest failure are exemplary; the no-marketplace rule is not enforced on `/api/ingest/url` |
| F | Pipeline + 16 checks | **Partial** | 3/3 documented and 5/5 novel contradictions caught, 0 false alarms — but no check compares a designation against a supplied dimension |
| G | Provenance/confidence | **Pass** | Colour-coded badges (Supplied/Standard/Parsed/Default) plus a confidence bar; evidence quotes the raw source string |
| H | Rules vs AI vs restricted | **Pass** | Gate reproduces the documented refusals exactly, free and keyless; determinism proven on fresh cache keys |
| I | Multi-format writing | **Partial** | All formats correct incl. 40-char token dropping — but none of them appear in the UI |
| J | Accuracy measurement | **Pass** | Endpoint reports both states (14/14 and 2/14) and every field carries both |
| K | Reliability / repo | **Partial** | 3/3 loads OK, repo genuinely public, no secrets in history; throughput claim not reproducible live |
| L | Known limitations | **Pass** | JS-rendered pages reported as unreadable, not as "no specs"; scanned PDF detected |
| M | Edge cases | **Pass** | 60 kB input, unicode, emoji, HTML injection, negative values, 8 rapid repeats — all sane |
| N | Headline claims | **Partial** | 5 of 7 reproduced exactly on the corpus; throughput fails live; "100% caught" is corpus-specific |

---

## 3. Confirmed claims

Re-run locally from the committed corpus (`run_benchmark.py`, `run_hybrid.py`, $0):

| Claim | Stated | Measured | |
|---|---|---|---|
| Coverage lift | 2.75× | **2.75× (129 → 355)** | reproduced |
| Withheld detail recovered | 61% | **61.1%** | reproduced |
| Contradictions on evidence-backed values | 0% | **0.0%** (11.1% incl. flagged defaults) | reproduced |
| Planted errors caught | 100% | **100.0% (51/51)** | reproduced *on their corpus* |
| False alarms | 0% | **0.0%** | reproduced, and corroborated live: 5/5 clean products published |
| Rules engine recall | 83% / 33% | **83.1% / 33.1%** | reproduced |
| AI-restricted recall | 99% / 42% | **99.5% / 41.7%** | reproduced; gate 57 gap-filled, 10 displaced, 28 refused |

Corroborated directly on the live site:

- **AI-restricted behaves as documented.** On the demo bearing the model proposed
  14.8 kN and 14,000 rpm; both **refused** against ISO 15's 14 kN / 16,000 rpm, with the
  reason printed. A Polyamide cage was accepted over the unbacked `Steel` default and
  re-labelled `inferred` at 50% confidence. No evidence-backed value changed.
- **Determinism.** Two fresh cache keys for the same product returned byte-identical
  attributes, content and readiness.
- **Refusal over invention.** Gibberish, empty input, unknown brands and unreadable
  pages all produce blocked records with a stated reason and zero fabricated attributes.

---

## 4. Unverifiable or unreproduced

- **305 products/second — fails on the live site.** Measured **19.1/s** server-side on a
  200-row upload (10.4 s) and 15.5/s on 12 rows. The engine itself reached **288.6/s**
  locally, so this is the Render free-tier CPU rather than the pipeline — but the number
  as printed cannot be reproduced at the advertised link. The derived claim
  ("200,000 rows in ~11 minutes") would be ~2.9 hours on the deployment.
- **"100% of planted errors caught" is corpus-specific, not universal.** It reproduces
  against their 51 seeded defects. My own defect class (§5, D1) is not caught.
- The cost-per-SKU figures were not exercised: doing so requires live AI calls.

---

## 5. Defects found

**D1 — A published value that a cited standard contradicts. (Highest severity.)**
Input: MPN `6205`, brand SKF, supplier spec `Bore = 30 mm`. ISO 15 fixes 6205 at a
**25 mm** bore. Result: **"Ready to publish", readiness 93**, bore 30 mm at **99%
confidence, provenance "Supplied"**, no conflict recorded, no warning. The same card
shows Outer Diameter 52 mm and Width 15 mm badged **"Standard"** — the ISO 15 values for
6205. The record therefore trusts the standard for two dimensions and silently ignores it
for the third, on one screen.

Cause is structural, not a tuning slip: the knowledge base is consulted only to *fill
gaps* during `infer`, so it can never challenge a supplied value, and none of the 16
registered rules compares a part-number designation against a supplied dimension. The
analogous check exists for fasteners — `grade_tensile` correctly caught my "class 10.9
but 400 MPa" case — so the capability is present but not applied to bearings.

This contradicts the documented reconciliation behaviour ("when two stages disagree the
stronger provenance wins, **the conflict is recorded**, and the winner's confidence is
reduced"): here nothing is recorded and confidence stays at 0.99. It also reaches the
catalogue path — the same row published in a bulk upload. Evidence:
`qa_defect1_bore.png`.

**D2 — Approving a learned category does not invalidate cached results.**
The documented learning loop says a product blocked before training will score highly
after approval. It does not. The product used in training returned `cached: true` with
its stale, wrong classification (Industrial Valves, 50%) and stayed blocked. An identical
product with one character changed in the SKU classified correctly as the learned
category at 95.7% and published at 99.7. The cache key covers input + mode + model but
not the taxonomy version, so every record enriched before a category is approved keeps
the pre-learning answer indefinitely.

**D3 — The no-marketplace rule is enforced on one path only.**
`/api/discover` refuses non-manufacturer domains properly and publishes a blocked list
naming Amazon, eBay, Grainger, McMaster, Home Depot and others by `kind`. But
`/api/ingest/url` — the Document tab — has no reference to the policy at all. I fetched
`amazon.com` and `grainger.com` through it successfully (HTTP 200). Nothing was published
in my tests because those pages yielded no specs, but a marketplace page that *did* parse
would enter the catalogue with a marketplace `source_url` cited as provenance. The
organizers' constraint is stated as absolute.

**D4 — Space-aligned PDF columns are mis-extracted.**
Of the three layouts claimed, (a) bordered and (c) dot-leader extracted 7/7 values
perfectly with "page 1" citations. Layout (b), space-aligned with no rules, clipped
values at the column boundary — `14.0 kN` → `14.0 k`, `Chrome Steel` → `Chrome`,
`16000 rpm` → `16000` — and invented two junk keys from the title line, one of which
became `Width = "d, no"` at 89.5% confidence. **Validation caught it** (two
`TYPE_MISMATCH` errors, blocked), so nothing false was published; the honesty layer held
where the extractor failed.

**D5 — The compliance formats and provisional markers are invisible in the UI.**
The five commerce descriptions (40-char invoice, 60–80 mobile, title, retail, long) are
correct in the API — the invoice line lands at exactly 40 chars, drops *whole* tokens,
never truncates the part number, and discloses what it dropped. But no UI component
references `compliance`; the app renders a different, generic content block. Likewise the
`uom: provisional` marker never reaches the screen (only Discover's registry note does),
and the profile-driven exports — including the 252-column Unilog delivery format, which
works correctly via the API — are unreachable from the UI's export buttons.

**Minor:** an unlearned pneumatic cylinder is misclassified as *Industrial Valves* at
50% rather than reported unrecognised (blocked, so honest, and the confidence cap fires
with a stated reason); a learned attribute range came back as `[0.0, 128.0]`, admitting
a 0 mm bore; a revoked category leaves an `approved` row in the proposals queue.

---

## 6. Evidence

- `qa_evidence/qa_defect1_bore.png` — D1. "Ready to publish / 93", Bore 30 mm
  "Supplied 99" beside Outer Diameter 52 mm and Width 15 mm badged "Standard".
- `qa_evidence/qa_g_provenance.png` — G. Badge colour ramp: Supplied (green),
  Standard (purple), Parsed (blue), Default (grey, red confidence bar at 45).
- Transcript evidence quoted inline above for D2 (`cached: true` vs cache-busted copy),
  D3 (HTTP 200 from amazon.com through `/api/ingest/url`), D4 (clipped values), D5
  (live DOM contains none of the compliance strings).

---

## 7. Open questions

1. **Live AI (unrestricted) could not be exercised** — it needs a key the reviewer
   supplies, and `PI_ALLOW_SERVER_KEY=0` on the deployment. Without a key the request
   silently falls back to demo (disclosed via `mode` in the response and a UI banner).
   AI-restricted *was* fully testable because its proposals ship precomputed. Closing the
   gap needs a funded key and the owner's consent to spend.
2. **Throughput at catalogue scale** — the 1,000-row and 200,000-row claims cannot be
   tested through a 200-row upload cap on free-tier CPU. A local run against the same
   file would separate engine from environment; the 288.6/s local figure suggests the
   engine is fine.
3. **Whether D1 is intended.** "Supplier data outranks everything" is a defensible
   policy; the defect is that the disagreement is neither recorded nor surfaced, which
   the documentation says it should be.

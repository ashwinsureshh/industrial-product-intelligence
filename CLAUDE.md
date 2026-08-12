# CLAUDE.md — project context

Working context for this repository. Read this first in a new session.

---

## 1. What this is

A hackathon submission: **AI-Powered Product Intelligence for Industrial Commerce**.
The brief asks for a solution that turns limited product information into rich,
reliable, commerce-ready product data, focusing on **data enrichment, validation
and explainable outputs**.

The four stated "expected outcomes" and where each is answered:

| Expected outcome | Where |
| --- | --- |
| Structured data generation | taxonomy classification → extraction → typed `EnrichedProduct` |
| Accuracy & consistency | unit normalization + 16 cross-field engineering rules |
| AI validation & enrichment | provider layer (deterministic + Claude tool-use), bounded by the hybrid gate — §7.2 |
| Scalable catalog engine | CSV/batch ingest, document ingest, **auto-taxonomy learning** |

**Guiding principle, stated in the README and worth preserving in every change:**
in industrial commerce a wrong specification ships a broken machine, so the
engine must refuse to guess silently. It leaves a field blank, flags a
contradiction, or blocks publication rather than emit a confident-looking value
it cannot defend.

---

## 1.5 Organizer briefing — the authoritative brief

The user attended a **UniHack live session with the organizers (Unilog)** and
relayed it on 6 Aug. This supersedes inference from the portal text. Anything in
this file that predates it was written from the portal blurb alone.

**The core problem as they state it:** take **minimal input — a manufacturer
name and part number — and search manufacturer websites, catalogues, PDFs, user
manuals and videos** to find detailed specifications, then output structured,
commerce-ready data. Unilog does this partly manually today and wants to scale
**150,000 → 750,000 SKUs/month on the same capacity**.

**Four judging criteria, equally weighted:** Innovation, Accuracy, Scalability,
Quality. Beyond those: cost-effectiveness **per SKU** (thin margins), source
transparency, completeness of submission, and a **working MVP** rather than a
production system.

**Hard requirements:**

- **Source URLs for every extracted value.** Stated three separate times — in
  the objectives, the judging criteria, and the definition of commerce-ready.
- **Output into a schema Unilog provides.** As of 6 Aug they had **not** given
  one; the user expects input/output sample data "in some days". §5 `export/`
  is the answer — target format is a profile, not code.
- **No e-commerce sources.** Amazon, eBay and similar are prohibited;
  manufacturer-provided sources only.
- **Generic across segments** — HVAC, plumbing, electrical — not single-domain.
- **Deliverables:** deck (their template), **public** GitHub repo, and a
  **3-minute** demo video.

**Nice to have:** schema.org compliance (shipped — §5 `export_profiles/`),
and extraction from manufacturer videos or tech talks (not built; roadmap).

**What this validated:** explainable outputs are an explicit ask (the refusal
ledger is directly on target), as are validation for trustworthiness and
domain-generic design.

**The one real gap:** autonomous **discovery** from brand + MPN. We enrich from
MPN via ISO decoding, which is genuinely on-target, but we do not search the
web. Held deliberately until their sample data arrives — see §11.

---

## 1.6 The Solution Guide (10 Aug) — this reframes §1.5

The organizers published a **Unihack Solution Guide** to the portal Resources
tab. Read it before §1.5; where they conflict, this wins. Local copy:
`C:\Users\Gaming PC\Downloads\Unihack Solution Guide.html`.

**The problem restated, in their words:** "Given a messy row, produce a
complete, standardised, search-ready product record." The pipeline they name is
**input analysis → de-duplication → taxonomy & classification → attribute
extraction → enrichment from manufacturer sources → cleansing and normalisation
→ description building → digital assets**, and they add: "You are not expected
to automate all of it. Picking two or three steps and doing them convincingly,
with evidence, beats a shallow attempt at everything."

**Consequence: web discovery is demoted.** It is one of eight steps and
explicitly optional. §11.1 called it "the one real gap" and treated it as the
critical path; that judgement predates this guide. Do not build it unless the
user asks.

**Nine data files, in four groups.** Only two carry items to process; the rest
are the rule book.

| File | Role |
| --- | --- |
| `Unilog-Sample_200_Items-Input-vs-Output.xlsx` | **The important one.** Input sheet + Delivery Format sheet, 252 columns. The only labelled ground truth |
| `Sample-1000_Items.xlsx` | 1,000 raw rows, 6 columns. Volume testing |
| `UNILOG_INTERNAL_CONTENT_GUIDELINES.docx` | Field formulas, character limits, casing, sourcing rules |
| `Unilog_Master_UOM_Standards_Abbreviations_and_Terms.xlsx` | ~500 approved abbreviations / 89 measurement types + 22 house-style rules |
| `Decimal_Fraction.xlsx` | 63 exact inch conversions, 1/64 → 63/64 |
| `UniCat_Manufacturer_and_Brand_List.xlsx` | 27,000+ approved manufacturer/brand rows with exact casing and ® / ™ |
| `Unicat_Lov_v1_0_Updated_With_Remarks.xlsx` | ~161,000-row cross-category List of Values |
| `FAUCETS_LOV.xlsx` / `Fittings_LOV.xlsx` | Two categories specified end-to-end |
| `Reference_Documents_Summary.xlsx` | Their own index of the pack — read first |

**Status as of 12 Aug: partially delivered, and the delivered half is fully
used.** Two CSVs arrived, now committed under `backend/data/unilog_samples/`:

- `input_1000.csv` — the 1,000-row, 6-column sample. Matches the guide.
- `delivery_expected.csv` — **the delivery format at exactly 252 columns, with
  two fully worked rows.** This is the labelled ground truth, and two rows of it
  turned out to be enough to derive every content formula (§7.3).

The other seven reference files — content guidelines, UOM standards,
manufacturer/brand list, the 161k-row LOV, Faucets/Fittings — are **still not
uploaded**. The stubs in `data/unilog/` stand in for them and still report
`source: provisional`.

**What the guide validates, unprompted:** "a confidence score or a 'needs human
review' flag is a genuinely valuable feature"; "Real data is imperfect — say
so"; sourcing from manufacturer sites with marketplaces excluded; and "Show
your evaluation" naming field-level accuracy, character-limit compliance and
percentage of values found in the LOV as the metrics judges will look for.

**Two things it changes about our claims:**

1. **"Getting these formats right is most of the task."** The same product is
   written five times at five lengths and casings — invoice ≤40 CAPS, mobile
   60–80, title/short, long, attributes. §5.7 is the answer.
2. **Our §7 ground truth is no longer the primary one.** Judges will want
   field-level accuracy against their 200 known-good rows. The ISO 15 /
   ISO 898-1 methodology stays as a rigor argument, but it becomes the
   *second* metric. Add a benchmark; **do not edit the frozen corpus** — see
   the gotcha in §11.

**Their scope advice is "depth beats breadth":** one category classified,
attributed, described and validated end-to-end beats a thin pass over 1,000
rows. Recommendation on record: **Fittings**, because 1,472 supplier connection
types collapsing onto 515 approved values is many-to-one normalisation, which
is what this engine is already best at. Faucets is the narrower fallback.

---

## 2. Submission requirements (from the portal)

**Deadline: Sun 23 Aug 2026, 10:31 IST.** Five deliverables, all mandatory:

| Deliverable | Notes |
| --- | --- |
| Solution Overview | How the prototype solves the problem |
| **Prototype Link** | A **live MVP link**. Deployment is mandatory. |
| **Project Deck** | **A mandatory template must be used** — download it from the portal. |
| **GitHub Repository** | Must be a **public** link. **Done** — public since 11 Aug (§9). |
| Demo Video | Short walkthrough of the solution |

Consequences that shaped the design:

- **Judging is asynchronous.** Reviewers click a link with no API key of their
  own. Live-mode results for the demo products are therefore pre-computed and
  committed to `backend/app/data/precomputed/`, so selecting "Live AI" shows
  genuine model output at zero cost to anyone.
- **One link means one service.** FastAPI serves the built SPA from the same
  origin (`_mount_frontend()` in `main.py`, registered last so it cannot shadow
  an `/api` route). `frontend/dist` must exist; the Dockerfile builds it.
- **The deployment must not be able to spend.** `PI_ALLOW_SERVER_KEY=0` and no
  server key is configured in the image.
- **No organizer API credits are provided.** Budget is the user's own. See §3.1.

Two committed result layers exist and they are **not** interchangeable:

| Layer | Purpose | Served by the app? |
| --- | --- | --- |
| `backend/app/data/precomputed/` | 20 demo products, so a reviewer with no key sees live output | **Yes** — counted as `bundled` in `/api/health` |
| `backend/benchmark/records/` | 102 corpus records, so the benchmark reproduces | No — benchmark only |

### Live deployment — already done

**https://industrial-product-intelligence.onrender.com** — Render free tier,
auto-deploys on push to `main`, built from the root `Dockerfile`.

- **UptimeRobot pings `/api/health` every 5 min.** This is load-bearing, not
  cosmetic: a sleeping free instance returns **404**, not a loading page, so a
  reviewer's first click would look like a dead link. Do not pause that monitor.
- Verified in production: all four tabs, PDF ingest, and the full taxonomy
  learning loop. Warm latency ~0.3s.
- **Re-verified after the `54a7831` deploy** (that commit touched `app/cache.py`,
  which the service imports): `/api/enrich` returned 200 with a classified
  record, and the cache counters moved `0/0` → `misses 1, writes 1`, which is
  `key_for()` executing on the server. Pinging `/api/health` alone would not
  have proven that.
- FastAPI answers **GET and HEAD** — monitors send HEAD by default and a 405
  makes them report the service down.
- Hugging Face was the first choice but its Docker SDK is now paid; only Static
  Spaces are free and a static host cannot run the backend. Cloud Run config is
  retained in `deploy/README.md` if a faster cold start is ever wanted.

## 3. Deadlines and status

- **Submission deadline: 23 Aug 2026.** User wants development finished ~20 Aug
  to leave time for the presentation.
- Work started 5 Aug 2026. Phases 1–3 (backend) were completed on day one, so
  the project is running roughly 4 days ahead of the original plan.

| Phase | Scope | Status |
| --- | --- | --- |
| 1 | Evaluation harness + measured accuracy | **Done, committed** |
| 2 | PDF datasheet + product-page ingestion | **Done, committed** |
| 3 | Auto-taxonomy learning | **Done, committed** (backend + review UI, `35ed3a2`) |
| — | Live ablation (Claude vs deterministic) | **Done, 102/102, $1.62. Negative result — see §7.1.** |
| — | Hybrid gate (bounded Claude) | **Done, $0 — see §7.2. Best result in the project, and now a selectable engine in the product with a refusal ledger.** |
| 4 | Public deployment | **Done — live and monitored** |
| 5 | Deck | **Done** — `docs/UniHack_Prototype_Submission.pptx`, 15 slides, screenshots from the deployed app. Regenerate with `docs/deck/build_deck.py`. Team details + video link outstanding |
| 5b | Demo video | Not started — running order in §11 |
| 6 | Unilog compliance layer (§5.7) | **Done, $0** — built against the solution guide (§1.6) |
| 7 | Delivery format + accuracy (§7.3, §7.7) | **Done, $0** — 252 columns, both states reported everywhere |
| 8 | Taxonomy learning at volume (§7.4) | **Done, $0** — 8.9% → 81.7% on their 1,000 rows (38 of 83 proposals; 91.4% if all are approved — §7.4) |
| 9 | Discovery (§7.5) | **Done, $0** — sourcing policy enforced; fetch blocked by client-side rendering |
| 10 | Pre-deck audit (§7.6) | **Done** — four defects found and fixed |

**Everything above is complete, committed, pushed and deployed.** Eight test
suites pass (298 checks), the benchmark reproduces, and the live site is
verified on desktop and phone at 1900 / 1440 / 1300 / 1000 / 901 / 900 / 375 /
320 px.

**Post-briefing work (6 Aug), all $0:** per-attribute source URLs (§5.5), the
cost model (§7.05), profile-driven export (§5 `export/`), and the hybrid gate
shipped as a product engine with a refusal ledger (§7.2).

**One engineering item remains: discovery from brand + MPN — §11.1.** It is the
organizers' stated core problem and is held pending their sample data.

---

## 3.1 Cost discipline — READ BEFORE ANY LIVE RUN

Credit was topped up to **$9.18**; **~$2.22 spent** (precompute $0.39, ablation
$0.21 + $1.62), so roughly **$6.96 remains**. An earlier mistake burned ~$2.63
with nothing to show for it. Do not repeat it.

The approved ~$3.00 plan is **complete**: precompute (done) and ablation (done).
The third item, a live taxonomy proposer, was never started and is now a
**weaker bet** — it is the same architecture the ablation showed produces
confident-looking values it cannot defend, measured against hand-authored
ground truth (the weaker half of the corpus). Recommendation on record: don't.

**There is nothing left worth buying.** Confirm before any further spend.

**What went wrong:** a background benchmark run was started, its empty log was
misread as a crash (Python block-buffers stdout to a file), and a *second* run
was launched. Both ran concurrently, doubling the burn rate, and both died
before writing results. `Get-Process python` returned 0 because the process is
actually named `python3.13.exe` — that false negative is what triggered the
second launch.

**Rules now enforced in code** (`backend/run_benchmark.py`, proven by
`backend/test_cost_guards.py`):

- `RunLock` — a second benchmark refuses to start while one holds the lock;
  a stale lock from a killed run auto-clears.
- Hard ceiling — measured spend is checked **after every case** and aborts the
  run the moment it crosses `--budget` (default $5). Max overshoot: one case.
- Result caching on the benchmark path — an aborted run resumes free.

**Rules for the assistant:**

- Never launch a paid run without the user explicitly agreeing to the spend.
- Never launch two of anything that spends.
- To check for a running Python process on Windows use
  `Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*run_benchmark*' }`,
  **not** `Get-Process python`.
- An empty log file does not mean a process died. Verify with the process list.

---

## 4. Secrets

- The live API key lives in **`backend/.env`** (gitignored, verified).
  `backend/.env.example` is **tracked** — never put a real key there.
  The user once pasted a key into `.env.example`; it was moved and scrubbed
  before any commit, and `git log --all -p | grep sk-ant-api03` returns nothing.
- `PI_ALLOW_SERVER_KEY` defaults to `0`, so a visitor supplying no key can
  **never** spend the server's key. This is verified behaviour, not a claim.
- Outstanding user actions (non-blocking): rotate the API key (it passed
  through a conversation transcript), and delete `backend/.env` when live
  testing is finished.

---

## 5. Architecture

```
Input ─┬─ form / CSV / batch
       ├─ PDF datasheet      ─┐
       └─ product page URL   ─┴─→ app/ingest/* → RawProduct
                                            │
   normalize → classify → extract → infer → reconcile → content → validate → score
                                            │
                                     EnrichedProduct
```

**The load-bearing design decision:** every input path produces a `RawProduct`
and hands off to the *same* pipeline. A value read off page 2 of a datasheet
earns the same provenance, confidence, cross-field validation and readiness
score as a CSV row. Do not add a parallel path for a new input type.

### Backend (`backend/app/`)

| Path | Role |
| --- | --- |
| `models.py` | All schemas. `RawProduct`, `Attribute`, `EnrichedProduct`, `GateDecision`, `CategoryProposal` |
| `config.py` | Env config; loads `backend/.env`; demo mode is the default |
| `cache.py` | Content-addressed result cache (input hash + mode + model). `key_for()` is public so other read-only layers address records identically |
| `main.py` | FastAPI app, all endpoints |
| `pipeline/units.py` | Unit parsing/normalization; canonical unit per dimension |
| `pipeline/taxonomy.py` | Category classification; merges curated + learned categories |
| `pipeline/extract.py` | Deterministic extraction (spec tables + 3 prose strategies) |
| `pipeline/validate.py` | Range/vocabulary/required checks + 16 cross-field rules + the standards contradiction check (§7.8) |
| `pipeline/run.py` | Stage orchestration, reconciliation, readiness scoring |
| `pipeline/gate.py` | **The hybrid gate** — model may add, never overrule; records every decision |
| `providers/mock.py` | Deterministic engine — knowledge-base driven, free, default |
| `providers/anthropic_provider.py` | Claude engine via tool-schema structured output |
| `ingest/pdf.py` | Datasheet parsing (3 layouts) |
| `ingest/web.py` | Product page parsing (JSON-LD first) + SSRF guard |
| `taxonomy_learning/propose.py` | Clusters unclassified products, infers schemas |
| `taxonomy_learning/store.py` | Proposal queue + learned-category persistence |
| `benchmark/corpus.py` | 102-case corpus; ISO-backed + archetype ground truth |
| `benchmark/evaluate.py` | Scoring. `enricher=` scores pre-built records without a provider |
| `benchmark/hybrid.py` | Thin re-export of `pipeline/gate.py` in the shape the scorer wants |
| `benchmark/records.py` | Loader/exporter for the committed live records |
| `benchmark/records/` | 102 committed live records, 0.88 MB — makes §7.2 reproducible |
| `unilog/house_style.py` | Approved UOM lookup + exact-64th decimal↔fraction + casing |
| `unilog/content_formats.py` | The five commerce descriptions, built by token formula to character limits |
| `unilog/lov.py` | Controlled vocabulary: accept / map / **refuse**, plus attribute sequence |
| `unilog/ground_truth.py` | Their labelled rows scored both ways; shared by the API, the CLI and the deck so no two can disagree |
| `ingest/unilog_rows.py` | Their catalogue rows → `RawProduct`; vendor ≠ manufacturer, placeholder filtering |
| `data/unilog_samples/` | Their 1,000-row input and 252-column labelled delivery rows |
| `unilog/ground_truth.py` | Their labelled rows scored both ways (§7.7) — shared by the API, the CLI and the deck |
| `data/unilog/` | `uom_standards`, `abbreviations`, `content_formats`, `lov/` — **all provisional stubs; their spreadsheets replace these files, not the code** |
| `export/profiles.py` | Profile-driven output rendering; target schema is data |
| `data/export_profiles/` | `catalog_csv`, `schema_org`, `unilog_delivery` — **add a customer schema here, not in code** |
| `data/taxonomy.json` | 10 curated categories — **edit data, not code, to add one** |

### Frontend (`frontend/src/`)

React 19 + Vite, no runtime UI dependencies. Five tabs: **Single Product**,
**Document**, **Discover**, **Catalog**, **Learning**. Three engines: **Demo**,
**Hybrid**, **Live AI**. Vite proxies `/api` to port 8000.

**The Accuracy tab was removed on 12 Aug** — §7.7 held the question open and the
user closed it. `GroundTruthPanel.jsx` and `api.getGroundTruth` are gone. The
measurement is not: `/api/ground-truth`, `run_expected_vs_ours.py` and
`app/unilog/ground_truth.py` are all untouched, `test_unilog.py` still asserts
both states, and deck slide 8 still carries the argument. It was a benchmark
wearing the costume of a product feature, and a skimming judge could read
**2/14** in large type and stop before the sentence explaining it.

`CompliancePanel.jsx` ("Content Standard") and `ExportPanel.jsx` surface the
§5.7 compliance layer and the profile-driven exports, which until 12 Aug existed
only in the API — see §7.8. `ExportPanel` reads `/api/export/profiles`, so a new
output schema still needs no UI change.

`DiscoveryPanel.jsx` carries the source ledger, built to mirror `GateLedger`:
refusals sort first, because what the crawler declined to read is the evidence
that the manufacturer-only rule is enforced rather than asserted. Verified in
the browser on all four demo parts; five tabs still fit the mobile bottom bar
(5 x 70px in 373px, no overflow).

**Header sizing is content-driven, and that was a bug fix.** `.main-nav` and
`.engine-toggle` were pinned at 380px and 150px from when there were four tabs
and two engines. A `.tab` is `flex: 1 1 0` with `min-width: auto`, so it may
shrink to its *min-content* width — and min-content for a two-word label is its
longest word. "Live AI" collapsed to the width of "Live" and wrapped onto two
lines while single-word "Hybrid" held its ground. Both containers are now
`width: auto; flex: 0 0 auto` and `.tab` is `white-space: nowrap`, re-enabled to
`normal` only in the mobile bottom bar where "Single Product" is *meant* to sit
over two lines. A new tab now widens the bar instead of breaking its narrowest
neighbour. Between 901px and 1300px the brand takes its own row: the header is
`nowrap`, so before that rule it crushed the brand to 128px and ellipsized the
status pill rather than wrapping.

**The audit that missed it, and why.** The first UI sweep checked
`scrollWidth > clientWidth`. Wrapped text does not trigger that — it overflows
*vertically*, and a flex item that shrinks to min-content reports no horizontal
overflow at all. Any future check must count rendered line boxes
(`Range.getClientRects().length`) for controls whose labels must stay on one
line, and must sweep the widths where media queries flip (1301 / 1300 / 901 /
900 / 375 / 320), not just one desktop and one phone size.

Design tokens in `styles.css` (`--s1..--s6` spacing, `--fs-*` type, three
elevation steps) and a dark theme driven by `prefers-color-scheme` plus a
`data-theme` override, so an explicit light choice beats an OS set to dark.
Below 900px the primary nav becomes a fixed bottom bar and both bars retreat on
a downward scroll. The header retreats by animating its sticky `top`, **never**
by transform: the nav is its DOM child, and a transformed ancestor becomes the
containing block for `position: fixed` descendants, which tears the bottom bar
off the screen.

---

## 5.5 Source citation — a stated "must"

`Attribute` carries `source_url` and `source_locator`. A value read off a web
page cites the page URL; a value read out of a datasheet cites **the page
number** it was found on, because "page 2" is what makes a spec checkable.
`RawProduct.spec_sources` maps each raw spec key to its origin, which is how the
page number survives into the attribute. Both travel into the UI (a followable
link in the attribute drawer) and the CSV export (a per-attribute column).

Values a **standard or calculation** yields keep a null `source_url`
deliberately — inventing a URL for an ISO 15 lookup would be worse than
admitting there is not one, and `evidence` already names the standard.

**Trap, already paid for:** `spec_sources` is excluded from `_cache_payload()`
in `main.py`. The cache key hashes that payload, so including it changed every
key and silently orphaned all 20 precomputed live results — hybrid mode would
have quietly stopped working for keyless reviewers. Any future field describing
the *fetch* rather than the *product* belongs in that exclusion. Caught only
because `test_hybrid.py` asserts the precomputed path still runs.

---

## 5.7 The compliance layer — house style, vocabularies, formats

Built 10 Aug against §1.6, all $0. Proven by `test_unilog.py` (100 checks).

Pipeline is now
`normalize → classify → extract → infer → reconcile → **vocabulary** → content
→ **compliance** → validate → score`.

**Compliance is scored separately from readiness, on purpose.** Readiness asks
whether the data is *right*; compliance asks whether it is *written the way the
customer's standard requires*. `ComplianceReport.verdict` is its own verdict.
Collapsing them would hide which one needs fixing — and, concretely, a mobile
description three characters short would have dragged down a data-quality score
and silently moved §7's `auto-publishable` figure.

**Every rule refuses rather than guesses**, matching the gate:

| Rule | Accepts | Refuses |
| --- | --- | --- |
| Fractions | exact 64ths only (`50.25 → 50-1/4`) | `0.3` stays `0.3 in`; it is not 19/64 |
| Units | any spelling in the approved table (`inches → in`, always number-space-unit) | an unapproved unit is **withheld from the copy**, not printed |
| List of values | exact, case, and explicit synonym (`CPLG → Coupling`, `BRS → Brass`) | an unlisted value keeps its original, raises `LOV_VIOLATION`, and a near miss is **suggested, never applied** |
| Character limits | drops whole low-priority tokens to fit | clipping only when *required* tokens overflow, and it is reported as a breach |

That last row is the one to demo. A 40-character invoice line built by cutting
at 40 gives `...PDSH4816AF DISHWA` — a truncated MPN is unsearchable. Dropping
tokens gives `DISHWASHER LEG 5 SST 120V 15A CLEANBOOST` and names what it
dropped.

Against their worked example the title comes out
`FRIGIDAIRE® Professional Series PDSH4816AF Dishwasher With CleanBoost™, Leg
Mounting, 5 Wash Cycles, Stainless Steel, 120 V` — structurally theirs, modulo
the `5-Wash Cycle` hyphenation rule that lives in the guidelines .docx we do not
have.

**Two design seams that matter when their files land:**

- `lov.json` entries carry `applies_to`, mapping *their* classpath onto our
  taxonomy codes. It is **deliberately empty**: binding a hand-written stub onto
  `Hose & Fittings` (40142000) would move published benchmark figures on the
  strength of invented values. Bind it and re-measure when the real
  `Fittings_LOV.xlsx` arrives.
- Every stub reports `source: "provisional"`, and that string travels into
  `ComplianceReport.standards` and the export. Nothing can claim verified
  compliance against a table we wrote ourselves.

**Verified non-regression:** all seven pre-existing suites pass, the benchmark
reproduces 2.75× / 0.0% / 100% / 31.4%, and the hybrid reproduces
99.5 / 41.7 / 57-10-28 unchanged. The vocabulary stage is inert on every
curated category, which is what keeps that true.

---

## 6. Key concepts

**Provenance** drives reconciliation, scoring and the UI colour ramp:
`supplied` > `parsed` > `knowledge_base` > `derived` > `inferred` > `defaulted`.
When two stages disagree the stronger provenance wins, the conflict is
recorded, and the winner's confidence is *reduced* — disagreement is itself
evidence of uncertainty.

**Readiness** is scored on three independent axes (completeness, confidence,
validity) because a record can be complete but contradictory, or clean but
sparse, and those need different remediation. Verdict: `publish` / `review` /
`blocked`.

**Integrity vs advisory warnings** (`validate.INTEGRITY_CODES`): an integrity
warning means the data may not describe a physically coherent product, so it
can never auto-publish. Advisory warnings (e.g. `LOW_CONFIDENCE`) do not block.

---

## 7. Measured results (deterministic engine, 102-case benchmark)

Run: `cd backend && python run_benchmark.py`

| Metric | Result |
| --- | --- |
| Attribute coverage lift | **2.75×** |
| Withheld attributes recovered | 61.1% |
| **Contradiction rate on evidence-backed values** | **0.0%** |
| Contradiction rate incl. flagged defaults | 11.1% |
| Seeded defects caught | **100%** (51/51) |
| Defective records stopped from auto-publishing | **100%** |
| False alarms on clean records | **0.0%** |
| Throughput | ~305 products/s |

**The headline is the contradiction rate, not coverage.** Coverage is cheap —
any system reaches 100% by inventing everything. Precision is 100% on
`knowledge_base`, `derived` and `parsed` values; only `defaulted` (explicitly
flagged as unconfirmed) sits at ~76%.

Methodology note that survives scrutiny: bearing and fastener ground truth
comes from **ISO 15 / ISO 898-1** (externally fixed — the engine cannot be
tuned to it without also being right in reality). Other categories use
hand-authored archetypes and are **reported separately**. Only *withheld*
attributes are scored.

**Known gap that motivated the live ablation:** recall is 83.1% on
standards-backed categories vs 33.1% on archetype categories.

---

## 7.05 Cost per SKU — an explicit judging factor

Run: `cd backend && python run_cost_model.py` ($0 — replays committed records).

**Triage is sound, not heuristic.** Under the gate policy the model may only
fill a gap or displace a default, so a record with neither offers it nothing it
is *allowed* to change. Skipping those forfeits nothing, and the script proves
it by gating the skipped cases anyway and asserting zero acceptances.

| | $/SKU | $/month at 750k |
| --- | --- | --- |
| Every SKU to the model, standard rate | $0.02381 | $17,857 |
| + deterministic-first triage (70.6% call rate) | $0.01681 | $12,605 |
| + Batch API (50%) | **$0.00840** | **$6,302** |

Against the organizers' own baseline — 10 min/SKU at $35/hr = **$5.83/SKU** —
that is **0.14% of manual cost**. Scalability at that volume: **0.7 compute
hours/month** deterministic and **0.20 sustained model calls/second**. The
binding constraint is the API rate limit, not the engine.

**Two traps this section exists to prevent:**

1. **The ablation was billed at Sonnet 5 *introductory* rates ($2/$10 per
   MTok), which lapse 2026-08-31 — eight days after the deadline.** Quote the
   standard $3/$15 figures above; the $0.01587 number that appears in
   `spend_live.json` is the introductory one.
2. **Output is 65% of spend** (2,777 input vs 1,032 output tokens per call), so
   prompt caching — an input-side discount — is a *smaller* lever than the
   Batch API, which discounts both halves.

Measured: triage rate, token counts, introductory cost. Projected: standard-rate
and batch figures, from published rates. `run_cost_model.py` labels which is
which, and the deck should too.

---

## 7.1 Live ablation result (102/102, $1.62) — a negative result

The LLM did **not** close the archetype gap. It widened it, and it broke the
submission's headline claim.

| Metric | demo (deterministic) | live (Claude) |
| --- | --- | --- |
| Archetype recall | 33.1% | **27.0%** |
| Standards recall | 83.1% | **98.1%** |
| Standards precision | 95.3% | **81.3%** |
| Contradiction rate | 11.1% | 18.6% |
| **…excluding flagged defaults** | **0.0%** | **16.5%** |
| False alarms | 0.0% | 2.0% |
| Throughput | 305/s | 0.1/s |

Precision by provenance shows where it fails: `knowledge_base` 100% → 79.8%,
`parsed` 100% → 94.9%, plus a live-only `inferred` class at 60.0%. On ISO 15 /
ISO 898-1 values — externally fixed ground truth — Claude recovers 31 more
attributes but contradicts 38 instead of 8.

**Trap in the summary line:** live reports "auto-publishable 51.0%" vs 31.4%.
That is worse, not better — more records clear the gate while carrying more
contradictions.

**Root cause, since fixed by the gate:** the Claude provider tags its own output
with provenance classes (`knowledge_base`, `parsed`) that mean *evidence-backed*.
It inherits trust it has not earned, so reconciliation lets it overrule the
knowledge base. §7.2 bounds this.

**Caveats before this goes in the deck:** 12 cases came from an earlier cached
run; and `inferred` exists only on the live path, so part of the precision gap
is a provenance-policy difference rather than pure model error.

**Framing:** this validates the architecture. The deterministic engine is the
correct default; the LLM is a recall instrument that must be gated behind
validation, not trusted as a source.

---

## 7.2 The hybrid gate — the result to lead with

`benchmark/hybrid.py`. Policy, not prompt engineering: under the existing
provenance rank a model proposal is worth less than evidence and more than a
category default, so Claude gets exactly two moves — **fill a gap** and
**displace a `defaulted` value** — and everything it contributes is re-stamped
`inferred`. It may never overrule `supplied` / `parsed` / `knowledge_base` /
`derived`.

| Metric | demo | live | **hybrid** |
| --- | --- | --- | --- |
| Standards recall | 83.1% | 98.1% | **99.5%** |
| Archetype recall | 33.1% | 27.0% | **41.7%** |
| Contradiction rate | 11.1% | 18.6% | 12.8% |
| False alarms | 0.0% | 2.0% | **0.0%** |
| Defects caught | 100% | 100% | **100%** |
| Defects stopped | 100% | 100% | **100%** |
| Auto-publishable | 31.4% | 51.0% | **52.9%** |

**The claim that survives, and it is the important one:** precision on
`knowledge_base`, `parsed` and `derived` is **still exactly 100.0%** (72/0,
43/0, 8/0 — byte-identical to the deterministic run). The gate raised standards
recall by 16.4 points and archetype recall by 8.6 without touching a single
evidence-backed value. The hybrid beats the raw LLM on *both* recall axes.

Gate actions across 102 cases: **57 gap-filled, 10 defaults displaced, 28
overrules refused.** Those 28 refusals are most of the live engine's damage.

**Do not quote "contradiction excluding defaults" for the hybrid** (8.8% vs the
deterministic 0.0%) without explaining it: that bucket now contains the new
`inferred` class (72.4% precision — better than live's 60.0%), which the
deterministic engine simply does not have. The like-for-like comparison is the
per-provenance table, where nothing regressed.

Verdict shift is real: blocked 33 → 22, publish 16 → 27 on clean records,
because gap-fills satisfied `MISSING_REQUIRED` rather than because the bar
moved.

**Shipped in the product, not just the benchmark.** `Hybrid` is a third engine
beside Demo and Live AI. The policy lives in `app/pipeline/gate.py` and
`benchmark/hybrid.py` re-exports it, so the published figures and the running
service can never describe different software — verified by the benchmark
reproducing 99.5 / 41.7 / 57-10-28 unchanged after the move.

Hybrid costs **nothing** on the demo products: it merges the deterministic run
with the live record already in `app/data/precomputed/`, so a reviewer with no
API key sees the gate work. Proven by `test_hybrid.py`, which asserts the cache
write count does not move — a write would mean a provider call, which would mean
spend. With no stored record and no key it returns the deterministic record and
says so, rather than pretending a gate ran with nothing to gate.

The UI shows a **refusal ledger**: every model proposal, whether it was accepted
or refused, and why. Refusals sort first. On the headline bearing the model
proposes 14.8 kN against ISO 15's 14 kN and 14000 rpm against 16000 — both
refused, with a Polyamide cage accepted over the `Steel` default. That is the
architecture's claim made visible in one screen.

**Reproducible by a judge.** The 102 paid live records are committed to
`backend/benchmark/records/` (0.88 MB), keyed by the same content address the
runtime cache uses. Verified by running `run_hybrid.py` with `PI_CACHE_DIR`
pointed at an empty directory — a fresh clone exactly — and getting identical
numbers. Deliberately *not* in `app/data/precomputed/`: that layer is what the
deployed app serves to reviewers, and corpus records would inflate the
`bundled: 20` count in `/api/health` and the image for files the service never
reads.

---

## 7.3 Delivery-format accuracy — the metric judges asked for

Run: `cd backend && python run_delivery_accuracy.py` ($0).

Scored against Unilog's two labelled 252-column rows. This is a **second**
benchmark, not a replacement for §7: that one asks whether the engineering is
right against ISO ground truth, this asks whether the output is written the way
the customer requires. They fail independently.

**Two numbers, and quoting the first without the second is overclaiming.**
Run `python run_expected_vs_ours.py` — it always prints both:

| | |
| --- | --- |
| **A. Formatter given the attribute values** | **14/14 exact**, both rows, character for character |
| **B. Pipeline from the 6-column input row** | **2/14 exact** |

A measures the content-format layer — character limits, token dropping, casing,
fractions — and it is genuinely exact. B is the end-to-end reality: Series,
Mounting, Wash Cycles and Voltage are simply not in a catalogue row, so the
prose comes out as "Dishwasher". The gap is **sourcing, not formatting**, and it
is the same gap the 14.0% field-level figure and the 88-blank-fields count
describe.

An earlier version of this section stated 14/14 alone, which reads as an
end-to-end claim the pipeline cannot support. Deck slide 8 now shows their
expected value beside ours with the condition on the slide.

The formatting rules behind A were derived from those two rows and live in
`data/unilog/content_formats.json`:

- Greedy priority fitting reproduces both invoice lines: row 1 keeps the depth
  and drops the sound level at 38 chars, row 2 drops the depth and keeps the
  sound level at 39. Same algorithm, no per-row tuning.
- The mobile line **stops growing once it clears 60**, which is why their padded
  row carries one extra attribute rather than every attribute that fits.
- Brand outranks manufacturer on a containment clash: "Whirlpool Corporation"
  yields to "Whirlpool", while "Rheem Manufacturing FRIGIDAIRE" keeps both.
- `5-Wash Cycle` hyphenates because the value is numeric; `Leg Mounting` does
  not, because it is an enum.
- A multi-value feature list fills the `With` column but never goes inline.

**On the full 252 columns the honest number is 14.0%,** and the split is the
point:

| | |
| --- | --- |
| Field-level accuracy | **14.0%** (16/114) |
| Coverage — fields attempted | 22.8% |
| **Precision when we answer** | **61.5%** (16/26) |
| Contradicted | 10 |
| Sourced beyond the label | 2 (their cell blank, ours populated) |

**88 of 114 fields are blank because the data is not in the input row.** Voltage,
amperage, sound level, rack heights and cabinet dimensions exist only on
frigidaire.com — which their own delivery row cites as `MFR URL`. A 6-column
catalogue row cannot yield them, and the engine leaves them empty rather than
inventing them.

**This is the measured case for discovery, and it supersedes the reasoning in
§1.6/§11.1.** Web discovery was demoted on the guide's "two or three steps done
well" advice; this benchmark now quantifies the ceiling without it. Roughly
three quarters of the delivery format is unreachable from the input alone. That
is an argument from evidence rather than from the brief — see §11.1.

**Volume, their 1,000-row file:** 1,000 rows in 1.64 s (**611 products/s**),
2,599 placeholders dropped, 959 vendor strings split from their account codes,
448 brands recovered (442 from the brand columns, 6 from descriptions — all
correct, no false positives). **Only 8.9% classify**, because our 11-category
industrial taxonomy does not cover their lighting, lumber, decking and window
SKUs. That is what the auto-taxonomy learner is for, and it is the other
measured gap.

---

## 7.4 Taxonomy learning on their 1,000 rows — three bugs it exposed

Run: the loop is `propose -> save_proposals -> approve -> reclassify`
(see `[8]` in `test_taxonomy_learning.py`). $0.

**Result: classification coverage 8.9% -> 81.7%**, from 38 categories learned
out of 911 unclassified rows. Every record under a learned category is
**blocked**, by design — see the third bug.

**Both halves of that sentence carry a condition, and it went unstated for a
day.** Re-measured 12 Aug: the loop produces **83 proposals and 91.4%** coverage
if every proposal is approved. The published 38 / 81.7% is what you get
approving only clusters with **at least 5 supporting rows** — verified exactly,
`support >= 5` reproduces 38 and 81.7% to the digit. That filter is a sensible
reviewer's behaviour (three rows is thin evidence for a whole category) but it
is a *human* act, not something the engine does, and quoting the filtered number
as the loop's output is the same overclaim §7.3 already corrected once for
14/14. Quote it as "38 categories a reviewer would accept, out of 83 proposed".

Support distribution, so the filter is inspectable: 82, 30, 21, 21, 21, 20, 18,
17, 14, 14, 14, 14, … with a floor of 3.

Running at volume broke three things that ten curated categories never could.
All three are fixed and each has a regression test.

**1. The clusterer collapsed 872 of 911 rows into one group.** Field overlap was
weighted 0.7 because a spec table is stronger evidence than wording — but these
rows have no spec table, so every pair scored a *perfect* overlap on nothing.
Field overlap now only counts when there is something to compare
(`len(union) >= 2`); otherwise the description decides alone. 306 clusters.

**2. Eleven proposals shared a code with another proposal.** `_code_for` hashed
the noun alone, so any two clusters named alike collided — and two learned
categories with one code make `revoke()` delete the wrong one. The code now
hashes noun + keywords, and clusters that produce the same name *and* keywords
are merged before proposing, because by our own definition they are the same
category. Zero collisions.

**3. The bad one: a row with no product data published at 99.7/100.** A 3M
abrasive disc classified as "Milw Discs", carrying exactly one attribute —
`vendor` — which arrived with `supplied` provenance because the feed genuinely
did supply it. Completeness is `filled / defined`, so 1 of 1 scored 100%.

Two fixes, because there were two faults:

- `_BOOKKEEPING` keys were already excluded from the clustering signature but
  not from the proposed *schema*. Vendor, manufacturer and the brand columns
  describe the row, not the product, and can never be attributes.
- **A category with no attribute schema can never auto-publish.** There is
  nothing to validate against, so every record under it scores full marks on an
  empty exam. `score_readiness` now blocks with that stated as the reason.

Schema-only categories are still *proposed* — knowing 82 rows are LED lamps is
worth having for routing and for aiming enrichment — but their confidence is
capped at 0.45 so they can never outrank a proposal that inferred a real schema.

**Honest caveat, visible in the output:** learned names are brand-led and
over-match. A Diablo sanding belt lands in "Saw Blades", a 3M disc in "Milw
Discs". Nothing published because of it, and human approval is the designed
mitigation, but do not claim clean classification — claim that wrong guesses are
caught before they reach a storefront. Re-measured 12 Aug, the names are worse
than that sentence suggests: "Led Meds", "Metal Offs", "Harvest Pvcs",
"Pvc Deckings" — mangled plurals of marketing words, not category names. Still
harmless (everything under them blocks) but do not put them on a slide.

**One fix that came out of re-running it:** two clusters that name alike but
keep different keywords are deliberately not merged — they are different groups
— and at volume that put **two separate "Trex Enhances" proposals in one review
queue**. Human approval is the designed mitigation for everything this feature
does, and a reviewer who cannot tell two proposals apart cannot review them.
`_disambiguate()` now qualifies a repeated name with the first keyword its
namesakes lack ("Trex Enhances (Decking)" / "(Golden)"), falling back to the
code's last four digits. **The code itself is untouched** — it is derived from
noun + keywords, is already unique, and `revoke()` depends on that stability.

---

## 7.5 Discovery — built, and the measurement is a negative result

`app/discovery/`. Run: `POST /api/discover {brand, mpn}`, or
`python test_discovery.py` (54 checks, no network, $0).

Brand + MPN -> candidate URLs -> **source policy** -> fetch -> `RawProduct` ->
the *same* pipeline. No parallel path: a value read off a manufacturer page
earns the same provenance, validation and readiness score as a form entry.

**The sourcing policy is the feature.** Their brief states three times that data
must be manufacturer-provided, so the policy is data (`data/discovery/sources.json`)
and every candidate is recorded accepted or refused with a reason — the same
ledger idea as the hybrid gate. Three choices are stricter than the brief:

- **Distributors and retailers are blocked alongside marketplaces.** A Grainger
  or Home Depot page is the second-hand copy Unilog exists to correct, so
  sourcing from it is circular.
- **An unknown domain is refused, not fetched.** Allow-by-default would let a
  blog become a cited source. A page is only manufacturer-provided if the domain
  can be shown to belong to the manufacturer.
- **Another maker's official site is refused for this part.** skf.com is not
  evidence about a Frigidaire dishwasher.

**Two backends, and the free one is default.** `BrandDomainBackend` ($0) builds
official URLs from the registry's templates — their own delivery row cites
`frigidaire.com/.../PDSH4816AF`, which is a template with the MPN in it, so no
search engine is needed for the predictable cases. `ClaudeWebSearchBackend`
spends, refuses to construct without a key, and **is not reachable from the API**.

### The result: fetch-and-parse does not work on modern manufacturer sites

Measured against four real sites, no API cost:

| Brand | HTTP | Bytes | JSON-LD | Specs parsed |
| --- | --- | --- | --- | --- |
| Frigidaire | 200 | 45 KB | 0 | **0** |
| Milwaukee | 200 | 1.0 MB | 1 | 0 specs, but name/brand/MPN recovered |
| SKF | 200 | 24 KB | 0 | **0** |
| Whirlpool | 404 | — | — | template wrong |

**Zero of four yielded a spec table.** §11.1 predicted this for SKF; it holds
for the product in their own ground truth too. The pages render client-side, and
the engine reports `fetched but nothing usable was parsed — likely rendered
client-side` rather than treating an empty page as a product with no
specifications. That distinction is the point: a tooling gap must not become a
false claim about the part.

**So discovery does not move §7.3's 14.0% yet.** Closing it needs headless
rendering or paid search with content extraction — not more parsing. Do not
claim discovery as a solved step; claim that the sourcing rule is enforced and
the ceiling is now known.

**A third bug, found only by looking at the UI:** an empty page was recorded as
an *accepted* source, so the ledger read "1 used" for a page that contributed
nothing. It is now recorded as refused — it passed policy but gave nothing, and
a ledger that calls it a source overstates what the record rests on. The panel
also states, when discovery finds nothing, that any record shown was built from
the part number alone; without that the SKF case shows "nothing was written"
directly above a 94/100 publishable record, which reads as a contradiction
rather than as ISO 15 decoding doing its job.

**Two bugs it exposed, both fixed:**

1. `_from_json_ld` read `additionalProperty` only. Milwaukee publishes a weight
   as a first-class schema.org property, so a page that *did* carry specs was
   walked away from. Standard product measures are now mapped.
2. **The classifier read application prose as identity.** A Milwaukee cut-off
   wheel scored **0.861 as a fastener** because its page says it cuts bolts,
   nuts and threaded rod. Confidence is now capped at
   `CIRCUMSTANTIAL_CONFIDENCE` (0.5) when no category keyword appears in the
   product *name* and the MPN pattern did not match. The cap deliberately cannot
   change which category wins — only how certain the claim is — so the 102-case
   benchmark is untouched.

---

## 7.6 Pre-deck audit (11 Aug) — what independent checking found

Everything below was verified rather than assumed, because most of these claims
were written by the same process that produced the code.

**What held up:**

- **The ISO ground truth is real.** Spot-checked against published ISO 15
  values: 6200 = 10/30/9, 6203 = 17/40/12, 6205 = 25/52/15, 6305 = 25/62/17,
  and the whole 62xx/63xx progression. These are externally fixed — the engine
  cannot be tuned to them without also being right in reality, which is the
  whole point of §7's methodology note.
- **16 cross-field rules registered, 16 referenced from taxonomy.json, zero
  orphans.** The count in §1 is accurate and nothing is dead.
- **All 13 documented commands run.** No stale instructions.
- **The SSRF guard works against the real target.** `169.254.169.254` (the AWS
  metadata endpoint) is refused, verified through the UI, error rendered.

**Four defects found and fixed:**

1. **Corrupted bullets in a record served to reviewers.** `[str(b) for b in ...]`
   iterates a bare string character by character, so a tool call answering
   `"bullets": "Standard"` stored `['S','t','a','n','d','a','r','d']`. **One of
   the twenty precomputed demo records shipped this** — the Koyo 6301-2RS
   bearing — and four benchmark records held leaked `<parameter` markup.
   Repaired by a validator on `CommerceContent` so the already-paid records
   render correctly without re-buying them, plus a type guard in the provider.
2. **Empty fields reported as compliant.** A format whose required tokens all
   resolved to nothing produced `""` and scored `compliant: true`, so an
   unclassified product passed the content standard on seven blank fields.
3. **Long unbroken tokens broke the layout.** A 200-character MPN set its own
   container width — `.content-title` at 1356px inside a 317px card, a `.pill`
   reaching x=1408 on a 375px screen. Fixed with `overflow-wrap: anywhere` and
   a capped, ellipsized pill.
4. Discovery's "1 used" badge for a page that yielded nothing (§7.5).

**One honest caveat for the deck.** The corpus uses *nominal* ISO 898-1 tensile
values (10.9 = 1000 MPa) where the standard's stated minimum is 1040 MPa. In the
live ablation Claude answered 1040 and 1220 and was scored as contradicting.
That is **2 of 46** contradictions where the model was arguably more precise than
the ground truth. It does not change §7.1's conclusion, but do not claim the 46
are all model error.

**UI verified, not assumed:** five tabs x two breakpoints x light and dark, with
records loaded and with pathological input. No overflow, no console errors, no
clipped text. Wide tables scroll inside their own containers rather than pushing
the page. Production bundle builds.

---

## 7.7 Their evaluation — endpoint and CLI, no longer a tab

`GET /api/ground-truth` and `python run_expected_vs_ours.py`. Both read
`app/unilog/ground_truth.py`, so the endpoint, the script and the deck cannot
quote different numbers.

**The Accuracy tab that used to render this was removed on 12 Aug** — the open
question this section carried is now settled, against keeping it. It was a
benchmark rather than a product feature, no real Unilog user would open it, and
a skimming judge could read **2/14** in large type and stop before the sentence
that explains it. `GroundTruthPanel.jsx` and `api.getGroundTruth` are deleted;
`docs/deck/shots.py` no longer captures a fifth screenshot (slide 12 only ever
used four).

**The measurement is untouched.** The endpoint, the CLI and
`expected_vs_ours.json` all still work, `test_unilog.py` still asserts both
states are present in the payload and on every field, and **deck slide 8 is now
the only place a judge sees this** — which makes it load-bearing. Do not weaken
slide 8's qualification when editing the deck.

---

## 7.8 QA pass (12 Aug) — three defects an outside test found

An independent A–Z pass against the deployed build. Most claims held: the 16
cross-field rules caught **5 of 5 novel contradictions** they had never seen,
including geometry in a category the documented example never used and a motor
current computed from power and voltage; 5 clean products across 5 categories
published with zero false alarms; the gate reproduced its documented refusals
keylessly; determinism was proven on two fresh cache keys. Every benchmark
figure in §7 and §7.2 re-measured **unchanged** after the fixes below.

Three defects were real, and all three broke the same promise from different
directions. Each has a regression in `backend/test_qa_fixes.py` ($0).

**1. A part number's own standard could not contradict a supplied dimension.**
A bearing marked **6205** published a supplier bore of **30 mm at 99%
confidence, verdict `publish`** — while the same card cited ISO 15 for the
Outer Diameter and Width either side of it. Root cause: `_from_series_table`
skipped any key the supplier had already filled (`if key in have: continue`),
so the knowledge base could only ever *agree*. The fastener path had the
equivalent check (`grade_tensile`) and caught its own version of this; bearings
did not.

The fix keeps the supplier's value — they may hold a variant the table does not
cover, and a lookup is not entitled to overrule the person holding the part —
but the standard is now *heard*: the disagreement is recorded, confidence drops
by the same 0.05 any conflict costs, the evidence line states what the standard
says, and `STANDARD_CONTRADICTION` is an integrity warning, so the record goes
to review instead of to a storefront. Deliberately a warning, not an error:
both numbers are individually plausible and we cannot know which is wrong.

**2. The cache ignored the learned taxonomy.** Approving a category did not
change the answer for a product already cached, so the documented learning loop
("re-submit and it now scores highly") failed for the exact product used to
train it — while an identical product with one character changed in the SKU
classified correctly. `key_for()` now folds in a taxonomy fingerprint. **The
fingerprint is empty when nothing has been learned**, which is load-bearing:
the 20 precomputed live results and the 102 committed benchmark records are
addressed by this same key, and a component that was always present would
orphan every one of them. `test_qa_fixes.py` asserts the no-learning key is
byte-identical to the pre-fix scheme.

**3. The manufacturer-only rule was enforced on one path.** `/api/discover`
refused marketplaces properly; `/api/ingest/url` beside it had no reference to
the policy, and amazon.com and grainger.com both fetched with HTTP 200. A page
that parsed would have entered the catalog with a marketplace `source_url`
cited as provenance — the second-hand copy Unilog exists to correct.
`policy.blocked_kind()` now gates that path too. It is **narrower than
`policy.check()` on purpose**: check() also refuses any domain it cannot prove
belongs to the manufacturer, which is right when the engine chose the URL, but
on the ingest path a person is asserting this is their supplier's page and
refusing every unrecognised domain would leave the Document tab able to read
almost nothing. Explicit marketplaces, retailers and distributors are refused;
unknown domains are still read.

**4. The compliance layer was invisible in the UI — fixed.** The five commerce
descriptions, the `provisional` standards markers and the profile-driven
exports all worked through the API and were rendered by no component: §5.7 and
§7.3 described work a judge could not see in the product. Two new panels:

- `CompliancePanel.jsx` — "Content Standard". Each field with its limit, a fill
  bar, and **the dropped-token disclosure**, which is the row worth demoing:
  *"Dropped whole to fit: Width, Dynamic Load Rating (C), Limiting Speed,
  Static Load Rating (C0) — the part number is never cut mid-code."* A
  provisional stub can never read as certified compliance: when any standard
  reports `provisional` the panel says so in a warning banner, and "no list of
  values covers this category" is stated as *not the same as passing one*.
- `ExportPanel.jsx` — replaces the two hard-coded buttons on both the Single
  Product and Catalog tabs. Profiles are fetched from `/api/export/profiles`, so
  **adding an export schema still means adding data, not code, and the UI picks
  it up with no change.** `api.exportCsv` is gone; `/api/export/csv` is now
  reached as the `catalog_csv` profile.

**5. Space-aligned PDF columns were sliced through a token — fixed.** The
bordered and dot-leader layouts were perfect; the space-aligned one returned
`14.0 kN` as `14.0 k`, `Chrome Steel` as `Chrome`, and invented a key from the
title line. Validation caught it (two `TYPE_MISMATCH` errors, record blocked),
so nothing false ever published — the honesty layer held where the extractor
failed, which is why this ranked last.

Cause: pdfplumber's `text` strategy infers column edges across the **whole
page**, so one wide title line drags an edge into the value column and every row
beneath is cut at that x. `_pairs_from_columns()` now reads such tables line by
line, splitting on runs of two or more spaces — a split point that is a run of
spaces **cannot fall inside a token**. It runs before the pdfplumber strategy,
which stays as a last resort. All three layouts now recover the same 7 values.

**The alignment check is what keeps it honest**, and it is the part to preserve:
two words with a wide gap happen constantly in prose, so a value offset must be
shared by at least three lines before any of them counts as a spec. That is what
stops the documented `Single Row D` → `eep Groove Ball` failure recurring, and
`test_qa_fixes.py` asserts a page of prose still yields nothing.

**A bug inside that fix, worth remembering:** the first version clustered on
*distinct* offsets rather than on how many rows shared each one, so a single
stray line (`FAG  Rolling Bearing Data`, two spaces) outvoted the eight real
rows beneath it and the reader returned nothing. It was invisible on the
handwritten test file, which had no such line, and only appeared against
`test_ingest.py`'s own fixture. Cluster by row count, not by offset count.

### 7.8.1 The re-test — running the pass again against the fixes

Worth recording because it earned its keep: re-running A–N found **four more
things, one of them a regression introduced by the fix above.**

**A false alarm on a clean record, which is the worst kind here.** The series
lookup searched a single corpus built from the part number *and* the prose, so a
correct **6305** whose description said "replaces the older 6205" was charged
with contradicting 6205's dimensions — quoting *"the part number's standard"*
for a series the part number never contained. Latent before §7.8's defect 1,
because the knowledge base only filled gaps; the standards check turned a silent
mis-detection into a visible false accusation, against a claimed 0.0%
false-alarm rate. **Identity is read first now, and only a series found in the
part number may accuse a supplier.** One found in prose can still fill a blank —
that is a suggestion, not a charge, and it is where §7's 6205 recall comes from.

**A marketplace stopped being one at another TLD.** The blocked list is written
in `.com`, so `amazon.co.uk` and `amazon.de` passed a policy whose entire purpose
is to exclude marketplaces. Global marketplaces now carry `any_tld` in
`sources.json` and match on their registrable name — without swallowing
`amazonaws.com` or `my-amazon-supplier.com`, both asserted in the tests.

**Two gaps in the new PDF reader:** a right-aligned numeric column read as
nothing (it shares its *end* offset, not its start), and a unit in its own
column was dropped — `16000` is a different fact from `16000 rpm`. It now
clusters on whichever edge more rows agree on and joins a trailing unit cell. A
header row survived by being joined to its own unit column, so headers are
judged *before* anything is joined to them.

**pdfplumber's page-wide inference is now gone rather than demoted.** It was the
source of both documented failures — values sliced through a token, and specs
invented from prose (`'These bearings are supplied sealed' → 'or open'`). A
reader that requires the same gutter on three or more lines cannot do either, so
the failure is structurally impossible instead of filtered afterwards. All three
claimed layouts still recover their values.

**A third round probed only the round-two changes and found one more, again
mine:** the unit-column join matched "a short alphabetic token", so a **NOTES**
column was joined onto the value — a cleanly read `25 mm` became
`25 mm typical`, which then failed numeric parsing and blocked a record that had
been read perfectly. It now matches against the engine's own unit vocabulary
(`pipeline/units._UNITS`) instead of guessing from shape.

**One deliberate loss, recorded so nobody treats it as a bug:** a spec table of
only *two* rows now yields nothing, where pdfplumber's inference used to return
the pair. Three lines sharing a gutter is what separates a column from a
coincidence, and inventing specs is worse than missing a two-row table. No
fixture or real datasheet in the corpus has one.

**The lesson worth keeping:** the first version of the column clustering counted
*distinct offsets* rather than rows, so one stray line outvoted the eight real
rows beneath it — and that was invisible on the file written to test it, showing
up only against `test_ingest.py`'s existing fixture. A fix verified only against
the case that motivated it is not verified.

**Not a defect, but do not quote it as one:** throughput on the deployed free
tier is **~19 products/s**, not the 305/s in §7. The engine reaches 287/s
locally on the same corpus, so this is Render's shared CPU rather than the
pipeline — but the number as printed cannot be reproduced at the live link.
Say "287/s measured locally" when the deployment is in the room.

---

### Deck tooling — `docs/deck/`

The deck is generated, not hand-edited, so a re-measurement is one command
rather than fifteen slides of retyping.

| File | Role |
| --- | --- |
| `build_deck.py` | Fills the organizers' template. Run from `docs/deck/` |
| `template.pptx` | Their untouched original |
| `shots.py` | Playwright against the **deployed** site; writes `shots/` |
| `preview.py` | Renders one slide to PNG by re-laying its geometry in HTML. Takes the **1-based slide number**, so `preview.py 8` is `S[7]` |
| `fitcheck.py` | Overflow, margin, overlap and chip-wrap checks |
| `expected_vs_ours.json` | Written by `run_expected_vs_ours.py`; slide 8 reads it |

**The build writes two copies and only one is the deliverable.** `prs.save()`
lands in `docs/deck/` (untracked scratch); the submitted file is
`docs/UniHack_Prototype_Submission.pptx`. That copy used to be a remembered
manual step, which meant a rebuild could look successful and still ship the
previous deck — the tracked file sat 18 hours behind the script. `build_deck.py`
now copies it up itself and prints the destination.

**There is no LibreOffice in this environment**, so slides cannot be rendered
the normal way. `fitcheck.py` substitutes for visual QA on the defect that
matters — text overflowing its shape — by laying out every box against real
Arial metrics. `preview.py` covers placement. Neither tells you whether it looks
good: open the file before trusting it.

Playwright drives the **installed Chrome** (`channel="chrome"`), because the
browser tool in this environment cannot screenshot — the pane does not
composite frames.

---

## 8. Commands

```bash
# Run everything (Windows)
.\start.ps1

# Backend only
cd backend && python -m uvicorn app.main:app --port 8000
# Frontend only
cd frontend && npm run dev

# Test suites — all free, no API calls
cd backend
python smoke_test.py               # 10 demo cases, pipeline behaviour
python test_ingest.py              # PDF (3 layouts) + web + SSRF guard
python test_cost_guards.py         # lock, ceiling, cache guarantees
python test_taxonomy_learning.py   # learn → approve → classify → revoke
python test_hybrid.py              # hybrid gate: adds, never overrules
python test_export.py              # output profiles, incl. a schema added at runtime
python test_unilog.py              # house style, LOV refusals, char limits, row ingest
python test_discovery.py           # sourcing policy, refusals, SSRF, no accidental spend
python test_qa_fixes.py            # standards contradiction, cache/taxonomy, ingest policy (§7.8)
python run_cost_model.py           # cost per SKU under deterministic-first triage
python run_benchmark.py            # 102-case benchmark
python run_hybrid.py               # hybrid vs demo vs live, $0 from committed records
python -m benchmark.records export # refresh committed records after a live run

# Prove the benchmark reproduces on a fresh clone (no runtime cache):
#   PI_CACHE_DIR=<empty dir> python run_hybrid.py

# Live ablation — SPENDS MONEY. Confirm with the user first.
python run_benchmark.py --live --budget 5
```

---

## 9. Repository

- **https://github.com/ashwinsureshh/industrial-product-intelligence** — **PUBLIC**
  since 11 Aug. Flipped after scanning all 37 commits for secrets: no API key,
  token or credential in any commit, and `.env` was never tracked. Verified
  reachable by an unauthenticated clone, not just by the visibility flag.
- Branch `main`. Commits so far:
  1. `0d8fde6` engine + measured accuracy
  2. `b4762e0` spend ceiling + run lock
  3. `53b9415` document ingestion
  4. `e207fe4` taxonomy learning (backend)
  5. `35ed3a2` taxonomy review UI + CLAUDE.md
  6. `60f5a47` single-value enum fix, pending-proposal refresh
  7. `ebab3ea` single-service build, Dockerfile, bundled cache layer
  8. `1b67f7d` HEAD support for uptime monitors
  9. `c3823a4` 20 precomputed live results
  10. `3e3a2a3` plain-English `docs/Project_Understanding.pdf`
  11. `872ed4e` context file updated with deployment and spend state
  12. `411cf81` **hybrid gate** — bound the LLM to gap-filling (§7.1, §7.2)
  13. `54a7831` **committed live records** — the hybrid result is reproducible
  14. `3e3a2a3`→`87f19ab` UI: dark theme, bottom nav, design tokens, responsive
      fixes (see §5 Frontend)
  15. `73af8d5` **hybrid shipped as a third engine** + refusal ledger (§7.2)
  16. `36263b9` **per-attribute source URLs** (§5.5) + first cost model
  17. `e54c7f4` **export profiles** — output schema is data (§5 `export/`)
  18. `f26aae4` cost model at standard rates + batch/scalability (§7.05)
  19. `26a71b2` **Unilog compliance layer** (§5.7) — house style, LOV refusals,
      formula-built descriptions, catalogue-row ingest, 100 tests
  20. `3b19213` casing fix: title case no longer flattens bracketed words
  21. `f706259` **real delivery format** (§7.3) — 252-column profile generated
      from their header, formulas derived from their two labelled rows,
      field-level accuracy benchmark, vendor≠manufacturer ingest
  22. `ebe012d` **taxonomy learning on their 1,000 rows** (§7.4) — 8.9% → 81.7%,
      and the three bugs volume exposed
  23. `25a8eb3` **discovery** (§7.5) — sourcing policy, refusal ledger, the
      measured zero-of-four result
  24. `68de57c` Discover UI tab
  25. `c764e3d` **pre-deck audit** (§7.6) — corrupted bullets in a served
      record, empty fields claiming compliance, long-token layout break
  26. `ba45bea` deck built from the organizers' template, `docs/deck/`
  27. `0a85c93` repository made public after scanning all 37 commits
  28. `45a48c4` header sizing: "Live AI" no longer wraps; 901–1300px band
  29. `63e9856` two glyphs that had rendered as mojibake since the dark theme
  30. `27f2129` slide 12: four screenshots captured from the deployed app
  31. `775612d` **stopped quoting 14/14 unqualified** — both states, everywhere
  32. `5f27011` **Accuracy tab** + `/api/ground-truth` (§7.7)
  33. `8573856` `.banner` is flex, so its prose needs one wrapper element
  34. `9319d57` deck screenshots re-captured against the current build
  35. `e549771` **Accuracy tab removed** (§7.7) — the endpoint, the CLI and the
      both-states tests stay; deck slide 8 is now the only place a judge sees
      those numbers
- `main` and `origin/main` are level; the working tree is clean.
- Public as of 11 Aug (submission requires it). No LICENSE yet — see below.
- No LICENSE yet, deliberately: organizers may have IP terms. Check before adding.

---

## 10. Conventions

- Comments explain **why**, never what. Match surrounding density.
- Every new capability ships with a test that proves the specific behaviour it
  claims, and the test must cost $0.
- Report fixed things as fixed. (Earlier a "two bugs found" write-up read as
  open issues when both were already repaired — the user asked for them to be
  fixed again. Be explicit about state.)
- Verify in the browser before claiming UI works; read actual output rather
  than trusting that a test passing means the output is good.
- Adding a category = edit `data/taxonomy.json`. Only a genuinely new *kind* of
  cross-field rule needs Python.

---

## 11. Immediate next steps

**Engineering is done and deployed. What remains is submission admin and two
things only the user can supply.** Deadline Sun 23 Aug 2026, 10:31 IST.

| # | Item | State |
| --- | --- | --- |
| 1 | ~~Team details, deck slide 2~~ | **Done 12 Aug.** Team Codes; leader **Ankur Goswami**; Ashwin S, Argho Kumar Halder, SV Chiranjeevi. Values live in `TEAM_NAME` / `TEAM_LEADER` / `TEAM_MEMBERS` at the top of slide 2's block in `build_deck.py`. Emails are on the portal roster and deliberately off the slide |
| 2 | **Demo video link, deck slide 14** | **Blocked on the user.** Slide has a marked placeholder |
| 3 | **Demo video, 3 minutes** | **Script and silent footage done** — `docs/video/`. Needs your voiceover and an upload |
| 4 | **Rotate the API key** | It passed through a conversation transcript. Delete `backend/.env` when local live testing is finished |
| 5 | ~~Decide the Accuracy tab question~~ | **Done 12 Aug — removed.** §7.7 |
| 6 | Leave UptimeRobot running | A sleeping free instance returns **404**, so a reviewer's first click looks like a dead link |

Done since this list was last written: repo public (`0a85c93`), deck built and
screenshotted from the deployed app (`ba45bea`, `27f2129`, `9319d57`),
`Project_Understanding.pdf` brought current.

### Demo video — `docs/video/`

`script.md` is the shooting script: 436 words of narration (2:55 at 150 wpm)
against a hard 3:00, an eight-segment shot list with every click path verified
on the deployed site, and a **"do not say" list** — 14/14 unqualified, 305
products/s while the live site is on screen, "100% of errors caught" without
"seeded, on our corpus", and the learned category names.

`record.py` drives the live site through that shot list and writes a silent
1280×720 webm to `docs/video/footage/` (gitignored — rebuildable, and the
submitted file will live on YouTube). Needs `playwright install ffmpeg` once.
`--fast` runs the same path with no dwells to check it still works after a
UI change.

`voiceover.py` speaks the narration with the **Windows** speech engine — free,
local, no account — and writes `narration.wav`, one full-length track with every
segment already at its own offset. Assembly is therefore "drop both at 0:00",
with nothing to nudge.

**The sync is exact because the audio drives the video, not the reverse.**
Each segment's real duration is read out of its WAV header and becomes
`record.py`'s marks. It also refuses to run long: the first cut measured 183.7 s
and the script printed *"over three minutes — cut the script, not the pauses"*,
which is what produced the three trims now in `voiceover.py`. Current state:
narration **2:57.4**, picture **3:02.9**.

Two things learned the expensive way:

- **Viewmax voiceover returns 402, no subscription.** Nothing was spent. If a
  better voice is wanted, a human read against the measured table in `script.md`
  needs no re-cut, because the picture is already timed to those marks.
- **Playwright's ffmpeg is video-only** — no WAV demuxer, no audio encoders, so
  it cannot mux the track in. Durations are read with the stdlib `wave` module
  and the track is assembled by writing PCM directly. Muxing to a single MP4
  needs a full ffmpeg or any editor.

**Never let a normaliser near the part numbers.** `normalize_tts_text` rendered
`6205` as "six thousand two hundred five" — a bearing designation is read
"sixty-two oh five". The spellings in `voiceover.py` are deliberate; tidying
them back produces the wrong number said confidently, which is the exact failure
this whole project argues against.

**It holds absolute marks, not relative waits.** The first take ran 97 seconds
against 175 seconds of narration, because hand-tuned dwells drift. `hold_until`
takes a mark from the script — "hold until 0:50" — so the gate is on screen at
0:50 whatever the network did on the way there, and it prints a warning if a
segment overruns. Current take: **3:02**.

Two framing traps already paid for: `scrollIntoView({block:'center'})` on a card
taller than the viewport pushes its first row off the top — which cost the
40-character invoice line, the only reason that shot exists, so it takes
`block:'start'` with a **-120 px offset to clear the sticky header**. And the
pointer left where it clicked holds a hover highlight on a sample card that is
not the one on screen; `park_mouse()` moves it away.

**Three things make it read as someone using the product rather than a
slideshow, and an edit can silently drop any of them:**

1. **A drawn pointer.** Screen capture records no cursor, so without the
   injected `CURSOR` overlay buttons press themselves and tabs switch on their
   own. It is added via `add_init_script`, and it also pulses on mousedown so a
   click is visible as an event.
2. **`behavior:'smooth'` on every scroll.** An instant jump between two dense
   screens gives the eye nothing to follow and reads as a cut.
3. **Pointer travel before each click** — `glide()` interpolates ~22 steps, so
   the cursor arrives at a control before pressing it.

Motion is measurable: the same three minutes went 413 → 503 kb/s once these
landed. Two staging notes that are easy to get wrong — park the pointer *only*
when the next action is not a click (otherwise it flies to the bottom of the
frame and straight back), and rest it on the control about to be used, because
a pointer drifting onto an unrelated button reads as a click that never comes.

**Video running order** — the three things worth the 3 minutes:

1. Hybrid engine on the sparse bearing. Point at the two refusals: the model
   proposed 14.8 kN and 14000 rpm, ISO 15 says 14 and 16000, both refused, and
   an unbacked default replaced. Twenty seconds, and it is the whole thesis.
2. Their expected row beside ours, with **both** numbers — 14/14 given the
   attribute values, 2/14 from the catalogue row. This used to be the Accuracy
   tab; with that gone it now comes off **deck slide 8**, or off
   `python run_expected_vs_ours.py` if the video prefers a terminal. Do not quote
   14/14 alone.
3. Discover on SKF: the page is fetched, refused as unusable, and the record
   below still scores 94 because ISO 15 decodes the part number. Says exactly
   what is and is not sourced.

**When the remaining seven reference files land** (§1.6), in this order:
(a) regenerate the `data/unilog/` stubs from their UOM sheet, guidelines .docx
and LOV files — no code change, and `source` flips `provisional` → `unilog`;
(b) set `applies_to` on the LOV entries to bind them to our taxonomy, then
**re-measure** — that binding is what makes the vocabulary live;
(c) re-run `run_delivery_accuracy.py` and `run_expected_vs_ours.py`, then
`docs/deck/build_deck.py` to refresh the slides from the new numbers.
**Do not touch `build_corpus()`** — it invalidates all 102 paid records.

### 11.1 Discovery from brand + part number — now measured, not argued

**Read §7.3 first.** The position has moved twice. §1.5 called discovery "the
one real gap"; §1.6 demoted it on the guide's "two or three steps done well"
advice; §7.3 now **measures** what it costs to skip: 88 of 114 scored delivery
fields are blank purely because the values live on the manufacturer's site,
which their own row cites as `MFR URL`. Precision on what we do fill is 61.5%,
so the ceiling is set by sourcing, not by the engine.

That reframes the decision. Discovery is no longer "nice to have per the brief"
— it is the single change that moves delivery-format accuracy, and the number
to quote when justifying it. Still not built, still the user's call, and the
cost caveats below stand.

The organizers' 6 Aug briefing (§1.5): take a manufacturer name and
part number and *search* manufacturer sites, catalogues, PDFs and manuals.
Today the user must hand us the document or URL; we enrich from the MPN via ISO
decoding, which is on-target but is not web discovery.

**Held deliberately** until their sample data lands, on the user's call.
Findings that will shape it:

- **The SKF product page returned HTTP 200 with zero specs — it is
  JavaScript-rendered.** Naive fetch-and-parse will not work on modern
  manufacturer sites. Expect to need a search API with content extraction, or
  Claude's own web-search tool (whose citations map neatly onto the source-URL
  requirement).
- Either option **costs money per SKU** and changes §7.05's arithmetic, so
  confirm the approach *and* the spend with the user before any live run.
- The no-e-commerce constraint means domain blocking is part of the design.

### Deliberately not done

- **Live taxonomy proposer.** See §3.1 — recommendation is don't.
- **Video / tech-talk extraction.** Organizers flagged it as innovative;
  expensive and slow. Roadmap slide, not a build.
- **Batch API path.** §7.05 costs it but does not implement it. It is a
  *catalog*-path feature, not the interactive one, and cannot be validated
  without spending.

### Gotchas already paid for

- Python `str.replace()` replaces **all** occurrences — it silently duplicated a
  JSX block across two branches of a conditional chain.
- A `%` inside a regex character class breaks `%`-formatting; build those
  patterns by concatenation.
- pdfplumber's whitespace table strategy will slice a page containing **no
  table**, inventing `'Single Row D' → 'eep Groove Ball'` from a heading.
  Strategies must be ordered by evidence strength: borders → explicit line
  syntax → **gutter-split lines** → inferred columns last. It also infers column
  edges across the *whole page*, so a wide title line cuts every value beneath
  it (§7.8 defect 5) — never let it read a page a line-level reader can.
- A loose numeric parse types `M10x1.25` as the measurement `10`. Values must
  be *essentially* a quantity to be typed numeric.
- The learned-taxonomy files (`data/learned_categories.json`,
  `data/proposals.json`) are gitignored runtime state. Stale state across test
  runs causes confusing results — delete both when debugging.
- Restart the backend after adding routes; a stale uvicorn returns 404 and
  looks like a frontend bug.
- **`.banner` is `display: flex`.** Every element child becomes a flex item, so
  a banner containing inline markup must wrap its prose in one element or the
  browser deals the sentence into columns. Cost one broken paragraph on the
  since-removed Accuracy tab; the constraint is now noted on the rule itself.
- **A `content:` value can be double-encoded and nothing will notice.** Two
  glyphs rendered as `â–¸` and `â†’` on the deployed site for several sessions.
  No geometry audit catches this — only reading the rendered pixels does.
- **`preview.py` used to invent that same bug.** It wrote UTF-8 HTML with no
  `<meta charset>`, so Chrome read it as latin-1 and slide 2's `·` came back as
  `Â·` — in the *preview*, while the .pptx held a clean U+00B7. Fixed. The moral
  cuts both ways: when a rendering shows mojibake, confirm the codepoints in the
  artefact before "fixing" the artefact.
- **Deck screenshots contain no navigation.** `docs/deck/shots.py` clips each
  capture to its card's bounding box, so a change to the tab bar does not
  require re-taking them. Check before re-running.
- **Changing `build_corpus()` silently invalidates every committed record.**
  The cache key covers the product payload, so any edit to corpus generation
  makes all 102 keys miss and `run_hybrid.py` aborts. That abort is correct
  behaviour, not a bug — recovering costs another live run (~$1.62). Treat the
  corpus as frozen unless a re-run is genuinely worth paying for.
- To simulate a fresh clone without touching the real cache, point
  `PI_CACHE_DIR` at an empty directory. Renaming `backend/.cache/` risks the
  paid records; the env var does not.
- Verifying a deploy by pinging `/api/health` proves almost nothing — it does
  not import most of the app. Exercise a real endpoint (`/api/enrich`) when the
  change touched code the service actually runs.
- `git check-ignore` exits **1** when a path is *not* ignored. In a chained
  PowerShell command that reads as a failure when it is the desired result.

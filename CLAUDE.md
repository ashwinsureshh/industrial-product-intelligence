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

**Status as of 10 Aug: the guide is up, the nine files are not.** Only the
HTML guide is in Resources. Chase the organizers for an ETA; if it slips past
~17 Aug, decide whether to demo against a hand-built stand-in.

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
| **GitHub Repository** | Must be a **public** link. The repo is currently private; flip it at submission. |
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
| 5 | Deck + demo video | Template is in Downloads (`[EXT] UniHack-Protoype Template .pptx`); not started |
| 6 | Unilog compliance layer (§5.7) | **Done, $0** — built against the solution guide (§1.6) |

**Everything above is complete, committed, pushed and deployed.** Seven test
suites pass, benchmark reproduces, live site verified on desktop and phone.

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
| `pipeline/validate.py` | Range/vocabulary/required checks + 16 cross-field rules |
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
| `ingest/unilog_rows.py` | Their 6- and 10-column catalogue rows → `RawProduct` |
| `data/unilog/` | `uom_standards`, `abbreviations`, `content_formats`, `lov/` — **all provisional stubs; their spreadsheets replace these files, not the code** |
| `export/profiles.py` | Profile-driven output rendering; target schema is data |
| `data/export_profiles/` | `catalog_csv`, `schema_org`, `unilog_delivery` — **add a customer schema here, not in code** |
| `data/taxonomy.json` | 10 curated categories — **edit data, not code, to add one** |

### Frontend (`frontend/src/`)

React 19 + Vite, no runtime UI dependencies. Four tabs: **Single Product**,
**Document**, **Catalog**, **Learning**. Three engines: **Demo**, **Hybrid**,
**Live AI**. Vite proxies `/api` to port 8000.

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

- **https://github.com/ashwinsureshh/industrial-product-intelligence** (PRIVATE)
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
  19. **Unilog compliance layer** (§5.7) — house style, LOV refusals, formula
      -built descriptions, catalogue-row ingest, delivery profile, 100 tests
- Local `main` and `origin/main` were level at `f26aae4` before the compliance
  layer landed.
- Decision: stay private until submission, then either flip to public or add
  judges as collaborators — check the rules for which is required.
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

**Everything now waits on the nine data files (§1.6), which are not uploaded
yet.** The compliance layer (§5.7) was built against the guide so that landing
them is a data drop.

0. **Chase the organizers for a dataset ETA.** As of 10 Aug only the HTML guide
   is in Resources. This is the critical path.
1. **When the pack lands**, in this order:
   (a) regenerate the four `data/unilog/` stubs from their UOM sheet,
   guidelines .docx, and LOV files — no code change, and `source` flips from
   `provisional` to `unilog`;
   (b) fill in `unilog_delivery.json` from the 252-column Delivery Format sheet;
   (c) set `applies_to` on the LOV entries to bind them to our taxonomy, then
   **re-measure** — that binding is what makes the vocabulary live;
   (d) add a *second* benchmark scoring field-level accuracy against their 200
   known-good rows. **Do not touch `build_corpus()`** — it invalidates all 102
   paid records (§11 gotchas);
   (e) then, and only then, decide on discovery with real examples in hand.
2. **The deck.** The user has the portal template and will supply it once
   engineering settles. `docs/Project_Understanding.pdf`, §7.1/§7.2 and §7.05
   carry the narrative; the hybrid gate is the strongest slide.
3. **Demo video — 3 minutes** (organizer-specified). Best 20 seconds: switch to
   the Hybrid engine on the sparse bearing and point at the two refusals.
4. **Flip the repo public** at submission. Mandatory.
5. **Rotate the API key** (it passed through a conversation transcript) and
   **delete `backend/.env`** once local live testing is finished.
6. **Leave the UptimeRobot monitor running.** A sleeping free instance returns
   404, so a reviewer's first click would look like a dead link.

### 11.1 Discovery from brand + part number — demoted by §1.6

**Read §1.6 first.** The solution guide makes discovery one of eight pipeline
steps and says outright that two or three done convincingly beat a shallow pass
at everything. This section's framing as "the one real gap" predates it.

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
  syntax → inferred columns last.
- A loose numeric parse types `M10x1.25` as the measurement `10`. Values must
  be *essentially* a quantity to be typed numeric.
- The learned-taxonomy files (`data/learned_categories.json`,
  `data/proposals.json`) are gitignored runtime state. Stale state across test
  runs causes confusing results — delete both when debugging.
- Restart the backend after adding routes; a stale uvicorn returns 404 and
  looks like a frontend bug.
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

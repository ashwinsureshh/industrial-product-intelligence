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
| — | Hybrid gate (bounded Claude) | **Done, $0 — see §7.2. Best result in the project; benchmark only, not wired into the UI.** |
| 4 | Public deployment | **Done — live and monitored** |
| 5 | Deck + demo video | **Blocked: need the portal's mandatory template** |

**All engineering is complete, committed and pushed.** Working tree clean, all
five test suites pass, deployment verified. What remains is the deck, the demo
video, and the submission-day actions in §11 — none of which are code.

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
| `models.py` | All schemas. `RawProduct`, `Attribute`, `EnrichedProduct`, `CategoryProposal` |
| `config.py` | Env config; loads `backend/.env`; demo mode is the default |
| `cache.py` | Content-addressed result cache (input hash + mode + model). `key_for()` is public so other read-only layers address records identically |
| `main.py` | FastAPI app, all endpoints |
| `pipeline/units.py` | Unit parsing/normalization; canonical unit per dimension |
| `pipeline/taxonomy.py` | Category classification; merges curated + learned categories |
| `pipeline/extract.py` | Deterministic extraction (spec tables + 3 prose strategies) |
| `pipeline/validate.py` | Range/vocabulary/required checks + 16 cross-field rules |
| `pipeline/run.py` | Stage orchestration, reconciliation, readiness scoring |
| `providers/mock.py` | Deterministic engine — knowledge-base driven, free, default |
| `providers/anthropic_provider.py` | Claude engine via tool-schema structured output |
| `ingest/pdf.py` | Datasheet parsing (3 layouts) |
| `ingest/web.py` | Product page parsing (JSON-LD first) + SSRF guard |
| `taxonomy_learning/propose.py` | Clusters unclassified products, infers schemas |
| `taxonomy_learning/store.py` | Proposal queue + learned-category persistence |
| `benchmark/corpus.py` | 102-case corpus; ISO-backed + archetype ground truth |
| `benchmark/evaluate.py` | Scoring. `enricher=` scores pre-built records without a provider |
| `benchmark/hybrid.py` | **The hybrid gate** — Claude may add, never overrule (§7.2) |
| `benchmark/records.py` | Loader/exporter for the committed live records |
| `benchmark/records/` | 102 committed live records, 0.88 MB — makes §7.2 reproducible |
| `data/taxonomy.json` | 10 curated categories — **edit data, not code, to add one** |

### Frontend (`frontend/src/`)

React 19 + Vite, no runtime UI dependencies. Four tabs: **Single Product**,
**Document**, **Catalog**, **Learning**. Vite proxies `/api` to port 8000.

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
- Local `main` and `origin/main` are level at `54a7831`; working tree clean.
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

**No engineering is outstanding.** Everything below is either a deliverable or
a user action.

1. **The deck.** The only real blocker, and it needs the user to download the
   portal's mandatory template. `docs/Project_Understanding.pdf` plus §7.1/§7.2
   carry the narrative; the hybrid gate is the strongest slide.
2. **Demo video** — a short walkthrough of the live site.
3. **Flip the repo public** at submission. Mandatory.
4. **Rotate the API key** (it passed through a conversation transcript) and
   **delete `backend/.env`** once local live testing is finished.
5. **Leave the UptimeRobot monitor running.** A sleeping free instance returns
   404, so a reviewer's first click would look like a dead link.

### Deliberately not done

- **The hybrid gate is benchmark-only.** It is not selectable in the UI, so a
  reviewer on the live site sees "Demo" and "Live AI" — the latter being the
  engine that scored *worse*. Wiring it in as a third mode is real backend +
  frontend work, not a small change. Skipped knowingly; cover it in the deck.
- **Live taxonomy proposer.** See §3.1 — recommendation is don't.

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

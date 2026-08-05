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
| AI validation & enrichment | provider layer (deterministic + Claude tool-use) |
| Scalable catalog engine | CSV/batch ingest, document ingest, **auto-taxonomy learning** |

**Guiding principle, stated in the README and worth preserving in every change:**
in industrial commerce a wrong specification ships a broken machine, so the
engine must refuse to guess silently. It leaves a field blank, flags a
contradiction, or blocks publication rather than emit a confident-looking value
it cannot defend.

---

## 2. Deadlines and status

- **Submission deadline: 23 Aug 2026.** User wants development finished ~20 Aug
  to leave time for the presentation.
- Work started 5 Aug 2026. Phases 1–3 (backend) were completed on day one, so
  the project is running roughly 4 days ahead of the original plan.

| Phase | Scope | Status |
| --- | --- | --- |
| 1 | Evaluation harness + measured accuracy | **Done, committed** |
| 2 | PDF datasheet + product-page ingestion | **Done, committed** |
| 3 | Auto-taxonomy learning | **Backend done + committed; review UI built, verified, not yet committed** |
| — | Live ablation (Claude vs deterministic) | **Deferred by decision to after Phase 3** |
| 4 | Review queue, scale demo, public deploy | Not started |
| 5 | Hardening, deck, demo video | Not started |

---

## 3. Cost discipline — READ BEFORE ANY LIVE RUN

The user has **very limited API credit** (~$1.44 remaining as of 5 Aug). An
earlier mistake burned ~$2.63 with nothing to show for it. Do not repeat it.

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
| `cache.py` | Content-addressed result cache (input hash + mode + model) |
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
| `benchmark/` | Corpus generation + evaluation |
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
| Throughput | ~340 products/s |

**The headline is the contradiction rate, not coverage.** Coverage is cheap —
any system reaches 100% by inventing everything. Precision is 100% on
`knowledge_base`, `derived` and `parsed` values; only `defaulted` (explicitly
flagged as unconfirmed) sits at ~76%.

Methodology note that survives scrutiny: bearing and fastener ground truth
comes from **ISO 15 / ISO 898-1** (externally fixed — the engine cannot be
tuned to it without also being right in reality). Other categories use
hand-authored archetypes and are **reported separately**. Only *withheld*
attributes are scored.

**Known gap that motivates the live ablation:** recall is 83.1% on
standards-backed categories vs 33.1% on archetype categories. That gap is the
argument for the LLM.

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
python run_benchmark.py            # 102-case benchmark

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

1. **Commit the Learning UI** (`frontend/src/components/TaxonomyPanel.jsx`,
   `App.jsx` wiring, `api.js` functions, `samples.json` `learning_demo`,
   and the `PROPOSE_BELOW_CONFIDENCE = 0.65` change in `main.py`).
2. **Live proposer** — `AnthropicProvider.propose_category()` so Claude
   improves naming, enum members and cross-field rules over the deterministic
   baseline. Build against demo mode; spend only at the end.
3. **Phase 4** — human review queue, persistence, scale demo, public deploy.
4. **Live ablation** once credit is topped up: `--budget 5`, ~$2.30 expected.
5. **Deck + demo video.**

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

# Industrial Product Intelligence

Turns sparse, messy supplier product data into **validated, explainable, commerce-ready
catalog records** — where every enriched value carries its evidence, its provenance and
its confidence.

The guiding principle: in industrial commerce a wrong specification ships a broken
machine. So the engine is built to **refuse to guess silently**. It will leave a field
blank, flag a contradiction, or block publication rather than emit a confident-looking
value it cannot defend.

---

## Quick start

```powershell
.\start.ps1
```

Then open **http://localhost:5173**.

No API key. No account. No cost. The default demo engine is fully offline and
deterministic.

<details>
<summary>Manual start</summary>

```bash
cd backend && pip install -r requirements.txt && python -m uvicorn app.main:app --port 8000
```

```bash
cd frontend && npm install && npm run dev
```
</details>

---

## Two engines, one output shape

| | Demo engine (default) | Live engine (opt-in) |
|---|---|---|
| Cost | Free | Caller's own API key |
| Network | None | Claude API |
| Determinism | Byte-identical every run | Model-dependent |
| Powered by | Curated standards knowledge base — ISO 15 bearing series, ISO 898-1 property classes, SAE J517, IEC 60529 | `claude-sonnet-5` with tool-schema structured output |

Both produce the **same schema**, so the UI, validation, scoring and export paths are
identical. Live mode is enabled per request by pasting a key into the UI; the key is
used for that call only and is never written to disk. Setting `PI_ALLOW_LIVE=0` makes
paid calls impossible for a deployment.

Results are cached by a hash of the input, so re-running the same product never pays
twice.

---

## How it works

```
normalize → classify → extract → infer → reconcile → content → validate → score
```

Every stage is timed and traced, and the UI renders that trace, so nothing about the
result is a black box.

**normalize** — cleans whitespace, canonicalizes brand spellings (`skf` → `SKF`),
recovers MPN/GTIN from prose.

**classify** — scores the input against a 10-category taxonomy using keywords, MPN
regex patterns, attribute-name mentions and brand-category affinity. Returns confidence
*and* the runner-up categories, because a narrow win should not read as certainty.

**extract** — deterministic, no model involved. Fuzzy-maps supplier spec keys onto the
canonical schema (`Body Matl` → `body_material`), then works prose with three
strategies: label-anchored (`Bore: 25 mm`), unit-anchored (`5 HP`, `1750 rpm`) and
controlled-vocabulary (`three phase` → `Three Phase`). Part-number suffixes are mined
too — `6205-2RS` names its own seal type. Units are normalized throughout, and a match
carrying the wrong physical dimension is rejected rather than relabelled.

**infer** — the only stage that varies by engine, and the only one that can cost money.
Fills what deterministic extraction could not.

**reconcile** — when stages disagree, the value with the stronger provenance wins, the
conflict is recorded, and the winner's confidence is *reduced* — disagreement is itself
evidence of uncertainty.

**validate** — range and vocabulary checks, required-field checks, and 16 cross-field
engineering rules. These are the ones that matter: most real catalog errors are
individually plausible values that contradict each other.

**score** — completeness, confidence and validity are scored separately (a record can be
complete but contradictory, or clean but sparse) and combined into a
publish / review / blocked verdict.

---

## Provenance

Every attribute is tagged, and the tag drives reconciliation, scoring and the UI colour
ramp alike:

| Tag | Meaning |
|---|---|
| `supplied` | Present verbatim in the supplier record |
| `parsed` | Deconstructed from supplier text or a spec key |
| `knowledge_base` | Fixed by a published standard |
| `derived` | Computed from other known attributes |
| `inferred` | Model inference from context |
| `defaulted` | Category-typical placeholder — needs confirmation |

Copy generation deliberately consumes only non-defaulted attributes, so marketing text
can never assert a value the catalog does not actually stand behind.

---

## What the demo cases prove

Load any of the ten built-in cases from the left panel.

- **Sparse bearing** — three input fields (`6205-2RS`, `skf`, a name) become an 11-attribute
  publishable record at 93/100, because the ISO 15 designation fixes every dimension.
- **Contradictory valve** — a PVC body rated to 180 °C. Every field is plausible alone;
  only cross-field validation catches that the product cannot exist. **Blocked.**
- **Transposed bearing** — bore 90 mm, OD 40 mm. Geometrically impossible, invisible to
  any single-field check. **Blocked.**
- **Imperial motor** — `5 HP` converts to 3.729 kW, full-load current is derived from
  power and voltage, then cross-checked against the stated nameplate.
- **Unsafe hose** — 2:1 burst-to-working ratio against SAE J517's required 4:1. A safety
  defect, not a formatting nit, so it **blocks** rather than warns.
- **Fastener mismatch** — a 316 stainless bolt cannot carry property class 10.9.
- **Barely identifiable input** — scores 35/100 and blocks. Honest failure, not a
  confident guess.

---

## Measured results

```bash
cd backend && python run_benchmark.py
```

102 cases across 10 categories. Bearing and fastener ground truth comes from
**ISO 15 and ISO 898-1** — externally fixed values the engine cannot be tuned to
without also being right in the real world. Remaining categories use hand-authored
archetypes and are **reported separately** rather than blended into the headline.

Each product yields a *sparse* case (most attributes withheld — does enrichment
recover truth?) and a *defect* case (one field corrupted in a known way — does
validation catch it?). Only withheld attributes are scored; values handed to the
engine would inflate every figure.

| Metric | Result |
| --- | --- |
| Attribute coverage lift | **2.75×** (129 → 355) |
| Withheld attributes recovered | **61.1%** |
| **Contradiction rate, values asserted on evidence** | **0.0%** |
| Contradiction rate including flagged defaults | 11.1% |
| Seeded defects caught | **100%** (51/51) |
| Defective records prevented from auto-publishing | **100%** |
| False alarms on clean records | **0.0%** |
| Throughput | 338 products/s |

**The headline number is the contradiction rate.** Coverage is easy — any system
reaches 100% by inventing everything. Of every value this engine asserts on real
evidence, *none* contradicted ground truth. The 11.1% figure comes entirely from
`defaulted` values, which the system explicitly labels as unconfirmed placeholders
rather than claims.

Precision by provenance:

| Provenance | Precision |
| --- | --- |
| `knowledge_base` (standards) | **100%** |
| `derived` (computed) | **100%** |
| `parsed` (from supplier text) | **100%** |
| `defaulted` (flagged placeholder) | 75.7% |

Recall splits sharply by ground-truth source — **83.1% on standards-backed
categories vs 33.1% on archetype categories** — which is precisely the gap the
LLM engine exists to close, and precisely why the deterministic layer handles
everything it can first.

Business model on a 100,000-SKU catalog, at 10 min/SKU manual enrichment and
\$35/hour analyst cost, crediting review-queue records at only half the saving:
**5,556 hours and \$194k saved**, with 0.08 hours of machine time.

Full reports, including every contradiction the engine produced, are written to
[`backend/benchmark/results/`](backend/benchmark/results/).

## Catalog scale

The **Catalog** tab ingests a supplier CSV or runs a 10-product demo catalog.
Unrecognised columns become supplier spec fields rather than being dropped, because a
column you can't map is a taxonomy gap, not noise.

Rows are processed concurrently across a thread pool — the demo catalog completes in
~50 ms — and export produces a flat CSV where **every attribute ships with its
provenance and confidence columns**, so the audit trail survives into whatever system
consumes it.

---

## API

| Endpoint | Purpose |
|---|---|
| `POST /api/enrich` | Enrich one product |
| `POST /api/enrich/batch` | Enrich up to 250 products concurrently |
| `POST /api/enrich/csv` | Upload a supplier CSV |
| `POST /api/export/csv` | Flatten results to a catalog-import CSV |
| `GET /api/taxonomy` | The full category and attribute schema |
| `GET /api/samples` | Demo inputs |
| `GET /api/health` | Status, config and cache stats |
| `GET`/`DELETE /api/cache` | Cache stats / clear |

Interactive docs at **http://127.0.0.1:8000/docs**.

---

## Extending the taxonomy

Categories live in [`backend/app/data/taxonomy.json`](backend/app/data/taxonomy.json).
Adding one is a data edit, not a code change: attribute definitions drive extraction,
validation, completeness scoring and the live-mode prompt from that single declaration.
Only a genuinely new *kind* of cross-field rule needs Python, and those are registered
by name in [`validate.py`](backend/app/pipeline/validate.py).

---

## Tests

```bash
cd backend && python smoke_test.py
```

Runs all ten demo cases and asserts the specific behaviour each was built to
demonstrate — that 6205 resolves to a 25 mm bore, that PVC-at-180 °C blocks, that
5 HP converts correctly — plus universal invariants: every attribute carries evidence
and in-band confidence, and demo mode is byte-for-byte reproducible.

---

## Stack

Python · FastAPI · Pydantic v2 · Claude API (tool-use structured output) ·
React 19 · Vite · zero runtime UI dependencies

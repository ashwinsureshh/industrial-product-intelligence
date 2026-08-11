# Benchmark Results

Engine: **demo (deterministic)** · 102 cases · 0.35 s · 289.7 products/s

## Headline

| Metric | Value |
| --- | --- |
| Attribute coverage lift | **2.75x** (129 → 355) |
| Withheld attributes recovered | **61.1%** |
| Recovered values correct | **88.9%** |
| **Contradiction rate** | **11.1%** |
| Contradiction rate, excluding flagged defaults | **0.0%** |
| Seeded defects caught | **100.0%** (51/51) |
| False alarms on clean records | **0.0%** |
| Auto-publishable (clean records) | **31.4%** |
| Defective records stopped | **100.0%** |

## Accuracy by provenance

| Provenance | Correct | Contradicted | Precision |
| --- | --- | --- | --- |
| defaulted | 78 | 25 | 75.7% |
| derived | 8 | 0 | 100.0% |
| knowledge_base | 72 | 0 | 100.0% |
| parsed | 43 | 0 | 100.0% |

## Accuracy by ground-truth strength

`standards` values come from ISO 15 and ISO 898-1 and are externally fixed. `archetype` values were hand-authored and are therefore weaker evidence.

| Source | Recall | Precision |
| --- | --- | --- |
| archetype | 33.1% | 68.5% |
| standards | 83.1% | 95.3% |

## Defect detection by kind

| Defect | Caught | Total | Recall |
| --- | --- | --- | --- |
| geometry | 3 | 3 | 100.0% |
| grade_conflict | 9 | 9 | 100.0% |
| invalid_code | 6 | 6 | 100.0% |
| magnitude | 3 | 3 | 100.0% |
| material_conflict | 6 | 6 | 100.0% |
| transposition | 21 | 21 | 100.0% |
| vocabulary | 3 | 3 | 100.0% |

## Business impact

Modelled on a **100,000 SKU** catalog.

| Metric | Value |
| --- | --- |
| Manual baseline | 16,667 hours |
| Hours saved | **5,556** |
| Cost saved | **$194,444** |
| FTE-years saved | 3.1 |
| Machine processing time | 0.1 hours |

Assumptions: 10.0 min/SKU manual enrichment, $35.0/hour analyst cost, records needing review credited at 50% of the manual time saving.

## Corpus composition

```json
{
  "total": 102,
  "by_category": {
    "Rolling Element Bearings": 36,
    "Fasteners": 18,
    "Industrial Valves": 6,
    "Electric Motors": 6,
    "Sensors & Transmitters": 6,
    "Industrial Pumps": 6,
    "Protective Equipment": 6,
    "Cutting Tools": 6,
    "Drives & Controls": 6,
    "Hose & Fittings": 6
  },
  "by_variant": {
    "sparse": 51,
    "defect": 51
  },
  "by_truth_source": {
    "standards": 54,
    "archetype": 48
  },
  "by_defect_kind": {
    "transposition": 21,
    "grade_conflict": 9,
    "material_conflict": 6,
    "magnitude": 3,
    "invalid_code": 6,
    "vocabulary": 3,
    "geometry": 3
  }
}
```
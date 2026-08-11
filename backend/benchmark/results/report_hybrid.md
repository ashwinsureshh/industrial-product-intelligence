# Benchmark Results

Engine: **hybrid (gated)** · 102 cases · 0.4 s · 253.7 products/s

## Headline

| Metric | Value |
| --- | --- |
| Attribute coverage lift | **3.19x** (129 → 412) |
| Withheld attributes recovered | **74.1%** |
| Recovered values correct | **87.2%** |
| **Contradiction rate** | **12.8%** |
| Contradiction rate, excluding flagged defaults | **8.8%** |
| Seeded defects caught | **100.0%** (51/51) |
| False alarms on clean records | **0.0%** |
| Auto-publishable (clean records) | **52.9%** |
| Defective records stopped | **100.0%** |

## Accuracy by provenance

| Provenance | Correct | Contradicted | Precision |
| --- | --- | --- | --- |
| defaulted | 74 | 19 | 79.6% |
| derived | 8 | 0 | 100.0% |
| inferred | 42 | 16 | 72.4% |
| knowledge_base | 72 | 0 | 100.0% |
| parsed | 43 | 0 | 100.0% |

## Accuracy by ground-truth strength

`standards` values come from ISO 15 and ISO 898-1 and are externally fixed. `archetype` values were hand-authored and are therefore weaker evidence.

| Source | Recall | Precision |
| --- | --- | --- |
| archetype | 41.7% | 69.1% |
| standards | 99.5% | 93.2% |

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
| Hours saved | **9,150** |
| Cost saved | **$320,261** |
| FTE-years saved | 5.1 |
| Machine processing time | 0.11 hours |

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
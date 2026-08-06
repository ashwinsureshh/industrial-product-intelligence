# Ablation: deterministic vs live vs gated hybrid

| Engine | Standards recall | Archetype recall | Contradiction | Contradiction excl. defaults | False alarms |
| --- | --- | --- | --- | --- | --- |
| demo (deterministic) | 83.1% | 33.1% | 11.1% | 0.0% | 0.0% |
| live (claude) | 98.1% | 27.0% | 18.6% | 16.5% | 2.0% |
| hybrid (gated) | 99.5% | 41.7% | 12.8% | 8.8% | 0.0% |

## What the gate actually did

- Gap-filled (key the deterministic engine left empty): **57**
- Displaced a category default: **10**
- **Refused** to overrule evidence-backed values: **28**

The refusal count is the point. Each one is a case where the live engine replaced a supplied, parsed, knowledge-base or derived value with a model guess, and the gate stopped it.
---
title: Industrial Product Intelligence
emoji: ⚙️
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Sparse supplier data into validated, explainable catalog records
---

# Industrial Product Intelligence

Turns sparse, messy supplier product data into **validated, explainable,
commerce-ready catalog records** — where every enriched value carries its
evidence, its provenance and its confidence.

In industrial commerce a wrong specification ships a broken machine, so this
engine is built to **refuse to guess silently**. It leaves a field blank, flags
a contradiction, or blocks publication rather than emit a confident-looking
value it cannot defend.

## Try it

| Tab | What to do |
| --- | --- |
| **Single Product** | Pick a demo case. *Contradictory valve* and *Transposed bearing* are the interesting ones — every field is plausible alone, and only cross-field validation catches that the product cannot exist. |
| **Document** | Drop a datasheet PDF. Ruled tables, whitespace columns and dot-leader lists are all read, and every value stays traceable to the document. |
| **Catalog** | Run the 10-product demo catalog, or upload your own CSV. |
| **Learning** | Analyse products from categories the engine was never taught. It infers a full schema — attributes, types, units, vocabularies, ranges — for review. |

Click any attribute row to see the evidence behind that value.

## Two engines

**Demo** is deterministic and free: it reasons from curated standards data
(ISO 15 bearing series, ISO 898-1 property classes, SAE J517, IEC 60529).

**Live AI** uses Claude via tool-schema structured output. Results for the demo
products are **pre-computed and bundled**, so you can select Live AI and see
genuine model output without supplying a key. For your own products, paste your
own API key — it is used for that call only and never stored.

This deployment cannot spend anyone's credits: no server-side key is
configured, and the server-key fallback is disabled.

## Measured results

102-case benchmark, deterministic engine. Bearing and fastener ground truth
comes from ISO 15 and ISO 898-1 — externally fixed values the engine cannot be
tuned to without also being correct in the real world.

| Metric | Result |
| --- | --- |
| Attribute coverage lift | **2.75×** |
| **Contradiction rate on evidence-backed values** | **0.0%** |
| Seeded defects caught | **100%** (51/51) |
| False alarms on clean records | **0.0%** |
| Throughput | ~340 products/s |

The headline is the contradiction rate, not coverage. Coverage is easy — any
system reaches 100% by inventing everything.

Source: https://github.com/ashwinsureshh/industrial-product-intelligence

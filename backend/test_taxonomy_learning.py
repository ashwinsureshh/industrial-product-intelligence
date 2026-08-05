"""Proves the engine can learn a category it was never taught.

The scenario is the one a judge will ask about: products arrive from a category
nobody curated. Before learning, the engine cannot classify them and says so.
After a proposal is reviewed and approved, the same products classify, validate
and score like any curated category — and a *new* product of that kind, never
seen during learning, classifies too.

Uses pneumatic cylinders, which are absent from taxonomy.json. No API calls.
"""

from __future__ import annotations

import sys

from app.models import RawProduct
from app.pipeline import run as pipeline
from app.pipeline import taxonomy as tax
from app.providers.mock import MockProvider
from app.taxonomy_learning import propose as proposer
from app.taxonomy_learning import store

FAILURES: list[str] = []

# A category the shipped taxonomy has never heard of.
CYLINDERS = [
    RawProduct(sku="PC-001", mpn="DSNU-25-100-PPV-A", brand="Festo",
               name="Round pneumatic cylinder double acting",
               raw_specs={"Bore Size": "25 mm", "Stroke Length": "100 mm",
                          "Operating Pressure": "10 bar", "Cushioning": "Adjustable",
                          "Piston Rod Thread": "M10x1.25", "Mounting": "Basic"}),
    RawProduct(sku="PC-002", mpn="DSNU-32-80-PPV-A", brand="Festo",
               name="Round pneumatic cylinder double acting",
               raw_specs={"Bore Size": "32 mm", "Stroke Length": "80 mm",
                          "Operating Pressure": "10 bar", "Cushioning": "Adjustable",
                          "Piston Rod Thread": "M10x1.25", "Mounting": "Basic"}),
    RawProduct(sku="PC-003", mpn="CP96SB50-200", brand="SMC",
               name="ISO pneumatic cylinder double acting",
               raw_specs={"Bore Size": "50 mm", "Stroke Length": "200 mm",
                          "Operating Pressure": "9 bar", "Cushioning": "Air cushion",
                          "Piston Rod Thread": "M16x1.5", "Mounting": "Flange"}),
    RawProduct(sku="PC-004", mpn="CP96SB63-160", brand="SMC",
               name="ISO pneumatic cylinder double acting",
               raw_specs={"Bore Size": "63 mm", "Stroke Length": "160 mm",
                          "Operating Pressure": "9 bar", "Cushioning": "Air cushion",
                          "Piston Rod Thread": "M16x1.5", "Mounting": "Flange"}),
    RawProduct(sku="PC-005", mpn="C85N25-125", brand="SMC",
               name="Mini pneumatic cylinder",
               raw_specs={"Bore Size": "25 mm", "Stroke Length": "125 mm",
                          "Operating Pressure": "10 bar", "Cushioning": "Rubber bumper",
                          "Piston Rod Thread": "M10x1.25", "Mounting": "Basic"}),
]

# Never shown to the learner — proves the schema generalises.
UNSEEN = RawProduct(
    sku="PC-999", mpn="DSNU-40-50-PPV-A", brand="Festo",
    name="Round pneumatic cylinder double acting",
    raw_specs={"Bore Size": "40 mm", "Stroke Length": "50 mm",
               "Operating Pressure": "10 bar", "Cushioning": "Adjustable",
               "Piston Rod Thread": "M12x1.25", "Mounting": "Basic"},
)


def check(condition: bool, message: str) -> None:
    print(f"  {'PASS' if condition else 'FAIL'}: {message}")
    if not condition:
        FAILURES.append(message)


def classify(product: RawProduct):
    return tax.classify(
        name=product.name, description=product.description,
        free_text=product.free_text, category_hint=product.category_hint,
        mpn=product.mpn, brand=product.brand, raw_specs=product.raw_specs,
    )


def main() -> int:
    print("=" * 66)
    print("  TAXONOMY LEARNING - no API calls, $0.00")
    print("=" * 66)

    # Start from a genuinely empty store. Rejecting leftovers is not enough:
    # a rejected proposal is settled, so re-proposing the same schema would be
    # correctly suppressed and the test would fail on its own residue.
    store.PROPOSALS_PATH.unlink(missing_ok=True)
    store.LEARNED_PATH.unlink(missing_ok=True)
    tax.invalidate()

    print("\n[1] Before learning, these products have no category that fits")
    before = [classify(p) for p in CYLINDERS]
    weak = sum(1 for cat, conf, _, _ in before if cat is None or conf < 0.55)
    check(weak >= 4, f"{weak}/{len(CYLINDERS)} products unclassified or low-confidence")

    nearest, nearest_conf, _, _ = before[0]
    print(f"       nearest existing category: "
          f"{nearest['path'][-1] if nearest else 'none'} at {nearest_conf:.0%}")

    result_before = pipeline.enrich(CYLINDERS[0], MockProvider())
    print(f"       -> readiness {result_before.readiness.overall}/100 "
          f"({result_before.readiness.verdict})")
    # The failure mode that matters is a *confident* wrong answer. A weak match
    # into a neighbouring category is acceptable provided the record does not
    # reach a storefront on the strength of it.
    check(result_before.readiness.verdict != "publish",
          f"a product with no proper category never auto-publishes "
          f"({result_before.readiness.verdict})")
    check(nearest is None or nearest_conf < 0.55,
          f"and is not confidently mis-classified ({nearest_conf:.0%})")

    print("\n[2] The engine proposes a category from the evidence")
    proposals = proposer.propose(CYLINDERS)
    check(len(proposals) >= 1, f"produced {len(proposals)} proposal(s)")
    proposal = proposals[0]
    print(f"       noun      : {proposal.noun}")
    print(f"       code      : {proposal.code}")
    print(f"       confidence: {proposal.confidence}")
    print(f"       attributes: {len(proposal.attributes)}")
    for attribute in proposal.attributes:
        detail = attribute.type
        if attribute.unit:
            detail += f" [{attribute.unit}]"
        if attribute.values:
            detail += f" enum{attribute.values}"
        if attribute.range:
            detail += f" range{attribute.range}"
        print(f"         - {attribute.key:22} {detail}"
              f"{'  (required)' if attribute.required else ''}")

    keys = {a.key for a in proposal.attributes}
    check("bore_size" in keys, "recovered 'bore_size' as an attribute")
    check("stroke_length" in keys, "recovered 'stroke_length' as an attribute")

    bore = next(a for a in proposal.attributes if a.key == "bore_size")
    check(bore.type == "number" and bore.unit == "mm",
          f"inferred bore_size as a number in mm (got {bore.type}/{bore.unit})")
    check(bore.range is not None and bore.range[0] <= 25 and bore.range[1] >= 63,
          f"inferred a range covering the observed 25-63 mm (got {bore.range})")

    cushioning = next((a for a in proposal.attributes if a.key == "cushioning"), None)
    check(cushioning is not None and cushioning.type == "enum",
          "inferred 'cushioning' as a controlled vocabulary")
    if cushioning:
        check(len(cushioning.values or []) == 3,
              f"vocabulary has the 3 observed values ({cushioning.values})")

    print("\n[3] Nothing is applied until a human approves")
    store.save_proposals([proposal])
    pending = store.list_proposals("pending")
    check(any(p.id == proposal.id for p in pending), "proposal queued as pending")
    still_unknown, conf, _, _ = classify(CYLINDERS[0])
    check(still_unknown is None or conf < 0.55,
          "taxonomy unchanged while the proposal is only pending")

    print("\n[4] After approval, the category is live")
    approved = store.approve(proposal.id, note="approved by test")
    check(approved is not None and approved.status == "approved",
          "proposal marked approved")

    category, confidence, _, _ = classify(CYLINDERS[0])
    check(category is not None and category["code"] == proposal.code,
          f"learned product now classifies (got "
          f"{category['code'] if category else None})")
    check(confidence >= 0.55, f"classified with usable confidence ({confidence})")

    result = pipeline.enrich(CYLINDERS[0], MockProvider())
    print(f"       -> {len(result.attributes)} attributes, "
          f"readiness {result.readiness.overall}/100 ({result.readiness.verdict})")
    check(len(result.attributes) >= 5,
          f"attributes now extracted against the learned schema "
          f"({len(result.attributes)})")

    bore_attr = result.attr("bore_size")
    check(bore_attr is not None and float(bore_attr.value) == 25,
          f"bore_size read as 25 mm (got {bore_attr.value if bore_attr else None})")

    print("\n[5] The schema generalises to a product never seen while learning")
    unseen_cat, unseen_conf, _, _ = classify(UNSEEN)
    check(unseen_cat is not None and unseen_cat["code"] == proposal.code,
          "unseen product classifies into the learned category")
    unseen_result = pipeline.enrich(UNSEEN, MockProvider())
    unseen_bore = unseen_result.attr("bore_size")
    check(unseen_bore is not None and float(unseen_bore.value) == 40,
          f"unseen bore read as 40 mm (got "
          f"{unseen_bore.value if unseen_bore else None})")
    print(f"       -> {len(unseen_result.attributes)} attributes, "
          f"readiness {unseen_result.readiness.overall}/100")

    print("\n[6] Learned validation rules actually fire")
    absurd = RawProduct(
        sku="PC-BAD", mpn="BAD-1", brand="Festo",
        name="Round pneumatic cylinder double acting",
        raw_specs={"Bore Size": "50000 mm", "Stroke Length": "100 mm",
                   "Operating Pressure": "10 bar", "Cushioning": "Adjustable"},
    )
    bad_result = pipeline.enrich(absurd, MockProvider())
    codes = [i.code for i in bad_result.issues]
    check("OUT_OF_RANGE" in codes,
          f"an out-of-range bore is caught by the learned range ({codes})")

    print("\n[7] Approval is reversible")
    check(store.revoke(proposal.code), "learned category revoked")
    gone, _, _, _ = classify(CYLINDERS[0])
    check(gone is None or gone["code"] != proposal.code,
          "taxonomy returns to its curated state")

    print("\n" + "=" * 66)
    if FAILURES:
        print(f"{len(FAILURES)} CHECK(S) FAILED")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("ALL TAXONOMY LEARNING CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

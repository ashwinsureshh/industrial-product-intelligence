"""Regressions for three defects a QA pass found on the deployed build.

All three broke the same promise from different directions: the engine would
rather leave a field blank than state something it cannot defend.

  1. A part number's own standard could not contradict a supplied dimension,
     because the knowledge base was only ever consulted to fill gaps. A bearing
     marked 6205 published a 30 mm bore at 99% confidence while citing ISO 15
     for the two dimensions either side of it.
  2. Approving a learned category did not change the answer for a product
     already in the cache, so the learning loop failed for the very product
     used to teach it.
  3. The manufacturer-only sourcing rule was enforced on the discovery path but
     not on the URL ingest path beside it.

Costs $0: deterministic engine, no network.
"""

from __future__ import annotations

import sys

from app.models import RawProduct
from app.pipeline import run
from app.providers.mock import MockProvider

PROVIDER = MockProvider()


def check(label: str, condition: bool) -> bool:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")
    return condition


def enrich(**kwargs):
    return run.enrich(RawProduct(**kwargs), PROVIDER)


def issue(result, code):
    return next((i for i in result.issues if i.code == code), None)


def value_of(result, key):
    return next((a for a in result.attributes if a.key == key), None)


# --------------------------------------------------------------- 1. standards
def test_standard_contradicts_supplier() -> bool:
    print("\n[1] a designation may contradict a supplied dimension")
    ok = True

    bad = enrich(sku="D1", mpn="6205", brand="SKF", name="Deep groove ball bearing",
                 raw_specs={"Bore": "30 mm", "Outer Diameter": "52 mm", "Width": "15 mm"})
    flag = issue(bad, "STANDARD_CONTRADICTION")
    bore = value_of(bad, "bore_diameter")

    ok &= check("the contradiction is reported", flag is not None)
    ok &= check("and names both numbers",
                flag is not None and "30 mm" in flag.message and "25 mm" in flag.message)
    ok &= check("the record cannot auto-publish", bad.readiness.verdict != "publish")
    # The supplier may hold a variant the table does not cover. Keeping their
    # value is the point: this is a flag, not a correction.
    ok &= check("the supplier's value is kept, not overwritten", bore.value == 30.0)
    ok &= check("but its confidence is reduced", bore.confidence < 0.99)
    ok &= check("and the evidence says the standard disagrees",
                "25 mm" in bore.evidence)

    good = enrich(sku="OK", mpn="6205", brand="SKF", name="Deep groove ball bearing",
                  raw_specs={"Bore": "25 mm", "Outer Diameter": "52 mm", "Width": "15 mm"})
    ok &= check("a record that agrees with the standard is untouched",
                issue(good, "STANDARD_CONTRADICTION") is None
                and good.readiness.verdict == "publish"
                and value_of(good, "bore_diameter").confidence == 0.99)

    # The headline demo supplies no dimensions at all; the standard fills them
    # and must not then be reported as disagreeing with itself.
    sparse = enrich(sku="BRG-6205-2RS", mpn="6205-2RS", brand="skf",
                    name="Deep groove ball bearing")
    ok &= check("the sparse headline case still publishes from ISO 15 alone",
                issue(sparse, "STANDARD_CONTRADICTION") is None
                and sparse.readiness.verdict == "publish"
                and value_of(sparse, "bore_diameter").value == 25)

    # Rounding is not a contradiction.
    rounded = enrich(sku="R", mpn="6205", brand="SKF", name="Deep groove ball bearing",
                     raw_specs={"Bore": "25.0 mm", "Outer Diameter": "52 mm", "Width": "15 mm"})
    ok &= check("25.0 is not treated as contradicting 25",
                issue(rounded, "STANDARD_CONTRADICTION") is None)

    from app.pipeline import validate
    ok &= check("the code counts as an integrity warning, so it blocks auto-publish",
                "STANDARD_CONTRADICTION" in validate.INTEGRITY_CODES)
    return ok


# ------------------------------------------------------------------- 2. cache
def test_cache_follows_the_taxonomy() -> bool:
    print("\n[2] the cache key follows the learned taxonomy")
    ok = True
    from app import cache

    payload = {"mpn": "PC-1", "name": "Double acting pneumatic cylinder"}
    baseline = cache.key_for(payload, "demo")

    # Nothing learned: the key must be exactly what it has always been, or the
    # 20 precomputed live results and 102 committed benchmark records orphan.
    ok &= check("no learned categories means no fingerprint at all",
                cache.taxonomy_fingerprint() == "")

    import hashlib
    import json as _json
    blob = _json.dumps(payload, sort_keys=True, default=str)
    legacy = hashlib.sha256(
        f"demo|deterministic|{blob}".encode("utf-8")
    ).hexdigest()[:32]
    ok &= check("and the key is byte-identical to the pre-fix scheme",
                baseline == legacy)

    # With a category in force the key must move, or an approval cannot change
    # an answer that is already cached.
    real = cache.taxonomy_fingerprint
    cache.taxonomy_fingerprint = lambda: "abc12345"
    try:
        shifted = cache.key_for(payload, "demo")
    finally:
        cache.taxonomy_fingerprint = real

    ok &= check("approving a category changes the key", shifted != baseline)
    ok &= check("and reverting the taxonomy restores it",
                cache.key_for(payload, "demo") == baseline)
    return ok


# ------------------------------------------------------------------ 3. policy
def test_marketplaces_refused_on_every_path() -> bool:
    print("\n[3] the manufacturer-only rule holds on the ingest path too")
    ok = True
    from app.discovery import policy

    for url, kind in [("https://www.amazon.com/dp/B00ABCDEF", "marketplace"),
                      ("https://www.ebay.com/itm/123", "marketplace"),
                      ("https://www.grainger.com/product/SKF-6205", "distributor"),
                      ("https://www.homedepot.com/p/12345", "retailer")]:
        got = policy.blocked_kind(url)
        ok &= check(f"{url.split('/')[2]} is refused as a {kind}", got == kind)

    ok &= check("a manufacturer's own page is still allowed",
                policy.blocked_kind("https://www.skf.com/productinfo/6205-2RS") is None)
    # Narrower than check() by design: a person pasting their supplier's page
    # is asserting provenance the engine cannot verify, and refusing every
    # unrecognised domain would leave the Document tab able to read nothing.
    ok &= check("an unrecognised domain is not blocked on this path",
                policy.blocked_kind("https://some-supplier.example.com/part/6205") is None)
    ok &= check("a malformed URL does not raise",
                policy.blocked_kind("not a url") is None)
    return ok


def main() -> int:
    print("=" * 66)
    print("  QA FIX REGRESSIONS")
    print("=" * 66)
    results = [
        test_standard_contradicts_supplier(),
        test_cache_follows_the_taxonomy(),
        test_marketplaces_refused_on_every_path(),
    ]
    print("\n" + "=" * 66)
    if all(results):
        print("  ALL QA FIX REGRESSIONS PASS")
        return 0
    print("  FAILURES ABOVE")
    return 1


if __name__ == "__main__":
    sys.exit(main())

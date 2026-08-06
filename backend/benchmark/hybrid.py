"""The hybrid gate: deterministic engine authoritative, Claude bounded.

The live ablation established the problem this module solves. Claude recovered
31 more standards-backed attributes than the deterministic engine but
contradicted 38 instead of 8, and its precision on `knowledge_base` values fell
from 100% to 79.8%. The cause is not that the model is bad at the task — it is
that the live path lets model output carry provenance classes that *mean*
evidence-backed, so reconciliation lets a guess outrank the knowledge base.

The fix is a policy, not a better prompt. Under the existing provenance rank
(`knowledge_base` 4 > `derived` 3 > `inferred` 2 > `defaulted` 1) a model
proposal is worth strictly less than measured or curated evidence and strictly
more than a category default. So Claude is allowed exactly two moves:

  * **fill a gap** — a key the deterministic engine left empty; and
  * **displace a default** — a `defaulted` value carries no supplier backing at
    all, so an informed guess genuinely beats it.

It may never overrule a `supplied`, `parsed`, `knowledge_base` or `derived`
value. Everything it does contribute is re-stamped `inferred`, which is what it
actually is, so the audit trail stays honest and the UI colours it correctly.

Merging happens offline against records both engines already produced, so
scoring a policy change costs nothing.
"""

from __future__ import annotations

from typing import Any

from app.models import Attribute, EnrichedProduct, Provenance
from app.pipeline import taxonomy, validate
from app.pipeline.run import _score

# Ceiling on the confidence a model-supplied value may claim. Calibrated, not
# chosen: `inferred` values in the live ablation were correct 60.0% of the time.
INFERRED_CONFIDENCE_CAP = 0.6

# The classes that represent real evidence. Claude never displaces these.
PROTECTED = frozenset({
    Provenance.SUPPLIED,
    Provenance.PARSED,
    Provenance.KNOWLEDGE_BASE,
    Provenance.DERIVED,
})


def _demote(attribute: Attribute, reason: str) -> Attribute:
    """Re-stamp a model-supplied value as what it is: an inference."""
    return attribute.model_copy(update={
        "provenance": Provenance.INFERRED,
        "confidence": round(min(attribute.confidence, INFERRED_CONFIDENCE_CAP), 3),
        "evidence": f"[hybrid: {reason}] {attribute.evidence}"[:600],
        "method": "hybrid:claude-bounded",
    })


def merge(demo: EnrichedProduct, live: EnrichedProduct) -> tuple[EnrichedProduct, dict[str, Any]]:
    """Apply the gate to one product. Returns the record and what changed.

    Validation and scoring are re-run on the merged attribute set rather than
    copied from either parent, because a record assembled under a different
    policy is a different record — its cross-field checks and verdict have to
    be earned again.
    """
    kept = {a.key: a for a in demo.attributes}
    incoming = {a.key: a for a in live.attributes}

    gap_filled: list[str] = []
    displaced: list[str] = []
    refused: list[str] = []

    for key, candidate in incoming.items():
        incumbent = kept.get(key)

        if incumbent is None:
            kept[key] = _demote(candidate, "gap fill")
            gap_filled.append(key)
        elif incumbent.provenance == Provenance.DEFAULTED:
            # A default is a placeholder, not evidence. Only count it displaced
            # if the model actually disagrees with it.
            if str(candidate.value).strip().lower() != str(incumbent.value).strip().lower():
                kept[key] = _demote(candidate, "displaced category default")
                displaced.append(key)
        elif incumbent.provenance in PROTECTED:
            if str(candidate.value).strip().lower() != str(incumbent.value).strip().lower():
                refused.append(key)

    attributes = sorted(kept.values(), key=lambda a: (a.group, -a.confidence, a.label))

    category = taxonomy.get_category(demo.category.code) if demo.category else None
    issues, missing = validate.run_all(attributes, category, demo.identity, demo.content)
    readiness = _score(attributes, category, issues, missing)

    merged = demo.model_copy(update={
        "attributes": attributes,
        "issues": issues,
        "readiness": readiness,
        "mode": "hybrid",
    })

    return merged, {
        "gap_filled": gap_filled,
        "displaced_defaults": displaced,
        "refused_overrules": refused,
    }

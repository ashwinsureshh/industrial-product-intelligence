"""The hybrid gate: the deterministic engine stays authoritative, Claude is bounded.

Measured on the 102-case benchmark, the unrestricted Claude engine recovered 31
more standards-backed attributes than the deterministic one but contradicted 38
instead of 8, and its precision on `knowledge_base` values fell from 100% to
79.8%. The cause was never the model's competence: the live path let model
output carry provenance classes that *mean* evidence-backed, so reconciliation
allowed a guess to outrank a standards lookup.

The remedy is a policy, not a better prompt. Under the provenance rank the
pipeline already uses (`knowledge_base` 4 > `derived` 3 > `inferred` 2 >
`defaulted` 1) a model proposal is worth strictly less than measured or curated
evidence and strictly more than a category default. So the model gets exactly
two moves:

  * **fill a gap** - a key the deterministic engine left empty; and
  * **displace a default** - a `defaulted` value carries no supplier backing at
    all, so an informed guess genuinely beats it.

It may never overrule a `supplied`, `parsed`, `knowledge_base` or `derived`
value. Everything it does contribute is re-stamped `inferred`, which is what it
is, so the audit trail stays honest.

Every decision - including every refusal - is recorded. A system that reports
only what the AI added cannot be audited; what it was stopped from doing is the
evidence that the guardrail exists.

This module is the single implementation. `benchmark/hybrid.py` re-exports it so
the published benchmark figures and the running service can never drift apart.
"""

from __future__ import annotations

from ..models import (
    Attribute,
    EnrichedProduct,
    GateAction,
    GateDecision,
    Provenance,
)
from . import taxonomy, validate
from . import units as U
from .run import score_readiness

# Ceiling on the confidence a model-supplied value may claim. Calibrated rather
# than chosen: `inferred` values measured 60.0% precision in the live ablation.
INFERRED_CONFIDENCE_CAP = 0.6

# The classes that represent real evidence. The model never displaces these.
PROTECTED = frozenset({
    Provenance.SUPPLIED,
    Provenance.PARSED,
    Provenance.KNOWLEDGE_BASE,
    Provenance.DERIVED,
})

_PROVENANCE_REASON = {
    Provenance.SUPPLIED: "the supplier stated this value",
    Provenance.PARSED: "this was parsed from the supplied identifiers",
    Provenance.KNOWLEDGE_BASE: "a published standard fixes this value",
    Provenance.DERIVED: "this was calculated from other known attributes",
}


def _show(attribute: Attribute) -> str:
    return U.format_value(attribute.value, attribute.unit)


def _same(a: Attribute, b: Attribute) -> bool:
    return str(a.value).strip().lower() == str(b.value).strip().lower()


def _adopt(attribute: Attribute, reason: str) -> Attribute:
    """Re-stamp a model-supplied value as what it actually is: an inference."""
    return attribute.model_copy(update={
        "provenance": Provenance.INFERRED,
        "confidence": round(min(attribute.confidence, INFERRED_CONFIDENCE_CAP), 3),
        "evidence": f"[gate: {reason}] {attribute.evidence}"[:600],
        "method": "hybrid:claude-bounded",
    })


def apply(
    deterministic: EnrichedProduct,
    model: EnrichedProduct,
    live_source: str | None = None,
) -> EnrichedProduct:
    """Merge a model record into a deterministic one under the gate policy.

    Validation and scoring are re-run rather than copied from either parent: a
    record assembled under a different policy is a different record, and its
    cross-field checks and verdict have to be earned again.
    """
    kept: dict[str, Attribute] = {a.key: a for a in deterministic.attributes}
    actions: list[GateAction] = []

    for candidate in model.attributes:
        incumbent = kept.get(candidate.key)

        if incumbent is None:
            kept[candidate.key] = _adopt(candidate, "gap fill")
            actions.append(GateAction(
                key=candidate.key, label=candidate.label, action="gap_filled",
                proposed=_show(candidate),
                reason="The deterministic engine found no value for this field, "
                       "so the model's proposal is recorded as an inference.",
            ))

        elif incumbent.provenance == Provenance.DEFAULTED:
            # A default is a placeholder, not evidence. Only a disagreement is
            # a displacement; agreement would inflate the action count.
            if not _same(candidate, incumbent):
                kept[candidate.key] = _adopt(candidate, "displaced category default")
                actions.append(GateAction(
                    key=candidate.key, label=candidate.label,
                    action="displaced_default",
                    proposed=_show(candidate), kept=_show(incumbent),
                    kept_provenance=incumbent.provenance.value,
                    reason="The existing value was a category default carrying no "
                           "supplier backing, which an informed inference outranks.",
                ))

        elif incumbent.provenance in PROTECTED and not _same(candidate, incumbent):
            actions.append(GateAction(
                key=candidate.key, label=candidate.label, action="refused",
                proposed=_show(candidate), kept=_show(incumbent),
                kept_provenance=incumbent.provenance.value,
                reason=f"Refused: {_PROVENANCE_REASON[incumbent.provenance]}, "
                       f"which outranks a model inference.",
            ))

    attributes = sorted(kept.values(), key=lambda a: (a.group, -a.confidence, a.label))

    category = taxonomy.get_category(deterministic.category.code) if deterministic.category else None
    issues, missing = validate.run_all(
        attributes, category, deterministic.identity, deterministic.content
    )
    readiness = score_readiness(attributes, category, issues, missing)

    decision = GateDecision(
        gap_filled=sum(1 for a in actions if a.action == "gap_filled"),
        displaced_defaults=sum(1 for a in actions if a.action == "displaced_default"),
        refused=sum(1 for a in actions if a.action == "refused"),
        actions=actions,
        live_source=live_source,
    )

    return deterministic.model_copy(update={
        "attributes": attributes,
        "issues": issues,
        "readiness": readiness,
        "gate": decision,
        "mode": "hybrid",
    })

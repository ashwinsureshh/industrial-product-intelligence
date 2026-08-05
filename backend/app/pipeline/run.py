"""Pipeline orchestration.

Stage order is deliberate and each stage is traced so the UI can show exactly
what happened and why:

    normalize -> classify -> extract -> infer -> reconcile -> validate -> score -> content

Reconciliation sits between inference and validation because that is where
competing values for the same attribute are resolved by provenance rank. Only
after a single value per attribute is settled does validation have something
coherent to check.
"""

from __future__ import annotations

import time
from typing import Any

from ..models import (
    Attribute,
    CategoryAssignment,
    EnrichedProduct,
    Provenance,
    RawProduct,
    ReadinessScore,
    Severity,
    StageTrace,
)
from ..providers.base import Provider
from . import extract, taxonomy, validate
from . import units as U

# How much we trust each provenance class when two stages disagree.
PROVENANCE_RANK = {
    Provenance.SUPPLIED: 6,
    Provenance.PARSED: 5,
    Provenance.KNOWLEDGE_BASE: 4,
    Provenance.DERIVED: 3,
    Provenance.INFERRED: 2,
    Provenance.DEFAULTED: 1,
}


class _Timer:
    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.ms = int((time.perf_counter() - self._start) * 1000)


def _normalize_input(raw: RawProduct) -> tuple[RawProduct, dict[str, Any], list[str]]:
    """Clean whitespace, canonicalize the brand, recover identity fields."""
    notes: list[str] = []
    cleaned = raw.model_copy(deep=True)

    for field in ("sku", "mpn", "brand", "name", "description", "category_hint", "free_text"):
        value = getattr(cleaned, field, None)
        if isinstance(value, str):
            setattr(cleaned, field, " ".join(value.split()).strip())

    identity = extract.identity_from_input(cleaned)
    if identity.get("_mpn_evidence"):
        notes.append(identity.pop("_mpn_evidence"))

    canonical, entry = taxonomy.canonical_brand(cleaned.brand)
    if canonical:
        identity["brand"] = canonical
        if entry and cleaned.brand and canonical.lower() != cleaned.brand.lower():
            notes.append(f"Brand '{cleaned.brand}' normalized to '{canonical}'.")
        if entry:
            identity["brand_country"] = entry.get("country")

    if cleaned.price is not None and not cleaned.currency:
        notes.append("Price supplied without a currency; assumed to need confirmation.")

    return cleaned, identity, notes


def _reconcile(attributes: list[Attribute]) -> tuple[list[Attribute], list[str]]:
    """Collapse duplicates, keeping the best-supported value for each key."""
    best: dict[str, Attribute] = {}
    conflicts: list[str] = []

    for attr in attributes:
        incumbent = best.get(attr.key)
        if incumbent is None:
            best[attr.key] = attr
            continue

        challenger_rank = PROVENANCE_RANK[attr.provenance]
        incumbent_rank = PROVENANCE_RANK[incumbent.provenance]

        if (challenger_rank, attr.confidence) > (incumbent_rank, incumbent.confidence):
            winner, loser = attr, incumbent
        else:
            winner, loser = incumbent, attr

        # Disagreement on the actual value is worth surfacing; agreement is not.
        if str(winner.value).strip().lower() != str(loser.value).strip().lower():
            conflicts.append(
                f"{winner.label}: kept {U.format_value(winner.value, winner.unit)} "
                f"({winner.provenance.value}) over "
                f"{U.format_value(loser.value, loser.unit)} ({loser.provenance.value})"
            )
            # Losing a contest is itself evidence of uncertainty.
            winner = winner.model_copy(
                update={"confidence": round(max(winner.confidence - 0.05, 0.1), 3)}
            )

        best[attr.key] = winner

    return list(best.values()), conflicts


def _score(
    attributes: list[Attribute],
    category: dict[str, Any] | None,
    issues: list,
    missing: list[str],
) -> ReadinessScore:
    """Three independent axes, then a weighted verdict.

    Kept separate on purpose: a record can be complete but contradictory, or
    clean but sparse, and those need different remediation.
    """
    notes: list[str] = []

    total_defined = len((category or {}).get("attributes", {})) or 1
    filled = len([a for a in attributes if a.value not in (None, "")])
    completeness = min(filled / total_defined, 1.0) * 100

    required = (category or {}).get("required", [])
    if required:
        satisfied = len(required) - len(missing)
        # Required coverage dominates: 70% of the completeness score.
        completeness = 0.7 * (satisfied / len(required)) * 100 + 0.3 * completeness

    if attributes:
        # Weight by provenance so a record padded with defaults scores honestly.
        weights = [PROVENANCE_RANK[a.provenance] / 6 for a in attributes]
        confidence = (
            sum(a.confidence * w for a, w in zip(attributes, weights))
            / sum(weights)
        ) * 100
    else:
        confidence = 0.0

    errors = [i for i in issues if i.severity == Severity.ERROR]
    warnings = [i for i in issues if i.severity == Severity.WARNING]
    integrity = [i for i in validate.integrity_issues(issues) if i.severity != Severity.ERROR]
    validity = max(0.0, 100.0 - 22.0 * len(errors) - 6.0 * len(warnings))

    overall = 0.35 * completeness + 0.30 * confidence + 0.35 * validity

    if category is None:
        verdict = "blocked"
        notes.append(
            "No category could be resolved, so no attribute schema or validation "
            "rules apply. Supply a product type or a fuller description."
        )
    elif errors:
        verdict = "blocked"
        notes.append(f"{len(errors)} blocking error(s) must be resolved before publication.")
    elif integrity:
        # The data may not describe a physically coherent product. Even at a
        # high score that has to reach a human before it reaches a storefront.
        verdict = "review"
        notes.append(
            f"{len(integrity)} data-integrity warning(s) require sign-off: "
            + ", ".join(i.code for i in integrity[:3])
            + "."
        )
    elif overall >= 78 and not missing:
        verdict = "publish"
        notes.append("Record meets the publication threshold.")
    else:
        verdict = "review"
        if missing:
            notes.append(f"Missing required field(s): {', '.join(missing)}.")
        if overall < 78:
            notes.append("Confidence and completeness are below the auto-publish threshold.")

    defaulted = [a for a in attributes if a.provenance == Provenance.DEFAULTED]
    if defaulted:
        notes.append(
            f"{len(defaulted)} value(s) are category defaults and carry no supplier backing."
        )

    return ReadinessScore(
        overall=round(min(overall, 100.0), 1),
        completeness=round(min(completeness, 100.0), 1),
        confidence=round(min(confidence, 100.0), 1),
        validity=round(validity, 1),
        verdict=verdict,
        missing_required=missing,
        notes=notes,
    )


def enrich(raw: RawProduct, provider: Provider) -> EnrichedProduct:
    """Run the full pipeline for one product."""
    trace: list[StageTrace] = []

    if raw.is_empty():
        return EnrichedProduct(
            input=raw,
            mode=provider.name,
            trace=[StageTrace(stage="normalize", summary="Input contained no usable fields.")],
            readiness=ReadinessScore(
                overall=0, completeness=0, confidence=0, validity=0,
                verdict="blocked", notes=["No input supplied."],
            ),
        )

    # ---------------------------------------------------------------- normalize
    with _Timer() as t:
        cleaned, identity, notes = _normalize_input(raw)
    trace.append(StageTrace(
        stage="normalize",
        summary=(
            f"Cleaned input and resolved identity"
            f"{': ' + '; '.join(notes) if notes else '.'}"
        ),
        duration_ms=t.ms,
        added=[k for k in identity if not k.startswith("_")],
        details={"identity": {k: v for k, v in identity.items() if not k.startswith("_")}},
    ))

    # ----------------------------------------------------------------- classify
    with _Timer() as t:
        category, cat_conf, reasons, alternatives = taxonomy.classify(
            name=cleaned.name,
            description=cleaned.description,
            free_text=cleaned.free_text,
            category_hint=cleaned.category_hint,
            mpn=identity.get("mpn"),
            brand=cleaned.brand,
            raw_specs=cleaned.raw_specs,
        )
    assignment = None
    if category:
        assignment = CategoryAssignment(
            code=category["code"],
            path=category["path"],
            confidence=cat_conf,
            rationale="; ".join(reasons) if reasons else "Matched on general product signals.",
            alternatives=alternatives,
        )
    trace.append(StageTrace(
        stage="classify",
        summary=(
            f"Assigned to {' > '.join(category['path'])} "
            f"(confidence {cat_conf:.0%})" if category
            else "Could not resolve a category from the supplied text."
        ),
        duration_ms=t.ms,
        details={"reasons": reasons, "alternatives": alternatives},
    ))

    # ------------------------------------------------------------------ extract
    with _Timer() as t:
        from_specs, unmapped = extract.from_raw_specs(cleaned, category)
        seen = {a.key for a in from_specs}
        from_text = extract.from_free_text(cleaned, category, seen, from_specs)
        extracted = from_specs + from_text
    trace.append(StageTrace(
        stage="extract",
        summary=(
            f"Resolved {len(extracted)} attribute(s) deterministically "
            f"({len(from_specs)} from the spec table, {len(from_text)} from prose)."
            + (f" {len(unmapped)} supplier field(s) had no taxonomy match." if unmapped else "")
        ),
        duration_ms=t.ms,
        added=[a.key for a in extracted],
        details={"unmapped_supplier_fields": unmapped},
    ))

    # -------------------------------------------------------------------- infer
    with _Timer() as t:
        inference = provider.infer_attributes(cleaned, category, extracted)
    trace.append(StageTrace(
        stage="infer",
        summary=(
            f"{provider.name} provider added {len(inference.attributes)} attribute(s)."
            + (" " + " ".join(inference.notes) if inference.notes else "")
        ),
        duration_ms=t.ms,
        added=[a.key for a in inference.attributes],
        details={"usage": inference.usage} if inference.usage else {},
    ))

    # ---------------------------------------------------------------- reconcile
    with _Timer() as t:
        attributes, conflicts = _reconcile(extracted + inference.attributes)
        attributes.sort(key=lambda a: (a.group, -a.confidence, a.label))
    trace.append(StageTrace(
        stage="reconcile",
        summary=(
            f"Settled on {len(attributes)} unique attribute(s)"
            + (f"; resolved {len(conflicts)} conflict(s) by provenance rank."
               if conflicts else " with no conflicts.")
        ),
        duration_ms=t.ms,
        changed=[c.split(":")[0] for c in conflicts],
        details={"conflicts": conflicts},
    ))

    # ------------------------------------------------------------------ content
    with _Timer() as t:
        content_result = provider.generate_content(cleaned, category, attributes, identity)
    trace.append(StageTrace(
        stage="content",
        summary=(
            "Generated storefront copy."
            if content_result.content else "No content generated."
        ),
        duration_ms=t.ms,
        details={"notes": content_result.notes},
    ))

    # ----------------------------------------------------------------- validate
    with _Timer() as t:
        issues, missing = validate.run_all(
            attributes, category, identity, content_result.content
        )
    errors = sum(1 for i in issues if i.severity == Severity.ERROR)
    warnings = sum(1 for i in issues if i.severity == Severity.WARNING)
    trace.append(StageTrace(
        stage="validate",
        summary=f"Ran {len(issues)} check finding(s): {errors} error(s), {warnings} warning(s).",
        duration_ms=t.ms,
        details={"errors": errors, "warnings": warnings},
    ))

    # -------------------------------------------------------------------- score
    with _Timer() as t:
        readiness = _score(attributes, category, issues, missing)
    trace.append(StageTrace(
        stage="score",
        summary=f"Readiness {readiness.overall}/100 — verdict '{readiness.verdict}'.",
        duration_ms=t.ms,
        details=readiness.model_dump(),
    ))

    return EnrichedProduct(
        input=raw,
        identity=identity,
        category=assignment,
        attributes=attributes,
        content=content_result.content,
        issues=issues,
        readiness=readiness,
        trace=trace,
        mode=provider.name,
    )

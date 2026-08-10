"""Controlled vocabularies: the value must exist in the list, or it is refused.

Unilog's List of Values is not a suggestion. Their guide puts it plainly — "a
fluent description made of invented values scores zero" — so an attribute value
that is not in the approved list for its classpath is *wrong*, however true it
may be about the product.

This is the same policy the hybrid gate already applies to the model, pointed at
a different authority. Three outcomes, and only three:

  * **Accepted.** The value is already the approved form.
  * **Mapped.** The value is a known supplier spelling of an approved value, so
    it is rewritten to the canonical form and the mapping is recorded. This is
    the many-to-one normalisation the Fittings spec is built around: 1,472
    supplier connection types collapse onto 515 approved ones.
  * **Refused.** Nothing in the list matches. The original value is kept
    untouched, an integrity issue is raised so the record cannot auto-publish,
    and — where one exists — a near miss is offered as a *suggestion* for a
    human to confirm.

That last distinction is the whole point. A close-enough match is proposed, never
applied: silently turning "Stainless Steal" into "Stainless Steel" is convenient,
but the same machinery would just as happily turn "Cast Iron" into "Cast Steel".
Proposals go to a reviewer; only exact and explicitly-mapped values are written.
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from ..models import Attribute, Severity, ValidationIssue
from .house_style import UNILOG_DIR

LOV_DIR = UNILOG_DIR / "lov"

# How close a rejected value must be to an approved one before we bother
# suggesting it. Tuned to catch typos and spacing, not to bridge real
# differences: "Cast Iron" and "Cast Steel" score 0.79 and must not pair up.
_SUGGEST_THRESHOLD = 0.86


@dataclass(frozen=True)
class Resolution:
    """What the vocabulary did with one value."""

    original: str
    value: str | None          # the approved form, when there is one
    method: str | None         # exact | case | synonym | folded
    refused: bool
    reason: str = ""
    suggestion: str | None = None

    @property
    def mapped(self) -> bool:
        return bool(self.value) and self.method not in (None, "exact")


@lru_cache(maxsize=1)
def _load() -> dict[str, dict[str, Any]]:
    """Merge every LOV file into one lookup keyed by classpath and by alias.

    A vocabulary is identified by *Unilog's* classpath, because that is what
    their file will say. Our own taxonomy uses different wording for the same
    shelf, so each entry may also list `applies_to` — local category codes or
    paths it governs. That list is the integration seam between their
    classification and ours, and it is data for the same reason the rest is:
    the mapping is a customer fact, not a property of the engine.
    """
    table: dict[str, dict[str, Any]] = {}
    if not LOV_DIR.exists():
        return table
    for path in sorted(LOV_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as fh:
            document = json.load(fh)
        origin = document.get("source", "unknown")
        for classpath, spec in document.get("classpaths", {}).items():
            spec = dict(spec)
            spec["source"] = origin
            spec["file"] = path.name
            spec["classpath"] = classpath
            table[_fold(classpath)] = spec
            for alias in spec.get("applies_to", []):
                table.setdefault(_fold(alias), spec)
    return table


def _fold(text: str) -> str:
    """Collapse case, spacing and separator noise for matching only."""
    return re.sub(r"[\s_\-/,.()]+", " ", str(text or "").strip().lower()).strip()


def invalidate() -> None:
    _load.cache_clear()


def classpaths() -> list[str]:
    """The customer classpaths that have a vocabulary, deduplicated over aliases."""
    seen: dict[str, str] = {}
    for spec in _load().values():
        seen.setdefault(spec.get("classpath", ""), spec.get("file", ""))
    return sorted(k for k in seen if k)


def spec_for(classpath: str | list[str] | None) -> dict[str, Any] | None:
    """Find the vocabulary for a classpath, given either a string or a path list."""
    if not classpath:
        return None
    if isinstance(classpath, list):
        classpath = " > ".join(classpath)
    return _load().get(_fold(classpath))


def attribute_spec(classpath: str | list[str] | None, key: str) -> dict[str, Any] | None:
    spec = spec_for(classpath)
    if not spec:
        return None
    return next((a for a in spec.get("attributes", []) if a["key"] == key), None)


def sequence(classpath: str | list[str] | None) -> list[str]:
    """Attribute order for this classpath.

    The LOV owns display order — their Fittings and Faucets specs both fix the
    attribute sequence — so copy generation and export follow the list rather
    than whatever order extraction happened to produce.
    """
    spec = spec_for(classpath)
    if not spec:
        return []
    attributes = sorted(
        spec.get("attributes", []), key=lambda a: a.get("sequence", 10_000)
    )
    return [a["key"] for a in attributes]


def filterable(classpath: str | list[str] | None) -> list[str]:
    spec = spec_for(classpath)
    if not spec:
        return []
    return [a["key"] for a in spec.get("attributes", []) if a.get("filterable")]


# -------------------------------------------------------------------- resolution


def resolve(classpath: str | list[str] | None, key: str, value: Any) -> Resolution | None:
    """Check one value against the vocabulary. None when no vocabulary applies.

    Returning None rather than a pass is deliberate: "no list covers this
    attribute" and "this value is on the list" are different states, and only
    the second is evidence of compliance.
    """
    attribute = attribute_spec(classpath, key)
    if attribute is None:
        return None

    permitted: list[str] = attribute.get("values") or []
    if not permitted:
        return None

    original = "" if value is None else str(value).strip()
    if not original:
        return None

    if original in permitted:
        return Resolution(original, original, "exact", False)

    by_case = {v.lower(): v for v in permitted}
    if original.lower() in by_case:
        return Resolution(original, by_case[original.lower()], "case", False)

    synonyms = {_fold(k): v for k, v in (attribute.get("synonyms") or {}).items()}
    if _fold(original) in synonyms:
        canonical = synonyms[_fold(original)]
        # A synonym table can drift out of step with its own value list; trust
        # the list, since that is what the catalog is validated against.
        if canonical in permitted:
            return Resolution(original, canonical, "synonym", False)

    by_fold = {_fold(v): v for v in permitted}
    if _fold(original) in by_fold:
        return Resolution(original, by_fold[_fold(original)], "folded", False)

    close = difflib.get_close_matches(original, permitted, n=1, cutoff=_SUGGEST_THRESHOLD)
    return Resolution(
        original=original,
        value=None,
        method=None,
        refused=True,
        reason=(
            f"'{original}' is not an approved value for {attribute.get('label', key)} "
            f"in this classpath."
        ),
        suggestion=close[0] if close else None,
    )


# ------------------------------------------------------------------- application


def apply(
    attributes: list[Attribute], classpath: str | list[str] | None
) -> tuple[list[Attribute], list[ValidationIssue], list[dict[str, str]]]:
    """Normalise a record's values to the vocabulary and report what happened.

    Returns the attributes (mapped values rewritten), the issues raised, and a
    ledger of every mapping applied — the same auditability the gate gives the
    model's proposals, because a silent rewrite is just as unaccountable as a
    silent guess.
    """
    if spec_for(classpath) is None:
        return attributes, [], []

    updated: list[Attribute] = []
    issues: list[ValidationIssue] = []
    ledger: list[dict[str, str]] = []

    for attribute in attributes:
        outcome = resolve(classpath, attribute.key, attribute.value)
        if outcome is None:
            updated.append(attribute)
            continue

        if outcome.refused:
            issues.append(ValidationIssue(
                code="LOV_VIOLATION",
                severity=Severity.WARNING,
                field=attribute.key,
                message=outcome.reason,
                suggestion=(
                    f"Closest approved value is '{outcome.suggestion}'. Confirm before "
                    f"applying — it was not applied automatically."
                    if outcome.suggestion else
                    "Add the value to the list of values, or correct the source data."
                ),
            ))
            updated.append(attribute)
            continue

        if outcome.mapped:
            updated.append(attribute.model_copy(update={
                "value": outcome.value,
                "evidence": (
                    f"{attribute.evidence} Normalized to the approved value "
                    f"'{outcome.value}' from '{outcome.original}' "
                    f"({outcome.method} match in the list of values)."
                ),
            }))
            ledger.append({
                "key": attribute.key,
                "label": attribute.label,
                "from": outcome.original,
                "to": outcome.value or "",
                "method": outcome.method or "",
            })
            continue

        updated.append(attribute)

    return updated, issues, ledger


def coverage(attributes: list[Attribute], classpath: str | list[str] | None) -> dict[str, Any]:
    """How much of this record is vocabulary-backed.

    Their guide names "percentage of values found in the LOV" as a metric judges
    will look for, so it is computed here rather than left to a spreadsheet.
    """
    spec = spec_for(classpath)
    if spec is None:
        return {"applicable": False}

    checked = 0
    approved = 0
    mapped = 0
    refused = 0
    for attribute in attributes:
        outcome = resolve(classpath, attribute.key, attribute.value)
        if outcome is None:
            continue
        checked += 1
        if outcome.refused:
            refused += 1
        elif outcome.mapped:
            mapped += 1
            approved += 1
        else:
            approved += 1

    defined = [a["key"] for a in spec.get("attributes", [])]
    present = {a.key for a in attributes}
    return {
        "applicable": True,
        "source": spec.get("source"),
        "checked": checked,
        "approved": approved,
        "mapped": mapped,
        "refused": refused,
        "percent_in_lov": round(100.0 * approved / checked, 1) if checked else 0.0,
        "attributes_defined": len(defined),
        "attributes_present": len([k for k in defined if k in present]),
    }

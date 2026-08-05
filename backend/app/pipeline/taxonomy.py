"""Taxonomy access and category classification.

Classification runs before extraction because the category determines which
attributes are worth looking for, which are mandatory, and which cross-field
checks apply. Getting it wrong cascades, so we always return alternatives and
an explicit rationale rather than a bare label.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from ..config import DATA_DIR


@lru_cache(maxsize=1)
def load_taxonomy() -> dict[str, Any]:
    with open(DATA_DIR / "taxonomy.json", encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def categories() -> list[dict[str, Any]]:
    """Curated categories plus any the engine has learned and a human approved.

    Learned categories are appended, never merged over a curated one, so an
    approved proposal can extend the taxonomy but can never silently redefine
    a hand-verified category.
    """
    base = list(load_taxonomy()["categories"])
    known = {c["code"] for c in base}

    # Imported lazily: the learning store imports this module for invalidation.
    from ..taxonomy_learning import store

    for learned in store.learned_categories():
        if learned.get("code") not in known:
            base.append(learned)
    return base


@lru_cache(maxsize=1)
def brand_index() -> dict[str, dict[str, Any]]:
    return load_taxonomy()["brands"]


def invalidate() -> None:
    """Drop cached taxonomy state after a category is approved or revoked."""
    categories.cache_clear()
    get_category.cache_clear()


@lru_cache(maxsize=64)
def get_category(code: str) -> dict[str, Any] | None:
    return next((c for c in categories() if c["code"] == code), None)


def attribute_spec(code: str, key: str) -> dict[str, Any] | None:
    cat = get_category(code)
    return (cat or {}).get("attributes", {}).get(key)


def canonical_brand(raw: str | None) -> tuple[str | None, dict[str, Any] | None]:
    """Map a supplier's brand spelling onto our canonical entry."""
    if not raw:
        return None, None
    probe = re.sub(r"[^a-z0-9 ]", "", raw.strip().lower())
    probe = re.sub(r"\s+", " ", probe)
    index = brand_index()
    if probe in index:
        return index[probe]["canonical"], index[probe]
    # tolerate suffixes like "SKF Group", "ABB Ltd."
    for key, entry in index.items():
        if probe.startswith(key + " ") or probe == key:
            return entry["canonical"], entry
    for key, entry in index.items():
        if key in probe.split():
            return entry["canonical"], entry
    return raw.strip(), None


def _score_category(cat: dict[str, Any], haystack: str, mpn: str | None) -> tuple[float, list[str]]:
    """Keyword and MPN-pattern scoring, with the reasons kept for the UI."""
    score = 0.0
    reasons: list[str] = []

    for kw in cat.get("keywords", []):
        # word-boundary match so "valve" doesn't fire inside "valveless"
        if re.search(rf"\b{re.escape(kw)}\b", haystack):
            weight = 2.5 if " " in kw else 1.5
            score += weight
            reasons.append(f"matched keyword '{kw}'")

    for pattern in cat.get("mpn_patterns", []):
        if mpn and re.match(pattern, mpn.strip(), re.IGNORECASE):
            score += 4.0
            reasons.append(f"part number matches the {cat['path'][-1]} pattern")

    # attribute names appearing verbatim in the input are strong evidence
    for key, spec in cat.get("attributes", {}).items():
        names = [spec["label"].lower(), key.replace("_", " ")]
        names += [a.lower() for a in spec.get("aliases", [])]
        for name in names:
            if len(name) > 3 and re.search(rf"\b{re.escape(name)}\b", haystack):
                score += 0.6
                reasons.append(f"input mentions '{name}'")
                break

    return score, reasons


def classify(
    *,
    name: str | None,
    description: str | None,
    free_text: str | None,
    category_hint: str | None,
    mpn: str | None,
    brand: str | None,
    raw_specs: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, float, list[str], list[dict[str, Any]]]:
    """Return (category, confidence, reasons, alternatives)."""
    parts = [name, description, free_text, category_hint]
    if raw_specs:
        parts += [f"{k} {v}" for k, v in raw_specs.items()]
    haystack = " ".join(p for p in parts if p).lower()
    haystack = re.sub(r"\s+", " ", haystack)

    scored: list[tuple[float, dict[str, Any], list[str]]] = []
    for cat in categories():
        score, reasons = _score_category(cat, haystack, mpn)

        # An explicit hint is authoritative-ish; weight it heavily but never
        # let it be the sole signal, since hints are often stale free text.
        if category_hint:
            hint = category_hint.lower()
            if any(kw in hint for kw in cat.get("keywords", [])):
                score += 3.0
                reasons.append(f"category hint '{category_hint}' points here")

        # A brand that only sells into certain categories narrows the field.
        _, brand_entry = canonical_brand(brand)
        if brand_entry and cat["code"] in brand_entry.get("categories", []):
            score += 1.5
            reasons.append(f"{brand_entry['canonical']} manufactures in this category")

        if score > 0:
            scored.append((score, cat, reasons))

    if not scored:
        return None, 0.0, ["No taxonomy signal found in the supplied text."], []

    scored.sort(key=lambda x: x[0], reverse=True)
    top_score, top_cat, top_reasons = scored[0]
    runner_up = scored[1][0] if len(scored) > 1 else 0.0

    # Confidence reflects both absolute evidence and the margin over the next
    # best candidate — a narrow win should not read as certainty.
    saturation = min(top_score / 9.0, 1.0)
    margin = (top_score - runner_up) / top_score if top_score else 0.0
    confidence = round(min(0.35 + 0.45 * saturation + 0.20 * margin, 0.99), 3)

    alternatives = [
        {
            "code": c["code"],
            "path": c["path"],
            "score": round(s, 2),
            "confidence": round(min(s / max(top_score, 1e-6), 1.0) * confidence, 3),
        }
        for s, c, _ in scored[1:4]
    ]

    # de-duplicate reasons while preserving order
    seen: set[str] = set()
    reasons = [r for r in top_reasons if not (r in seen or seen.add(r))][:6]

    return top_cat, confidence, reasons, alternatives

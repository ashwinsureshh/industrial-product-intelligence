"""Infer a new category schema from products the taxonomy cannot classify.

The engine ships with ten hand-curated categories. A real catalog has hundreds,
so the interesting question is not "how many did you curate" but "what happens
when a product arrives that you never anticipated". This module answers it: the
unclassified products are clustered, and each cluster yields a proposed
category — attributes, types, units, controlled vocabularies, plausible ranges
and required fields — derived from the evidence in the products themselves.

Nothing here is applied automatically. A proposal is a recommendation with its
working shown; a human approves before it becomes a validation rule that every
future product is judged against.

The inference is deliberately deterministic, so the capability demonstrates
with no API key and no cost. The live provider improves the *naming and
judgement* — better labels, sensible enum members, cross-field rules — but the
structure below is recoverable from data alone.
"""

from __future__ import annotations

import hashlib
import re
import time
from collections import Counter, defaultdict
from typing import Any

from ..models import CategoryProposal, ProposedAttribute, RawProduct
from ..pipeline import units as U

# A field seen in only one product of a cluster is more likely a typo or a
# one-off than a real category attribute.
MIN_FIELD_SUPPORT = 0.34
# Above this share of products, a field is treated as required.
REQUIRED_SUPPORT = 0.75
# A field whose values repeat within a small set is a controlled vocabulary.
MAX_ENUM_MEMBERS = 12
ENUM_REPEAT_RATIO = 0.6

# A value that is a measurement and nothing else: an optional sign, a number,
# and at most a short unit. Rejects 'M10x1.25', '1/2 NPT', 'Type 4X'.
_QUANTITY_ONLY = re.compile(
    r"\s*[-+]?\d+(?:[.,]\d+)?\s*(?:°|[A-Za-z]{1,12}(?:/[A-Za-z0-9]{1,6})?|%|\")?\s*"
)

_STOPWORDS = {
    "the", "and", "for", "with", "type", "series", "model", "new", "high",
    "industrial", "duty", "grade", "standard", "product", "item", "unit",
    "mm", "inch", "kw", "hp", "pcs", "set", "kit", "assembly",
}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (text or "").strip().lower()).strip("_")


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z]{3,}", (text or "").lower())
            if w not in _STOPWORDS]


def _signature(product: RawProduct) -> frozenset[str]:
    """Fields present, used to group products that describe the same kind."""
    return frozenset(_slug(k) for k in (product.raw_specs or {}) if _slug(k))


def cluster(products: list[RawProduct]) -> list[list[RawProduct]]:
    """Group unclassified products into candidate categories.

    Two signals are combined: shared spec-field vocabulary (products of a kind
    are described by the same fields) and shared name words. Field overlap is
    weighted higher because a spec table is stronger evidence of kind than
    marketing wording.
    """
    if not products:
        return []

    clusters: list[dict[str, Any]] = []
    for product in products:
        fields = _signature(product)
        name_words = set(_words(f"{product.name or ''} {product.category_hint or ''}"))

        best_index, best_score = None, 0.0
        for index, group in enumerate(clusters):
            field_overlap = (
                len(fields & group["fields"]) / len(fields | group["fields"])
                if (fields or group["fields"]) else 0.0
            )
            name_overlap = (
                len(name_words & group["words"]) / len(name_words | group["words"])
                if (name_words or group["words"]) else 0.0
            )
            score = 0.7 * field_overlap + 0.3 * name_overlap
            if score > best_score:
                best_index, best_score = index, score

        if best_index is not None and best_score >= 0.35:
            group = clusters[best_index]
            group["items"].append(product)
            group["fields"] |= fields
            group["words"] |= name_words
        else:
            clusters.append({"items": [product], "fields": set(fields),
                             "words": set(name_words)})

    return [g["items"] for g in clusters]


def _infer_type(values: list[str]) -> tuple[str, str | None, list[float] | None,
                                            list[str] | None]:
    """Decide what kind of attribute a field is, from its observed values.

    Returns (type, unit, range, enum_values).
    """
    cleaned = [v.strip() for v in values if v and v.strip()]
    if not cleaned:
        return "text", None, None, None

    booleans = {"yes", "no", "true", "false", "y", "n"}
    if all(v.lower() in booleans for v in cleaned):
        return "boolean", None, None, None

    # Numeric only if the value is *essentially* a quantity. A loose parse
    # finds a number inside almost anything — 'M10x1.25' yields 10 — which
    # would type a thread designation as a measurement and then range-check it.
    parsed: list[tuple[float, str | None]] = []
    for value in cleaned:
        if not _QUANTITY_ONLY.fullmatch(value):
            continue
        quantity = U.parse_quantity(value)
        if quantity is not None:
            parsed.append(quantity)

    if len(parsed) >= max(2, int(0.7 * len(cleaned))):
        numbers = [n for n, _ in parsed]
        found_units = [u for _, u in parsed if u]
        unit = Counter(found_units).most_common(1)[0][0] if found_units else None

        # Normalise to the canonical unit so the range is expressed consistently.
        if unit:
            canonical = U.CANONICAL.get(U.dimension_of(unit) or "", unit)
            converted = [U.convert(n, u or unit, canonical) or n for n, u in parsed]
            numbers, unit = converted, canonical

        low, high = min(numbers), max(numbers)
        span = max(high - low, abs(high) * 0.5, 1.0)
        # Widen generously: the sample is small, and a range fitted tightly to
        # five products would reject legitimate future ones.
        lower, upper = low - span, high + span
        # A dimension observed only as positive cannot sensibly be negative;
        # letting the widening cross zero would make the check meaningless.
        if low >= 0:
            lower = max(lower, 0.0)
        return "number", unit, [round(lower, 4), round(upper, 4)], None

    distinct = sorted({v for v in cleaned})
    if (len(distinct) <= MAX_ENUM_MEMBERS
            and len(distinct) <= max(1, int(len(cleaned) * ENUM_REPEAT_RATIO))
            and all(len(v) <= 40 for v in distinct)):
        return "enum", None, None, distinct

    return "text", None, None, None


def _group_for(key: str) -> str:
    """Bucket an attribute so the UI can present it sensibly."""
    probe = key.lower()
    table = [
        ("Dimensions", ("diameter", "length", "width", "height", "size", "bore",
                        "thickness", "depth", "radius", "pitch", "od", "id")),
        ("Performance", ("pressure", "speed", "flow", "power", "rating", "load",
                         "temp", "capacity", "torque", "accuracy", "range")),
        ("Electrical", ("voltage", "current", "amp", "volt", "frequency", "phase",
                        "watt", "signal", "output", "supply")),
        ("Materials", ("material", "coating", "finish", "housing", "body", "seal")),
        ("Standards", ("standard", "certification", "compliance", "class",
                       "grade", "approval", "ip_")),
    ]
    for group, needles in table:
        if any(n in probe for n in needles):
            return group
    return "General"


def _category_name(products: list[RawProduct]) -> tuple[str, list[str]]:
    """Name the category from the words its products have in common.

    Frequency picks *which* words matter; reading order decides how they are
    arranged. Ranking the name by frequency alone produces 'Cylinder
    Pneumatic', because the head noun is not always the commonest word.
    """
    counter: Counter[str] = Counter()
    positions: dict[str, list[int]] = defaultdict(list)

    for product in products:
        words = _words(f"{product.name or ''} {product.category_hint or ''}")
        counter.update(set(words))
        for index, word in enumerate(words):
            positions[word].append(index)

    common = [w for w, n in counter.most_common(6)
              if n >= max(1, len(products) * 0.4)]
    if not common:
        return "Uncategorised Product", []

    def mean_position(word: str) -> float:
        seen = positions.get(word) or [99]
        return sum(seen) / len(seen)

    head = sorted(common[:2], key=mean_position)
    noun = " ".join(w.capitalize() for w in head)
    keywords = common[:6] + [" ".join(head)]
    return noun, sorted(set(keywords))


def _code_for(noun: str) -> str:
    """Stable pseudo-UNSPSC code, marked as learned by its 99 prefix."""
    digest = hashlib.sha256(noun.lower().encode("utf-8")).hexdigest()
    return "99" + str(int(digest[:8], 16))[:6].zfill(6)


def propose_from_cluster(
    products: list[RawProduct], method: str = "deterministic-inference"
) -> CategoryProposal | None:
    """Build one category proposal from a group of similar products."""
    if not products:
        return None

    # Collect every spec field and the values observed for it.
    observed: dict[str, list[str]] = defaultdict(list)
    labels: dict[str, str] = {}
    for product in products:
        for raw_key, value in (product.raw_specs or {}).items():
            key = _slug(raw_key)
            if not key:
                continue
            labels.setdefault(key, raw_key.strip())
            if value not in (None, ""):
                observed[key].append(str(value))

    total = len(products)
    attributes: list[ProposedAttribute] = []

    for key, values in observed.items():
        support = len(values) / total
        if support < MIN_FIELD_SUPPORT:
            continue

        kind, unit, value_range, enum_values = _infer_type(values)
        label = labels.get(key, key.replace("_", " ").title())

        rationale = (
            f"Seen in {len(values)} of {total} sample products. "
            f"Inferred as {kind}"
            + (f" in {unit}" if unit else "")
            + (f" from {len(enum_values)} repeating values" if enum_values else "")
            + "."
        )

        attributes.append(ProposedAttribute(
            key=key,
            label=label,
            type=kind,
            unit=unit,
            group=_group_for(key),
            values=enum_values,
            range=value_range,
            aliases=sorted({label.lower()} - {key.replace("_", " ")}),
            required=support >= REQUIRED_SUPPORT,
            observed_in=len(values),
            sample_values=sorted(set(values))[:5],
            rationale=rationale,
        ))

    if not attributes:
        return None

    attributes.sort(key=lambda a: (-a.observed_in, a.key))
    noun, keywords = _category_name(products)
    code = _code_for(noun)

    required = ["brand", "mpn"] + [a.key for a in attributes if a.required][:4]

    identifier = hashlib.sha256(
        (code + "|" + "|".join(sorted(a.key for a in attributes))).encode()
    ).hexdigest()[:12]

    # Confidence rises with sample size and with how consistently the fields
    # recur — one product with five fields is a guess, eight products sharing
    # the same eight fields is a pattern.
    consistency = (sum(a.observed_in for a in attributes)
                   / (len(attributes) * total)) if attributes else 0.0
    confidence = round(min(0.25 + 0.45 * min(total / 6, 1.0) + 0.30 * consistency, 0.95), 3)

    return CategoryProposal(
        id=identifier,
        code=code,
        path=["Industrial Components", "Learned Categories", noun + "s"],
        noun=noun,
        keywords=keywords,
        attributes=attributes,
        required=required,
        sample_count=total,
        sample_skus=[p.sku or p.mpn or "(unidentified)" for p in products][:8],
        confidence=confidence,
        method=method,
        rationale=(
            f"{total} product(s) shared no existing category but described "
            f"themselves with a consistent set of {len(attributes)} fields. "
            f"Proposing '{noun}' so these and future products of this kind can "
            f"be classified, validated and scored."
        ),
        created_at=time.time(),
    )


def propose(products: list[RawProduct]) -> list[CategoryProposal]:
    """Cluster unclassified products and propose a category for each group."""
    proposals: list[CategoryProposal] = []
    for group in cluster(products):
        proposal = propose_from_cluster(group)
        if proposal is not None:
            proposals.append(proposal)
    proposals.sort(key=lambda p: (-p.sample_count, -p.confidence))
    return proposals

"""Deterministic attribute extraction.

This stage runs before any model call and does the unglamorous work: matching
supplier spec keys onto canonical attribute keys, pulling values out of prose,
and converting units. Whatever it resolves here is high-confidence and needs no
inference, which keeps the model's job small and its output auditable.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from ..models import Attribute, Provenance, RawProduct
from . import units as U

_STOP = {"the", "a", "an", "of", "for", "with", "and", "type", "size"}
_NUM = r"[-+]?\d+(?:\.\d+)?"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _tokens(text: str) -> set[str]:
    return {t for t in _slug(text).split() if t and t not in _STOP}


def _key_similarity(supplier_key: str, canonical_key: str, spec: dict[str, Any]) -> float:
    """How likely is this supplier column the canonical attribute?"""
    probe = _slug(supplier_key)
    if not probe:
        return 0.0

    candidates = [canonical_key.replace("_", " "), _slug(spec.get("label", ""))]
    candidates += [_slug(a) for a in spec.get("aliases", [])]

    best = 0.0
    probe_tokens = _tokens(probe)
    for cand in candidates:
        if not cand:
            continue
        if probe == cand:
            return 1.0
        cand_tokens = _tokens(cand)
        if probe_tokens and cand_tokens:
            overlap = len(probe_tokens & cand_tokens) / len(probe_tokens | cand_tokens)
            best = max(best, 0.55 + 0.4 * overlap if overlap else 0.0)
        best = max(best, SequenceMatcher(None, probe, cand).ratio() * 0.9)
    return best


def _coerce(value: Any, spec: dict[str, Any]) -> tuple[Any, str | None, str]:
    """Return (value, unit, note) coerced to the spec's declared type."""
    kind = spec.get("type", "text")
    target_unit = spec.get("unit")

    if kind == "number":
        parsed = U.parse_quantity(str(value), default_unit=target_unit)
        if parsed is None:
            return value, None, "kept as text; no numeric value found"
        num, unit = parsed
        if unit and target_unit and unit.lower() != target_unit.lower():
            converted = U.convert(num, unit, target_unit)
            if converted is not None:
                return (
                    U.tidy(converted),
                    target_unit,
                    f"converted {U.format_value(num, unit)} to {target_unit}",
                )
            # A value carrying a unit from a different physical dimension is not
            # this attribute's value at all — it is a mis-anchored match. Refuse
            # it rather than silently relabelling horsepower as rpm.
            if U.dimension_of(unit) != U.dimension_of(target_unit):
                return (
                    str(value),
                    None,
                    f"rejected: '{unit}' measures {U.dimension_of(unit)}, "
                    f"not {U.dimension_of(target_unit)}",
                )
        return num, unit or target_unit, ""

    if kind == "boolean":
        text = str(value).strip().lower()
        if text in {"true", "yes", "y", "1", "self-priming", "self priming"}:
            return True, None, ""
        if text in {"false", "no", "n", "0", "none"}:
            return False, None, ""
        return bool(value), None, ""

    if kind == "enum":
        allowed = spec.get("values", [])
        text = str(value).strip()
        for option in allowed:
            if text.lower() == option.lower():
                return option, None, ""
            # Vocabulary values gloss their code in parentheses — "2RS (Rubber
            # Sealed)". Supplier tables carry the bare code, so match on it too
            # rather than reporting a vocabulary violation for a correct value.
            short = option.split("(")[0].strip()
            if short and text.lower() == short.lower():
                return option, None, f"expanded '{text}' to the full '{option}' value"
        # partial match: supplier writes "SS316", spec says "316 Stainless Steel"
        probe = _tokens(text)
        best, best_score = None, 0.0
        for option in allowed:
            opt_tokens = _tokens(option)
            if not opt_tokens:
                continue
            overlap = len(probe & opt_tokens) / len(opt_tokens)
            ratio = SequenceMatcher(None, _slug(text), _slug(option)).ratio()
            score = max(overlap, ratio)
            if score > best_score:
                best, best_score = option, score
        if best and best_score >= 0.5:
            note = "" if best_score > 0.95 else f"mapped '{text}' onto the '{best}' enum value"
            return best, None, note
        return text, None, "value is outside the controlled vocabulary"

    return str(value).strip(), None, ""


def from_raw_specs(
    raw: RawProduct, category: dict[str, Any] | None
) -> tuple[list[Attribute], list[dict[str, Any]]]:
    """Map the supplier's own spec table onto canonical attributes.

    Also returns the keys we could not map, which the UI surfaces rather than
    silently dropping — unmapped supplier data is a taxonomy gap, not noise.
    """
    attributes: list[Attribute] = []
    unmapped: list[dict[str, Any]] = []
    if not raw.raw_specs:
        return attributes, unmapped

    specs = (category or {}).get("attributes", {})
    taken: set[str] = set()

    for supplier_key, supplier_value in raw.raw_specs.items():
        if supplier_value in (None, "", []):
            continue

        best_key, best_score = None, 0.0
        for key, spec in specs.items():
            if key in taken:
                continue
            score = _key_similarity(supplier_key, key, spec)
            if score > best_score:
                best_key, best_score = key, score

        if not best_key or best_score < 0.62:
            unmapped.append({"key": supplier_key, "value": supplier_value})
            continue

        spec = specs[best_key]
        value, unit, note = _coerce(supplier_value, spec)
        norm_value, norm_unit = (None, None)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and unit:
            norm_value, norm_unit = U.normalize(float(value), unit)

        # Naming the originating document is what lets a buyer audit a value
        # back to the page it was read from, rather than trusting the record.
        origin = f" of {raw.source_document}" if raw.source_document else ""
        evidence = f"Supplier field '{supplier_key}'{origin} = '{supplier_value}'"
        if note:
            evidence += f"; {note}"

        # An exact key match deserves near-total confidence; a fuzzy one does not.
        confidence = round(min(0.72 + 0.27 * best_score, 0.99), 3)
        if note.startswith("value is outside"):
            confidence = min(confidence, 0.6)

        taken.add(best_key)
        attributes.append(
            Attribute(
                key=best_key,
                label=spec.get("label", best_key.replace("_", " ").title()),
                value=value,
                unit=unit,
                normalized_value=norm_value,
                normalized_unit=norm_unit,
                provenance=Provenance.SUPPLIED if best_score > 0.95 else Provenance.PARSED,
                confidence=confidence,
                evidence=evidence,
                method="structured-spec-mapping",
                group=spec.get("group", "General"),
            )
        )

    return attributes, unmapped


def _owns_dimension(category: dict[str, Any], spec: dict[str, Any]) -> bool:
    """True when this attribute is the only one in its category using its unit.

    Unit-anchored matching ('5 HP' -> power_rating) is only safe when no sibling
    attribute shares the dimension. A bearing has three attributes in
    millimetres, so a bare '52 mm' is ambiguous and we refuse to guess; a motor
    has exactly one attribute in kW, so '5 HP' is unambiguous.
    """
    unit = spec.get("unit")
    dim = U.dimension_of(unit)
    if not dim:
        return False
    owners = [
        k for k, s in category.get("attributes", {}).items()
        if U.dimension_of(s.get("unit")) == dim
    ]
    return len(owners) == 1


def _build_attribute(
    key: str,
    spec: dict[str, Any],
    value: Any,
    unit: str | None,
    evidence: str,
    confidence: float,
    method: str,
) -> Attribute:
    norm_value, norm_unit = (None, None)
    if isinstance(value, (int, float)) and not isinstance(value, bool) and unit:
        norm_value, norm_unit = U.normalize(float(value), unit)
    return Attribute(
        key=key,
        label=spec.get("label", key.replace("_", " ").title()),
        value=value,
        unit=unit,
        normalized_value=norm_value,
        normalized_unit=norm_unit,
        provenance=Provenance.PARSED,
        confidence=confidence,
        evidence=evidence,
        method=method,
        group=spec.get("group", "General"),
    )


def _match_label_anchored(
    corpus: str, key: str, spec: dict[str, Any]
) -> Attribute | None:
    """'Bore: 25 mm', 'Bore diameter = 25mm', 'Frame 184T'."""
    names = [spec.get("label", ""), key.replace("_", " ")] + spec.get("aliases", [])
    for name in [n for n in names if n and len(n) > 1]:
        # "Bore: 25 mm" — label first. Horizontal whitespace only, so a match
        # can never reach across a line into an unrelated sentence.
        m = re.search(
            rf"\b{re.escape(name)}\b[ \t]*[:=\-]?[ \t]*([^,;\n|]{{1,40}})",
            corpus,
            re.IGNORECASE,
        )
        # "1750 rpm", "5 HP" — value first, which is how datasheets read. Only
        # safe for unit tokens or names long enough not to collide (never 'd').
        if not m and (U.dimension_of(name) or len(name) >= 4):
            m = re.search(
                rf"({_NUM}[ \t]*{re.escape(name)})\b",
                corpus,
                re.IGNORECASE,
            )
        if not m:
            continue
        candidate = m.group(1).strip().rstrip(".")
        if not candidate:
            continue

        value, unit, note = _coerce(candidate, spec)
        if spec.get("type") == "number" and not isinstance(value, (int, float)):
            continue
        # A label-anchored enum capture drags in trailing words, so accept it
        # only when it actually landed on a vocabulary member.
        if spec.get("type") == "enum" and str(value) not in spec.get("values", []):
            continue
        if isinstance(value, str) and not value:
            continue

        evidence = f'Found in product text: "{m.group(0).strip()}"'
        if note:
            evidence += f"; {note}"
        return _build_attribute(
            key, spec, value, unit, evidence,
            0.82 if spec.get("type") == "number" else 0.74,
            "text-pattern-extraction",
        )
    return None


def _match_unit_anchored(
    corpus: str, key: str, spec: dict[str, Any], category: dict[str, Any]
) -> Attribute | None:
    """'5 HP', '460 volts', '1750 RPM' — the number leads, the unit identifies it."""
    if spec.get("type") != "number" or not _owns_dimension(category, spec):
        return None

    dim = U.dimension_of(spec["unit"])
    tokens = [re.escape(t) for t in U.units_for_dimension(dim)]
    m = re.search(
        rf"({_NUM})\s*({'|'.join(tokens)})\b",
        corpus,
        re.IGNORECASE,
    )
    if not m:
        return None

    value, unit, note = _coerce(f"{m.group(1)} {m.group(2)}", spec)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None

    evidence = f'Unit-anchored match in product text: "{m.group(0).strip()}"'
    if note:
        evidence += f"; {note}"
    return _build_attribute(
        key, spec, value, unit, evidence, 0.79, "unit-anchored-extraction"
    )


def _claimed_spans(corpus: str, snippets: list[str]) -> list[tuple[int, int]]:
    """Locate, in the corpus, the text already explained by other attributes."""
    spans: list[tuple[int, int]] = []
    lowered = corpus.lower()
    for snippet in snippets:
        probe = snippet.strip().lower()
        if len(probe) < 2:
            continue
        start = lowered.find(probe)
        while start != -1:
            spans.append((start, start + len(probe)))
            start = lowered.find(probe, start + 1)
    return spans


def _match_vocabulary(
    corpus: str, key: str, spec: dict[str, Any], claimed: list[tuple[int, int]]
) -> tuple[Attribute, str] | None:
    """Find a controlled-vocabulary term stated inline: 'three phase', 'ball valve'.

    Text already claimed by another attribute is off limits. Without that,
    'Hex Bolt' — which names the fastener type — leaks into drive_type and
    asserts 'Hex' at high confidence on evidence that belongs to a different
    field. Falling through to a flagged default is the correct outcome: the
    engine should not claim what it cannot independently support.
    """
    if spec.get("type") != "enum":
        return None

    def blocked(start: int, end: int) -> bool:
        return any(start >= s and end <= e for s, e in claimed)

    best: tuple[int, str, str] | None = None
    for option in spec.get("values", []):
        # "2RS (Rubber Sealed)" should also match a bare "2RS"
        probes = {option, option.split("(")[0].strip()}
        for probe in probes:
            if len(probe) < 2:
                continue
            for m in re.finditer(rf"\b{re.escape(probe)}\b", corpus, re.IGNORECASE):
                if blocked(m.start(), m.end()):
                    continue
                if best is None or len(probe) > best[0]:
                    best = (len(probe), option, m.group(0))
                break

    if best is None:
        return None
    _, option, matched = best
    attribute = _build_attribute(
        key,
        spec,
        option,
        None,
        f'Product text states "{matched}", which maps to the "{option}" vocabulary value.',
        0.8,
        "vocabulary-match",
    )
    return attribute, matched


def from_free_text(
    raw: RawProduct,
    category: dict[str, Any] | None,
    already: set[str],
    resolved: list[Attribute] | None = None,
) -> list[Attribute]:
    """Recover attributes from prose using three complementary strategies.

    They run in descending order of specificity: an explicit label beats a bare
    unit, which beats a vocabulary term appearing somewhere in the sentence.
    """
    if not category:
        return []

    corpus = " \n ".join(p for p in [raw.name, raw.description, raw.free_text] if p)

    # Part numbers encode specs as suffixes — 6205-2RS names its own seal type,
    # W22-...-B3 its mounting. Those codes are only fed to the vocabulary
    # matcher: numeric matching against a part number would be pure noise.
    code_corpus = " ".join(
        p.replace("-", " ") for p in [raw.mpn, raw.sku, corpus] if p
    )
    if not corpus.strip() and not code_corpus.strip():
        return []

    found: list[Attribute] = []
    # Text consumed by a resolved attribute cannot also justify a different one.
    # Seeded with values already settled from the spec table, since those claim
    # their words just as firmly as a prose match does.
    claimed_text: list[str] = [
        str(a.value) for a in (resolved or []) if isinstance(a.value, str)
    ]

    for key, spec in category.get("attributes", {}).items():
        if key in already:
            continue

        attr = _match_label_anchored(corpus, key, spec) or _match_unit_anchored(
            corpus, key, spec, category
        )
        matched: str | None = None

        if attr is None:
            vocabulary = _match_vocabulary(
                code_corpus, key, spec, _claimed_spans(code_corpus, claimed_text)
            )
            if vocabulary is not None:
                attr, matched = vocabulary

        if attr is None:
            continue

        found.append(attr)
        already.add(key)
        claimed_text.append(matched if matched else str(attr.value))

    return found


def identity_from_input(raw: RawProduct) -> dict[str, Any]:
    """Best-effort MPN/SKU recovery when the caller left the fields blank."""
    identity: dict[str, Any] = {}
    corpus = " ".join(p for p in [raw.name, raw.description, raw.free_text] if p)

    if raw.mpn:
        identity["mpn"] = raw.mpn.strip()
    else:
        # Part numbers: alphanumeric, at least one digit, often hyphenated.
        m = re.search(
            r"\b(?:p/?n|part(?:\s*(?:no|number))?|mpn|model)\b\s*[:#=]?\s*([A-Z0-9][A-Z0-9\-/.]{2,24})",
            corpus,
            re.IGNORECASE,
        )
        if m:
            identity["mpn"] = m.group(1).strip(" .")
            identity["_mpn_evidence"] = f"Recovered from text: \"{m.group(0).strip()}\""
        else:
            m = re.search(r"\b(?=[A-Z0-9\-]*\d)[A-Z]{0,4}\d{3,5}[A-Z0-9\-]{0,8}\b", corpus)
            if m:
                identity["mpn"] = m.group(0)
                identity["_mpn_evidence"] = f"Pattern-matched token \"{m.group(0)}\" in the product text"

    if raw.sku:
        identity["sku"] = raw.sku.strip()

    # GTIN/EAN/UPC if it happens to be sitting in the text
    m = re.search(r"\b(?:gtin|ean|upc)\b\s*[:#=]?\s*(\d{8,14})", corpus, re.IGNORECASE)
    if m:
        identity["gtin"] = m.group(1)

    return identity

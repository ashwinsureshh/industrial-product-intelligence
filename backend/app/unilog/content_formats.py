"""The five commerce descriptions, built by formula against character limits.

Their guide is explicit that this is the bulk of the work: the same product is
rewritten five times at five different lengths and casings — the till receipt,
the mobile app, the search result, the product page and the marketing copy —
and "getting these formats right is most of the task".

Two decisions define this module.

**Formulas are data.** A format is a list of tokens with priorities, a length
window and a casing rule, all in `data/unilog/content_formats.json`. Their
content guidelines document replaces that file; it does not replace this code.

**Overlong copy loses tokens, never characters.** The obvious way to hit a
40-character limit is to cut the string at 40. That produces `FRIGIDAIRE
PROFESSIONAL SERIES PDSH4816AF DISHWA` — a truncated MPN and a truncated noun,
which is worse than useless because it is unsearchable and looks deliberate.
Instead the builder drops whole tokens in reverse priority order until the line
fits, and reports what it dropped. Character truncation happens only when the
*required* tokens alone overflow, and that case is reported as a compliance
failure rather than passed off as output.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Iterable

from ..models import Attribute, Provenance
from . import house_style as HS
from .house_style import UNILOG_DIR


@lru_cache(maxsize=1)
def _config() -> dict[str, Any]:
    path = UNILOG_DIR / "content_formats.json"
    if not path.exists():
        return {"source": "missing", "formats": []}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def _abbreviations() -> dict[str, str]:
    path = UNILOG_DIR / "abbreviations.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        return {k.lower(): v for k, v in json.load(fh).get("terms", {}).items()}


def invalidate() -> None:
    _config.cache_clear()
    _abbreviations.cache_clear()
    _terminal.cache_clear()
    _self_describing.cache_clear()
    _prefix_labels.cache_clear()


def source() -> str:
    return _config().get("source", "unknown")


def formats() -> list[dict[str, Any]]:
    return _config().get("formats", [])


# ------------------------------------------------------------------- the record


@dataclass
class ContentContext:
    """Everything a format may draw on, flattened out of the enriched record."""

    brand: str = ""
    manufacturer: str = ""
    mpn: str = ""
    item_type: str = ""
    attributes: list[Attribute] = field(default_factory=list)

    @classmethod
    def from_record(cls, record: Any) -> "ContentContext":
        identity = getattr(record, "identity", {}) or {}
        category = getattr(record, "category", None)
        noun = ""
        if category and getattr(category, "path", None):
            # The shelf is "Built-In Dishwashers"; the product is a "Dishwasher".
            # The taxonomy declares the noun for exactly this reason.
            noun = getattr(category, "noun", "") or _singular(category.path[-1])
        return cls(
            brand=identity.get("brand") or (record.input.brand or ""),
            manufacturer=identity.get("manufacturer") or "",
            mpn=identity.get("mpn") or (record.input.mpn or ""),
            item_type=noun,
            attributes=list(record.attributes),
        )


def _singular(noun: str) -> str:
    """Singularize a category noun or an attribute label's last word.

    The sibilant endings are listed explicitly rather than stripping every
    trailing "es": that rule turns "Hoses" into "Hos" and "Cycles" into "Cycl".
    """
    if noun.endswith("ies"):
        return noun[:-3] + "y"
    if noun.endswith(("sses", "shes", "ches", "xes", "zes")):
        return noun[:-2]
    if noun.endswith("s") and not noun.endswith("ss"):
        return noun[:-1]
    return noun


# -------------------------------------------------------------------- the result


@dataclass
class FieldResult:
    """One rendered field, with the evidence that it is compliant."""

    id: str
    label: str
    text: str
    length: int
    min_length: int | None = None
    max_length: int | None = None
    compliant: bool = True
    dropped: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "text": self.text,
            "length": self.length,
            "min_length": self.min_length,
            "max_length": self.max_length,
            "compliant": self.compliant,
            "dropped": self.dropped,
            "notes": self.notes,
        }


@dataclass
class _Piece:
    """A token that resolved to text, waiting to be fitted."""

    key: str
    label: str
    text: str
    priority: int
    required: bool
    tail: bool
    order: int
    join_with_space: bool = False
    bare: str = ""  # the value without its prefix or label, for repeat detection


# ------------------------------------------------------------------- rendering


def _visible(attributes: Iterable[Attribute], excluded: set[str]) -> list[Attribute]:
    """Copy is written from backed values only.

    A default is a category-typical guess. Printing one into a product title
    launders it into a claim the catalog cannot support, so excluded classes
    never reach the page even though they remain on the record.
    """
    return [a for a in attributes if a.provenance.value not in excluded]


def _display_label(attribute: Attribute) -> str:
    """The label as it appears in copy, not as it appears in the schema.

    Their attribute is called "Number of Wash Cycles" but the prose reads
    "5 Wash Cycles" — the counting prefix belongs in the spec table, not the
    sentence.
    """
    label = (attribute.label or "").strip()
    for prefix in _config().get("label_prefixes_to_drop", []):
        if label.lower().startswith(prefix.lower()):
            label = label[len(prefix):]
            break
    for suffix in _config().get("label_suffixes_to_drop", []):
        if label.lower().endswith(suffix.lower()):
            label = label[: -len(suffix)]
            break
    return label.strip()


def _label_singular(label: str) -> str:
    """'Wash Cycles' -> 'Wash Cycle'. Only the last word is a plural."""
    words = label.split()
    if not words:
        return label
    return " ".join(words[:-1] + [_singular(words[-1])])


def _attribute_text(
    attribute: Attribute, *, compact: bool, abbreviate: bool, with_label: bool,
    label_style: str = "space",
) -> tuple[str | None, str | None, str | None]:
    """Render one attribute, or explain why it cannot be written.

    Returns (text, bare_value, refusal). The bare value is kept alongside the
    labelled text so the assembler can spot a repeat: an item type of "Coupling"
    and a Fitting Type of "Coupling" are the same fact written twice.

    A refusal means the value exists but has no house-style spelling — an
    unapproved unit — and writing it anyway would put a non-compliant unit into
    published copy.
    """
    value = attribute.value
    if value is None or value == "":
        return None, None, None

    if attribute.unit:
        written = HS.format_measure(value, attribute.unit, compact=compact)
        if written is None:
            return None, None, (
                f"{attribute.label}: unit '{attribute.unit}' is not in the approved "
                f"UOM list, so the value was left out of the copy rather than "
                f"written in a non-standard form."
            )
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        written = HS.format_measure(value, None)
    else:
        written = str(value).strip()
        if abbreviate:
            written = _abbreviations().get(written.lower(), written)

    bare = written
    if with_label and not compact and _wants_label(attribute):
        label = _display_label(attribute)
        numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
        if attribute.key.lower() in _prefix_labels():
            # "Additional Information: 240 kW-hr Annual Energy"
            written = f"{label}: {written}"
        elif label_style == "hyphen_singular" and numeric:
            # A count binds to its noun: "5-Wash Cycle". An enum does not —
            # the same row writes "Leg Mounting", not "Leg-Mounting".
            written = f"{written}-{_label_singular(label)}"
        else:
            written = f"{written} {label}"

    return written, bare, None


def _wants_label(attribute: Attribute) -> bool:
    """Whether the label adds anything the value has not already said.

    Two suppressions, both visible in the organizers' own delivery format:

      * The unit already names the quantity — they write `120 V`, not
        `120 V Voltage`.
      * A terminal descriptor names itself — `Stainless Steel`, not
        `Stainless Steel Material`.

    Everything else keeps its label, because a bare `5` or a bare `Leg` in a
    comma-separated list is unreadable.
    """
    label = (attribute.label or "").strip().lower()
    if not label:
        return False
    if attribute.key.lower() in _terminal() or label in _terminal():
        return False
    unit = HS.approved_unit(attribute.unit) if attribute.unit else None
    if unit and unit.abbreviation in _self_describing():
        return False
    if unit and unit.measurement.strip().lower() == label:
        return False
    return True


@lru_cache(maxsize=1)
def _terminal() -> frozenset[str]:
    return frozenset(
        str(t).strip().lower() for t in _config().get("terminal_attributes", [])
    )


@lru_cache(maxsize=1)
def _self_describing() -> frozenset[str]:
    """Units that name their own quantity, so a label would only repeat them."""
    return frozenset(str(u) for u in _config().get("self_describing_units", []))


@lru_cache(maxsize=1)
def _prefix_labels() -> frozenset[str]:
    return frozenset(
        str(k).strip().lower() for k in _config().get("prefix_label_attributes", [])
    )


def _render_tokens(
    spec: dict[str, Any], ctx: ContentContext
) -> tuple[list[_Piece], list[str]]:
    compact = bool(spec.get("compact_units"))
    abbreviate = bool(spec.get("abbreviate"))
    label_style = spec.get("label_style", "space")
    excluded = set(spec.get("exclude_provenance", []))
    skipped = {str(k).lower() for k in spec.get("exclude_keys", [])}
    attributes = [
        a for a in _visible(ctx.attributes, excluded) if a.key.lower() not in skipped
    ]
    by_key = {a.key: a for a in attributes}

    named = {
        t["source"][5:]
        for t in spec.get("tokens", [])
        if t["source"].startswith("attr:") and t["source"] != "attr:*"
    }

    pieces: list[_Piece] = []
    refusals: list[str] = []
    order = 0

    for token in spec.get("tokens", []):
        source = token["source"]
        priority = int(token.get("priority", 5))
        required = bool(token.get("required"))
        tail = bool(token.get("tail"))
        join_space = token.get("join") == "space"

        def add(key: str, label: str, text: str | None, bare: str | None = None) -> None:
            nonlocal order
            if not text:
                return
            # A multi-value list is a column of its own, not a clause inside a
            # sentence: their row 3 keeps its two-item feature list out of both
            # the short and the long description while still filling "With".
            if token.get("single_value_only") and "," in text:
                return
            if prefix := token.get("prefix"):
                text = f"{prefix} {text}"
            pieces.append(_Piece(key, label, text, priority, required, tail, order,
                                 join_space, bare or text))
            order += 1

        if source == "attr:*":
            limit = int(token.get("limit", 0)) or None
            spillover = [a for a in attributes if a.key not in named]
            for attribute in spillover[:limit]:
                text, bare, refusal = _attribute_text(
                    attribute,
                    compact=compact,
                    abbreviate=abbreviate,
                    with_label=bool(token.get("with_label")),
                    label_style=label_style,
                )
                if refusal:
                    refusals.append(refusal)
                add(attribute.key, attribute.label, text, bare)
            continue

        if source.startswith("attr:"):
            attribute = by_key.get(source[5:])
            if attribute is None:
                continue
            text, bare, refusal = _attribute_text(
                attribute,
                compact=compact,
                abbreviate=abbreviate,
                with_label=bool(token.get("with_label")),
                label_style=label_style,
            )
            if refusal:
                refusals.append(refusal)
            add(attribute.key, attribute.label, text, bare)
            continue

        value = getattr(ctx, source, "") or ""
        if value and token.get("strip_symbols"):
            value = re.sub(r"[®™©]", "", value).strip()
        if value and abbreviate:
            value = _abbreviations().get(str(value).lower(), value)
        add(source, source.replace("_", " ").title(), str(value).strip())

    return pieces, refusals


# Tokens that name the product itself rather than one of its specifications.
_IDENTITY = frozenset({"brand", "manufacturer", "mpn", "item_type"})


def _drop_repeats(pieces: list[_Piece]) -> list[_Piece]:
    """Say each identifying fact once.

    Their own rows show both halves of this rule. Row 2 writes "Rheem
    Manufacturing FRIGIDAIRE" because the two names are unrelated; row 3 writes
    only "Whirlpool" because the brand is contained in "Whirlpool Corporation"
    and printing both would stutter. Equally, a coupling whose item type is
    "Coupling" and whose Fitting Type is also "Coupling" should say it once.

    But two *specifications* may legitimately share a value, and their rows rely
    on it: a dishwasher with Material "Stainless Steel" and Color "Stainless
    Steel" is written out twice in both the short and long descriptions. So
    de-duplication applies to identity tokens only, and an attribute is dropped
    solely when it merely repeats one of them.
    """
    seen: list[tuple[str, bool]] = []
    kept: list[_Piece] = []

    # Priority decides which of two clashing names survives, not declaration
    # order: the brand outranks the manufacturer, so "Whirlpool Corporation"
    # yields to "Whirlpool" rather than the other way round.
    for piece in sorted(pieces, key=lambda p: (not p.required, p.priority, p.order)):
        signature = " ".join((piece.bare or piece.text).lower().split())
        is_identity = piece.key in _IDENTITY

        duplicate = False
        for earlier, earlier_identity in seen:
            # Two specifications may share a value and both still belong: their
            # rows write "Stainless Steel, Stainless Steel" for Material and
            # Color. Only a clash involving an identity name is a real repeat.
            if signature == earlier and (is_identity or earlier_identity):
                duplicate = True
                break
            # Containment only collapses one identity name into another; a spec
            # value that happens to be a substring of a name is still a spec.
            if is_identity and earlier_identity and (
                signature in earlier or earlier in signature
            ):
                duplicate = True
                break
        if duplicate:
            continue

        seen.append((signature, is_identity))
        kept.append(piece)

    return sorted(kept, key=lambda p: p.order)


def _assemble(pieces: list[_Piece], spec: dict[str, Any]) -> str:
    separator = spec.get("separator", " ")
    tail_separator = spec.get("tail_separator", separator)

    head = [p for p in sorted(pieces, key=lambda p: p.order) if not p.tail]
    tail = [p for p in sorted(pieces, key=lambda p: p.order) if p.tail]

    text = ""
    for index, piece in enumerate(head):
        if index == 0:
            text = piece.text
        else:
            text += (" " if piece.join_with_space else separator) + piece.text
    if tail:
        joined = tail_separator.join(p.text for p in tail)
        text = f"{text}{tail_separator}{joined}" if text else joined
    return " ".join(text.split())


def _cased(text: str, case: str) -> str:
    if case == "upper":
        return HS.upper_case(text)
    if case == "title":
        return HS.title_case(text)
    return text


def build(spec: dict[str, Any], ctx: ContentContext) -> FieldResult:
    """Render one format, fitting it to its length window by dropping tokens."""
    pieces, refusals = _render_tokens(spec, ctx)
    pieces = _drop_repeats(pieces)
    case = spec.get("case", "preserve")
    maximum = spec.get("max_length")
    minimum = spec.get("min_length")
    notes = list(refusals)

    kept = [p for p in pieces if p.required]
    optional = sorted(
        (p for p in pieces if not p.required), key=lambda p: (p.priority, p.order)
    )
    dropped: list[str] = []

    for piece in optional:
        # A length window is a target, not an appetite. Once the minimum is met
        # the line stops growing, which is why their padded mobile description
        # carries one extra attribute rather than every attribute that fits.
        if minimum is not None and len(_cased(_assemble(kept, spec), case)) >= minimum:
            break
        candidate = kept + [piece]
        if maximum is not None and len(_cased(_assemble(candidate, spec), case)) > maximum:
            dropped.append(piece.label)
            continue
        kept = candidate

    text = _cased(_assemble(kept, spec), case)
    compliant = True

    if maximum is not None and len(text) > maximum:
        # Only reachable when the required tokens alone overflow. Cutting is the
        # last resort and is reported, never silently absorbed.
        text = _clip(text, maximum)
        compliant = False
        notes.append(
            f"Required tokens alone exceed the {maximum}-character limit; the field "
            f"was clipped and needs a human-authored short form."
        )

    if minimum is not None and len(text) < minimum:
        compliant = False
        notes.append(
            f"Field is {len(text)} characters, below the {minimum}-character minimum. "
            f"No further backed values were available to extend it."
        )

    if dropped:
        notes.append(
            f"Dropped to fit the {maximum}-character limit: {', '.join(dropped)}."
        )

    return FieldResult(
        id=spec["id"],
        label=spec.get("label", spec["id"]),
        text=text,
        length=len(text),
        min_length=minimum,
        max_length=maximum,
        compliant=compliant and not refusals,
        dropped=dropped,
        notes=notes,
    )


def _clip(text: str, limit: int) -> str:
    """Cut on a word boundary. A half-word is never a useful abbreviation."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    if " " in cut and not text[limit:limit + 1].isspace():
        cut = cut[: cut.rfind(" ")]
    return cut.strip()


def build_all(ctx: ContentContext) -> list[FieldResult]:
    return [build(spec, ctx) for spec in formats()]

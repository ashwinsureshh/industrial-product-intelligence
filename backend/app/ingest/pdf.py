"""Turn a supplier datasheet PDF into a RawProduct.

This module deliberately does *not* enrich, validate or score anything — it
only recovers structure. Whatever it produces flows into the same pipeline a
CSV row would, so a value read off page 2 of a datasheet earns its provenance,
confidence and cross-field checks exactly like any other input.

Datasheets come in three broad shapes and all three are handled:

  1. Ruled tables  — real table borders. pdfplumber's `lines` strategy.
  2. Ruleless tables — columns held apart by whitespace only. The `text`
     strategy, which infers columns from gutters between words.
  3. Dot-leader lists — "Bore Diameter ......... 25 mm" running down the page,
     which are not tables at all and need line-level parsing.

Anything not recognised as a spec is preserved as free text rather than
discarded, because an unparsed line is a parser gap, not noise.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Any

from ..models import RawProduct
from ..pipeline.taxonomy import brand_index

# A spec key is a label, not a sentence. These bounds reject prose that happens
# to contain a colon ("Note: consult the engineering team before...").
MAX_KEY_CHARS = 48
MAX_VALUE_CHARS = 120

# The label charset contains '%', so these are built by concatenation rather
# than %-formatting, which would try to interpret it as a conversion.
_KEY_CHARS = r"[A-Za-z][A-Za-z0-9 ()/µ°%,.+-]"

# "Bore Diameter .......... 25 mm"
_DOT_LEADER = re.compile(
    r"^\s*(?P<key>" + _KEY_CHARS + r"{1," + str(MAX_KEY_CHARS) + r"}?)"
    r"\s*[:.]{2,}\s*(?P<value>.{1," + str(MAX_VALUE_CHARS) + r"})\s*$"
)

# "Bore Diameter:  25 mm"
_COLON_PAIR = re.compile(
    r"^\s*(?P<key>" + _KEY_CHARS + r"{1," + str(MAX_KEY_CHARS) + r"}?)"
    r"\s*:\s+(?P<value>\S.{0," + str(MAX_VALUE_CHARS) + r"})\s*$"
)

# Header rows that mean "the next columns are key and value".
_KEY_HEADERS = {"parameter", "property", "characteristic", "specification",
                "spec", "attribute", "feature", "description", "item"}
_VALUE_HEADERS = {"value", "specification", "spec", "data", "rating", "detail"}

_MPN_LABEL = re.compile(
    r"\b(?:part\s*(?:no\.?|number)|p/?n|mpn|model(?:\s*no\.?)?|order(?:ing)?\s*code|"
    r"cat(?:alog(?:ue)?)?\s*(?:no\.?|number))\b\s*[:#=]?\s*([A-Z0-9][A-Z0-9\-/.]{2,24})",
    re.IGNORECASE,
)


@dataclass
class IngestReport:
    """What the parser saw, so the UI can show its working."""

    source: str
    pages: int = 0
    tables_found: int = 0
    spec_pairs: int = 0
    text_chars: int = 0
    strategies_used: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "pages": self.pages,
            "tables_found": self.tables_found,
            "spec_pairs": self.spec_pairs,
            "text_chars": self.text_chars,
            "strategies_used": self.strategies_used,
            "notes": self.notes,
        }


def _clean(cell: Any) -> str:
    if cell is None:
        return ""
    # PDF text carries soft hyphens, non-breaking spaces and stray newlines.
    text = str(cell).replace("\xad", "").replace("\xa0", " ")
    return " ".join(text.split()).strip()


def _looks_like_spec(key: str, value: str) -> bool:
    """Filter out prose that structurally resembles a key/value pair.

    The whitespace table strategy will happily slice a heading down the middle
    and hand back `D` -> `eep Groove Ball`, so a permissive filter admits
    garbage into the spec table. These rules reject split words while keeping
    genuine short labels like `ID`, `OD` and `Cv`.
    """
    if not key or not value:
        return False
    if len(key) < 2 or len(key) > MAX_KEY_CHARS or len(value) > MAX_VALUE_CHARS:
        return False
    if key.endswith((".", "?", "!")):
        return False
    # A label is a few words, not a clause.
    if len(key.split()) > 6:
        return False
    # A real label carries letters; a bare number means misaligned columns.
    if len(re.findall(r"[A-Za-z]", key)) < 2:
        return False
    # A short key paired with a lowercase-leading value is almost always a word
    # that got cut in half — 'ID: 25 mm' survives, 'D: eep Groove' does not.
    if len(key) <= 3 and value[:1].islower():
        return False
    # Leftover dot leaders mean the row was split through the dots, not at the
    # value: 'Bore Diameter' -> '...........' carries no information.
    if len(re.findall(r"[.…]", value)) >= 4:
        return False
    return True


def _pairs_from_table(table: list[list[Any]]) -> list[tuple[str, str]]:
    """Read key/value pairs out of one extracted table.

    Handles the two-column case directly, and wider tables by locating the
    key and value columns from a header row.
    """
    rows = [[_clean(c) for c in row] for row in table if row]
    rows = [r for r in rows if any(r)]
    if not rows:
        return []

    key_col, value_col = 0, 1
    header = [c.lower() for c in rows[0]]

    if len(rows[0]) > 2:
        found_key = next((i for i, h in enumerate(header) if h in _KEY_HEADERS), None)
        found_value = next(
            (i for i, h in enumerate(header)
             if h in _VALUE_HEADERS and i != found_key),
            None,
        )
        if found_key is None or found_value is None:
            # No usable header: fall back to the first two populated columns.
            populated = [i for i in range(len(rows[0]))
                         if any(len(r) > i and r[i] for r in rows)]
            if len(populated) < 2:
                return []
            key_col, value_col = populated[0], populated[1]
        else:
            key_col, value_col = found_key, found_value
            rows = rows[1:]  # drop the header itself
    elif header and (header[0] in _KEY_HEADERS or
                     (len(header) > 1 and header[1] in _VALUE_HEADERS)):
        rows = rows[1:]

    pairs: list[tuple[str, str]] = []
    for row in rows:
        if len(row) <= max(key_col, value_col):
            continue
        key, value = row[key_col], row[value_col]
        if _looks_like_spec(key, value):
            pairs.append((key, value))
    return pairs


def _pairs_from_lines(text: str) -> list[tuple[str, str]]:
    """Recover dot-leader and 'Label: value' specs that are not in a table."""
    pairs: list[tuple[str, str]] = []
    for line in (text or "").splitlines():
        for pattern in (_DOT_LEADER, _COLON_PAIR):
            m = pattern.match(line)
            if not m:
                continue
            key, value = _clean(m.group("key")), _clean(m.group("value"))
            if _looks_like_spec(key, value):
                pairs.append((key, value))
            break
    return pairs


def _detect_brand(text: str) -> str | None:
    """Match a known manufacturer anywhere in the document."""
    lowered = text.lower()
    best: tuple[int, str] | None = None
    for probe, entry in brand_index().items():
        if re.search(rf"\b{re.escape(probe)}\b", lowered):
            if best is None or len(probe) > best[0]:
                best = (len(probe), entry["canonical"])
    return best[1] if best else None


def _detect_mpn(text: str) -> str | None:
    m = _MPN_LABEL.search(text or "")
    return m.group(1).strip(" .") if m else None


def _detect_name(text: str) -> str | None:
    """The product name is normally the first substantial heading line."""
    for line in (text or "").splitlines():
        line = _clean(line)
        if not (8 <= len(line) <= 90):
            continue
        # Skip boilerplate headers and pure identifiers.
        if re.fullmatch(r"[A-Z0-9\-/. ]+", line) and not re.search(r"[a-z]", line):
            continue
        if any(word in line.lower() for word in
               ("datasheet", "data sheet", "technical data", "specification sheet",
                "product data", "www.", "http", "page ")):
            continue
        if len(line.split()) < 2:
            continue
        return line
    return None


def from_pdf(data: bytes, filename: str = "datasheet.pdf") -> tuple[RawProduct, IngestReport]:
    """Parse a datasheet into a RawProduct plus a report of what was found."""
    import pdfplumber

    report = IngestReport(source=filename)
    specs: dict[str, str] = {}
    page_texts: list[str] = []

    try:
        pdf = pdfplumber.open(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001 - surface any parse failure to the caller
        report.notes.append(f"Could not open the PDF: {exc}")
        return RawProduct(source_document=filename), report

    with pdf:
        report.pages = len(pdf.pages)
        for number, page in enumerate(pdf.pages, start=1):
            try:
                text = page.extract_text(layout=True) or ""
            except Exception:  # noqa: BLE001 - a bad page must not kill the document
                text = ""
                report.notes.append(f"Page {number}: text extraction failed.")
            page_texts.append(text)

            # Strategies are tried strongest-evidence first, and the first one
            # that works wins the page. This ordering matters: the whitespace
            # strategy will slice a page that has no table at all, inventing
            # pairs like 'Single Row D' -> 'eep Groove Ball' from a heading. A
            # page is only handed to it once the unambiguous readers decline.
            def absorb(pairs: list[tuple[str, str]], label: str) -> int:
                added = 0
                for key, value in pairs:
                    if key not in specs:
                        specs[key] = value
                        added += 1
                if added and label not in report.strategies_used:
                    report.strategies_used.append(label)
                return added

            def read_tables(settings: dict[str, Any]) -> list[tuple[str, str]]:
                try:
                    tables = page.extract_tables(settings) or []
                except Exception:  # noqa: BLE001
                    return []
                collected: list[tuple[str, str]] = []
                for table in tables:
                    pairs = _pairs_from_table(table)
                    if pairs:
                        report.tables_found += 1
                        collected.extend(pairs)
                return collected

            # 1. Ruled tables — real borders, unambiguous.
            found_here = absorb(read_tables({}), "table:lines")

            # 2. Dot-leader and colon lines — explicit syntax, also unambiguous.
            if not found_here:
                line_pairs = _pairs_from_lines(text)
                if len(line_pairs) >= 3:
                    found_here = absorb(line_pairs, "text:line-pairs")

            # 3. Whitespace columns — inferred, and wrong on non-tabular pages.
            if not found_here:
                found_here = absorb(
                    read_tables({"vertical_strategy": "text",
                                 "horizontal_strategy": "text",
                                 "text_x_tolerance": 2}),
                    "table:text",
                )

            # Finally, pick up any stray labelled lines the winner missed.
            absorb(_pairs_from_lines(text), "text:line-pairs")

    corpus = "\n".join(page_texts)
    report.text_chars = len(corpus)
    report.spec_pairs = len(specs)

    if not specs and not corpus.strip():
        report.notes.append(
            "No text layer found. This is likely a scanned PDF; OCR would be "
            "required to read it."
        )
    elif not specs:
        report.notes.append(
            "No spec table detected — the full text was passed through for "
            "pattern extraction instead."
        )

    product = RawProduct(
        mpn=_detect_mpn(corpus),
        brand=_detect_brand(corpus),
        name=_detect_name(corpus),
        raw_specs=dict(specs),
        free_text=corpus.strip() or None,
        source_document=filename,
    )
    return product, report

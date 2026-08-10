"""House style: how a value is allowed to be *written*.

Two rules from the content standard drive this module, and both are the kind of
thing that silently fails an accuracy score while looking perfectly fine to a
human reader:

  * A unit may only appear in its approved abbreviation, with a space between
    the number and the unit — `24 in`, never `24in` or `24 inches`.
  * Manufacturers publish decimals and trade buyers search fractions, so an
    inch measurement is written `50-1/4 in`, not `50.25 in`.

The fraction rule is where the project's guiding principle shows up in
formatting. `to_fraction` converts only values that land *exactly* on a 64th and
returns None otherwise, because 0.3 in is not 19/64 in — it is 0.296875 in, and
rounding it to make the house style happy would put a wrong dimension in front
of a buyer. A refused conversion keeps the decimal; it does not invent a
fraction.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from math import gcd
from typing import Any

from ..config import DATA_DIR

UNILOG_DIR = DATA_DIR / "unilog"

# Their conversion table runs 1/64 to 63/64, so 64ths is the full permitted
# resolution — not an arbitrary precision choice on our part.
MAX_DENOMINATOR = 64

# Floats carry conversion dust (25.4 / 25.4 is not always exactly 1.0), so
# "exactly a 64th" needs a tolerance. This one is far tighter than any real
# dimension tolerance and far looser than float noise.
_EXACT = 1e-9


@dataclass(frozen=True)
class Unit:
    """One approved unit of measure."""

    measurement: str
    abbreviation: str

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return self.abbreviation


@lru_cache(maxsize=1)
def _standards() -> dict[str, Any]:
    path = UNILOG_DIR / "uom_standards.json"
    if not path.exists():
        return {"source": "missing", "units": [], "rules": {}}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def _lookup() -> dict[str, Unit]:
    """Every accepted spelling mapped to its approved abbreviation.

    The approved form is registered as an accepted spelling of itself so that
    already-compliant input round-trips instead of being reported as unknown.
    """
    table: dict[str, Unit] = {}
    for row in _standards().get("units", []):
        unit = Unit(measurement=row["measurement"], abbreviation=row["abbreviation"])
        for spelling in [row["abbreviation"], *row.get("accepts", [])]:
            table.setdefault(_fold(spelling), unit)
    return table


def _fold(text: str) -> str:
    return " ".join(str(text).strip().lower().split())


def source() -> str:
    """Where the unit table came from: 'unilog' once their sheet is loaded.

    Exposed so the UI and export can say which standard was actually applied.
    A provisional table producing confident-looking compliance claims is
    exactly the failure mode this project exists to avoid.
    """
    return _standards().get("source", "unknown")


def invalidate() -> None:
    _standards.cache_clear()
    _lookup.cache_clear()


def approved_unit(unit: str | None) -> Unit | None:
    """Resolve any supplier spelling to the approved unit, or None if unknown."""
    if unit is None:
        return None
    return _lookup().get(_fold(unit))


def known_units() -> list[Unit]:
    seen: dict[str, Unit] = {}
    for unit in _lookup().values():
        seen.setdefault(unit.abbreviation, unit)
    return list(seen.values())


# ------------------------------------------------------------------- fractions


def to_fraction(value: float, denominator: int = MAX_DENOMINATOR) -> str | None:
    """Render a decimal as a trade fraction, or None when it is not exact.

    `0.5 -> '1/2'`, `50.25 -> '50-1/4'`, `3.0 -> '3'`, `0.3 -> None`.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    sign = "-" if value < 0 else ""
    value = abs(value)

    scaled = value * denominator
    nearest = round(scaled)
    if abs(scaled - nearest) > _EXACT:
        return None

    whole, remainder = divmod(int(nearest), denominator)
    if remainder == 0:
        return f"{sign}{whole}"

    divisor = gcd(remainder, denominator)
    fraction = f"{remainder // divisor}/{denominator // divisor}"
    # A whole part joins with a hyphen, matching '50-1/4 in' in their own
    # delivery format. A bare fraction has no leading zero.
    return f"{sign}{whole}-{fraction}" if whole else f"{sign}{fraction}"


_FRACTION_TEXT = re.compile(
    r"^\s*(?:(?P<whole>\d+)\s*[-\s]\s*)?(?P<num>\d+)\s*/\s*(?P<den>\d+)\s*$"
)


def from_fraction(text: str) -> float | None:
    """Read '50-1/4' or '1/2' back into a decimal. None if it is not a fraction."""
    match = _FRACTION_TEXT.match(text or "")
    if not match:
        return None
    denominator = int(match.group("den"))
    if denominator == 0:
        return None
    value = int(match.group("num")) / denominator
    if match.group("whole"):
        value += int(match.group("whole"))
    return value


# ------------------------------------------------------------------ measurement


def _trim(value: float) -> str:
    """Drop trailing zeros without turning 24.0 into '24.0' or 2e-05 into junk."""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def format_measure(
    value: float | int | str,
    unit: str | None = None,
    *,
    compact: bool = False,
    fractional: bool | None = None,
) -> str | None:
    """Write a measurement in house style, or None if the unit is not approved.

    `fractional` defaults to on for inch dimensions, since that is where the
    trade convention applies; pass it explicitly to force either behaviour.
    `compact` drops the separating space for the 40-character invoice line,
    which is the one place the source data shows units run onto the number
    (`50-1/4IN`).
    """
    resolved = approved_unit(unit) if unit else None
    if unit and resolved is None:
        return None

    if isinstance(value, str):
        as_fraction = from_fraction(value)
        number = as_fraction if as_fraction is not None else _as_number(value)
        if number is None:
            # Not a quantity at all (an enum, a code). Pass the text through
            # untouched rather than mangling it into a measurement.
            return value.strip() if not resolved else f"{value.strip()} {resolved.abbreviation}"
    else:
        number = float(value)

    if fractional is None:
        fractional = bool(resolved and resolved.abbreviation == "in")

    shown = (to_fraction(number) if fractional else None) or _trim(number)

    if not resolved:
        return shown
    if compact:
        return f"{shown}{resolved.abbreviation.upper()}"
    return f"{shown} {resolved.abbreviation}"


def _as_number(text: str) -> float | None:
    try:
        return float(str(text).strip().replace(",", ""))
    except (TypeError, ValueError):
        return None


# ----------------------------------------------------------------------- casing

# Words the trade writes in full caps regardless of position. Left as a small
# explicit set: a general "all short words are acronyms" heuristic would
# capitalise legitimate words like 'and'.
_ALWAYS_UPPER = {"mpn", "sku", "npt", "pvc", "cpvc", "ptfe", "abs", "ss", "sst",
                 "led", "ul", "csa", "nsf", "iso", "ansi", "asme", "awg", "hp",
                 "gpm", "psi", "rpm", "id", "od", "nps", "bspp", "bspt"}


def title_case(text: str) -> str:
    """Title Case that leaves acronyms, units and part numbers alone.

    Naive `str.title()` produces 'Frigidaire® Pdsh4816Af Dishwasher' — it
    destroys both the MPN and every acronym, and an MPN written wrong is a
    product a buyer cannot find.
    """
    words = []
    for word in (text or "").split():
        # Brackets are stripped alongside punctuation, or '(Rubber' reads as
        # neither title case nor mixed case and gets flattened to '(rubber'.
        stripped = word.strip(".,;:()[]")
        folded = stripped.lower()
        if folded in _ALWAYS_UPPER:
            words.append(word.replace(stripped, stripped.upper()))
        elif approved_unit(stripped):
            words.append(word.replace(stripped, approved_unit(stripped).abbreviation))
        elif (
            any(c.isdigit() for c in stripped)
            or _is_mixed_case(stripped)
            or stripped.istitle()
        ):
            # MPNs, sizes, deliberately-cased brand marks, and anything already
            # correctly capitalised: never rewrite. Only lower-case input needs
            # casing applied, and re-casing what is already right can only break it.
            words.append(word)
        else:
            words.append(word[:1].upper() + word[1:].lower())
    return " ".join(words)


def _is_mixed_case(word: str) -> bool:
    """True for CleanBoost, FRIGIDAIRE, pH — anything the author cased on purpose."""
    letters = [c for c in word if c.isalpha()]
    if len(letters) < 2:
        return False
    return not (word.islower() or word.istitle())


def upper_case(text: str) -> str:
    """CAPS for the invoice line. Symbols are dropped, not uppercased."""
    return re.sub(r"[®™©]", "", (text or "")).upper()

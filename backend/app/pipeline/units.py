"""Unit parsing and normalization.

Supplier data mixes inches with millimetres, HP with kW, GPM with L/min, and
frequently omits units entirely. Normalizing to one canonical unit per
dimension is what makes cross-supplier comparison and validation possible.
"""

from __future__ import annotations

import re

# canonical unit per physical dimension
CANONICAL = {
    "length": "mm",
    "pressure": "bar",
    "power": "kW",
    "flow": "L/min",
    "temperature": "C",
    "force": "kN",
    "current": "A",
    "voltage": "V",
    "speed": "rpm",
    "frequency": "Hz",
    "angle": "deg",
    "time": "ms",
    "mass": "kg",
}

# factor converts *to* the canonical unit; offset applied after scaling
_UNITS: dict[str, tuple[str, float, float]] = {
    # length -> mm
    "mm": ("length", 1.0, 0.0),
    "millimeter": ("length", 1.0, 0.0),
    "millimetre": ("length", 1.0, 0.0),
    "cm": ("length", 10.0, 0.0),
    "m": ("length", 1000.0, 0.0),
    "meter": ("length", 1000.0, 0.0),
    "in": ("length", 25.4, 0.0),
    "inch": ("length", 25.4, 0.0),
    "inches": ("length", 25.4, 0.0),
    '"': ("length", 25.4, 0.0),
    "ft": ("length", 304.8, 0.0),
    "foot": ("length", 304.8, 0.0),
    "feet": ("length", 304.8, 0.0),
    # pressure -> bar
    "bar": ("pressure", 1.0, 0.0),
    "mbar": ("pressure", 0.001, 0.0),
    "psi": ("pressure", 0.0689476, 0.0),
    "kpa": ("pressure", 0.01, 0.0),
    "mpa": ("pressure", 10.0, 0.0),
    "pa": ("pressure", 1e-5, 0.0),
    "atm": ("pressure", 1.01325, 0.0),
    # power -> kW
    "kw": ("power", 1.0, 0.0),
    "w": ("power", 0.001, 0.0),
    "watt": ("power", 0.001, 0.0),
    "watts": ("power", 0.001, 0.0),
    "mw": ("power", 1000.0, 0.0),
    "hp": ("power", 0.7457, 0.0),
    "horsepower": ("power", 0.7457, 0.0),
    # flow -> L/min
    "l/min": ("flow", 1.0, 0.0),
    "lpm": ("flow", 1.0, 0.0),
    "l/s": ("flow", 60.0, 0.0),
    "l/h": ("flow", 1 / 60, 0.0),
    "m3/h": ("flow", 16.6667, 0.0),
    "m³/h": ("flow", 16.6667, 0.0),
    "gpm": ("flow", 3.78541, 0.0),
    "cfm": ("flow", 28.3168, 0.0),
    # temperature -> C
    "c": ("temperature", 1.0, 0.0),
    "°c": ("temperature", 1.0, 0.0),
    "degc": ("temperature", 1.0, 0.0),
    "celsius": ("temperature", 1.0, 0.0),
    "f": ("temperature", 5 / 9, -32.0),
    "°f": ("temperature", 5 / 9, -32.0),
    "degf": ("temperature", 5 / 9, -32.0),
    "fahrenheit": ("temperature", 5 / 9, -32.0),
    "k": ("temperature", 1.0, -273.15),
    # force -> kN
    "kn": ("force", 1.0, 0.0),
    "n": ("force", 0.001, 0.0),
    "lbf": ("force", 0.00444822, 0.0),
    "kgf": ("force", 0.00980665, 0.0),
    # electrical
    "a": ("current", 1.0, 0.0),
    "amp": ("current", 1.0, 0.0),
    "amps": ("current", 1.0, 0.0),
    "ma": ("current", 0.001, 0.0),
    "v": ("voltage", 1.0, 0.0),
    "volt": ("voltage", 1.0, 0.0),
    "volts": ("voltage", 1.0, 0.0),
    "kv": ("voltage", 1000.0, 0.0),
    # rotation / time
    "rpm": ("speed", 1.0, 0.0),
    "min-1": ("speed", 1.0, 0.0),
    "hz": ("frequency", 1.0, 0.0),
    "khz": ("frequency", 1000.0, 0.0),
    "deg": ("angle", 1.0, 0.0),
    "°": ("angle", 1.0, 0.0),
    "ms": ("time", 1.0, 0.0),
    "s": ("time", 1000.0, 0.0),
    "us": ("time", 0.001, 0.0),
    # mass
    "kg": ("mass", 1.0, 0.0),
    "g": ("mass", 0.001, 0.0),
    "lb": ("mass", 0.453592, 0.0),
    "lbs": ("mass", 0.453592, 0.0),
}

_NUM = r"[-+]?\d+(?:[.,]\d+)?"
_VALUE_UNIT = re.compile(
    rf"(?P<num>{_NUM})\s*(?P<unit>°?[a-zA-Z³/\"]+(?:/[a-zA-Z0-9³]+)?|\")?"
)

# "1/2 inch", "3-1/4"" — fractional imperial sizes are pervasive in this domain
_FRACTION = re.compile(
    r"(?:(?P<whole>\d+)\s*[-\s])?(?P<num>\d+)\s*/\s*(?P<den>\d+)\s*(?P<unit>in|inch|inches|\")?",
    re.IGNORECASE,
)


def dimension_of(unit: str | None) -> str | None:
    if not unit:
        return None
    entry = _UNITS.get(unit.strip().lower())
    return entry[0] if entry else None


def units_for_dimension(dimension: str) -> list[str]:
    """Every spelling we recognise for a dimension, longest first.

    Longest-first matters for regex alternation: 'horsepower' must be tried
    before 'hp', and '°c' before 'c'.
    """
    tokens = [u for u, (dim, _, _) in _UNITS.items() if dim == dimension]
    return sorted(tokens, key=len, reverse=True)


def convert(value: float, from_unit: str, to_unit: str) -> float | None:
    """Convert between any two units sharing a physical dimension."""
    src = _UNITS.get((from_unit or "").strip().lower())
    dst = _UNITS.get((to_unit or "").strip().lower())
    if not src or not dst or src[0] != dst[0]:
        return None
    # to canonical, then out to the target
    canonical = (value + src[2]) * src[1]
    return canonical / dst[1] - dst[2]


def normalize(value: float, unit: str | None) -> tuple[float | None, str | None]:
    """Express a value in the canonical unit for its dimension."""
    entry = _UNITS.get((unit or "").strip().lower())
    if not entry:
        return None, None
    dim, factor, offset = entry
    return round((value + offset) * factor, 6), CANONICAL[dim]


def parse_fraction(text: str) -> tuple[float, str] | None:
    """Read '1/2"', '3-1/4 inch' and similar into a decimal inch value."""
    m = _FRACTION.search(text or "")
    if not m:
        return None
    den = int(m.group("den"))
    if den == 0:
        return None
    value = int(m.group("num")) / den
    if m.group("whole"):
        value += int(m.group("whole"))
    return round(value, 5), "in"


def parse_quantity(text: str, default_unit: str | None = None) -> tuple[float, str | None] | None:
    """Pull a number and its unit out of free text.

    Returns None rather than guessing when there is no number at all, so the
    caller can distinguish 'absent' from 'present but unitless'.
    """
    if text is None:
        return None
    text = str(text).strip()
    if not text:
        return None

    frac = parse_fraction(text)
    if frac and "/" in text:
        return frac

    m = _VALUE_UNIT.search(text)
    if not m:
        return None
    try:
        num = float(m.group("num").replace(",", "."))
    except ValueError:
        return None

    unit = (m.group("unit") or "").strip()
    if unit and unit.lower() in _UNITS:
        return num, unit
    return num, default_unit


def tidy(value: float, significant: int = 4) -> float | int:
    """Trim conversion artefacts without discarding engineering precision.

    A 1/2" port converts to exactly 12.7 mm, but 5 HP converts to
    3.72849... kW, and a catalog should show 3.728 rather than the full float.
    """
    if value == 0:
        return 0
    import math

    places = significant - int(math.floor(math.log10(abs(value)))) - 1
    rounded = round(value, max(places, 0))
    return int(rounded) if rounded == int(rounded) else rounded


def format_value(value: float | int | str | None, unit: str | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        shown = f"{value:g}"
    else:
        shown = str(value)
    return f"{shown} {unit}".strip() if unit else shown

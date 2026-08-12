"""Validation: range, vocabulary, completeness and cross-field consistency.

Single-field checks catch typos and unit mistakes. The cross-field rules are
what actually catch bad catalog data, because most real errors are individually
plausible values that contradict each other — a PVC valve rated to 200 C, a
bore larger than the outer diameter, a hose whose burst pressure is below its
own working pressure.

Every rule is registered by name and referenced from taxonomy.json, so adding a
category means editing data, not code.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from ..models import Attribute, Severity, ValidationIssue

CrossCheck = Callable[[dict[str, Attribute], dict[str, Any]], list[ValidationIssue]]
_REGISTRY: dict[str, CrossCheck] = {}

# Warnings split into two kinds, and the distinction decides whether a record
# may auto-publish. An INTEGRITY warning says the data itself is suspect — the
# product may not be physically coherent — so it must never publish unreviewed.
# Everything else is advisory: worth showing a merchandiser, not worth blocking.
INTEGRITY_CODES = frozenset({
    "VOCABULARY_VIOLATION",
    # A value outside the customer's approved list of values is not publishable
    # even when it is factually correct, because the catalog is validated
    # against the list rather than against reality.
    "LOV_VIOLATION",
    "INVALID_IP_CODE",
    "SAFETY_FACTOR_LOW",
    "MATERIAL_TEMP_CONFLICT",
    "SEAT_TEMP_CONFLICT",
    "MATERIAL_PRESSURE_CONFLICT",
    "ELECTRICAL_INCONSISTENCY",
    "LOAD_RATING_SUSPECT",
    "SPEED_SEAL_CONFLICT",
    "PORT_SIZE_SUSPECT",
    "STRENGTH_MISMATCH",
    "GRADE_MATERIAL_CONFLICT",
    "GEOMETRY_CONTRADICTION",
    # A supplied value that the part number's own standard contradicts. The
    # supplier is kept, because they may hold a special variant — but one of
    # the two is wrong about a dimension, and shipping either unreviewed is
    # how a wrong specification reaches a machine.
    "STANDARD_CONTRADICTION",
    "PRESSURE_CONTRADICTION",
    "UNVERIFIED_FIGURE",
    "UNSUPPORTED_CLAIM",
    "TYPE_MISMATCH",
    "OUT_OF_RANGE",
})


def integrity_issues(issues: list[ValidationIssue]) -> list[ValidationIssue]:
    return [i for i in issues if i.code in INTEGRITY_CODES]


def rule(name: str) -> Callable[[CrossCheck], CrossCheck]:
    def decorate(fn: CrossCheck) -> CrossCheck:
        _REGISTRY[name] = fn
        return fn
    return decorate


def _num(attrs: dict[str, Attribute], key: str) -> float | None:
    a = attrs.get(key)
    if a is None or isinstance(a.value, bool):
        return None
    return float(a.value) if isinstance(a.value, (int, float)) else None


def _text(attrs: dict[str, Attribute], key: str) -> str:
    a = attrs.get(key)
    return str(a.value) if a is not None and a.value is not None else ""


# --------------------------------------------------------------- generic checks


def check_ranges(attributes: list[Attribute], category: dict[str, Any] | None) -> list[ValidationIssue]:
    if not category:
        return []
    issues: list[ValidationIssue] = []
    specs = category.get("attributes", {})

    for attr in attributes:
        spec = specs.get(attr.key)
        if not spec:
            continue

        if spec.get("type") == "number":
            if not isinstance(attr.value, (int, float)) or isinstance(attr.value, bool):
                issues.append(ValidationIssue(
                    code="TYPE_MISMATCH",
                    severity=Severity.ERROR,
                    field=attr.key,
                    message=f"{attr.label} should be numeric but holds '{attr.value}'.",
                    suggestion="Extract the numeric portion and record the unit separately.",
                ))
                continue

            lo, hi = spec.get("range", [None, None])
            if lo is not None and hi is not None and not (lo <= attr.value <= hi):
                # Out by a factor of ~25.4 or ~10 is almost always a unit error.
                hint = "Check the source value and its unit."
                for factor, name in ((25.4, "inches were read as millimetres"),
                                     (1000, "a kilo- prefix was dropped"),
                                     (0.7457, "horsepower was read as kilowatts")):
                    if lo <= attr.value / factor <= hi or lo <= attr.value * factor <= hi:
                        hint = f"The magnitude suggests {name}."
                        break
                issues.append(ValidationIssue(
                    code="OUT_OF_RANGE",
                    severity=Severity.ERROR,
                    field=attr.key,
                    message=(
                        f"{attr.label} is {attr.value}{' ' + attr.unit if attr.unit else ''}, "
                        f"outside the plausible range {lo}–{hi} for this category."
                    ),
                    suggestion=hint,
                ))

        if spec.get("type") == "enum":
            allowed = spec.get("values", [])
            if allowed and str(attr.value) not in allowed:
                issues.append(ValidationIssue(
                    code="VOCABULARY_VIOLATION",
                    severity=Severity.WARNING,
                    field=attr.key,
                    message=f"'{attr.value}' is not in the controlled vocabulary for {attr.label}.",
                    suggestion=f"Expected one of: {', '.join(allowed)}.",
                ))

    return issues


def check_required(
    attributes: list[Attribute], category: dict[str, Any] | None, identity: dict[str, Any]
) -> tuple[list[ValidationIssue], list[str]]:
    if not category:
        return [], []
    present = {a.key for a in attributes if a.value not in (None, "")}
    present |= {k for k, v in identity.items() if v and not k.startswith("_")}

    issues, missing = [], []
    for key in category.get("required", []):
        if key in present:
            continue
        missing.append(key)
        label = category.get("attributes", {}).get(key, {}).get("label", key.replace("_", " ").title())
        issues.append(ValidationIssue(
            code="MISSING_REQUIRED",
            severity=Severity.ERROR,
            field=key,
            message=f"{label} is required for {category['path'][-1]} but could not be resolved.",
            suggestion="Request this field from the supplier or source it from the datasheet.",
        ))
    return issues, missing


def check_confidence(attributes: list[Attribute]) -> list[ValidationIssue]:
    issues = []
    weak = [a for a in attributes if a.confidence < 0.5]
    if weak:
        issues.append(ValidationIssue(
            code="LOW_CONFIDENCE",
            severity=Severity.WARNING,
            field=None,
            message=(
                f"{len(weak)} attribute(s) rest on category defaults rather than "
                f"supplier data: {', '.join(a.label for a in weak[:6])}."
            ),
            suggestion="Confirm these against the manufacturer datasheet before publishing.",
        ))
    return issues


def check_content(content: Any, attributes: list[Attribute]) -> list[ValidationIssue]:
    """Guard against the classic generative failure: copy asserting unbacked specs."""
    if content is None:
        return []
    issues = []

    if len(content.title) > 150:
        issues.append(ValidationIssue(
            code="TITLE_TOO_LONG", severity=Severity.WARNING, field="title",
            message=f"Title is {len(content.title)} characters; most marketplaces truncate at 150.",
            suggestion="Trim to the brand, part number and two defining specs.",
        ))
    if content.meta_description and len(content.meta_description) > 160:
        issues.append(ValidationIssue(
            code="META_TOO_LONG", severity=Severity.WARNING, field="meta_description",
            message="Meta description exceeds 160 characters and will be cut off in search results.",
        ))

    banned = ["best in class", "world class", "premium quality", "cutting edge",
              "state of the art", "unbeatable", "revolutionary"]
    blob = f"{content.title} {content.short_description} {content.long_description}".lower()
    hits = [b for b in banned if b in blob]
    if hits:
        issues.append(ValidationIssue(
            code="UNSUPPORTED_CLAIM", severity=Severity.WARNING, field="content",
            message=f"Copy contains unverifiable marketing claims: {', '.join(hits)}.",
            suggestion="Replace with a measurable specification.",
        ))

    # Numbers in the copy that appear in no attribute are the dangerous case.
    known = set()
    for a in attributes:
        if isinstance(a.value, (int, float)) and not isinstance(a.value, bool):
            known.add(f"{float(a.value):g}")
        else:
            # Text attributes carry figures too — "10-30 VDC", "8 mm sensing
            # range" — and those are backed, not orphaned.
            for token in re.findall(r"\d+(?:\.\d+)?", str(a.value)):
                known.add(f"{float(token):g}")
    stated = set(re.findall(r"\b\d+(?:\.\d+)?\b", content.long_description or ""))
    orphans = [s for s in stated if f"{float(s):g}" not in known and float(s) > 3]
    if len(orphans) > 2:
        issues.append(ValidationIssue(
            code="UNVERIFIED_FIGURE", severity=Severity.WARNING, field="long_description",
            message=(
                f"The description cites figures not present in the attribute set: "
                f"{', '.join(sorted(orphans)[:5])}."
            ),
            suggestion="Remove them or promote them to attributes with evidence.",
        ))
    return issues


# ------------------------------------------------------------ cross-field rules


@rule("bore_lt_od")
def _bore_lt_od(attrs, spec):
    bore, od = _num(attrs, "bore_diameter"), _num(attrs, "outer_diameter")
    if bore is None or od is None or bore < od:
        return []
    return [ValidationIssue(
        code="GEOMETRY_CONTRADICTION", severity=Severity.ERROR, field="bore_diameter",
        message=f"Bore diameter ({bore} mm) is not smaller than outer diameter ({od} mm).",
        suggestion="The two values are most likely transposed in the source data.",
    )]


@rule("static_vs_dynamic")
def _static_vs_dynamic(attrs, spec):
    static, dynamic = _num(attrs, "static_load_rating"), _num(attrs, "dynamic_load_rating")
    bore = _num(attrs, "bore_diameter")
    # Below roughly 50 mm bore, C exceeds C0; above it the relationship inverts.
    if static is None or dynamic is None or bore is None or bore >= 50:
        return []
    if static <= dynamic:
        return []
    return [ValidationIssue(
        code="LOAD_RATING_SUSPECT", severity=Severity.WARNING, field="static_load_rating",
        message=(
            f"Static rating ({static} kN) exceeds dynamic rating ({dynamic} kN) on a "
            f"{bore} mm bore bearing, which is atypical for this size class."
        ),
        suggestion="Verify that C and C0 have not been swapped.",
    )]


@rule("sealed_speed")
def _sealed_speed(attrs, spec):
    seal, speed = _text(attrs, "seal_type"), _num(attrs, "max_speed")
    if speed is None or "2RS" not in seal.upper() or speed <= 20000:
        return []
    return [ValidationIssue(
        code="SPEED_SEAL_CONFLICT", severity=Severity.WARNING, field="max_speed",
        message=f"Contact seals (2RS) limit speed well below the stated {speed:g} rpm.",
        suggestion="The figure likely belongs to the open or shielded variant.",
    )]


@rule("pvc_temp")
def _pvc_temp(attrs, spec):
    material, temp = _text(attrs, "body_material"), _num(attrs, "temp_rating_max")
    if temp is None or "PVC" not in material.upper() or temp <= 60:
        return []
    return [ValidationIssue(
        code="MATERIAL_TEMP_CONFLICT", severity=Severity.ERROR, field="temp_rating_max",
        message=f"A PVC body cannot be rated to {temp:g} C; PVC softens above about 60 C.",
        suggestion="Either the body material or the temperature rating is wrong.",
    )]


@rule("ptfe_temp")
def _ptfe_temp(attrs, spec):
    seat, temp = _text(attrs, "seat_material"), _num(attrs, "temp_rating_max")
    if temp is None or "PTFE" not in seat.upper() or temp <= 230:
        return []
    return [ValidationIssue(
        code="SEAT_TEMP_CONFLICT", severity=Severity.WARNING, field="seat_material",
        message=f"PTFE seats degrade above ~230 C but the valve is rated to {temp:g} C.",
        suggestion="A metal-seated variant is implied; confirm the seat material.",
    )]


@rule("brass_pressure")
def _brass_pressure(attrs, spec):
    material, pressure = _text(attrs, "body_material"), _num(attrs, "pressure_rating")
    if pressure is None or "BRASS" not in material.upper() or pressure <= 3000:
        return []
    return [ValidationIssue(
        code="MATERIAL_PRESSURE_CONFLICT", severity=Severity.WARNING, field="pressure_rating",
        message=f"{pressure:g} psi is beyond the usual envelope for a brass body.",
        suggestion="Confirm the rating, or the body may in fact be stainless.",
    )]


@rule("motor_power_current")
def _motor_power_current(attrs, spec):
    power, voltage, current = (_num(attrs, "power_rating"), _num(attrs, "voltage"),
                               _num(attrs, "full_load_current"))
    if None in (power, voltage, current) or voltage <= 0:
        return []
    phase = _text(attrs, "phase")
    root3 = 1.732 if "Three" in phase or not phase else 1.0
    expected = (power * 1000) / (root3 * voltage * 0.85 * 0.92)
    if expected <= 0:
        return []
    ratio = current / expected
    if 0.6 <= ratio <= 1.7:
        return []
    return [ValidationIssue(
        code="ELECTRICAL_INCONSISTENCY", severity=Severity.WARNING, field="full_load_current",
        message=(
            f"{current:g} A does not fit {power:g} kW at {voltage:g} V; roughly "
            f"{expected:.1f} A would be expected."
        ),
        suggestion="Check whether the current is per-phase or the power is in horsepower.",
    )]


@rule("motor_pole_speed")
def _motor_pole_speed(attrs, spec):
    speed, freq = _num(attrs, "speed"), _num(attrs, "frequency")
    if speed is None:
        return []
    freq = freq or 50
    synchronous = [120 * freq / poles for poles in (2, 4, 6, 8, 10, 12)]
    # Induction motors run 1-6% below synchronous speed.
    if any(0.93 * s <= speed <= 1.001 * s for s in synchronous):
        return []
    return [ValidationIssue(
        code="SPEED_NOT_STANDARD", severity=Severity.INFO, field="speed",
        message=(
            f"{speed:g} rpm matches no standard pole count at {freq:g} Hz "
            f"(expected near {', '.join(f'{s:.0f}' for s in synchronous[:4])})."
        ),
        suggestion="Normal for inverter-duty or servo motors; verify otherwise.",
    )]


@rule("stainless_grade")
def _stainless_grade(attrs, spec):
    material, grade = _text(attrs, "material"), _text(attrs, "grade")
    if "STAINLESS" not in material.upper() or not grade:
        return []
    if grade.upper().startswith("A"):
        return []
    return [ValidationIssue(
        code="GRADE_MATERIAL_CONFLICT", severity=Severity.ERROR, field="grade",
        message=f"Property class '{grade}' is a carbon-steel designation but the material is {material}.",
        suggestion="Stainless fasteners use A2-70 or A4-80 per ISO 3506.",
    )]


@rule("grade_tensile")
def _grade_tensile(attrs, spec):
    grade, tensile = _text(attrs, "grade"), _num(attrs, "tensile_strength")
    table = spec.get("_grade_kb", {})
    if not grade or tensile is None or grade not in table:
        return []
    expected = table[grade].get("tensile_strength")
    if expected is None or abs(tensile - expected) / expected <= 0.12:
        return []
    return [ValidationIssue(
        code="STRENGTH_MISMATCH", severity=Severity.ERROR, field="tensile_strength",
        message=(
            f"Property class {grade} requires about {expected} MPa minimum tensile "
            f"strength, but {tensile:g} MPa is stated."
        ),
        suggestion="ISO 898-1 fixes this relationship; one of the two values is wrong.",
    )]


@rule("ip_plausible")
def _ip_plausible(attrs, spec):
    ip = _text(attrs, "ip_rating").strip()
    if not ip or re.fullmatch(r"IP\s?[0-6][0-9K]", ip.upper().replace("X", "0")):
        return []
    if re.fullmatch(r"IP\s?[0-6X][0-9XK]", ip.upper()):
        return []
    return [ValidationIssue(
        code="INVALID_IP_CODE", severity=Severity.WARNING, field="ip_rating",
        message=f"'{ip}' is not a valid IEC 60529 ingress protection code.",
        suggestion="Expected the form IP54, IP67, IP69K.",
    )]


@rule("pump_ports")
def _pump_ports(attrs, spec):
    inlet, outlet = _num(attrs, "inlet_size"), _num(attrs, "outlet_size")
    if inlet is None or outlet is None or outlet <= inlet:
        return []
    return [ValidationIssue(
        code="PORT_SIZE_SUSPECT", severity=Severity.INFO, field="outlet_size",
        message=f"Outlet ({outlet}\") is larger than inlet ({inlet}\"), which is unusual.",
        suggestion="Centrifugal pumps normally have the larger port on the suction side.",
    )]


@rule("pp_temp")
def _pp_temp(attrs, spec):
    material, temp = _text(attrs, "body_material"), _num(attrs, "max_temp")
    if temp is None or "POLYPROPYLENE" not in material.upper() or temp <= 90:
        return []
    return [ValidationIssue(
        code="MATERIAL_TEMP_CONFLICT", severity=Severity.ERROR, field="max_temp",
        message=f"Polypropylene wetted parts are not rated to {temp:g} C.",
        suggestion="Above 90 C requires PVDF or stainless steel.",
    )]


@rule("flute_vs_overall")
def _flute_vs_overall(attrs, spec):
    flute, overall = _num(attrs, "flute_length"), _num(attrs, "overall_length")
    if flute is None or overall is None or flute < overall:
        return []
    return [ValidationIssue(
        code="GEOMETRY_CONTRADICTION", severity=Severity.ERROR, field="flute_length",
        message=f"Flute length ({flute} mm) is not shorter than overall length ({overall} mm).",
        suggestion="A cutting tool needs shank beyond the flutes; check both values.",
    )]


@rule("burst_vs_working")
def _burst_vs_working(attrs, spec):
    burst, working = _num(attrs, "burst_pressure"), _num(attrs, "working_pressure")
    if burst is None or working is None:
        return []
    if burst < working:
        return [ValidationIssue(
            code="PRESSURE_CONTRADICTION", severity=Severity.ERROR, field="burst_pressure",
            message=f"Burst pressure ({burst:g} bar) is below working pressure ({working:g} bar).",
            suggestion="The values are transposed; burst must always exceed working pressure.",
        )]
    if burst < working * 4:
        ratio = burst / working
        # Below 3:1 this is not a data-quality nit but a part that must not be
        # listed for hydraulic service, so it blocks rather than warns.
        severe = ratio < 3
        return [ValidationIssue(
            code="SAFETY_FACTOR_LOW",
            severity=Severity.ERROR if severe else Severity.WARNING,
            field="burst_pressure",
            message=(
                f"Safety factor is {ratio:.1f}:1; SAE J517 requires at least 4:1 "
                f"for hydraulic hose."
            ),
            suggestion=(
                "Do not list this for hydraulic service until the rating is confirmed."
                if severe else
                "Confirm the burst rating against the manufacturer datasheet."
            ),
        )]
    return []


@rule("hose_id_od")
def _hose_id_od(attrs, spec):
    idia, odia = _num(attrs, "inner_diameter"), _num(attrs, "outer_diameter")
    if idia is None or odia is None or idia < odia:
        return []
    return [ValidationIssue(
        code="GEOMETRY_CONTRADICTION", severity=Severity.ERROR, field="inner_diameter",
        message=f"Inner diameter ({idia} mm) is not smaller than outer diameter ({odia} mm).",
        suggestion="Check whether the two columns are swapped in the source.",
    )]


def check_cross_fields(
    attributes: list[Attribute], category: dict[str, Any] | None
) -> list[ValidationIssue]:
    if not category:
        return []
    attrs = {a.key: a for a in attributes}
    # rules that need lookup tables get them through the spec dict
    spec = dict(category)
    spec["_grade_kb"] = category.get("grade_kb", {})

    issues: list[ValidationIssue] = []
    for check in category.get("cross_checks", []):
        fn = _REGISTRY.get(check.get("rule", ""))
        if fn:
            issues.extend(fn(attrs, spec))
    return issues


def check_standard_conflicts(
    standard_conflicts: list[dict[str, Any]],
) -> list[ValidationIssue]:
    """Report a supplied value that its own part number contradicts.

    A warning rather than an error, deliberately: both numbers are individually
    plausible and the supplier may be describing a variant the table does not
    cover. It is an integrity warning, so the record goes to a human instead of
    to the storefront.
    """
    return [
        ValidationIssue(
            code="STANDARD_CONTRADICTION",
            severity=Severity.WARNING,
            field=c["key"],
            message=(
                f"{c['label']} is given as {c['held']} but the part number's "
                f"standard fixes it at {c['standard']}."
            ),
            suggestion=(
                "Confirm the part number against the dimension. One of the two "
                "is wrong, and the supplier value has been kept unchanged."
            ),
        )
        for c in standard_conflicts
    ]


def run_all(
    attributes: list[Attribute],
    category: dict[str, Any] | None,
    identity: dict[str, Any],
    content: Any = None,
    standard_conflicts: list[dict[str, Any]] | None = None,
) -> tuple[list[ValidationIssue], list[str]]:
    issues: list[ValidationIssue] = []
    issues += check_ranges(attributes, category)
    required_issues, missing = check_required(attributes, category, identity)
    issues += required_issues
    issues += check_cross_fields(attributes, category)
    issues += check_standard_conflicts(standard_conflicts or [])
    issues += check_confidence(attributes)
    issues += check_content(content, attributes)

    order = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
    issues.sort(key=lambda i: order[i.severity])
    return issues, missing

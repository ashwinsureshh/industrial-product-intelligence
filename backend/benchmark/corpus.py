"""Benchmark corpus generation.

METHODOLOGY (stated up front, because a benchmark you grade yourself is only
worth what its methodology is worth):

Ground truth comes from two sources of differing strength, and results are
reported separately for each so the distinction is never hidden.

  STANDARDS-DERIVED (strong). Bearing dimensions come from the ISO 15 series
  tables and fastener strengths from ISO 898-1. These values are externally
  fixed — we did not choose them, and the engine cannot be tuned to them
  without also being correct in the real world.

  ARCHETYPE-DERIVED (weaker). The remaining categories have no equivalent
  universal table, so realistic archetypes were authored by hand from
  commercial product data. We report these separately and never blend them
  into the headline accuracy figure without labelling.

From each complete product we derive two evaluation cases:

  SPARSE  — most attributes stripped, leaving only what a thin supplier feed
            actually carries. Measures whether enrichment recovers truth.
  DEFECT  — all attributes present but exactly one corrupted in a known way.
            Measures whether validation catches errors, and the expected
            issue code is recorded so detection can be scored precisely.

Every case is generated from a fixed seed, so the whole benchmark is
reproducible.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from app.pipeline import taxonomy

# --------------------------------------------------------------------- models


@dataclass
class Defect:
    kind: str
    field: str
    expected_codes: list[str]
    description: str


@dataclass
class Case:
    id: str
    category_code: str
    truth_source: str  # "standards" | "archetype"
    ground_truth: dict[str, Any]
    product: dict[str, Any]
    variant: str  # "sparse" | "defect"
    defect: Defect | None = None
    withheld: list[str] = field(default_factory=list)


# ----------------------------------------------------------------- archetypes

# Hand-authored from commercial product data. Values are internally consistent
# and satisfy every cross-field rule, so a clean case should raise no errors.
ARCHETYPES: dict[str, list[dict[str, Any]]] = {
    "40141600": [  # valves
        {"valve_type": "Ball", "nominal_size": 0.5, "pressure_rating": 2000,
         "body_material": "316 Stainless Steel", "seat_material": "PTFE",
         "connection_type": "NPT Threaded", "actuation": "Manual Lever",
         "port_configuration": "2-Way", "temp_rating_max": 200, "cv_value": 12},
        {"valve_type": "Butterfly", "nominal_size": 4, "pressure_rating": 150,
         "body_material": "Ductile Iron", "seat_material": "EPDM",
         "connection_type": "Flanged", "actuation": "Manual Gear",
         "port_configuration": "2-Way", "temp_rating_max": 120, "cv_value": 900},
        {"valve_type": "Globe", "nominal_size": 2, "pressure_rating": 600,
         "body_material": "Carbon Steel", "seat_material": "Metal",
         "connection_type": "Flanged", "actuation": "Pneumatic",
         "port_configuration": "2-Way", "temp_rating_max": 400, "cv_value": 45},
    ],
    "26101100": [  # motors
        {"power_rating": 3, "voltage": 400, "phase": "Three Phase", "frequency": 50,
         "speed": 1450, "frame_size": "100L", "efficiency_class": "IE3 (Premium)",
         "enclosure": "TEFC", "insulation_class": "Class F", "mounting": "Foot (B3)",
         "full_load_current": 6.2},
        {"power_rating": 11, "voltage": 400, "phase": "Three Phase", "frequency": 50,
         "speed": 2940, "frame_size": "160M", "efficiency_class": "IE3 (Premium)",
         "enclosure": "TEFC", "insulation_class": "Class F", "mounting": "Foot & Flange (B35)",
         "full_load_current": 21.5},
        {"power_rating": 0.75, "voltage": 230, "phase": "Single Phase", "frequency": 50,
         "speed": 1400, "frame_size": "80B", "efficiency_class": "IE2 (High)",
         "enclosure": "TEFC", "insulation_class": "Class B", "mounting": "Flange (B5)",
         "full_load_current": 5.1},
    ],
    "41111700": [  # sensors
        {"sensor_type": "Inductive Proximity", "measuring_range": "8 mm",
         "output_signal": "PNP Discrete", "supply_voltage": "10-30 VDC",
         "ip_rating": "IP67", "housing_material": "Nickel Plated Brass",
         "response_time": 1.5, "operating_temp_max": 70},
        {"sensor_type": "Pressure", "measuring_range": "0-16 bar",
         "output_signal": "4-20 mA", "supply_voltage": "12-36 VDC",
         "ip_rating": "IP65", "housing_material": "316 Stainless Steel",
         "response_time": 5, "operating_temp_max": 125, "accuracy": "0.5% FS"},
        {"sensor_type": "Temperature (RTD)", "measuring_range": "-50 to 400 C",
         "output_signal": "4-20 mA", "supply_voltage": "24 VDC",
         "ip_rating": "IP68", "housing_material": "316 Stainless Steel",
         "response_time": 2000, "operating_temp_max": 400},
    ],
    "40151500": [  # pumps
        {"pump_type": "Centrifugal", "flow_rate": 200, "max_head": 35,
         "power_rating": 1.5, "inlet_size": 2, "outlet_size": 1.5,
         "body_material": "316 Stainless Steel", "seal_type": "Mechanical Seal",
         "max_temp": 90, "self_priming": False},
        {"pump_type": "Diaphragm (AODD)", "flow_rate": 150, "max_head": 70,
         "power_rating": 0.5, "inlet_size": 1, "outlet_size": 1,
         "body_material": "Polypropylene", "seal_type": "Lip Seal",
         "max_temp": 65, "self_priming": True},
        {"pump_type": "Gear", "flow_rate": 40, "max_head": 120,
         "power_rating": 2.2, "inlet_size": 1, "outlet_size": 0.75,
         "body_material": "Cast Iron", "seal_type": "Mechanical Seal",
         "max_temp": 120, "self_priming": True},
    ],
    "46181500": [  # PPE
        {"ppe_type": "Safety Gloves", "size": "L", "standard": "EN 388 4X42C",
         "material": "HPPE with PU coating", "protection_level": "Cut Level C",
         "color": "Grey", "reusable": True},
        {"ppe_type": "Hard Hat", "size": "Universal", "standard": "EN 397",
         "material": "HDPE", "protection_level": "440 VAC", "color": "White",
         "reusable": True},
        {"ppe_type": "Respirator", "size": "M", "standard": "EN 149 FFP3",
         "material": "Polypropylene", "protection_level": "FFP3",
         "color": "White", "reusable": False},
    ],
    "27112700": [  # cutting tools
        {"tool_type": "End Mill", "cutting_diameter": 6, "shank_diameter": 6,
         "overall_length": 57, "flute_length": 13, "flute_count": 4,
         "material": "Solid Carbide", "coating": "TiAlN", "helix_angle": 30},
        {"tool_type": "Drill Bit", "cutting_diameter": 8.5, "shank_diameter": 8,
         "overall_length": 117, "flute_length": 75, "flute_count": 2,
         "material": "HSS-Co (Cobalt)", "coating": "TiN", "helix_angle": 30},
        {"tool_type": "Ball Nose End Mill", "cutting_diameter": 10, "shank_diameter": 10,
         "overall_length": 72, "flute_length": 22, "flute_count": 2,
         "material": "Solid Carbide", "coating": "AlTiN", "helix_angle": 35},
    ],
    "39121000": [  # drives
        {"device_type": "Variable Frequency Drive", "power_rating": 22,
         "input_voltage": "380-480 VAC", "output_current": 45, "phase": "Three Phase",
         "control_method": "Sensorless Vector", "communication": "Modbus RTU",
         "ip_rating": "IP21", "overload_capacity": "150% for 60 s"},
        {"device_type": "Servo Drive", "power_rating": 1.5,
         "input_voltage": "200-240 VAC", "output_current": 9, "phase": "Single Phase",
         "control_method": "Servo", "communication": "EtherCAT",
         "ip_rating": "IP20", "overload_capacity": "300% for 3 s"},
        {"device_type": "Soft Starter", "power_rating": 75,
         "input_voltage": "400 VAC", "output_current": 145, "phase": "Three Phase",
         "control_method": "V/f Scalar", "communication": "Modbus RTU",
         "ip_rating": "IP20", "overload_capacity": "400% for 10 s"},
    ],
    "40142000": [  # hose
        {"inner_diameter": 12.7, "outer_diameter": 21.4, "working_pressure": 350,
         "burst_pressure": 1400, "material": "Synthetic Rubber (NBR)",
         "reinforcement": "2-Wire Braid", "bend_radius": 130,
         "temp_range": "-40 C to +100 C", "standard": "SAE 100R2AT"},
        {"inner_diameter": 25.4, "outer_diameter": 37.3, "working_pressure": 165,
         "burst_pressure": 660, "material": "Synthetic Rubber (NBR)",
         "reinforcement": "1-Wire Braid", "bend_radius": 300,
         "temp_range": "-40 C to +100 C", "standard": "SAE 100R1AT"},
        {"inner_diameter": 6.4, "outer_diameter": 13.4, "working_pressure": 250,
         "burst_pressure": 1000, "material": "PTFE",
         "reinforcement": "Textile Braid", "bend_radius": 50,
         "temp_range": "-70 C to +260 C", "standard": "SAE 100R14"},
    ],
}

BRANDS = {
    "31171500": ["SKF", "FAG", "NSK", "NTN", "Timken", "Koyo"],
    "40141600": ["Swagelok", "Parker Hannifin", "Festo", "SMC"],
    "26101100": ["Siemens", "ABB", "WEG", "Baldor"],
    "31161500": ["Bosch Rexroth", "Wurth", "Hilti"],
    "41111700": ["ifm electronic", "Pepperl+Fuchs", "Banner Engineering"],
    "40151500": ["Grundfos", "KSB"],
    "46181500": ["3M", "Ansell", "Honeywell"],
    "27112700": ["Sandvik Coromant", "Kennametal", "ISCAR"],
    "39121000": ["ABB", "Siemens", "Schneider Electric", "Danfoss"],
    "40142000": ["Gates", "Parker Hannifin", "Eaton"],
}

NAME_TEMPLATES = {
    "31171500": "Deep groove ball bearing",
    "40141600": "{valve_type} valve",
    "26101100": "{phase} induction motor",
    "31161500": "{fastener_type}",
    "41111700": "{sensor_type} sensor",
    "40151500": "{pump_type} pump",
    "46181500": "{ppe_type}",
    "27112700": "{tool_type}",
    "39121000": "{device_type}",
    "40142000": "Hydraulic hose",
}


# ------------------------------------------------------------- base products


def _bearing_products() -> list[tuple[str, dict[str, Any]]]:
    """Ground truth straight out of the ISO 15 dimension series tables."""
    category = taxonomy.get_category("31171500")
    seals = ["Open", "2RS (Rubber Sealed)", "ZZ (Metal Shielded)"]
    suffix = {"Open": "", "2RS (Rubber Sealed)": "-2RS", "ZZ (Metal Shielded)": "-ZZ"}

    products = []
    for index, (series, dims) in enumerate(category["series_kb"].items()):
        seal = seals[index % len(seals)]
        truth = dict(dims)
        truth["seal_type"] = seal
        truth["material"] = "Chrome Steel (GCr15/52100)"
        truth["cage_material"] = "Steel"
        truth["precision_class"] = "ABEC-1 / P0"
        truth["operating_temp_max"] = 120
        products.append((f"{series}{suffix[seal]}", truth))
    return products


def _fastener_products() -> list[tuple[str, dict[str, Any]]]:
    """Property class -> minimum tensile strength is fixed by ISO 898-1."""
    category = taxonomy.get_category("31161500")
    sizes = [(6, 1.0, 25), (8, 1.25, 30), (10, 1.5, 50), (12, 1.75, 60), (16, 2.0, 80)]

    products = []
    for index, (grade, values) in enumerate(category["grade_kb"].items()):
        diameter, pitch, length = sizes[index % len(sizes)]
        stainless = grade.startswith("A")
        truth = {
            "fastener_type": "Hex Bolt",
            "thread_size": f"M{diameter}",
            "thread_pitch": pitch,
            "length": length,
            "material": "316 Stainless Steel" if stainless else "Alloy Steel",
            "grade": grade,
            "finish": "Passivated" if stainless else "Zinc Plated",
            "drive_type": "External Hex",
            "tensile_strength": values["tensile_strength"],
        }
        products.append((f"M{diameter}x{length}-{grade}", truth))
    return products


def _archetype_products(code: str, rng: random.Random) -> list[tuple[str, dict[str, Any]]]:
    products = []
    for index, archetype in enumerate(ARCHETYPES[code]):
        truth = dict(archetype)
        mpn = f"{code[:3]}-{index + 1}{rng.randint(100, 999)}"
        products.append((mpn, truth))
    return products


def _make_name(code: str, truth: dict[str, Any]) -> str:
    template = NAME_TEMPLATES[code]
    try:
        return template.format(**truth)
    except KeyError:
        return template


# ------------------------------------------------------------------- defects


def _inject(code: str, truth: dict[str, Any], rng: random.Random) -> Defect | None:
    """Corrupt exactly one field in a way a real supplier feed actually does."""
    specs = taxonomy.get_category(code)["attributes"]

    candidates: list[Defect] = []

    # transposed geometry — the classic data-entry slip
    for a, b, msg in (
        ("bore_diameter", "outer_diameter", "bore/OD swapped"),
        ("inner_diameter", "outer_diameter", "ID/OD swapped"),
    ):
        if a in truth and b in truth and truth[a] != truth[b]:
            truth[a], truth[b] = truth[b], truth[a]
            return Defect("transposition", a, ["GEOMETRY_CONTRADICTION"], msg)

    # flute longer than the tool itself
    if "flute_length" in truth and "overall_length" in truth:
        truth["flute_length"] = truth["overall_length"] + 5
        return Defect("geometry", "flute_length", ["GEOMETRY_CONTRADICTION"],
                      "flute length exceeds overall length")

    # material/temperature impossibility
    if code == "40141600" and "temp_rating_max" in truth:
        truth["body_material"] = "PVC"
        truth["temp_rating_max"] = 180
        return Defect("material_conflict", "temp_rating_max",
                      ["MATERIAL_TEMP_CONFLICT"], "PVC body rated to 180 C")
    if code == "40151500" and "max_temp" in truth:
        truth["body_material"] = "Polypropylene"
        truth["max_temp"] = 140
        return Defect("material_conflict", "max_temp",
                      ["MATERIAL_TEMP_CONFLICT"], "polypropylene rated to 140 C")

    # fastener property class contradicting the material
    if code == "31161500":
        truth["material"] = "316 Stainless Steel"
        truth["grade"] = "10.9"
        return Defect("grade_conflict", "grade", ["GRADE_MATERIAL_CONFLICT"],
                      "stainless bolt carrying a carbon-steel property class")

    # hose safety factor below the SAE J517 minimum
    if code == "40142000" and "burst_pressure" in truth:
        truth["burst_pressure"] = truth["working_pressure"] * 2
        return Defect("safety_factor", "burst_pressure", ["SAFETY_FACTOR_LOW"],
                      "burst pressure only 2x working pressure")

    # malformed ingress protection code
    if "ip_rating" in truth:
        truth["ip_rating"] = "IP7X9"
        return Defect("invalid_code", "ip_rating", ["INVALID_IP_CODE"],
                      "IP rating is not a valid IEC 60529 code")

    # magnitude error: a kilo- prefix dropped somewhere upstream
    numeric = [k for k, v in truth.items()
               if isinstance(v, (int, float)) and not isinstance(v, bool)
               and specs.get(k, {}).get("range")]
    if numeric:
        key = rng.choice(numeric)
        truth[key] = truth[key] * 1000
        return Defect("magnitude", key, ["OUT_OF_RANGE"],
                      f"{key} inflated by 1000x")

    # last resort: break the controlled vocabulary
    enums = [k for k, v in truth.items() if specs.get(k, {}).get("type") == "enum"]
    if enums:
        key = rng.choice(enums)
        truth[key] = "Unspecified Material X"
        return Defect("vocabulary", key, ["VOCABULARY_VIOLATION"],
                      f"{key} set to a value outside the vocabulary")

    return None


# -------------------------------------------------------------------- corpus


def build_corpus(seed: int = 20260805, sparse_keep: float = 0.3) -> list[Case]:
    """Generate the full benchmark.

    `sparse_keep` is the fraction of ground-truth attributes left in the sparse
    input. 0.3 models a thin supplier feed: a name, a part number, and roughly
    a third of the spec table.
    """
    rng = random.Random(seed)
    cases: list[Case] = []

    sources: list[tuple[str, str, list[tuple[str, dict[str, Any]]]]] = [
        ("31171500", "standards", _bearing_products()),
        ("31161500", "standards", _fastener_products()),
    ]
    for code in ARCHETYPES:
        sources.append((code, "archetype", _archetype_products(code, rng)))

    for code, truth_source, products in sources:
        brands = BRANDS[code]
        for index, (mpn, truth) in enumerate(products):
            brand = brands[index % len(brands)]
            name = _make_name(code, truth)
            base = {"sku": f"{code[:4]}-{index:03d}", "mpn": mpn, "brand": brand, "name": name}

            # --- sparse case: withhold most of the spec table
            keys = sorted(truth.keys())
            rng.shuffle(keys)
            keep_count = max(1, int(len(keys) * sparse_keep))
            kept, withheld = keys[:keep_count], keys[keep_count:]

            specs = {}
            for key in kept:
                spec = taxonomy.attribute_spec(code, key) or {}
                unit = spec.get("unit")
                value = truth[key]
                label = spec.get("label", key)
                specs[label] = f"{value} {unit}" if unit else str(value)

            cases.append(Case(
                id=f"{code}-{index:03d}-sparse",
                category_code=code,
                truth_source=truth_source,
                ground_truth=dict(truth),
                product={**base, "raw_specs": specs},
                variant="sparse",
                withheld=withheld,
            ))

            # --- defect case: everything present, one field corrupted
            corrupted = dict(truth)
            defect = _inject(code, corrupted, rng)
            if defect is None:
                continue

            specs = {}
            for key, value in corrupted.items():
                spec = taxonomy.attribute_spec(code, key) or {}
                unit = spec.get("unit")
                label = spec.get("label", key)
                specs[label] = f"{value} {unit}" if unit else str(value)

            cases.append(Case(
                id=f"{code}-{index:03d}-defect-{defect.kind}",
                category_code=code,
                truth_source=truth_source,
                ground_truth=dict(truth),
                product={**base, "raw_specs": specs},
                variant="defect",
                defect=defect,
            ))

    return cases


def corpus_stats(cases: list[Case]) -> dict[str, Any]:
    by_category: dict[str, int] = {}
    by_variant: dict[str, int] = {}
    by_source: dict[str, int] = {}
    by_defect: dict[str, int] = {}

    for case in cases:
        path = taxonomy.get_category(case.category_code)["path"][-1]
        by_category[path] = by_category.get(path, 0) + 1
        by_variant[case.variant] = by_variant.get(case.variant, 0) + 1
        by_source[case.truth_source] = by_source.get(case.truth_source, 0) + 1
        if case.defect:
            by_defect[case.defect.kind] = by_defect.get(case.defect.kind, 0) + 1

    return {
        "total": len(cases),
        "by_category": by_category,
        "by_variant": by_variant,
        "by_truth_source": by_source,
        "by_defect_kind": by_defect,
    }

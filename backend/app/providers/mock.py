"""Demo-mode provider: deterministic, offline, and free to run.

This is not a stub that returns canned strings. It reasons from the curated
knowledge base in taxonomy.json — dimensional series tables for bearings,
property-class tables for fasteners, category-typical defaults elsewhere — so
the enrichment it produces is genuinely defensible and every value still
carries provenance and evidence. A reviewer with no API key sees the real
product, and identical inputs always yield identical outputs.
"""

from __future__ import annotations

import re
from typing import Any

from ..models import Attribute, CommerceContent, Provenance, RawProduct
from ..pipeline import units as U
from .base import InferenceResult, Provider


class MockProvider(Provider):
    name = "demo"

    # ---------------------------------------------------------------- attributes

    def infer_attributes(
        self,
        raw: RawProduct,
        category: dict[str, Any] | None,
        known: list[Attribute],
    ) -> InferenceResult:
        if not category:
            return InferenceResult(notes=["No category resolved; skipped inference."])

        have = {a.key for a in known}
        out: list[Attribute] = []
        notes: list[str] = []

        out += self._from_series_table(raw, category, have)
        out += self._from_grade_table(category, known, have)
        out += self._from_derivations(category, known + out, have)
        out += self._from_defaults(category, have)

        if not out:
            notes.append("Every category attribute was already resolved from supplier data.")
        return InferenceResult(attributes=out, notes=notes)

    def _from_series_table(
        self, raw: RawProduct, category: dict[str, Any], have: set[str]
    ) -> list[Attribute]:
        """Bearing dimensions are fully determined by the ISO series number."""
        table = category.get("series_kb")
        if not table:
            return []

        corpus = " ".join(
            p for p in [raw.mpn, raw.sku, raw.name, raw.description, raw.free_text] if p
        )
        series = None
        for candidate in sorted(table, key=len, reverse=True):
            if re.search(rf"\b{candidate}\b", corpus):
                series = candidate
                break
        if not series:
            return []

        specs = category.get("attributes", {})
        out: list[Attribute] = []
        for key, value in table[series].items():
            if key in have:
                continue
            spec = specs.get(key, {})
            unit = spec.get("unit")
            norm_value, norm_unit = (
                U.normalize(float(value), unit) if unit else (None, None)
            )
            out.append(
                Attribute(
                    key=key,
                    label=spec.get("label", key.replace("_", " ").title()),
                    value=value,
                    unit=unit,
                    normalized_value=norm_value,
                    normalized_unit=norm_unit,
                    provenance=Provenance.KNOWLEDGE_BASE,
                    confidence=0.93,
                    evidence=(
                        f"ISO 15:2017 dimension series {series}: this designation fixes "
                        f"{spec.get('label', key)} at {U.format_value(value, unit)} for every "
                        f"manufacturer."
                    ),
                    method="knowledge-base-lookup",
                    group=spec.get("group", "General"),
                )
            )
            have.add(key)
        return out

    def _from_grade_table(
        self, category: dict[str, Any], known: list[Attribute], have: set[str]
    ) -> list[Attribute]:
        """Fastener property class implies minimum tensile strength."""
        table = category.get("grade_kb")
        if not table:
            return []
        grade_attr = next((a for a in known if a.key == "grade"), None)
        if not grade_attr or str(grade_attr.value) not in table:
            return []

        specs = category.get("attributes", {})
        out: list[Attribute] = []
        for key, value in table[str(grade_attr.value)].items():
            if key in have:
                continue
            spec = specs.get(key, {})
            unit = spec.get("unit")
            norm_value, norm_unit = (
                U.normalize(float(value), unit) if unit else (None, None)
            )
            out.append(
                Attribute(
                    key=key,
                    label=spec.get("label", key),
                    value=value,
                    unit=unit,
                    normalized_value=norm_value,
                    normalized_unit=norm_unit,
                    provenance=Provenance.DERIVED,
                    confidence=0.9,
                    evidence=(
                        f"ISO 898-1 specifies {U.format_value(value, unit)} minimum tensile "
                        f"strength for property class {grade_attr.value}."
                    ),
                    method="standards-derivation",
                    group=spec.get("group", "General"),
                )
            )
            have.add(key)
        return out

    def _from_derivations(
        self, category: dict[str, Any], known: list[Attribute], have: set[str]
    ) -> list[Attribute]:
        """Compute attributes that follow arithmetically from known ones."""
        by_key = {a.key: a for a in known}
        specs = category.get("attributes", {})
        out: list[Attribute] = []

        def num(key: str) -> float | None:
            attr = by_key.get(key)
            if attr is None or isinstance(attr.value, bool):
                return None
            return float(attr.value) if isinstance(attr.value, (int, float)) else None

        def emit(key: str, value: float, evidence: str, confidence: float) -> None:
            if key in have:
                return
            spec = specs.get(key, {})
            unit = spec.get("unit")
            norm_value, norm_unit = (
                U.normalize(float(value), unit) if unit else (None, None)
            )
            out.append(
                Attribute(
                    key=key,
                    label=spec.get("label", key.replace("_", " ").title()),
                    value=round(value, 3),
                    unit=unit,
                    normalized_value=norm_value,
                    normalized_unit=norm_unit,
                    provenance=Provenance.DERIVED,
                    confidence=confidence,
                    evidence=evidence,
                    method="engineering-derivation",
                    group=spec.get("group", "General"),
                )
            )
            have.add(key)

        code = category["code"]

        if code == "26101100":  # electric motors
            power, voltage = num("power_rating"), num("voltage")
            if power and voltage and "full_load_current" not in have:
                # I = P / (sqrt(3) * V * pf * eta) for a three-phase machine
                phase = by_key.get("phase")
                three_phase = not phase or "Three" in str(phase.value)
                root3 = 1.732 if three_phase else 1.0
                current = (power * 1000) / (root3 * voltage * 0.85 * 0.92)
                emit(
                    "full_load_current",
                    current,
                    f"Estimated from {power} kW at {voltage} V "
                    f"({'three' if three_phase else 'single'}-phase, assuming 0.85 power factor "
                    f"and 92% efficiency). Confirm against the nameplate before publishing.",
                    0.66,
                )

        if code == "40142000":  # hose
            working = num("working_pressure")
            if working and "burst_pressure" not in have:
                emit(
                    "burst_pressure",
                    working * 4,
                    f"SAE J517 requires a 4:1 design factor for hydraulic hose, giving "
                    f"{working * 4:g} bar minimum burst from {working:g} bar working pressure.",
                    0.72,
                )

        if code == "31171500":  # bearings
            bore, od = num("bore_diameter"), num("outer_diameter")
            if bore and od and "mean_diameter" not in specs:
                pass  # nothing further to derive without load context

        return out

    def _from_defaults(self, category: dict[str, Any], have: set[str]) -> list[Attribute]:
        """Category-typical values — the weakest provenance, flagged as such."""
        specs = category.get("attributes", {})
        out: list[Attribute] = []
        for key, value in (category.get("defaults") or {}).items():
            if key in have:
                continue
            spec = specs.get(key, {})
            unit = spec.get("unit")
            norm_value, norm_unit = (
                U.normalize(float(value), unit)
                if unit and isinstance(value, (int, float)) and not isinstance(value, bool)
                else (None, None)
            )
            out.append(
                Attribute(
                    key=key,
                    label=spec.get("label", key.replace("_", " ").title()),
                    value=value,
                    unit=unit,
                    normalized_value=norm_value,
                    normalized_unit=norm_unit,
                    provenance=Provenance.DEFAULTED,
                    confidence=0.45,
                    evidence=(
                        f"Not stated by the supplier. {U.format_value(value, unit)} is the "
                        f"most common value for {category['path'][-1]} and is offered as a "
                        f"placeholder requiring confirmation."
                    ),
                    method="category-default",
                    group=spec.get("group", "General"),
                )
            )
            have.add(key)
        return out

    # ------------------------------------------------------------------- content

    def generate_content(
        self,
        raw: RawProduct,
        category: dict[str, Any] | None,
        attributes: list[Attribute],
        identity: dict[str, Any],
    ) -> InferenceResult:
        brand = identity.get("brand") or raw.brand or ""
        mpn = identity.get("mpn") or raw.mpn or ""
        # Taxonomy leaves are plural collection names ("Hose & Fittings"); each
        # category carries the singular trade noun a buyer would actually type.
        noun = (category or {}).get("noun") or "Industrial Product"
        noun_singular = noun

        trusted = [
            a for a in attributes
            if a.provenance != Provenance.DEFAULTED and a.value not in (None, "")
        ]
        trusted.sort(key=lambda a: -a.confidence)

        def phrase(a: Attribute) -> str:
            return f"{a.label} {U.format_value(a.value, a.unit)}"

        # --- title: brand + MPN + the two most identifying specs
        headline_keys = self._headline_keys(category)
        headline = [a for a in trusted if a.key in headline_keys][:2]
        title_bits = [b for b in [brand, mpn] if b]
        descriptor = ", ".join(U.format_value(a.value, a.unit) for a in headline)
        title = " ".join(title_bits)
        title = f"{title} {noun_singular}".strip()
        if descriptor:
            title = f"{title} — {descriptor}"
        title = title[:150]

        # --- descriptions
        spec_clause = "; ".join(phrase(a) for a in trusted[:5])
        short = (
            f"{brand + ' ' if brand else ''}{mpn + ' ' if mpn else ''}{noun_singular.lower()}"
            f"{' with ' + spec_clause.lower() if spec_clause else ''}."
        ).strip()
        short = short[0].upper() + short[1:] if short else ""
        short = short[:300]

        groups: dict[str, list[Attribute]] = {}
        for a in trusted:
            groups.setdefault(a.group, []).append(a)

        paragraphs = [
            f"The {title_bits and ' '.join(title_bits) or noun_singular} is a "
            f"{noun_singular.lower()} intended for industrial service where consistent, "
            f"documented performance matters."
        ]
        for group, items in list(groups.items())[:4]:
            listing = ", ".join(phrase(a).lower() for a in items[:5])
            paragraphs.append(f"{group}: {listing}.")
        if raw.description:
            paragraphs.append(raw.description.strip())
        long = " ".join(paragraphs)[:1800]

        bullets = [phrase(a) for a in trusted[:6]]
        if brand:
            bullets.append(f"Genuine {brand} part{f', MPN {mpn}' if mpn else ''}")

        keywords = self._keywords(brand, mpn, noun, trusted)

        content = CommerceContent(
            title=title,
            short_description=short,
            long_description=long,
            bullets=bullets,
            meta_description=(short or title)[:158],
            keywords=keywords[:12],
            search_terms=self._search_terms(brand, mpn, noun_singular),
        )
        return InferenceResult(
            content=content,
            notes=["Copy composed from verified attributes only; defaulted values were excluded."],
        )

    @staticmethod
    def _headline_keys(category: dict[str, Any] | None) -> list[str]:
        if not category:
            return []
        # the required attributes minus identity fields make the best headline
        return [k for k in category.get("required", []) if k not in {"brand", "mpn"}]

    @staticmethod
    def _keywords(
        brand: str, mpn: str, noun: str, attributes: list[Attribute]
    ) -> list[str]:
        words: list[str] = []
        base = noun.lower()
        if mpn:
            words += [mpn, f"{brand} {mpn}".strip()]
        if brand:
            words.append(f"{brand} {base}".strip())
        words.append(base)
        for a in attributes[:4]:
            words.append(f"{U.format_value(a.value, a.unit)} {base}".strip().lower())
        seen: set[str] = set()
        return [w for w in words if w and not (w.lower() in seen or seen.add(w.lower()))]

    @staticmethod
    def _search_terms(brand: str, mpn: str, noun: str) -> list[str]:
        terms = []
        if mpn:
            terms += [mpn, mpn.replace("-", ""), mpn.replace("-", " ")]
        if brand and mpn:
            terms.append(f"{brand} {mpn}")
        terms.append(noun.lower())
        seen: set[str] = set()
        return [t for t in terms if t and not (t.lower() in seen or seen.add(t.lower()))]

"""Live-mode provider backed by the Claude API.

Two design decisions worth calling out:

1. Structured output is obtained through a tool schema, not by asking for JSON
   in prose. The model must fill a typed shape, which removes the parsing
   failure mode entirely.

2. The prompt forbids inventing values and requires per-attribute evidence and
   confidence. An enrichment system that quietly guesses is worse than one that
   returns nothing, because a wrong spec on a bearing ships a broken machine.
"""

from __future__ import annotations

import json
from typing import Any

from ..config import MAX_TOKENS, MODEL
from ..models import Attribute, CommerceContent, Provenance, RawProduct
from ..pipeline import units as U
from .base import InferenceResult, Provider

_ATTR_TOOL = {
    "name": "record_attributes",
    "description": (
        "Record product attributes you can justify from the supplied information "
        "or from well-established industry standards. Omit any attribute you "
        "cannot support with concrete evidence."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "attributes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "Must be one of the attribute keys listed in the prompt.",
                        },
                        "value": {
                            "type": ["string", "number", "boolean"],
                            "description": "The value in the unit specified for that attribute.",
                        },
                        "confidence": {
                            "type": "number",
                            "description": (
                                "0.9+ only for values fixed by a published standard. "
                                "0.6-0.85 for strong inference. Below 0.6 for plausible "
                                "category-typical guesses."
                            ),
                        },
                        "evidence": {
                            "type": "string",
                            "description": (
                                "Cite the source text verbatim, or name the standard and "
                                "clause. Never write 'common knowledge'."
                            ),
                        },
                        "basis": {
                            "type": "string",
                            "enum": ["standard", "input_text", "engineering_inference", "typical_value"],
                        },
                    },
                    "required": ["key", "value", "confidence", "evidence", "basis"],
                },
            },
            "unresolvable": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Attribute keys you deliberately left blank for lack of evidence.",
            },
        },
        "required": ["attributes"],
    },
}

_CONTENT_TOOL = {
    "name": "record_content",
    "description": "Record storefront-ready merchandising copy for this product.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Max 150 chars. Brand, MPN, product type, key specs."},
            "short_description": {"type": "string", "description": "One or two sentences, max 300 chars."},
            "long_description": {"type": "string", "description": "2-4 paragraphs covering construction, specs and application."},
            "bullets": {"type": "array", "items": {"type": "string"}, "description": "5-8 scannable spec highlights."},
            "meta_description": {"type": "string", "description": "Max 158 chars for search snippets."},
            "keywords": {"type": "array", "items": {"type": "string"}},
            "search_terms": {"type": "array", "items": {"type": "string"}, "description": "Alternate spellings and part-number variants buyers type."},
        },
        "required": ["title", "short_description", "long_description", "bullets"],
    },
}

_BASIS_TO_PROVENANCE = {
    "standard": Provenance.KNOWLEDGE_BASE,
    "input_text": Provenance.PARSED,
    "engineering_inference": Provenance.INFERRED,
    "typical_value": Provenance.DEFAULTED,
}


def _string_list(value: Any) -> list[str]:
    """Coerce a model's answer for a list field into an actual list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if not isinstance(value, (list, tuple)):
        return [str(value)]
    return [str(v) for v in value if str(v).strip()]


class AnthropicProvider(Provider):
    name = "live"

    def __init__(self, api_key: str, model: str = MODEL) -> None:
        try:
            from anthropic import Anthropic
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise RuntimeError(
                "The anthropic package is not installed. Run "
                "`pip install -r requirements.txt`, or use demo mode."
            ) from exc
        self._client = Anthropic(api_key=api_key)
        self._model = model
        self._usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}

    # ------------------------------------------------------------------ helpers

    def _call(self, system: str, prompt: str, tool: dict[str, Any]) -> dict[str, Any] | None:
        message = self._client.messages.create(
            model=self._model,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
            messages=[{"role": "user", "content": prompt}],
        )
        self._usage["input_tokens"] += message.usage.input_tokens
        self._usage["output_tokens"] += message.usage.output_tokens
        for block in message.content:
            if block.type == "tool_use":
                return block.input
        return None

    @staticmethod
    def _describe_schema(category: dict[str, Any] | None) -> str:
        if not category:
            return "(no category resolved — infer only widely applicable attributes)"
        lines = []
        for key, spec in category.get("attributes", {}).items():
            bits = [f"- {key} ({spec.get('type', 'text')}"]
            if spec.get("unit"):
                bits.append(f", report in {spec['unit']}")
            bits.append(f"): {spec.get('label', key)}")
            if spec.get("values"):
                bits.append(f" — must be exactly one of: {', '.join(spec['values'])}")
            if spec.get("range"):
                lo, hi = spec["range"]
                bits.append(f" — plausible range {lo} to {hi}")
            lines.append("".join(bits))
        return "\n".join(lines)

    @staticmethod
    def _describe_known(known: list[Attribute]) -> str:
        if not known:
            return "(nothing resolved yet)"
        return "\n".join(
            f"- {a.key} = {U.format_value(a.value, a.unit)} [{a.provenance.value}]"
            for a in known
        )

    @staticmethod
    def _describe_input(raw: RawProduct) -> str:
        payload = raw.model_dump(exclude_none=True, exclude_defaults=True)
        return json.dumps(payload, indent=2, default=str)

    # --------------------------------------------------------------- attributes

    def infer_attributes(
        self,
        raw: RawProduct,
        category: dict[str, Any] | None,
        known: list[Attribute],
    ) -> InferenceResult:
        system = (
            "You are a product data engineer building an industrial commerce catalog. "
            "Accuracy outranks completeness: a wrong specification on an industrial part "
            "causes equipment failure, so leaving a field blank is always preferable to "
            "guessing.\n\n"
            "Rules you must follow:\n"
            "1. Never invent a value that cannot be traced to the input text or to a "
            "published standard you can name.\n"
            "2. Do not restate attributes that are already resolved.\n"
            "3. Where a dimensional standard fixes a value (ISO bearing series, ISO 898-1 "
            "fastener classes, NEMA/IEC frame sizes), use it and cite it.\n"
            "4. Report every value in the unit named in the schema, converting if needed.\n"
            "5. Enum attributes must use one of the listed values verbatim."
        )
        prompt = (
            f"Supplier-provided product record:\n{self._describe_input(raw)}\n\n"
            f"Resolved category: {' > '.join(category['path']) if category else 'unknown'}\n\n"
            f"Attributes this category defines:\n{self._describe_schema(category)}\n\n"
            f"Already resolved deterministically (do not repeat these):\n"
            f"{self._describe_known(known)}\n\n"
            "Fill in the attributes that remain, following the rules exactly."
        )

        data = self._call(system, prompt, _ATTR_TOOL)
        if not data:
            return InferenceResult(notes=["Model returned no structured attributes."])

        specs = (category or {}).get("attributes", {})
        have = {a.key for a in known}
        out: list[Attribute] = []

        for item in data.get("attributes", []):
            key = item.get("key")
            if not key or key in have or key not in specs:
                continue
            spec = specs[key]
            value = item.get("value")
            unit = spec.get("unit")

            norm_value, norm_unit = (None, None)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and unit:
                norm_value, norm_unit = U.normalize(float(value), unit)

            confidence = float(item.get("confidence", 0.5))
            basis = item.get("basis", "engineering_inference")
            provenance = _BASIS_TO_PROVENANCE.get(basis, Provenance.INFERRED)

            # A model's self-reported confidence is an input, not a verdict. Cap
            # anything it merely inferred so it can never outrank parsed data.
            if provenance == Provenance.INFERRED:
                confidence = min(confidence, 0.85)
            elif provenance == Provenance.DEFAULTED:
                confidence = min(confidence, 0.55)

            out.append(
                Attribute(
                    key=key,
                    label=spec.get("label", key),
                    value=value,
                    unit=unit,
                    normalized_value=norm_value,
                    normalized_unit=norm_unit,
                    provenance=provenance,
                    confidence=round(max(0.0, min(confidence, 1.0)), 3),
                    evidence=item.get("evidence", "No evidence supplied by the model."),
                    method=f"claude:{self._model}",
                    group=spec.get("group", "General"),
                )
            )
            have.add(key)

        notes = []
        if data.get("unresolvable"):
            notes.append(
                "Model declined to guess: " + ", ".join(data["unresolvable"])
            )
        return InferenceResult(attributes=out, notes=notes, usage=dict(self._usage))

    # ------------------------------------------------------------------ content

    def generate_content(
        self,
        raw: RawProduct,
        category: dict[str, Any] | None,
        attributes: list[Attribute],
        identity: dict[str, Any],
    ) -> InferenceResult:
        system = (
            "You write product content for an industrial B2B catalog. Your readers are "
            "maintenance engineers and procurement specialists who need to confirm a part "
            "fits their application.\n\n"
            "Rules:\n"
            "1. Use only the attributes provided. Never introduce a specification that is "
            "not in the list.\n"
            "2. No marketing superlatives — no 'premium quality', 'best in class', "
            "'cutting edge'. State facts.\n"
            "3. Lead with the part number and the specs an engineer searches on.\n"
            "4. Do not claim certifications, warranties, or country of origin unless given."
        )
        verified = [a for a in attributes if a.provenance != Provenance.DEFAULTED]
        attr_lines = "\n".join(
            f"- {a.label}: {U.format_value(a.value, a.unit)}" for a in verified
        ) or "(no verified attributes)"

        prompt = (
            f"Brand: {identity.get('brand') or raw.brand or 'unknown'}\n"
            f"MPN: {identity.get('mpn') or raw.mpn or 'unknown'}\n"
            f"Category: {' > '.join(category['path']) if category else 'unknown'}\n\n"
            f"Verified attributes:\n{attr_lines}\n\n"
            f"Original supplier text (for tone and any context not captured above):\n"
            f"{raw.description or raw.free_text or '(none)'}\n\n"
            "Write the catalog content."
        )

        data = self._call(system, prompt, _CONTENT_TOOL)
        if not data:
            return InferenceResult(notes=["Model returned no content."])

        content = CommerceContent(
            title=str(data.get("title", ""))[:150],
            short_description=str(data.get("short_description", ""))[:300],
            long_description=str(data.get("long_description", "")),
            # Not `[str(b) for b in ...]`: when the tool call answers with a
            # bare string instead of an array, that iterates it letter by letter
            # and stores ['S','t','a','n','d','a','r','d'].
            bullets=_string_list(data.get("bullets"))[:8],
            meta_description=str(data.get("meta_description", ""))[:158],
            keywords=_string_list(data.get("keywords"))[:12],
            search_terms=_string_list(data.get("search_terms"))[:10],
        )
        return InferenceResult(content=content, usage=dict(self._usage))

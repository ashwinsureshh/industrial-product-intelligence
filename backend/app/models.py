"""Canonical schemas for product intelligence.

Everything the pipeline produces is one of these. The rule we follow throughout:
no enriched value exists without provenance attached to it, because an
unexplainable attribute is not usable in a commerce catalog.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Provenance(str, Enum):
    """Where a value came from. Ordered loosely by how much we trust it."""

    SUPPLIED = "supplied"          # present in the caller's raw input
    PARSED = "parsed"              # deconstructed from a supplied string (e.g. MPN pattern)
    DERIVED = "derived"            # computed from other known attributes (e.g. unit conversion)
    KNOWLEDGE_BASE = "knowledge_base"  # matched against curated category/series data
    INFERRED = "inferred"          # model-generated from context
    DEFAULTED = "defaulted"        # category-typical fallback, weakest of all


class Severity(str, Enum):
    ERROR = "error"      # blocks publication
    WARNING = "warning"  # publishable, needs review
    INFO = "info"        # advisory only


class RawProduct(BaseModel):
    """The sparse, messy input a supplier actually gives you."""

    sku: str | None = None
    mpn: str | None = None
    brand: str | None = None
    name: str | None = None
    description: str | None = None
    category_hint: str | None = None
    price: float | None = None
    currency: str | None = None
    raw_specs: dict[str, Any] = Field(default_factory=dict)
    spec_sources: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Per-spec-key origin inside the source document, e.g. "
            "{'Bore': 'page 2'}. Lets an extracted attribute cite the exact "
            "place it came from rather than the document as a whole."
        ),
    )
    source_url: str | None = None
    free_text: str | None = Field(
        default=None,
        description="Unstructured dump: catalog blurb, PDF paragraph, scraped table.",
    )
    source_document: str | None = Field(
        default=None,
        description=(
            "Origin of the record when it came from a document rather than a feed, "
            "e.g. 'datasheet.pdf p.2'. Carried into attribute evidence so a buyer "
            "can trace any value back to the page it was read from."
        ),
    )

    def is_empty(self) -> bool:
        return not any(
            [self.sku, self.mpn, self.brand, self.name, self.description,
             self.free_text, self.raw_specs, self.category_hint]
        )


class Attribute(BaseModel):
    """One enriched fact about the product, with its full audit trail."""

    key: str                       # machine name, e.g. "bore_diameter"
    label: str                     # human name, e.g. "Bore Diameter"
    value: Any
    unit: str | None = None
    normalized_value: float | str | None = None
    normalized_unit: str | None = None
    provenance: Provenance
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = Field(
        description="The specific text or rule that justifies this value."
    )
    # Where the value physically came from. A buyer auditing a spec needs to
    # reach the page it was read off, not just be told a stage produced it.
    # Null for values a standard or calculation yields rather than a document:
    # inventing a URL for those would be worse than admitting there isn't one,
    # which is why `evidence` still names the standard.
    source_url: str | None = Field(
        default=None,
        description="URL of the manufacturer page or document the value was read from.",
    )
    source_locator: str | None = Field(
        default=None,
        description="Where inside that source, e.g. 'page 2' or 'datasheet.pdf'.",
    )
    method: str = Field(description="Which pipeline stage produced it.")
    group: str = "General"


class ValidationIssue(BaseModel):
    code: str
    severity: Severity
    field: str | None = None
    message: str
    suggestion: str | None = None


class CategoryAssignment(BaseModel):
    code: str
    path: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    alternatives: list[dict[str, Any]] = Field(default_factory=list)


class CommerceContent(BaseModel):
    """The merchandising layer — what a storefront actually renders."""

    title: str
    short_description: str
    long_description: str
    bullets: list[str] = Field(default_factory=list)
    meta_description: str = ""
    keywords: list[str] = Field(default_factory=list)
    search_terms: list[str] = Field(default_factory=list)


class ComplianceReport(BaseModel):
    """Whether the record obeys the customer's content standard, and on what basis.

    Kept separate from validation because these are different questions. A
    validation issue says the data may be wrong; a compliance finding says the
    data may be right but written in a form the catalog will not accept — an
    unapproved unit, a value outside the list, a description over its character
    limit. Both block publication, for different reasons.
    """

    fields: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Per-format rendering with its length window and any breaches.",
    )
    lov: dict[str, Any] = Field(
        default_factory=dict,
        description="Vocabulary coverage: how many values were found in the approved list.",
    )
    vocabulary_mappings: list[dict[str, str]] = Field(
        default_factory=list,
        description="Every many-to-one normalization applied, so a rewrite is auditable.",
    )
    standards: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Which table backed each rule. 'provisional' means a stand-in was "
            "used, so nothing here claims verified compliance on a stub."
        ),
    )
    compliant: bool = True
    breaches: list[str] = Field(
        default_factory=list,
        description="Fields that could not be written inside their limits.",
    )

    @property
    def verdict(self) -> str:
        """Deliberately separate from ReadinessScore.verdict.

        Readiness asks whether the data is *right*; compliance asks whether it
        is *written the way the customer's standard requires*. A record can pass
        one and fail the other, and collapsing them would hide which needs
        fixing — so a character-limit breach never silently drags down a data
        quality score, and clean prose never covers for a bad value.
        """
        return "compliant" if self.compliant else "non_compliant"


class ReadinessScore(BaseModel):
    """Is this record good enough to publish? Broken into defensible parts."""

    overall: float = Field(ge=0.0, le=100.0)
    completeness: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=100.0)
    validity: float = Field(ge=0.0, le=100.0)
    verdict: Literal["publish", "review", "blocked"]
    missing_required: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class StageTrace(BaseModel):
    """Per-stage record so the whole run is inspectable in the UI."""

    stage: str
    summary: str
    duration_ms: int = 0
    added: list[str] = Field(default_factory=list)
    changed: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class GateAction(BaseModel):
    """One decision the hybrid gate took about a model-proposed value.

    Refusals are recorded as deliberately as acceptances. A system that only
    reports what the AI contributed cannot be audited; what it was *stopped*
    from doing is the evidence that the guardrail is real.
    """

    key: str
    label: str
    action: Literal["gap_filled", "displaced_default", "refused"]
    proposed: str = Field(description="The value the model put forward.")
    kept: str | None = Field(
        default=None, description="The value that survived, when the model was refused."
    )
    kept_provenance: str | None = None
    reason: str


class GateDecision(BaseModel):
    """Summary of how the gate treated the model's proposals for one product."""

    gap_filled: int = 0
    displaced_defaults: int = 0
    refused: int = 0
    actions: list[GateAction] = Field(default_factory=list)
    live_source: Literal["api", "precomputed", "cache"] | None = Field(
        default=None,
        description="Where the model's contribution came from, so a reviewer "
                    "can tell a live call from a replayed one.",
    )


class EnrichedProduct(BaseModel):
    input: RawProduct
    identity: dict[str, Any] = Field(default_factory=dict)
    category: CategoryAssignment | None = None
    attributes: list[Attribute] = Field(default_factory=list)
    content: CommerceContent | None = None
    compliance: ComplianceReport | None = None
    issues: list[ValidationIssue] = Field(default_factory=list)
    readiness: ReadinessScore | None = None
    trace: list[StageTrace] = Field(default_factory=list)
    gate: GateDecision | None = None
    mode: str = "demo"
    cached: bool = False

    def attr(self, key: str) -> Attribute | None:
        return next((a for a in self.attributes if a.key == key), None)


class ProposedAttribute(BaseModel):
    """One attribute in a proposed category schema, with its justification."""

    key: str
    label: str
    type: Literal["number", "text", "enum", "boolean"]
    unit: str | None = None
    group: str = "General"
    values: list[str] | None = None
    range: list[float] | None = None
    aliases: list[str] = Field(default_factory=list)
    required: bool = False
    observed_in: int = Field(
        default=0, description="How many sample products carried this field."
    )
    sample_values: list[str] = Field(default_factory=list)
    rationale: str = ""


class CategoryProposal(BaseModel):
    """A new category the engine believes it should learn.

    Proposals are never applied automatically. An unreviewed schema would let a
    misread spec table silently become a validation rule for every future
    product, so a human approves before anything enters the taxonomy.
    """

    id: str
    status: Literal["pending", "approved", "rejected"] = "pending"
    code: str
    path: list[str]
    noun: str
    keywords: list[str] = Field(default_factory=list)
    attributes: list[ProposedAttribute] = Field(default_factory=list)
    required: list[str] = Field(default_factory=list)
    sample_count: int = 0
    sample_skus: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    method: str = ""
    rationale: str = ""
    created_at: float = 0.0
    reviewed_at: float | None = None
    reviewer_note: str | None = None

    def to_category(self) -> dict[str, Any]:
        """Render into the exact shape taxonomy.json uses."""
        attributes: dict[str, Any] = {}
        for attribute in self.attributes:
            spec: dict[str, Any] = {
                "label": attribute.label,
                "type": attribute.type,
                "group": attribute.group,
            }
            if attribute.unit:
                spec["unit"] = attribute.unit
            if attribute.values:
                spec["values"] = attribute.values
            if attribute.range:
                spec["range"] = attribute.range
            if attribute.aliases:
                spec["aliases"] = attribute.aliases
            attributes[attribute.key] = spec

        return {
            "code": self.code,
            "path": self.path,
            "noun": self.noun,
            "keywords": self.keywords,
            "required": self.required,
            "attributes": attributes,
            "cross_checks": [],
            "learned": True,
            "learned_from": {
                "proposal_id": self.id,
                "sample_count": self.sample_count,
                "method": self.method,
            },
        }


class EnrichRequest(BaseModel):
    product: RawProduct
    mode: Literal["demo", "live", "hybrid"] = "demo"
    api_key: str | None = Field(
        default=None,
        description="Caller-supplied Anthropic key. Never persisted to disk.",
    )


class BatchEnrichRequest(BaseModel):
    products: list[RawProduct]
    mode: Literal["demo", "live", "hybrid"] = "demo"
    api_key: str | None = None

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


class EnrichedProduct(BaseModel):
    input: RawProduct
    identity: dict[str, Any] = Field(default_factory=dict)
    category: CategoryAssignment | None = None
    attributes: list[Attribute] = Field(default_factory=list)
    content: CommerceContent | None = None
    issues: list[ValidationIssue] = Field(default_factory=list)
    readiness: ReadinessScore | None = None
    trace: list[StageTrace] = Field(default_factory=list)
    mode: str = "demo"
    cached: bool = False

    def attr(self, key: str) -> Attribute | None:
        return next((a for a in self.attributes if a.key == key), None)


class EnrichRequest(BaseModel):
    product: RawProduct
    mode: Literal["demo", "live"] = "demo"
    api_key: str | None = Field(
        default=None,
        description="Caller-supplied Anthropic key. Never persisted to disk.",
    )


class BatchEnrichRequest(BaseModel):
    products: list[RawProduct]
    mode: Literal["demo", "live"] = "demo"
    api_key: str | None = None

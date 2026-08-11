"""Discovery: from a brand and a part number to a sourced RawProduct.

This is the organizers' stated core problem — "take a manufacturer name and part
number and search manufacturer websites, catalogues and PDFs" — and §7.3
measures why it matters: 88 of 114 scored delivery fields come back blank from a
catalogue row alone, because the values only exist on the manufacturer's site.

**It produces a `RawProduct` and stops.** Everything after that is the existing
pipeline, unchanged: classification, extraction, unit normalisation, the sixteen
cross-field rules, the vocabulary stage, readiness scoring. A value found on a
manufacturer page earns exactly the same provenance and validation as one typed
into the form, which is the architectural rule the rest of this codebase already
follows. There is no separate "discovered product" path and there must not be.

**Every candidate is recorded, accepted or refused.** The ledger is the same
idea as the hybrid gate's: a system that only reports what it used cannot be
audited, and what it declined to use is the evidence that the sourcing rule is
real. A run that finds nothing returns its reasons rather than an empty result.

**Known limitation, measured rather than assumed:** the SKF product page returns
HTTP 200 with zero specifications because it renders its content in JavaScript.
A fetch-and-parse discovery layer cannot read pages like that, and this one
reports `fetched but no specifications found` rather than treating an empty page
as an absent product. Headless rendering would fix it and is not built.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from ..ingest import web
from ..models import RawProduct
from . import policy
from .search import Backend, Candidate, SearchOutcome, default_backend


@dataclass
class SourceRecord:
    """One candidate URL and what became of it."""

    url: str
    origin: str
    accepted: bool
    reason: str
    kind: str = ""
    fetched: bool = False
    status: int | None = None
    specs_found: int = 0
    title: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "origin": self.origin,
            "accepted": self.accepted,
            "reason": self.reason,
            "kind": self.kind,
            "fetched": self.fetched,
            "status": self.status,
            "specs_found": self.specs_found,
            "title": self.title,
        }


@dataclass
class DiscoveryResult:
    """What discovery found, and everything it refused on the way."""

    brand: str | None
    mpn: str | None
    product: RawProduct | None = None
    sources: list[SourceRecord] = field(default_factory=list)
    backend: str = ""
    spent_usd: float = 0.0
    duration_ms: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return self.product is not None

    @property
    def refused(self) -> list[SourceRecord]:
        return [s for s in self.sources if not s.accepted]

    def as_dict(self) -> dict[str, Any]:
        return {
            "brand": self.brand,
            "mpn": self.mpn,
            "found": self.found,
            "backend": self.backend,
            "spent_usd": round(self.spent_usd, 6),
            "duration_ms": self.duration_ms,
            "accepted": len([s for s in self.sources if s.accepted]),
            "refused": len(self.refused),
            "sources": [s.as_dict() for s in self.sources],
            "notes": self.notes,
            "policy_source": policy.source(),
        }


def discover(
    brand: str | None,
    mpn: str | None,
    *,
    backend: Backend | None = None,
    fetcher=None,
    max_pages: int = 3,
) -> DiscoveryResult:
    """Find and read the manufacturer's page for a part.

    `fetcher` exists so the whole path is testable without a network call; it
    defaults to the SSRF-guarded fetcher the document-ingest tab already uses.
    """
    started = time.perf_counter()
    backend = backend or default_backend()
    fetch = fetcher or web.from_url

    result = DiscoveryResult(brand=brand, mpn=mpn, backend=backend.name)

    outcome: SearchOutcome = backend.find(brand, mpn)
    result.spent_usd += outcome.cost_usd
    result.notes.extend(outcome.notes)

    if not outcome.candidates:
        result.notes.append(
            "No candidate source was produced, so nothing was fetched and nothing "
            "was invented. The record is left as the caller supplied it."
        )
        result.duration_ms = int((time.perf_counter() - started) * 1000)
        return result

    merged: RawProduct | None = None
    fetched = 0

    for candidate in outcome.candidates:
        verdict = policy.check(candidate.url, brand)
        record = SourceRecord(
            url=candidate.url,
            origin=candidate.origin,
            accepted=verdict.allowed,
            reason=verdict.reason,
            kind=verdict.kind,
            title=candidate.title,
        )

        if not verdict.allowed or fetched >= max_pages:
            if verdict.allowed:
                record.accepted = False
                record.reason = (
                    f"Within policy, but the per-product page budget of {max_pages} "
                    f"was already spent on higher-ranked sources."
                )
            result.sources.append(record)
            continue

        try:
            product, report = fetch(candidate.url)
            fetched += 1
            record.fetched = True
            record.status = getattr(report, "status", None)
            record.specs_found = len(product.raw_specs or {})
        except web.UnsafeURL as exc:
            record.accepted = False
            record.reason = f"Refused by the SSRF guard: {exc}"
            result.sources.append(record)
            continue
        except Exception as exc:  # noqa: BLE001 - a dead link is a normal outcome
            record.accepted = False
            record.reason = f"Fetch failed: {type(exc).__name__}: {exc}"
            result.sources.append(record)
            continue

        if not _is_useful(product):
            # An HTTP 200 with nothing in it is the JavaScript-rendered case. It
            # is not the same as "this product does not exist", and conflating
            # them would turn a tooling gap into a false claim about the part.
            record.reason = (
                f"Fetched successfully but nothing usable was parsed. The page is "
                f"likely rendered client-side, which this fetcher cannot read."
            )
            result.sources.append(record)
            continue

        merged = _merge(merged, product, candidate.url)
        result.sources.append(record)

    if merged is not None:
        merged.brand = merged.brand or brand
        merged.mpn = merged.mpn or mpn
        result.product = merged
        result.notes.append(
            f"Sourced {len(merged.raw_specs)} specification(s) from "
            f"{fetched} manufacturer page(s); every value carries the URL it was "
            f"read from."
        )
    else:
        result.notes.append(
            "No manufacturer page yielded specifications. Nothing was written to "
            "the record — a blank field is recoverable, a fabricated one is not."
        )

    result.duration_ms = int((time.perf_counter() - started) * 1000)
    return result


def _is_useful(product: RawProduct) -> bool:
    """Whether a fetched page told us anything worth keeping.

    A spec table is the prize, but it is not the only prize. Milwaukee's product
    markup publishes the canonical product name, the manufacturer, the brand and
    a weight and no spec table at all — and the canonical name is what makes
    classification work, which is the step that unlocks every downstream field.
    Requiring a spec table would have thrown that page away.
    """
    if product.raw_specs:
        return True
    return bool(product.name or product.description or product.brand)


def _merge(base: RawProduct | None, incoming: RawProduct, url: str) -> RawProduct:
    """Fold a fetched page into the record, first source winning per field.

    Sources are tried in rank order, so an earlier page is the better-trusted
    one. Its value stays, and the later page does not silently overwrite it.
    Every spec carries the URL it came from, which is what lets `Attribute`
    cite a per-value source later in the pipeline.
    """
    if base is None:
        base = incoming.model_copy(deep=True)
        base.source_url = base.source_url or url
        base.spec_sources = {key: url for key in (base.raw_specs or {})}
        return base

    for key, value in (incoming.raw_specs or {}).items():
        if key not in base.raw_specs:
            base.raw_specs[key] = value
            base.spec_sources[key] = url

    for attribute in ("name", "description", "free_text"):
        if not getattr(base, attribute, None) and getattr(incoming, attribute, None):
            setattr(base, attribute, getattr(incoming, attribute))

    return base


def enrich_from_discovery(
    brand: str | None,
    mpn: str | None,
    provider,
    *,
    backend: Backend | None = None,
    fetcher=None,
    base: RawProduct | None = None,
):
    """Discover, then run the ordinary pipeline over what was found.

    Returns (EnrichedProduct, DiscoveryResult). When discovery finds nothing the
    caller still gets a record built from the input it already had, so the tab
    degrades to the existing behaviour rather than failing.
    """
    from ..pipeline.run import enrich

    result = discover(brand, mpn, backend=backend, fetcher=fetcher)

    product = result.product
    if product is None:
        product = (base or RawProduct()).model_copy(deep=True)
        product.brand = product.brand or brand
        product.mpn = product.mpn or mpn
    elif base is not None:
        # Anything the caller supplied outranks anything discovered: they know
        # their own catalogue better than a web page does.
        for key, value in (base.raw_specs or {}).items():
            product.raw_specs[key] = value
        product.sku = base.sku or product.sku
        product.description = base.description or product.description

    return enrich(product, provider), result

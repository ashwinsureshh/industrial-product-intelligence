"""Finding candidate URLs for a part. Two backends, and the free one is default.

Discovery splits cleanly into "where might this part be documented" and "what
does that page say". Only the first half needs a search engine, and often not
even that:

  * `BrandDomainBackend` — **$0**. Where a manufacturer's product URL is
    predictable from the part number, the registry's template produces it
    directly. Their own delivery row cites
    `frigidaire.com/en/p/owner-center/product-support/PDSH4816AF`, which is a
    template with the MPN in it. No search engine involved.

  * `ClaudeWebSearchBackend` — **costs money per SKU**. For the brands whose
    URLs are not predictable. It is never selected by default and cannot be
    constructed without an explicit key.

The split matters for the cost model in §7.05: the free backend covers the
predictable cases, so paid search is a fallback rather than a per-SKU floor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from . import policy


@dataclass
class Candidate:
    """One URL worth considering, and where the idea came from."""

    url: str
    origin: str              # brand_template | web_search | supplied
    title: str = ""
    snippet: str = ""


@dataclass
class SearchOutcome:
    candidates: list[Candidate] = field(default_factory=list)
    cost_usd: float = 0.0
    notes: list[str] = field(default_factory=list)
    backend: str = ""


class Backend(Protocol):
    name: str
    spends: bool

    def find(self, brand: str | None, mpn: str | None) -> SearchOutcome: ...


class BrandDomainBackend:
    """Build official-site URLs from the approved brand-domain registry. $0."""

    name = "brand-domain"
    spends = False

    def find(self, brand: str | None, mpn: str | None) -> SearchOutcome:
        outcome = SearchOutcome(backend=self.name)
        entry = policy.brand_entry(brand)

        if not brand:
            outcome.notes.append(
                "No brand supplied, so there is no manufacturer site to look on. "
                "Discovery needs a brand as well as a part number."
            )
            return outcome
        if entry is None:
            outcome.notes.append(
                f"'{brand}' is not in the approved manufacturer registry, so its "
                f"official domain is unknown and no page can be cited as "
                f"manufacturer-provided. Add the brand to sources.json, or use a "
                f"search backend."
            )
            return outcome
        if not mpn:
            outcome.notes.append(
                f"{entry['brand']} is a known manufacturer, but a product URL "
                f"cannot be built without a part number."
            )
            return outcome

        urls = policy.candidate_urls(brand, mpn)
        if not urls:
            outcome.notes.append(
                f"{entry['brand']} has no URL template in the registry — its "
                f"product URLs are not derivable from the part number. A search "
                f"backend is required for this brand."
            )
            return outcome

        outcome.candidates = [
            Candidate(url=url, origin="brand_template",
                      title=f"{entry['brand']} {mpn} on the manufacturer's site")
            for url in urls
        ]
        return outcome


class ClaudeWebSearchBackend:
    """Ask Claude to search the web for the manufacturer's page. SPENDS MONEY.

    Its citations are the reason to prefer it over a bare search API: the model
    returns the URLs it actually read, which is precisely the per-value source
    the brief demands three times over.

    Every result still goes through `policy.check`. The model is not trusted to
    honour the no-marketplace rule — a search for a part number returns Amazon
    first far more often than not, and the policy is what makes that harmless.
    """

    name = "claude-web-search"
    spends = True

    # Published rate for the server-side web search tool, per 1,000 searches.
    SEARCH_RATE_USD = 10.0 / 1000

    def __init__(self, api_key: str, model: str | None = None, max_uses: int = 3) -> None:
        if not api_key:
            raise ValueError(
                "ClaudeWebSearchBackend needs an API key. It is never constructed "
                "implicitly, because constructing it is what makes a run cost money."
            )
        from ..config import MODEL

        self._api_key = api_key
        self._model = model or MODEL
        self._max_uses = max_uses

    def find(self, brand: str | None, mpn: str | None) -> SearchOutcome:
        outcome = SearchOutcome(backend=self.name)
        if not (brand and mpn):
            outcome.notes.append("Both a brand and a part number are needed to search.")
            return outcome

        from anthropic import Anthropic

        allowed = policy.brand_entry(brand)
        domains = list(allowed.get("domains", [])) if allowed else []

        tool: dict = {
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": self._max_uses,
        }
        # Constrain the search itself where we can, so spend is not wasted
        # fetching pages the policy will refuse anyway.
        if domains:
            tool["allowed_domains"] = domains
        else:
            tool["blocked_domains"] = [b["domain"] for b in _blocked_domains()]

        message = Anthropic(api_key=self._api_key).messages.create(
            model=self._model,
            max_tokens=1024,
            tools=[tool],
            messages=[{
                "role": "user",
                "content": (
                    f"Find the official manufacturer product page or datasheet for "
                    f"{brand} part number {mpn}. Only the manufacturer's own site "
                    f"or documentation. Do not use marketplaces, retailers or "
                    f"distributors. Reply with the URLs only."
                ),
            }],
        )

        outcome.candidates = _citations(message)
        outcome.cost_usd = self._estimate(message)
        if not outcome.candidates:
            outcome.notes.append(
                f"Search returned no citation for {brand} {mpn} on its own domains."
            )
        return outcome

    def _estimate(self, message) -> float:
        """Search charges plus tokens, so the ledger can carry a real number."""
        usage = getattr(message, "usage", None)
        searches = getattr(usage, "server_tool_use", None)
        count = getattr(searches, "web_search_requests", 0) or 0
        # Standard Sonnet rates; the introductory ones lapse before judging.
        tokens = (
            (getattr(usage, "input_tokens", 0) or 0) / 1e6 * 3.0
            + (getattr(usage, "output_tokens", 0) or 0) / 1e6 * 15.0
        )
        return round(count * self.SEARCH_RATE_USD + tokens, 6)


def _blocked_domains() -> list[dict]:
    from .policy import _config

    return _config().get("blocked", [])


def _citations(message) -> list[Candidate]:
    """Pull the URLs the model actually read out of the response."""
    found: dict[str, Candidate] = {}
    for block in getattr(message, "content", []) or []:
        for citation in getattr(block, "citations", None) or []:
            url = getattr(citation, "url", None)
            if url and url not in found:
                found[url] = Candidate(
                    url=url,
                    origin="web_search",
                    title=getattr(citation, "title", "") or "",
                    snippet=(getattr(citation, "cited_text", "") or "")[:200],
                )
        # Search-result blocks carry URLs even when nothing was quoted.
        for result in getattr(block, "content", None) or []:
            url = getattr(result, "url", None)
            if url and url not in found:
                found[url] = Candidate(
                    url=url, origin="web_search",
                    title=getattr(result, "title", "") or "",
                )
    return list(found.values())


def default_backend() -> Backend:
    """The one used unless a caller deliberately asks for the paid path."""
    return BrandDomainBackend()

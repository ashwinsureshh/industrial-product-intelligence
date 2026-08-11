"""Which sources may be cited, and why the rest are refused.

The organizers state the rule three separate times: product data must come from
the manufacturer's own site or documentation, and marketplaces are excluded.
This module is that rule, made checkable.

Two decisions are stronger than a naive reading of the brief, and both are
deliberate.

**Distributors and retailers are blocked alongside marketplaces.** Their brief
names Amazon and eBay, but a Grainger or Home Depot listing is the same failure
in a more respectable font: a second-hand copy of the manufacturer's data,
which is exactly where catalogue errors come from. Unilog's whole business is
correcting that copy, so sourcing from it would be circular.

**An unknown domain is refused, not fetched.** Allowing anything not explicitly
blocked would be the easy default and it inverts the rule — a blog, a reseller
or a scraper farm would silently become a cited source. A page can only be
called manufacturer-provided if the domain can be shown to belong to the
manufacturer, so the brand-to-domain registry is the gate. Where a brand is not
in the registry, discovery reports that it cannot proceed rather than guessing.

That last choice is what keeps the source URL meaningful. A citation nobody
checked is decoration; a citation the engine refused to make is evidence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from urllib.parse import urlparse

from ..config import DATA_DIR

DISCOVERY_DIR = DATA_DIR / "discovery"


@dataclass(frozen=True)
class Verdict:
    """Whether one URL may be used as a source."""

    allowed: bool
    reason: str
    kind: str = ""          # marketplace / distributor / manufacturer / unknown
    brand: str | None = None


@lru_cache(maxsize=1)
def _config() -> dict[str, Any]:
    path = DISCOVERY_DIR / "sources.json"
    if not path.exists():
        return {"source": "missing", "blocked": [], "manufacturers": [], "policy": {}}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def invalidate() -> None:
    _config.cache_clear()
    _blocked.cache_clear()
    _by_domain.cache_clear()
    _by_brand.cache_clear()


def source() -> str:
    return _config().get("source", "unknown")


@lru_cache(maxsize=1)
def _blocked() -> dict[str, str]:
    return {
        str(entry["domain"]).lower(): str(entry.get("kind", "blocked"))
        for entry in _config().get("blocked", [])
    }


@lru_cache(maxsize=1)
def _by_domain() -> dict[str, dict[str, Any]]:
    table: dict[str, dict[str, Any]] = {}
    for entry in _config().get("manufacturers", []):
        for domain in entry.get("domains", []):
            table[str(domain).lower()] = entry
    return table


@lru_cache(maxsize=1)
def _by_brand() -> dict[str, dict[str, Any]]:
    return {
        str(entry["brand"]).strip().lower(): entry
        for entry in _config().get("manufacturers", [])
    }


def _registrable(host: str) -> list[str]:
    """Every suffix of a host, so 'www.shop.amazon.com' matches 'amazon.com'."""
    parts = host.lower().strip(".").split(".")
    return [".".join(parts[i:]) for i in range(len(parts))]


def brand_entry(brand: str | None) -> dict[str, Any] | None:
    if not brand:
        return None
    return _by_brand().get(brand.strip().lower())


def known_brands() -> list[str]:
    return sorted(e["brand"] for e in _config().get("manufacturers", []))


def check(url: str, brand: str | None = None) -> Verdict:
    """Decide whether a URL may be cited as a source."""
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in ("http", "https"):
        return Verdict(False, f"Only http(s) sources are fetched; got '{parsed.scheme or 'no scheme'}'.")

    host = (parsed.hostname or "").lower()
    if not host:
        return Verdict(False, "No host in the URL.")

    suffixes = _registrable(host)

    blocked = _blocked()
    for suffix in suffixes:
        if suffix in blocked:
            kind = blocked[suffix]
            return Verdict(
                False,
                f"{suffix} is a {kind}. The content standard requires "
                f"manufacturer-provided sources, so {kind}s are excluded.",
                kind=kind,
            )

    registry = _by_domain()
    for suffix in suffixes:
        if suffix in registry:
            entry = registry[suffix]
            # A domain belonging to a *different* manufacturer is not a source
            # for this product, even though it is somebody's official site.
            if brand and brand_entry(brand) and entry is not brand_entry(brand):
                return Verdict(
                    False,
                    f"{suffix} is the official site of {entry['brand']}, not of "
                    f"'{brand}'. A manufacturer page for the wrong manufacturer "
                    f"is not evidence about this part.",
                    kind="manufacturer",
                    brand=entry["brand"],
                )
            return Verdict(
                True,
                f"{suffix} is the approved domain for {entry['brand']} "
                f"({entry.get('manufacturer', entry['brand'])}).",
                kind="manufacturer",
                brand=entry["brand"],
            )

    if _config().get("policy", {}).get("allow_unknown_domains"):
        return Verdict(True, f"{host} is not blocked, and unknown domains are permitted.",
                       kind="unknown")

    return Verdict(
        False,
        f"{host} is not a known manufacturer domain. It cannot be cited as a "
        f"manufacturer-provided source, so it was not fetched.",
        kind="unknown",
    )


def candidate_urls(brand: str | None, mpn: str | None) -> list[str]:
    """Official-site URLs to try for a part, from the registry's templates.

    This is the free half of discovery: where a manufacturer's product URL is
    predictable from the part number, no search engine is needed to find it.
    """
    entry = brand_entry(brand)
    if not entry or not mpn:
        return []
    part = str(mpn).strip()
    return [t.format(mpn=part) for t in entry.get("url_templates", []) if t]

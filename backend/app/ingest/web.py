"""Turn a supplier product page into a RawProduct.

Extraction runs in descending order of reliability:

  1. JSON-LD `Product` markup (schema.org). When a site publishes it, this is
     authoritative — the merchant is telling you the SKU, brand and MPN
     directly rather than you inferring them from rendered text.
  2. Spec tables and definition lists, the usual home of technical attributes.
  3. Meta tags and headings for identity fields the above missed.
  4. Whatever readable text remains, kept as free text.

Fetching a caller-supplied URL from the server is an SSRF surface, so the
fetcher refuses non-HTTP schemes and addresses that resolve to private or
loopback ranges.
"""

from __future__ import annotations

import ipaddress
import json
import re
import socket
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from ..models import RawProduct

MAX_KEY_CHARS = 48
MAX_VALUE_CHARS = 160
MAX_BYTES = 4_000_000
FETCH_TIMEOUT = 15.0

_SKIP_TAGS = {"script", "style", "noscript", "nav", "footer", "header",
              "form", "svg", "iframe", "template"}

# Built by concatenation: the label charset contains '%', which %-formatting
# would try to read as a conversion specifier.
_LIST_PAIR = re.compile(
    r"^([A-Za-z][A-Za-z0-9 ()/µ°%,+-]{1," + str(MAX_KEY_CHARS) + r"}?)"
    r"\s*:\s+(\S.{0," + str(MAX_VALUE_CHARS) + r"})$"
)


@dataclass
class WebIngestReport:
    source: str
    status: int | None = None
    spec_pairs: int = 0
    tables_found: int = 0
    text_chars: int = 0
    strategies_used: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "status": self.status,
            "spec_pairs": self.spec_pairs,
            "tables_found": self.tables_found,
            "text_chars": self.text_chars,
            "strategies_used": self.strategies_used,
            "notes": self.notes,
        }


class UnsafeURL(ValueError):
    """The URL is not something the server should be made to fetch."""


def _clean(text: Any) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\xa0", " ").split()).strip()


def assert_fetchable(url: str) -> None:
    """Block non-HTTP schemes and anything resolving inside the network."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeURL("Only http and https URLs can be fetched.")
    if not parsed.hostname:
        raise UnsafeURL("The URL has no host.")

    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as exc:
        raise UnsafeURL(f"Could not resolve {parsed.hostname}.") from exc

    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if (address.is_private or address.is_loopback or address.is_link_local
                or address.is_reserved or address.is_multicast):
            raise UnsafeURL(
                f"{parsed.hostname} resolves to a non-public address "
                f"({address}); refusing to fetch."
            )


def _from_json_ld(soup) -> dict[str, Any]:
    """Read schema.org Product markup, the most trustworthy source available."""
    found: dict[str, Any] = {}

    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            payload = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        # A page may publish a bare object, a list, or an @graph wrapper.
        candidates = payload if isinstance(payload, list) else [payload]
        if isinstance(payload, dict) and "@graph" in payload:
            candidates = payload["@graph"]

        for node in candidates:
            if not isinstance(node, dict):
                continue
            types = node.get("@type", "")
            types = types if isinstance(types, list) else [types]
            if not any(str(t).lower() == "product" for t in types):
                continue

            found.setdefault("name", _clean(node.get("name")))
            found.setdefault("sku", _clean(node.get("sku")))
            found.setdefault("mpn", _clean(node.get("mpn")))
            found.setdefault("description", _clean(node.get("description")))

            brand = node.get("brand")
            if isinstance(brand, dict):
                brand = brand.get("name")
            found.setdefault("brand", _clean(brand))

            offers = node.get("offers")
            offers = offers[0] if isinstance(offers, list) and offers else offers
            if isinstance(offers, dict):
                try:
                    found.setdefault("price", float(offers.get("price")))
                except (TypeError, ValueError):
                    pass
                found.setdefault("currency", _clean(offers.get("priceCurrency")))

            specs: dict[str, str] = {}
            for prop in node.get("additionalProperty", []) or []:
                if isinstance(prop, dict):
                    key, value = _clean(prop.get("name")), _clean(prop.get("value"))
                    if key and value:
                        specs[key] = value
            if specs:
                found.setdefault("raw_specs", specs)

    return {k: v for k, v in found.items() if v not in ("", None)}


def _looks_like_spec(key: str, value: str) -> bool:
    if not key or not value:
        return False
    if len(key) < 2 or len(key) > MAX_KEY_CHARS or len(value) > MAX_VALUE_CHARS:
        return False
    if len(key.split()) > 6 or key.endswith((".", "?", "!")):
        return False
    # A real label carries letters; a bare number means a misread layout.
    if len(re.findall(r"[A-Za-z]", key)) < 2:
        return False
    return True


def _from_tables(soup, report: WebIngestReport) -> dict[str, str]:
    specs: dict[str, str] = {}

    for table in soup.find_all("table"):
        rows_added = 0
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) < 2:
                continue
            key, value = _clean(cells[0].get_text()), _clean(cells[1].get_text())
            if _looks_like_spec(key, value) and key not in specs:
                specs[key] = value
                rows_added += 1
        if rows_added:
            report.tables_found += 1
            if "html:table" not in report.strategies_used:
                report.strategies_used.append("html:table")

    # Definition lists are the other common spec container.
    for dl in soup.find_all("dl"):
        terms = dl.find_all("dt")
        definitions = dl.find_all("dd")
        for term, definition in zip(terms, definitions):
            key, value = _clean(term.get_text()), _clean(definition.get_text())
            if _looks_like_spec(key, value) and key not in specs:
                specs[key] = value
                if "html:deflist" not in report.strategies_used:
                    report.strategies_used.append("html:deflist")

    # "Label: value" bullets, common on smaller supplier sites.
    for item in soup.find_all("li"):
        text = _clean(item.get_text())
        m = _LIST_PAIR.match(text)
        if m:
            key, value = _clean(m.group(1)), _clean(m.group(2))
            if _looks_like_spec(key, value) and key not in specs:
                specs[key] = value
                if "html:list" not in report.strategies_used:
                    report.strategies_used.append("html:list")

    return specs


def _meta(soup, *names: str) -> str | None:
    for name in names:
        for attr in ("property", "name", "itemprop"):
            tag = soup.find("meta", attrs={attr: name})
            if tag and tag.get("content"):
                return _clean(tag["content"])
    return None


def from_html(
    html: str, url: str = "", status: int | None = None
) -> tuple[RawProduct, WebIngestReport]:
    """Parse an already-fetched product page."""
    from bs4 import BeautifulSoup

    report = WebIngestReport(source=url or "pasted HTML", status=status)
    soup = BeautifulSoup(html, "lxml")

    structured = _from_json_ld(soup)
    if structured:
        report.strategies_used.append("json-ld:Product")

    specs: dict[str, str] = dict(structured.pop("raw_specs", {}) or {})
    specs.update({k: v for k, v in _from_tables(soup, report).items() if k not in specs})

    for tag in soup.find_all(_SKIP_TAGS):
        tag.decompose()
    body_text = _clean(soup.get_text(" "))

    heading = soup.find(["h1", "h2"])
    name = (structured.get("name")
            or _meta(soup, "og:title", "twitter:title")
            or (_clean(heading.get_text()) if heading else None))

    description = (structured.get("description")
                   or _meta(soup, "og:description", "description"))

    report.spec_pairs = len(specs)
    report.text_chars = len(body_text)
    if not specs:
        report.notes.append(
            "No spec table found on the page; the readable text was passed "
            "through for pattern extraction instead."
        )

    product = RawProduct(
        sku=structured.get("sku"),
        mpn=structured.get("mpn"),
        brand=structured.get("brand") or _meta(soup, "product:brand", "brand"),
        name=name,
        description=description,
        price=structured.get("price"),
        currency=structured.get("currency"),
        raw_specs=specs,
        free_text=body_text[:20000] or None,
        source_url=url or None,
        source_document=url or None,
    )
    return product, report


def from_url(url: str) -> tuple[RawProduct, WebIngestReport]:
    """Fetch and parse a product page, refusing unsafe targets."""
    import httpx

    assert_fetchable(url)
    with httpx.Client(follow_redirects=True, timeout=FETCH_TIMEOUT) as client:
        response = client.get(
            url,
            headers={"User-Agent": "ProductIntelligence/1.0 (catalog enrichment)"},
        )
        response.raise_for_status()
        body = response.text[:MAX_BYTES]

    return from_html(body, url=url, status=response.status_code)

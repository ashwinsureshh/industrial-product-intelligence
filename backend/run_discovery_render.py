"""Measure headless rendering against the four sites §7.5 already tried.

    python run_discovery_render.py

§7.5's result was zero of four: Frigidaire, Milwaukee and SKF all return HTTP
200 and then build their content in JavaScript, and Whirlpool's URL template was
simply wrong. This runs the same four URLs twice — once with the plain fetch the
deployment uses, once through a real browser — and reports both, so the change
is a measurement rather than a claim.

Costs nothing: public pages, no API key, no model call.
"""
from __future__ import annotations

import sys
import time

from app.discovery import policy, render
from app.ingest import web

CASES = [
    ("FRIGIDAIRE", "PDSH4816AF"),
    ("Milwaukee", "49-94-0107"),
    ("SKF", "6205-2RS"),
    ("Whirlpool", "WDT750SAKZ"),
]


def probe(brand: str, mpn: str) -> dict:
    urls = policy.candidate_urls(brand, mpn)
    if not urls:
        return {"brand": brand, "url": "(no template in the registry)",
                "plain": None, "rendered": None}

    url = urls[0]
    row: dict = {"brand": brand, "url": url}
    for label, fetcher in (("plain", web.from_url), ("rendered", render.fetch)):
        started = time.perf_counter()
        try:
            product, report = fetcher(url)
            row[label] = {
                "status": getattr(report, "status", None),
                "specs": len(product.raw_specs or {}),
                "name": (product.name or "")[:38],
                "mpn": product.mpn,
                "seconds": time.perf_counter() - started,
            }
        except Exception as exc:  # noqa: BLE001 - a dead link is a result
            row[label] = {"error": f"{type(exc).__name__}", "seconds":
                          time.perf_counter() - started}
    return row


def cell(result: dict | None) -> str:
    if result is None:
        return "—"
    if "error" in result:
        return f"{result['error']} ({result['seconds']:.1f}s)"
    return (f"HTTP {result['status']} · {result['specs']} specs "
            f"({result['seconds']:.1f}s)")


def main() -> int:
    if not render.available():
        print("No browser available. Install one with: playwright install chromium")
        return 1

    print("=" * 78)
    print("  HEADLESS RENDERING vs PLAIN FETCH — the four sites from §7.5")
    print("=" * 78)
    rows = [probe(brand, mpn) for brand, mpn in CASES]

    print(f"\n  {'BRAND':<12} {'PLAIN FETCH':<26} {'RENDERED':<26}")
    for row in rows:
        print(f"  {row['brand']:<12} {cell(row.get('plain')):<26} "
              f"{cell(row.get('rendered')):<26}")

    def won(row) -> bool:
        plain = row.get("plain") or {}
        rendered = row.get("rendered") or {}
        return rendered.get("specs", 0) > plain.get("specs", 0)

    plain_ok = sum(1 for r in rows if (r.get("plain") or {}).get("specs", 0) > 0)
    rendered_ok = sum(1 for r in rows if (r.get("rendered") or {}).get("specs", 0) > 0)

    print(f"\n  sites yielding a spec table:  plain {plain_ok}/4   "
          f"rendered {rendered_ok}/4")
    improved = [r["brand"] for r in rows if won(r)]
    print(f"  rendering recovered: {', '.join(improved) if improved else 'nothing'}")

    for row in rows:
        detail = row.get("rendered") or {}
        if detail.get("specs"):
            print(f"\n  {row['brand']} — {detail['specs']} specs, "
                  f"name {detail['name']!r}, mpn {detail['mpn']!r}")
    print("\n  Report whichever number this prints. A negative result is still a"
          "\n  measurement, and the honest ceiling is worth more than a hopeful one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

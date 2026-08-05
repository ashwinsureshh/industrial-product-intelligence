"""Pre-compute live-mode results for the demo products, once.

Judging is asynchronous: reviewers open the deployed link with no API key of
their own. Without this, selecting "Live AI" degrades to the deterministic
engine and the model path is invisible to exactly the audience that needs to
see it. Running it here, once, ships genuine Claude output in the repository so
the deployed app can serve it to anyone at zero cost.

    python precompute_demo.py --budget 1.50

Spend is measured after every product and the run aborts the moment it crosses
the ceiling. Products already present are skipped, so a re-run is free.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from app import cache
from app.config import DATA_DIR, MODEL
from app.models import RawProduct
from app.pipeline import run as pipeline
from run_benchmark import PRICE_NOTE, cost_usd


def collect() -> list[tuple[str, RawProduct]]:
    """The products a reviewer can actually click on: demo cases and catalog."""
    with open(DATA_DIR / "samples.json", encoding="utf-8") as fh:
        data = json.load(fh)

    products: list[tuple[str, RawProduct]] = []
    for sample in data.get("samples", []):
        products.append((sample["id"], RawProduct(**sample["product"])))
    for row in data.get("batch_demo", []):
        products.append((row.get("sku", "batch"), RawProduct(**row)))
    return products


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget", type=float, default=1.50,
                        help="Hard ceiling in USD; aborts the moment it is crossed.")
    parser.add_argument("--dry-run", action="store_true",
                        help="List what would be computed without calling the API.")
    args = parser.parse_args()

    key = os.getenv("ANTHROPIC_API_KEY")
    if not key and not args.dry_run:
        print("ANTHROPIC_API_KEY is not set (put it in backend/.env).")
        return 1

    products = collect()
    pending = [
        (name, product) for name, product in products
        if cache.get(product.model_dump(exclude_none=True), "live") is None
    ]

    print(f"{len(products)} demo products, {len(pending)} not yet computed.")
    print(f"Model: {MODEL} · {PRICE_NOTE}")
    if args.dry_run:
        for name, _ in pending:
            print(f"  would compute: {name}")
        return 0
    if not pending:
        print("Nothing to do — all demo products already have bundled results.")
        return 0

    from app.providers.anthropic_provider import AnthropicProvider

    providers: list[AnthropicProvider] = []

    def spent() -> float:
        return cost_usd(
            sum(p._usage["input_tokens"] for p in providers),
            sum(p._usage["output_tokens"] for p in providers),
        )

    written = 0
    for index, (name, product) in enumerate(pending, start=1):
        provider = AnthropicProvider(key)
        providers.append(provider)

        result = pipeline.enrich(product, provider)
        payload = product.model_dump(exclude_none=True)
        cache.put_bundled(payload, "live", result.model_dump(mode="json"))
        written += 1

        print(f"  [{index}/{len(pending)}] {name:22} "
              f"{len(result.attributes):2} attrs  "
              f"{result.readiness.overall:5}/100 {result.readiness.verdict:8} "
              f"${spent():.3f}", flush=True)

        if spent() > args.budget:
            print(f"\nSTOPPING: ${spent():.2f} crossed the ${args.budget:.2f} ceiling.")
            print(f"{written} product(s) written; re-running resumes from here for free.")
            return 2

    print(f"\nWrote {written} bundled result(s). Total spend: ${spent():.2f}")
    print("These ship in the repository so reviewers see real model output "
          "without an API key.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

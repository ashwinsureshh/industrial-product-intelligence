"""HTTP API for the product intelligence engine."""

from __future__ import annotations

import csv
import io
import json
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from . import cache
from .config import (
    ALLOW_LIVE,
    APP_DIR,
    ALLOW_SERVER_KEY_FALLBACK,
    CORS_ORIGINS,
    DATA_DIR,
    MODEL,
    SERVER_API_KEY,
)
from .models import BatchEnrichRequest, EnrichedProduct, EnrichRequest, RawProduct
from .pipeline import run as pipeline
from .pipeline import taxonomy
from .providers.base import Provider
from .providers.mock import MockProvider

app = FastAPI(
    title="Industrial Product Intelligence API",
    version="1.0.0",
    description=(
        "Transforms sparse supplier product data into validated, explainable, "
        "commerce-ready product records."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in CORS_ORIGINS if o.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_BATCH = 250
BATCH_WORKERS = 8

# Classification confidence below which a product is treated as uncategorised
# for learning purposes, and a new category is proposed instead.
PROPOSE_BELOW_CONFIDENCE = 0.65


# --------------------------------------------------------------------- provider


def _resolve_provider(mode: str, api_key: str | None) -> tuple[Provider, str | None]:
    """Pick a provider, degrading to demo mode rather than failing the request.

    Returns the provider plus an optional warning explaining any downgrade, so
    the UI can be honest about which engine actually ran.
    """
    if mode != "live":
        return MockProvider(), None

    if not ALLOW_LIVE:
        return MockProvider(), (
            "Live mode is disabled on this deployment; the request ran in demo mode."
        )

    key = api_key or (SERVER_API_KEY if ALLOW_SERVER_KEY_FALLBACK else None)
    if not key:
        return MockProvider(), (
            "Live mode needs an Anthropic API key. Supply your own key in the "
            "request and it will be used for that call only — it is never stored. "
            "This request ran in demo mode."
        )

    try:
        from .providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider(key), None
    except Exception as exc:  # noqa: BLE001 - surface any setup failure to the caller
        return MockProvider(), f"Live provider unavailable ({exc}); ran in demo mode."


def _cache_payload(product: RawProduct) -> dict[str, Any]:
    return product.model_dump(exclude_none=True)


def _enrich_one(product: RawProduct, mode: str, api_key: str | None) -> EnrichedProduct:
    payload = _cache_payload(product)
    hit = cache.get(payload, mode)
    if hit is not None:
        result = EnrichedProduct.model_validate(hit)
        result.cached = True
        return result

    provider, warning = _resolve_provider(mode, api_key)
    result = pipeline.enrich(product, provider)

    if warning:
        result.trace.insert(
            0,
            pipeline.StageTrace(stage="provider", summary=warning),
        )

    # Only cache what actually ran; a downgraded live call caches as demo.
    cache.put(payload, result.mode if result.mode == "demo" else mode,
              result.model_dump(mode="json"))
    return result


# ---------------------------------------------------------------------- routes


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "model": MODEL,
        "live_mode_allowed": ALLOW_LIVE,
        "server_key_configured": bool(SERVER_API_KEY),
        "server_key_fallback": ALLOW_SERVER_KEY_FALLBACK,
        "categories": len(taxonomy.categories()),
        "cache": cache.stats(),
    }


@app.get("/api/taxonomy")
def get_taxonomy() -> dict[str, Any]:
    """Expose the taxonomy so the UI can explain what the engine knows."""
    return {
        "version": taxonomy.load_taxonomy()["version"],
        "categories": [
            {
                "code": c["code"],
                "path": c["path"],
                "attribute_count": len(c.get("attributes", {})),
                "required": c.get("required", []),
                "cross_checks": len(c.get("cross_checks", [])),
                "attributes": [
                    {
                        "key": k,
                        "label": s.get("label", k),
                        "type": s.get("type", "text"),
                        "unit": s.get("unit"),
                        "group": s.get("group", "General"),
                        "values": s.get("values"),
                    }
                    for k, s in c.get("attributes", {}).items()
                ],
            }
            for c in taxonomy.categories()
        ],
        "brands": sorted({b["canonical"] for b in taxonomy.brand_index().values()}),
    }


@app.get("/api/samples")
def samples() -> dict[str, Any]:
    with open(DATA_DIR / "samples.json", encoding="utf-8") as fh:
        return json.load(fh)


@app.post("/api/enrich", response_model=EnrichedProduct)
def enrich(request: EnrichRequest = Body(...)) -> EnrichedProduct:
    return _enrich_one(request.product, request.mode, request.api_key)


@app.post("/api/enrich/batch")
def enrich_batch(request: BatchEnrichRequest = Body(...)) -> dict[str, Any]:
    """Catalog-scale path: fan out across a thread pool, summarize the run."""
    if not request.products:
        raise HTTPException(status_code=400, detail="No products supplied.")
    if len(request.products) > MAX_BATCH:
        raise HTTPException(
            status_code=413,
            detail=f"Batch of {len(request.products)} exceeds the {MAX_BATCH} product limit.",
        )

    started = time.perf_counter()
    workers = min(BATCH_WORKERS, len(request.products))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(
            pool.map(
                lambda p: _enrich_one(p, request.mode, request.api_key),
                request.products,
            )
        )

    return {"results": results, "summary": _summarize(results, started)}


@app.post("/api/enrich/csv")
async def enrich_csv(
    file: UploadFile = File(...),
    mode: str = Form("demo"),
    api_key: str | None = Form(None),
) -> dict[str, Any]:
    """Bulk ingest.

    Recognised columns map onto the input model; every other column is treated
    as a supplier spec, which is the only assumption that survives contact with
    real catalog exports.
    """
    if not file.filename or not file.filename.lower().endswith((".csv", ".txt")):
        raise HTTPException(status_code=400, detail="Please upload a .csv file.")

    body = (await file.read()).decode("utf-8-sig", errors="replace")
    try:
        rows = list(csv.DictReader(io.StringIO(body)))
    except csv.Error as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse the CSV: {exc}") from exc

    if not rows:
        raise HTTPException(status_code=400, detail="The CSV contained no data rows.")
    if len(rows) > MAX_BATCH:
        raise HTTPException(
            status_code=413,
            detail=f"{len(rows)} rows exceeds the {MAX_BATCH} row limit for one upload.",
        )

    known = {"sku", "mpn", "brand", "name", "description", "category_hint",
             "price", "currency", "source_url", "free_text"}
    products: list[RawProduct] = []
    for row in rows:
        fields: dict[str, Any] = {}
        specs: dict[str, Any] = {}
        for raw_key, value in row.items():
            if raw_key is None or value in (None, ""):
                continue
            key = raw_key.strip().lower().replace(" ", "_")
            if key in known:
                fields[key] = value.strip()
            else:
                specs[raw_key.strip()] = value.strip()

        if fields.get("price"):
            try:
                fields["price"] = float(str(fields["price"]).replace(",", ""))
            except ValueError:
                specs["price_raw"] = fields.pop("price")

        products.append(RawProduct(**fields, raw_specs=specs))

    started = time.perf_counter()
    workers = min(BATCH_WORKERS, len(products))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda p: _enrich_one(p, mode, api_key), products))

    return {
        "results": results,
        "summary": _summarize(results, started),
        "source": {"filename": file.filename, "rows": len(rows)},
    }


def _summarize(results: list[EnrichedProduct], started: float) -> dict[str, Any]:
    total = len(results) or 1
    verdicts = {"publish": 0, "review": 0, "blocked": 0}
    for r in results:
        if r.readiness:
            verdicts[r.readiness.verdict] += 1

    scores = [r.readiness.overall for r in results if r.readiness]
    attribute_total = sum(len(r.attributes) for r in results)
    supplied_total = sum(
        len([a for a in r.attributes if a.provenance.value in ("supplied", "parsed")])
        for r in results
    )

    return {
        "count": len(results),
        "verdicts": verdicts,
        "avg_readiness": round(sum(scores) / len(scores), 1) if scores else 0.0,
        "avg_attributes": round(attribute_total / total, 1),
        "attributes_added": attribute_total - supplied_total,
        "issues": sum(len(r.issues) for r in results),
        "cached": sum(1 for r in results if r.cached),
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
    }


@app.post("/api/export/csv")
def export_csv(results: list[EnrichedProduct] = Body(...)) -> StreamingResponse:
    """Flatten enriched records into a catalog-import-shaped CSV."""
    if not results:
        raise HTTPException(status_code=400, detail="Nothing to export.")

    attribute_keys: list[str] = []
    for r in results:
        for a in r.attributes:
            if a.key not in attribute_keys:
                attribute_keys.append(a.key)

    base = ["sku", "mpn", "brand", "category_code", "category_path", "title",
            "short_description", "long_description", "bullets", "keywords",
            "readiness", "verdict", "errors", "warnings"]
    # Each attribute ships with its provenance so downstream systems inherit the audit trail.
    header = base + [c for k in attribute_keys for c in (k, f"{k}__provenance", f"{k}__confidence")]

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)

    for r in results:
        by_key = {a.key: a for a in r.attributes}
        row = [
            r.input.sku or "",
            r.identity.get("mpn") or r.input.mpn or "",
            r.identity.get("brand") or r.input.brand or "",
            r.category.code if r.category else "",
            " > ".join(r.category.path) if r.category else "",
            r.content.title if r.content else "",
            r.content.short_description if r.content else "",
            r.content.long_description if r.content else "",
            " | ".join(r.content.bullets) if r.content else "",
            ", ".join(r.content.keywords) if r.content else "",
            r.readiness.overall if r.readiness else "",
            r.readiness.verdict if r.readiness else "",
            sum(1 for i in r.issues if i.severity.value == "error"),
            sum(1 for i in r.issues if i.severity.value == "warning"),
        ]
        for key in attribute_keys:
            attr = by_key.get(key)
            if attr is None:
                row += ["", "", ""]
            else:
                unit = f" {attr.unit}" if attr.unit else ""
                row += [f"{attr.value}{unit}", attr.provenance.value, attr.confidence]
        writer.writerow(row)

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="enriched_catalog.csv"'},
    )


@app.post("/api/ingest/pdf")
async def ingest_pdf(
    file: UploadFile = File(...),
    mode: str = Form("demo"),
    api_key: str | None = Form(None),
) -> dict[str, Any]:
    """Read a supplier datasheet and enrich it through the normal pipeline."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a .pdf file.")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file was empty.")
    if len(data) > 25_000_000:
        raise HTTPException(status_code=413, detail="PDF exceeds the 25 MB limit.")

    from .ingest.pdf import from_pdf

    product, report = from_pdf(data, filename=file.filename)
    if product.is_empty():
        return {
            "result": None,
            "ingest": report.as_dict(),
            "extracted_input": product.model_dump(exclude_none=True),
        }

    result = _enrich_one(product, mode, api_key)
    return {
        "result": result,
        "ingest": report.as_dict(),
        "extracted_input": product.model_dump(exclude_none=True),
    }


@app.post("/api/ingest/url")
def ingest_url(payload: dict = Body(...)) -> dict[str, Any]:
    """Read a supplier product page and enrich it through the normal pipeline."""
    url = (payload.get("url") or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="No URL supplied.")

    from .ingest.web import UnsafeURL, from_url

    try:
        product, report = from_url(url)
    except UnsafeURL as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - report fetch failures to the caller
        raise HTTPException(
            status_code=502, detail=f"Could not fetch that page: {exc}"
        ) from exc

    if product.is_empty():
        return {
            "result": None,
            "ingest": report.as_dict(),
            "extracted_input": product.model_dump(exclude_none=True),
        }

    result = _enrich_one(product, payload.get("mode", "demo"), payload.get("api_key"))
    return {
        "result": result,
        "ingest": report.as_dict(),
        "extracted_input": product.model_dump(exclude_none=True),
    }


@app.post("/api/taxonomy/propose")
def propose_categories(request: BatchEnrichRequest = Body(...)) -> dict[str, Any]:
    """Find products the taxonomy cannot classify and propose categories for them.

    This is the answer to "your knowledge base is hardcoded": products that fit
    no existing category are clustered, and each cluster yields a full schema
    proposal — attributes, types, units, vocabularies, ranges — for review.
    """
    from .pipeline import taxonomy as tax
    from .taxonomy_learning import propose as proposer
    from .taxonomy_learning import store

    if not request.products:
        raise HTTPException(status_code=400, detail="No products supplied.")
    if len(request.products) > MAX_BATCH:
        raise HTTPException(
            status_code=413,
            detail=f"Batch of {len(request.products)} exceeds the {MAX_BATCH} limit.",
        )

    unclassified: list[RawProduct] = []
    classified = 0
    for product in request.products:
        category, confidence, _, _ = tax.classify(
            name=product.name,
            description=product.description,
            free_text=product.free_text,
            category_hint=product.category_hint,
            mpn=product.mpn,
            brand=product.brand,
            raw_specs=product.raw_specs,
        )
        # A weak match is as much a gap as no match: forcing a product into a
        # category it barely fits produces confident-looking nonsense. Linear
        # guides scored 55% against bearings purely because their material is
        # called "Bearing Steel" — a coincidence, not a classification. Below
        # this bar the honest move is to propose a category, not to guess.
        if category is None or confidence < PROPOSE_BELOW_CONFIDENCE:
            unclassified.append(product)
        else:
            classified += 1

    proposals = proposer.propose(unclassified)
    added = store.save_proposals(proposals)

    return {
        "examined": len(request.products),
        "classified": classified,
        "unclassified": len(unclassified),
        "proposals": proposals,
        "new_proposals": len(added),
    }


@app.get("/api/taxonomy/proposals")
def list_proposals(status: str | None = None) -> dict[str, Any]:
    from .taxonomy_learning import store

    proposals = store.list_proposals(status)
    return {
        "proposals": proposals,
        "counts": {
            state: len(store.list_proposals(state))
            for state in ("pending", "approved", "rejected")
        },
    }


@app.post("/api/taxonomy/proposals/{proposal_id}/approve")
def approve_proposal(proposal_id: str, payload: dict = Body(default={})) -> dict[str, Any]:
    """Accept a proposal — the category becomes live for all future products."""
    from .taxonomy_learning import store

    proposal = store.approve(proposal_id, note=payload.get("note"))
    if proposal is None:
        raise HTTPException(status_code=404, detail="No such proposal.")
    return {"proposal": proposal, "categories": len(taxonomy.categories())}


@app.post("/api/taxonomy/proposals/{proposal_id}/reject")
def reject_proposal(proposal_id: str, payload: dict = Body(default={})) -> dict[str, Any]:
    from .taxonomy_learning import store

    proposal = store.reject(proposal_id, note=payload.get("note"))
    if proposal is None:
        raise HTTPException(status_code=404, detail="No such proposal.")
    return {"proposal": proposal}


@app.delete("/api/taxonomy/learned/{code}")
def revoke_learned(code: str) -> dict[str, Any]:
    """Undo an approval, removing a learned category from the taxonomy."""
    from .taxonomy_learning import store

    if not store.revoke(code):
        raise HTTPException(status_code=404, detail="No such learned category.")
    return {"revoked": code, "categories": len(taxonomy.categories())}


def _mount_frontend() -> None:
    """Serve the built UI from the API process.

    The submission requires a single live link, so the deployed artefact has to
    be one service. In development the Vite dev server proxies /api here and
    this mount simply does not exist; in production the built SPA is served
    from the same origin, which also removes the CORS surface entirely.
    """
    dist = APP_DIR.parent.parent / "frontend" / "dist"
    if not dist.is_dir():
        return

    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        # Anything that is not an API route resolves to the SPA entry point, so
        # a deep link or a refresh does not 404.
        candidate = dist / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")


@app.get("/api/cache")
def cache_stats() -> dict[str, Any]:
    return cache.stats()


@app.delete("/api/cache")
def cache_clear() -> dict[str, Any]:
    return {"removed": cache.clear()}


# Registered last: the SPA catch-all must not shadow any /api route.
_mount_frontend()

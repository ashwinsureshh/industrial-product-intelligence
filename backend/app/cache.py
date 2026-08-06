"""Content-addressed cache for enrichment results.

The point is cost control: a reviewer can re-run the same product as many times
as they like and only the first run in live mode ever reaches the API. The key
covers the input, the mode and the model, so changing any of them correctly
misses the cache. API keys are never part of the key and never written to disk.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any

from .config import CACHE_DIR, CACHE_ENABLED, MODEL, PRECOMPUTED_DIR

_lock = threading.Lock()
_stats = {"hits": 0, "misses": 0, "writes": 0, "bundled_hits": 0}


def key_for(payload: dict[str, Any], mode: str) -> str:
    """The content address for a result. Public so other read-only layers
    (e.g. the committed benchmark records) can be keyed identically."""
    blob = json.dumps(payload, sort_keys=True, default=str)
    fingerprint = f"{mode}|{MODEL if mode == 'live' else 'deterministic'}|{blob}"
    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:32]


_key = key_for


def _path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def get(payload: dict[str, Any], mode: str) -> dict[str, Any] | None:
    """Look up a result, preferring the writable cache then the bundled one.

    The bundled layer ships pre-computed live-mode results in the repository.
    It is what lets a reviewer with no API key select 'Live AI' and see genuine
    model output for the demo products, at zero cost to anyone — the alternative
    is either asking every reviewer for a key or leaving the AI path invisible.
    """
    if not CACHE_ENABLED:
        return None

    key = _key(payload, mode)
    for directory, bundled in ((CACHE_DIR, False), (PRECOMPUTED_DIR, True)):
        path = directory / f"{key}.json"
        if not path.exists():
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                record = json.load(fh)
        except (OSError, json.JSONDecodeError):
            # A corrupt entry degrades to a miss, never breaks the request.
            continue
        with _lock:
            _stats["hits"] += 1
            if bundled:
                _stats["bundled_hits"] += 1
        return record.get("result")

    with _lock:
        _stats["misses"] += 1
    return None


def put(payload: dict[str, Any], mode: str, result: dict[str, Any]) -> None:
    if not CACHE_ENABLED:
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _path(_key(payload, mode))
    record = {"stored_at": time.time(), "mode": mode, "result": result}
    tmp = path.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(record, fh, default=str)
        tmp.replace(path)
    except OSError:
        return
    with _lock:
        _stats["writes"] += 1


def put_bundled(payload: dict[str, Any], mode: str, result: dict[str, Any]) -> Path:
    """Write a result into the committed, read-only layer.

    Used once by the pre-compute script so live-mode output for the demo
    products ships in the repository. Separate from put() because these entries
    are deliberately durable and reviewed, not incidental runtime state.
    """
    PRECOMPUTED_DIR.mkdir(parents=True, exist_ok=True)
    path = PRECOMPUTED_DIR / f"{_key(payload, mode)}.json"
    record = {"stored_at": time.time(), "mode": mode, "result": result}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, default=str)
    return path


def stats() -> dict[str, Any]:
    entries = len(list(CACHE_DIR.glob("*.json"))) if CACHE_DIR.exists() else 0
    bundled = len(list(PRECOMPUTED_DIR.glob("*.json"))) if PRECOMPUTED_DIR.exists() else 0
    with _lock:
        snapshot = dict(_stats)
    total = snapshot["hits"] + snapshot["misses"]
    snapshot["entries"] = entries
    snapshot["bundled"] = bundled
    snapshot["hit_rate"] = round(snapshot["hits"] / total, 3) if total else 0.0
    snapshot["enabled"] = CACHE_ENABLED
    return snapshot


def clear() -> int:
    if not CACHE_DIR.exists():
        return 0
    removed = 0
    for path in CACHE_DIR.glob("*.json"):
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    return removed

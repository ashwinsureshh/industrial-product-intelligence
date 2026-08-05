"""Persistence for proposals and the categories learned from them.

Two files, deliberately separate:

  proposals.json         — the review queue, including rejected ones. Kept so a
                           rejection is auditable and the same bad proposal is
                           not silently re-raised.
  learned_categories.json — approved categories, merged into the taxonomy at
                           load time and indistinguishable to the pipeline from
                           the hand-curated ones.

Writes are atomic (temp file then replace) because an approval that half-writes
the taxonomy would corrupt every subsequent classification.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from ..config import DATA_DIR
from ..models import CategoryProposal

PROPOSALS_PATH = DATA_DIR / "proposals.json"
LEARNED_PATH = DATA_DIR / "learned_categories.json"

_lock = threading.Lock()


def _read(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        # A corrupt store must not take the whole app down; the taxonomy still
        # works from its curated base.
        return default


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    tmp.replace(path)


# ------------------------------------------------------------------ proposals


def list_proposals(status: str | None = None) -> list[CategoryProposal]:
    raw = _read(PROPOSALS_PATH, [])
    proposals = []
    for item in raw:
        try:
            proposals.append(CategoryProposal.model_validate(item))
        except Exception:  # noqa: BLE001 - skip entries from an older schema
            continue
    if status:
        proposals = [p for p in proposals if p.status == status]
    proposals.sort(key=lambda p: -p.created_at)
    return proposals


def get_proposal(proposal_id: str) -> CategoryProposal | None:
    return next((p for p in list_proposals() if p.id == proposal_id), None)


def save_proposals(new: list[CategoryProposal]) -> list[CategoryProposal]:
    """Add proposals, and refresh any that are still awaiting review.

    A reviewed proposal is settled: re-raising one a human already rejected
    would be noise, and overwriting one already approved would silently change
    a live category. A *pending* proposal is not settled, so it is replaced by
    the newer inference — otherwise an improvement to the inference engine can
    never reach a queue item that was generated before it.
    """
    with _lock:
        existing = list_proposals()
        settled = {p.id: p for p in existing if p.status != "pending"}
        pending = {p.id: p for p in existing if p.status == "pending"}

        added: list[CategoryProposal] = []
        for proposal in new:
            if proposal.id in settled:
                continue
            if proposal.id not in pending:
                added.append(proposal)
            pending[proposal.id] = proposal  # refresh in place

        _write(PROPOSALS_PATH,
               [p.model_dump(mode="json")
                for p in list(settled.values()) + list(pending.values())])
        return added


def _update(proposal_id: str, **changes: Any) -> CategoryProposal | None:
    with _lock:
        proposals = list_proposals()
        found = None
        for proposal in proposals:
            if proposal.id == proposal_id:
                for key, value in changes.items():
                    setattr(proposal, key, value)
                found = proposal
                break
        if found:
            _write(PROPOSALS_PATH,
                   [p.model_dump(mode="json") for p in proposals])
        return found


# ---------------------------------------------------------- learned taxonomy


def learned_categories() -> list[dict[str, Any]]:
    return _read(LEARNED_PATH, [])


def approve(proposal_id: str, note: str | None = None) -> CategoryProposal | None:
    """Accept a proposal and merge it into the live taxonomy."""
    proposal = get_proposal(proposal_id)
    if proposal is None or proposal.status == "approved":
        return proposal

    with _lock:
        categories = learned_categories()
        if not any(c.get("code") == proposal.code for c in categories):
            categories.append(proposal.to_category())
            _write(LEARNED_PATH, categories)

    updated = _update(proposal_id, status="approved",
                      reviewed_at=time.time(), reviewer_note=note)

    # The taxonomy is cached for speed; a new category must be visible at once.
    from ..pipeline import taxonomy

    taxonomy.invalidate()
    return updated


def reject(proposal_id: str, note: str | None = None) -> CategoryProposal | None:
    return _update(proposal_id, status="rejected",
                   reviewed_at=time.time(), reviewer_note=note)


def revoke(code: str) -> bool:
    """Remove a learned category. Used to undo an approval."""
    with _lock:
        categories = learned_categories()
        remaining = [c for c in categories if c.get("code") != code]
        if len(remaining) == len(categories):
            return False
        _write(LEARNED_PATH, remaining)

    from ..pipeline import taxonomy

    taxonomy.invalidate()
    return True

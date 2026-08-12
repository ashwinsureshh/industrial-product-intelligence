"""Provider interface for the inference stage.

Everything upstream of this (parsing, unit conversion, taxonomy matching) is
deterministic. Only the genuinely open-ended work — inferring attributes that
were never stated, and writing merchandising copy — goes through a provider.
That boundary is what lets demo mode and live mode produce the same shape of
output, and it keeps the expensive path small.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..models import Attribute, CommerceContent, RawProduct


class InferenceResult:
    def __init__(
        self,
        attributes: list[Attribute] | None = None,
        content: CommerceContent | None = None,
        notes: list[str] | None = None,
        usage: dict[str, Any] | None = None,
        cross_checks: list[Attribute] | None = None,
    ) -> None:
        self.attributes = attributes or []
        self.content = content
        self.notes = notes or []
        self.usage = usage or {}
        # Values a published standard fixes for fields the supplier already
        # filled. They are not added to the record — the supplier outranks a
        # lookup — but they must be heard, or a designation can never
        # contradict the value it determines. See _check_against_standards.
        self.cross_checks = cross_checks or []


class Provider(ABC):
    name: str = "base"

    @abstractmethod
    def infer_attributes(
        self,
        raw: RawProduct,
        category: dict[str, Any] | None,
        known: list[Attribute],
    ) -> InferenceResult:
        """Fill gaps the deterministic stages could not."""

    @abstractmethod
    def generate_content(
        self,
        raw: RawProduct,
        category: dict[str, Any] | None,
        attributes: list[Attribute],
        identity: dict[str, Any],
    ) -> InferenceResult:
        """Produce storefront-ready copy from the resolved attribute set."""

"""Profile-driven export: the output schema is data, not code.

Unilog will supply a target schema, and it had not arrived when this was
written. Hardcoding a guess would mean rewriting the exporter the day it lands,
so the target is described by a JSON profile instead and the engine reads it.
Adding a customer's schema becomes the same kind of change as adding a product
category: edit data, not Python.

A profile names its fields and where each one comes from. Paths address the
enriched record directly - `content.title`, `readiness.verdict` - with two
extras that matter for this domain:

  * `attr:<key>`            the value of one attribute, unit included
  * `attr:<key>.source_url` its citation, so a target schema can carry sources

Attributes the profile does not name individually are expanded by its
`attributes` block, either into flat columns (a catalog import sheet) or into a
nested list (JSON-LD). That is what lets one mechanism serve both an Excel
worksheet and schema.org.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..config import DATA_DIR
from ..models import Attribute, EnrichedProduct

PROFILE_DIR = DATA_DIR / "export_profiles"


class ProfileError(ValueError):
    """Raised when a profile is unknown or malformed."""


@lru_cache(maxsize=1)
def _load_all() -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    if not PROFILE_DIR.exists():
        return profiles
    for path in sorted(PROFILE_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as fh:
            profile = json.load(fh)
        profiles[profile["id"]] = profile
    return profiles


def available() -> list[dict[str, str]]:
    return [
        {
            "id": p["id"],
            "label": p.get("label", p["id"]),
            "format": p.get("format", "json"),
            "description": p.get("description", ""),
        }
        for p in _load_all().values()
    ]


def get(profile_id: str) -> dict[str, Any]:
    profiles = _load_all()
    if profile_id not in profiles:
        raise ProfileError(
            f"Unknown export profile '{profile_id}'. "
            f"Available: {', '.join(sorted(profiles)) or 'none'}"
        )
    return profiles[profile_id]


def invalidate() -> None:
    _load_all.cache_clear()


# ------------------------------------------------------------------ resolution


def _format_value(attribute: Attribute) -> str:
    unit = f" {attribute.unit}" if attribute.unit else ""
    return f"{attribute.value}{unit}"


def _walk(obj: Any, parts: list[str]) -> Any:
    for part in parts:
        if obj is None:
            return None
        if isinstance(obj, (list, tuple)) and part.isdigit():
            index = int(part)
            obj = obj[index] if index < len(obj) else None
        elif isinstance(obj, dict):
            obj = obj.get(part)
        else:
            obj = getattr(obj, part, None)
    return obj


def resolve(record: EnrichedProduct, path: str) -> Any:
    """Read one value out of an enriched record by profile path."""
    by_key = {a.key: a for a in record.attributes}

    if path.startswith("attr:"):
        rest = path[5:]
        key, _, field = rest.partition(".")
        attribute = by_key.get(key)
        if attribute is None:
            return None
        if not field:
            return _format_value(attribute)
        if field == "provenance":
            return attribute.provenance.value
        return getattr(attribute, field, None)

    # `field:<id>` addresses one of the house-style commerce descriptions. A
    # customer schema names these by their own column titles, so the mapping
    # from "Invoice Desc" to our `invoice_desc` belongs in the profile.
    if path.startswith("field:"):
        rest = path[6:]
        identifier, _, part = rest.partition(".")
        rendered = next(
            (f for f in (record.compliance.fields if record.compliance else [])
             if f.get("id") == identifier),
            None,
        )
        if rendered is None:
            return None
        return rendered.get(part or "text")

    # A handful of shapes a flat target schema always wants but the record
    # stores structurally.
    if path == "category.path":
        return " > ".join(record.category.path) if record.category else None
    # Their sheet writes the classpath without spaces around the separator, and
    # a classpath that does not match theirs character-for-character fails a
    # field-level accuracy check even when the classification is right.
    if path == "category.classpath":
        if not record.category:
            return None
        # The customer's own wording wins where the taxonomy declares it;
        # otherwise our path is the honest answer, written their way.
        return record.category.customer.get("classpath") or ">".join(record.category.path)
    if path == "issues.errors":
        return sum(1 for i in record.issues if i.severity.value == "error")
    if path == "issues.warnings":
        return sum(1 for i in record.issues if i.severity.value == "warning")
    if path == "content.bullets":
        return " | ".join(record.content.bullets) if record.content else None
    if path == "content.keywords":
        return ", ".join(record.content.keywords) if record.content else None

    value = _walk(record, path.split("."))
    if hasattr(value, "value") and hasattr(value, "provenance"):  # an Attribute
        return _format_value(value)
    return value


# -------------------------------------------------------------------- rendering


def _named_keys(profile: dict[str, Any]) -> set[str]:
    """Attribute keys the profile addresses explicitly, so we do not repeat them."""
    keys = set()
    for field in profile.get("fields", []):
        source = field.get("from", "")
        if source.startswith("attr:"):
            keys.add(source[5:].partition(".")[0])
    return keys


def _slot_values(record: EnrichedProduct, slots: dict[str, Any]) -> list[dict[str, Any]]:
    """The items a numbered slot block draws from, in order."""
    source = slots.get("source", "")
    if source == "attributes":
        from ..unilog import house_style as HS

        return [
            {
                "label": a.label,
                # House style, and the unit deliberately left off: their sheet
                # carries it in its own column.
                "value": HS.value_only(a.value, a.unit),
                "unit": a.unit or "",
                "source_url": a.source_url or "",
                "provenance": a.provenance.value,
            }
            for a in record.attributes
        ]
    value = resolve(record, source)
    if value is None:
        return []
    if isinstance(value, str):
        # A path that already joined a list (content.bullets) is split back out.
        value = [v.strip() for v in value.split("|") if v.strip()]
    return [{".": item} for item in value]


def _expand_slots(slots: dict[str, Any]) -> list[str]:
    """Header names for one slot block, e.g. ATTRIBUTE_LABEL 1..50."""
    count = int(slots.get("count", 0))
    columns = slots.get("columns") or [{"target": slots["target"], "from": "."}]
    names: list[str] = []
    for index in range(1, count + 1):
        names += [c["target"].format(n=index) for c in columns]
    return names


def _slot_row(record: EnrichedProduct, slots: dict[str, Any]) -> list[Any]:
    """One record's cells for a slot block, padded to the fixed slot count.

    Empty slots are emitted, not skipped. Their delivery sheet is positional —
    every row carries all 50 attribute triplets whether or not the category
    fills them — so a short row would silently shift every later column.
    """
    count = int(slots.get("count", 0))
    columns = slots.get("columns") or [{"target": slots["target"], "from": "."}]
    items = _slot_values(record, slots)[:count]

    cells: list[Any] = []
    for index in range(count):
        item = items[index] if index < len(items) else {}
        for column in columns:
            cells.append(item.get(column["from"], ""))
    return cells


def to_rows(profile: dict[str, Any], records: list[EnrichedProduct]) -> tuple[list[str], list[list[Any]]]:
    """Flatten records into header + rows for a tabular profile."""
    fields = profile.get("fields", [])
    header: list[str] = []
    for field in fields:
        if "slots" in field:
            header += _expand_slots(field["slots"])
        else:
            header.append(field["target"])

    attr_block = profile.get("attributes") or {}
    columns: list[dict[str, str]] = attr_block.get("columns", [])
    skip = _named_keys(profile)

    # Union of attribute keys across the batch, so every row has the same shape
    # even when one product carries a field another does not.
    attribute_keys: list[str] = []
    if columns:
        for record in records:
            for a in record.attributes:
                if a.key not in attribute_keys and a.key not in skip:
                    attribute_keys.append(a.key)
        for key in attribute_keys:
            header += [f"{key}{c.get('suffix', '')}" for c in columns]

    rows: list[list[Any]] = []
    for record in records:
        row: list[Any] = []
        for field in fields:
            if "slots" in field:
                row += _slot_row(record, field["slots"])
            elif "from" in field:
                row.append(resolve(record, field["from"]))
            else:
                row.append(field.get("const", ""))
        row = ["" if v is None else v for v in row]

        for key in attribute_keys:
            for column in columns:
                value = resolve(record, column["from"].format(key=key))
                row.append("" if value is None else value)
        rows.append(row)

    return header, rows


def to_documents(profile: dict[str, Any], records: list[EnrichedProduct]) -> list[dict[str, Any]]:
    """Render records into nested documents for a JSON/JSON-LD profile."""
    fields = profile.get("fields", [])
    attr_block = profile.get("attributes") or {}
    skip = _named_keys(profile)

    documents = []
    for record in records:
        doc: dict[str, Any] = {}
        for field in fields:
            value = field["const"] if "const" in field else resolve(record, field["from"])
            if value is None and field.get("omit_empty", True):
                continue
            doc[field["target"]] = value

        item_template = attr_block.get("item")
        if item_template:
            items = []
            for attribute in record.attributes:
                if attribute.key in skip:
                    continue
                item = {}
                for target, source in item_template.items():
                    value = (
                        source["const"] if isinstance(source, dict) and "const" in source
                        else resolve(record, source.format(key=attribute.key))
                    )
                    if value is None:
                        continue
                    item[target] = value
                items.append(item)
            if items:
                doc[attr_block["target"]] = items

        documents.append(doc)

    return documents

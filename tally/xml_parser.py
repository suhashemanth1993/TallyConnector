"""Parses Tally "Collection" export response XML into plain dicts, driven
by the same EntitySpec used to build the request.

Tally is known to emit a handful of stray low-value control characters
(e.g. &#4;, &#5;) inside text nodes; these are stripped before parsing so a
single bad byte doesn't fail an entire response.
"""

from __future__ import annotations

import re
from typing import Any

from lxml import etree

from models.entity_spec import EntitySpec
from utils.exceptions import TallyXMLParseError

_CONTROL_CHAR_ENTITY_PATTERN = re.compile(rb"&#(?:[0-8]|1[124-9]|2[0-9]|3[01]);")

_LEDGER_ENTRIES_TAG = "ALLLEDGERENTRIES.LIST"
_INVENTORY_ENTRIES_TAG = "ALLINVENTORYENTRIES.LIST"

_ACRONYM_BOUNDARY = re.compile(r"(.)([A-Z][a-z]+)")
_LOWER_UPPER_BOUNDARY = re.compile(r"([a-z0-9])([A-Z])")


def _pascal_to_snake(name: str) -> str:
    step1 = _ACRONYM_BOUNDARY.sub(r"\1_\2", name)
    return _LOWER_UPPER_BOUNDARY.sub(r"\1_\2", step1).lower()


def _row_tag(spec: EntitySpec) -> str:
    return spec.tally_object_type.upper()


def _field_value(row: etree._Element, field_name: str) -> str | None:
    tag = field_name.upper()
    child = row.find(tag)
    if child is not None and child.text is not None:
        text = child.text.strip()
        return text or None
    attr = row.get(tag)
    if attr is not None:
        attr = attr.strip()
        return attr or None
    return None


def _extract_fields(row: etree._Element, fields: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field_name in fields:
        value = _field_value(row, field_name)
        if value is not None:
            result[_pascal_to_snake(field_name)] = value
    return result


def _extract_entry_list(
    row: etree._Element, list_tag: str, fields: list[str]
) -> list[dict[str, Any]]:
    # Tally sometimes emits an empty list-tag occurrence (e.g. a service-only
    # purchase voucher can still carry a blank ALLINVENTORYENTRIES.LIST) —
    # that yields an entry dict with none of `fields` populated, which isn't
    # a real line item and would fail model validation (missing required
    # fields) if kept.
    entries = [_extract_fields(entry, fields) for entry in row.findall(list_tag)]
    return [entry for entry in entries if entry]


def parse_collection_response(xml_bytes: bytes, spec: EntitySpec) -> list[dict[str, Any]]:
    """Parse a raw Tally XML response into a list of plain dicts (one per
    row), with keys already converted to the snake_case names the Pydantic
    models expect. Raises TallyXMLParseError on malformed XML."""
    cleaned = _CONTROL_CHAR_ENTITY_PATTERN.sub(b"", xml_bytes)
    try:
        root = etree.fromstring(cleaned)
    except etree.XMLSyntaxError as exc:
        raise TallyXMLParseError(
            f"Could not parse Tally response for entity '{spec.name}': {exc}"
        ) from exc

    row_tag = _row_tag(spec)
    rows = root.findall(f".//{row_tag}")

    records: list[dict[str, Any]] = []
    for row in rows:
        record = _extract_fields(row, spec.fetch_fields)

        name_attr = row.get("NAME")
        if name_attr and "name" not in record:
            record["name"] = name_attr.strip()

        if spec.is_voucher:
            record["voucher_type"] = spec.voucher_type_filter or record.get("voucher_type_name", "")
            if spec.ledger_entries_fields:
                record["ledger_entries"] = _extract_entry_list(
                    row, _LEDGER_ENTRIES_TAG, spec.ledger_entries_fields
                )
            if spec.inventory_entries_fields:
                record["inventory_entries"] = _extract_entry_list(
                    row, _INVENTORY_ENTRIES_TAG, spec.inventory_entries_fields
                )

        records.append(record)

    return records

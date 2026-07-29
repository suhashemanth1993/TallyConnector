"""Duplicate detection: is a Tally record already pushed to Frappe?

Checks the local StateStore cache first (fast, no network); falls back to a
Frappe GET-by-filter on the record's natural-key field and populates the
cache so subsequent lookups for the same record are free.
"""

from __future__ import annotations

from frappe.client import FrappeClient
from frappe.mapping import MappingEntry
from sync.state_store import StateStore


def find_existing(
    store: StateStore,
    client: FrappeClient,
    mapping_entry: MappingEntry,
    natural_key_field: str,
    natural_key_value: str,
) -> str | None:
    """`natural_key_field` is the model attribute used as this entity's
    identity (see EntitySpec.natural_key_field — usually "guid", but e.g.
    "name" for Company). Its mapped Frappe field name is looked up from
    `mapping_entry.field_map`, falling back to the field name itself."""
    cached = store.get_cached_frappe_name(mapping_entry.entity_name, natural_key_value)
    if cached:
        return cached

    frappe_field = mapping_entry.field_map.get(natural_key_field, natural_key_field)
    matches = client.get(
        mapping_entry.frappe_doctype, {frappe_field: natural_key_value}, fields=["name"]
    )
    if not matches:
        return None

    frappe_name = matches[0]["name"]
    store.upsert_cache(
        entity_name=mapping_entry.entity_name,
        tally_guid=natural_key_value,
        frappe_name=frappe_name,
        frappe_doctype=mapping_entry.frappe_doctype,
        content_hash="",
    )
    return frappe_name

from __future__ import annotations

from frappe.mapping import load_mapping
from models.registry import REGISTRY


def test_mapping_covers_every_registry_entity():
    mapping = load_mapping("frappe/mapping.yaml")
    assert set(mapping.keys()) == set(REGISTRY.keys())


def test_mapping_entry_apply_renames_and_drops_none():
    mapping = load_mapping("frappe/mapping.yaml")
    ledger = mapping["ledger"]
    result = ledger.apply({"guid": "g-1", "name": "Cash", "parent": None, "alter_id": 5})
    assert result == {"tally_guid": "g-1", "title": "Cash", "tally_alter_id": 5}

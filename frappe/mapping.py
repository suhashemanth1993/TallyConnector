"""Loads the Tally -> Frappe entity/field mapping from an editable YAML file."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml


@dataclass(frozen=True)
class MappingEntry:
    entity_name: str
    frappe_doctype: str
    field_map: dict[str, str]

    def apply(self, model_dict: dict) -> dict:
        """Rename model_dict keys per field_map; keys with no mapping are dropped."""
        return {
            frappe_field: model_dict[tally_field]
            for tally_field, frappe_field in self.field_map.items()
            if tally_field in model_dict and model_dict[tally_field] is not None
        }


def load_mapping(path: str) -> dict[str, MappingEntry]:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    return {
        entity_name: MappingEntry(
            entity_name=entity_name,
            frappe_doctype=entry["frappe_doctype"],
            field_map=entry.get("field_map", {}),
        )
        for entity_name, entry in raw.items()
    }


@lru_cache
def get_mapping(path: str = "frappe/mapping.yaml") -> dict[str, MappingEntry]:
    return load_mapping(path)

"""Declarative description of one Tally entity (master or voucher type).

Adding a new Tally entity to the connector means adding one EntitySpec to
the registry, not writing a new module — the XML builder, parser, and sync
engine are all generic over this spec.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import BaseModel


class EntityKind(str, Enum):
    MASTER = "master"
    VOUCHER = "voucher"


@dataclass(frozen=True)
class EntitySpec:
    name: str
    kind: EntityKind
    tally_object_type: str
    fetch_fields: list[str]
    pydantic_model: type[BaseModel]
    voucher_type_filter: str | None = None
    ledger_entries_fields: list[str] | None = None
    inventory_entries_fields: list[str] | None = None
    natural_key_field: str = "guid"
    depends_on: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_voucher(self) -> bool:
        return self.kind is EntityKind.VOUCHER

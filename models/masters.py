"""Generic model covering all 14 Tally master entity types."""

from __future__ import annotations

from models.base import TallyBaseModel


class TallyMaster(TallyBaseModel):
    # `guid` is optional: some Tally objects (notably Company, which is a
    # container rather than a true master) don't reliably expose one.
    # Which field actually identifies a given entity is configured via
    # EntitySpec.natural_key_field in models/registry.py.
    guid: str | None = None
    name: str
    parent: str | None = None
    alter_id: int | None = None

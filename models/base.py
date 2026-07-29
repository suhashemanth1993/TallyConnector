"""Shared Pydantic base for all Tally-derived models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class TallyBaseModel(BaseModel):
    """Base for models hydrated from Tally XML.

    `extra="allow"` is what lets one generic model cover every master/voucher
    entity: entity-specific fields (e.g. a Ledger's GSTIN, a StockItem's
    base units) land as extra attributes without a dedicated class per entity.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True, str_strip_whitespace=True)

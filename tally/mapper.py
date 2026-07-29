"""Hydrates a parsed raw dict into the appropriate Pydantic model for an entity."""

from __future__ import annotations

from typing import Any, cast

from models.entity_spec import EntitySpec
from models.masters import TallyMaster
from models.vouchers import TallyVoucher


def to_model(raw: dict[str, Any], spec: EntitySpec) -> TallyMaster | TallyVoucher:
    return cast("TallyMaster | TallyVoucher", spec.pydantic_model(**raw))

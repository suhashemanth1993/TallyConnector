"""Generic models covering all 9 Tally voucher entity types."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from pydantic import field_validator

from models.base import TallyBaseModel

_TALLY_DATE_FMT = "%Y%m%d"
_TRUE_STRINGS = {"yes", "true", "1"}

# Tally's ActualQty/Rate come back as compound strings, not plain numbers —
# e.g. "500 kgs", "0.07/no", or "10000 no =  2 Bin" (an alternate-unit
# conversion). We only want the leading numeric value; the unit/conversion
# suffix is discarded (not currently modeled — a future enhancement if the
# alternate-unit quantity itself is ever needed).
_LEADING_NUMBER = re.compile(r"^\s*(-?[\d,]+(?:\.\d+)?)")


def _coerce_tally_date(value: object) -> object:
    if isinstance(value, str) and len(value) == 8 and value.isdigit():
        return datetime.strptime(value, _TALLY_DATE_FMT).date()
    return value


def _coerce_tally_bool(value: object) -> object:
    if isinstance(value, str):
        return value.strip().lower() in _TRUE_STRINGS
    return value


def _coerce_tally_decimal(value: object) -> object:
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        match = _LEADING_NUMBER.match(cleaned)
        if not match:
            return value
        try:
            return Decimal(match.group(1).replace(",", ""))
        except InvalidOperation:
            return value
    return value


class LedgerEntry(TallyBaseModel):
    ledger_name: str
    amount: Decimal
    is_deemed_positive: bool | None = None

    _coerce_amount = field_validator("amount", mode="before")(staticmethod(_coerce_tally_decimal))
    _coerce_positive = field_validator("is_deemed_positive", mode="before")(
        staticmethod(_coerce_tally_bool)
    )


class InventoryEntry(TallyBaseModel):
    stock_item_name: str
    actual_qty: Decimal | None = None
    rate: Decimal | None = None
    amount: Decimal | None = None
    godown_name: str | None = None

    _coerce_qty = field_validator("actual_qty", "rate", "amount", mode="before")(
        staticmethod(_coerce_tally_decimal)
    )


class TallyVoucher(TallyBaseModel):
    guid: str
    voucher_type: str
    voucher_number: str | None = None
    date: date
    party_ledger_name: str | None = None
    narration: str | None = None
    alter_id: int | None = None
    ledger_entries: list[LedgerEntry] = []
    inventory_entries: list[InventoryEntry] = []

    _coerce_date = field_validator("date", mode="before")(staticmethod(_coerce_tally_date))

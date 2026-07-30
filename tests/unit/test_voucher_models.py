"""Real TallyPrime emits ActualQty/Rate as compound strings, not plain
numbers — confirmed against real sync failures, not guessed."""

from __future__ import annotations

from decimal import Decimal

from models.vouchers import InventoryEntry, LedgerEntry


def test_actual_qty_strips_unit_suffix():
    entry = InventoryEntry(stock_item_name="Widget", actual_qty="500 kgs")
    assert entry.actual_qty == Decimal("500")


def test_actual_qty_strips_alternate_unit_conversion():
    entry = InventoryEntry(stock_item_name="Widget", actual_qty="10000 no =  2 Bin")
    assert entry.actual_qty == Decimal("10000")


def test_rate_strips_unit_suffix():
    entry = InventoryEntry(stock_item_name="Widget", rate="0.07/no")
    assert entry.rate == Decimal("0.07")

    entry2 = InventoryEntry(stock_item_name="Widget", rate="235.00/kgs")
    assert entry2.rate == Decimal("235.00")


def test_amount_without_suffix_still_parses_normally():
    entry = InventoryEntry(stock_item_name="Widget", amount="-30012.00")
    assert entry.amount == Decimal("-30012.00")

    ledger_entry = LedgerEntry(ledger_name="Cash", amount="43802.00")
    assert ledger_entry.amount == Decimal("43802.00")


def test_negative_qty_with_suffix():
    entry = InventoryEntry(stock_item_name="Widget", actual_qty="-100 kgs")
    assert entry.actual_qty == Decimal("-100")

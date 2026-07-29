from __future__ import annotations

from decimal import Decimal

from models.masters import TallyMaster
from models.registry import get_entity
from models.vouchers import TallyVoucher
from tally.mapper import to_model
from tally.xml_parser import parse_collection_response


def test_maps_ledger_records_to_master_model(fixture_loader):
    spec = get_entity("ledger")
    records = parse_collection_response(fixture_loader("ledger_collection_response.xml"), spec)
    models = [to_model(r, spec) for r in records]

    assert all(isinstance(m, TallyMaster) for m in models)
    assert models[0].name == "Sales Account"
    assert models[0].alter_id == 201
    assert models[0].party_gstin == "29ABCDE1234F1Z5"  # extra field, via extra="allow"


def test_maps_company_without_guid_using_name_as_natural_key(fixture_loader):
    spec = get_entity("company")
    records = parse_collection_response(
        fixture_loader("company_collection_response_no_guid.xml"), spec
    )
    model = to_model(records[0], spec)

    assert model.guid is None
    assert model.name == "Acme Traders Pvt Ltd"
    assert spec.natural_key_field == "name"
    assert getattr(model, spec.natural_key_field) == "Acme Traders Pvt Ltd"


def test_maps_sales_voucher_records_to_voucher_model(fixture_loader):
    spec = get_entity("sales_voucher")
    records = parse_collection_response(
        fixture_loader("sales_voucher_collection_response.xml"), spec
    )
    models = [to_model(r, spec) for r in records]

    assert all(isinstance(m, TallyVoucher) for m in models)
    first = models[0]
    assert first.date.isoformat() == "2024-01-15"
    assert first.ledger_entries[0].amount == Decimal("-11800.00")
    assert first.ledger_entries[1].is_deemed_positive is True
    assert first.inventory_entries[0].stock_item_name == "Widget A"

    second = models[1]
    assert second.inventory_entries == []

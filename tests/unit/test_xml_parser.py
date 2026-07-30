from __future__ import annotations

import pytest

from models.registry import get_entity
from tally.xml_parser import parse_collection_response
from utils.exceptions import TallyXMLParseError


def test_parses_company_master(fixture_loader):
    spec = get_entity("company")
    records = parse_collection_response(fixture_loader("company_collection_response.xml"), spec)
    assert len(records) == 2
    assert records[0]["name"] == "Acme Traders Pvt Ltd"
    assert records[0]["guid"] == "c1a1a1a1-0001-0001-0001-000000000001"
    assert records[0]["alter_id"] == "101"


def test_parses_company_without_guid(fixture_loader):
    """Real TallyPrime doesn't reliably expose GUID for Company (it's a
    container object, not a true master) — the parser must not choke on it,
    and 'guid' should simply be absent from the record."""
    spec = get_entity("company")
    records = parse_collection_response(
        fixture_loader("company_collection_response_no_guid.xml"), spec
    )
    assert len(records) == 1
    assert records[0]["name"] == "Acme Traders Pvt Ltd"
    assert "guid" not in records[0]


def test_parses_ledger_master_with_special_chars_and_missing_fields(fixture_loader):
    spec = get_entity("ledger")
    records = parse_collection_response(fixture_loader("ledger_collection_response.xml"), spec)
    assert len(records) == 3

    full, minimal, special = records
    assert full["party_gstin"] == "29ABCDE1234F1Z5"
    assert full["opening_balance"] == "0"

    assert "party_gstin" not in minimal
    assert "opening_balance" not in minimal

    assert special["name"] == "M/s Sharma & Sons"
    assert special["opening_balance"] == "15000.50"


def test_parses_sales_voucher_with_nested_entries(fixture_loader):
    spec = get_entity("sales_voucher")
    records = parse_collection_response(
        fixture_loader("sales_voucher_collection_response.xml"), spec
    )
    assert len(records) == 2

    first = records[0]
    assert first["voucher_number"] == "SV-1001"
    assert first["voucher_type"] == "Sales"
    assert len(first["ledger_entries"]) == 2
    assert first["ledger_entries"][0]["ledger_name"] == "M/s Sharma & Sons"
    assert len(first["inventory_entries"]) == 1
    assert first["inventory_entries"][0]["stock_item_name"] == "Widget A"

    second = records[1]
    assert len(second["ledger_entries"]) == 2
    assert second["inventory_entries"] == []


def test_empty_inventory_entry_list_tag_is_filtered_not_kept_as_blank_row():
    """A service-only purchase voucher can still carry a blank
    ALLINVENTORYENTRIES.LIST tag from Tally — real sync failure showed this
    produces a `{}` entry that then fails model validation if not filtered."""
    xml = b"""<ENVELOPE>
        <VOUCHER>
            <DATE>20260722</DATE>
            <VOUCHERNUMBER>6293</VOUCHERNUMBER>
            <GUID>vch-empty-inv-0001</GUID>
            <PARTYLEDGERNAME>Office Express</PARTYLEDGERNAME>
            <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
            <ALLLEDGERENTRIES.LIST>
                <LEDGERNAME>Office Express</LEDGERNAME>
                <AMOUNT>6843.00</AMOUNT>
                <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
            </ALLLEDGERENTRIES.LIST>
            <ALLINVENTORYENTRIES.LIST>
            </ALLINVENTORYENTRIES.LIST>
        </VOUCHER>
    </ENVELOPE>"""
    spec = get_entity("purchase_voucher")
    records = parse_collection_response(xml, spec)
    assert len(records) == 1
    assert records[0]["inventory_entries"] == []


def test_empty_collection_returns_empty_list(fixture_loader):
    spec = get_entity("ledger")
    records = parse_collection_response(fixture_loader("empty_collection_response.xml"), spec)
    assert records == []


def test_malformed_xml_raises_typed_error(fixture_loader):
    spec = get_entity("ledger")
    with pytest.raises(TallyXMLParseError):
        parse_collection_response(fixture_loader("malformed_response.xml"), spec)

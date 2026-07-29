from __future__ import annotations

from datetime import date

from lxml import etree

from models.registry import get_entity
from tally.xml_builder import build_collection_request


def test_master_request_has_no_date_range_or_voucher_filter():
    spec = get_entity("ledger")
    xml_bytes = build_collection_request(spec)
    root = etree.fromstring(xml_bytes)

    assert root.find(".//COLLECTION/TYPE").text == "Ledger"
    assert root.find(".//SVFROMDATE") is None
    fetch_texts = [el.text for el in root.findall(".//COLLECTION/FETCH")]
    assert "Name" in fetch_texts
    assert "GUID" in fetch_texts


def test_voucher_request_adds_date_range_and_type_filter():
    spec = get_entity("sales_voucher")
    xml_bytes = build_collection_request(
        spec, date_from=date(2024, 1, 1), date_to=date(2024, 1, 31)
    )
    root = etree.fromstring(xml_bytes)

    assert root.find(".//COLLECTION/TYPE").text == "Voucher"
    assert root.find(".//SVFROMDATE").text == "20240101"
    assert root.find(".//SVTODATE").text == "20240131"

    formula = root.find('.//SYSTEM[@NAME="VchTypeFilter"]')
    assert formula is not None
    assert formula.text == '$VoucherTypeName = "Sales"'

    fetch_texts = [el.text for el in root.findall(".//COLLECTION/FETCH")]
    assert "ALLLEDGERENTRIES.LIST" in fetch_texts
    assert "ALLINVENTORYENTRIES.LIST" in fetch_texts


def test_incremental_filter_added_for_master_and_voucher():
    for entity_name in ("ledger", "sales_voucher"):
        spec = get_entity(entity_name)
        xml_bytes = build_collection_request(spec, since_alter_id=500)
        root = etree.fromstring(xml_bytes)
        formula = root.find('.//SYSTEM[@NAME="AlterIdFilter"]')
        assert formula is not None
        assert formula.text == "$AlterID > 500"


def test_non_inventory_voucher_has_no_inventory_fetch():
    spec = get_entity("payment_voucher")
    xml_bytes = build_collection_request(spec)
    root = etree.fromstring(xml_bytes)
    fetch_texts = [el.text for el in root.findall(".//COLLECTION/FETCH")]
    assert "ALLLEDGERENTRIES.LIST" in fetch_texts
    assert "ALLINVENTORYENTRIES.LIST" not in fetch_texts

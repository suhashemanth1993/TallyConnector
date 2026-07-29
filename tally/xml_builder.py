"""Builds Tally "Collection" export request XML from an EntitySpec.

One generic builder covers both masters and vouchers: the shared scaffolding
(ENVELOPE/HEADER + BODY/DESC/STATICVARIABLES/TDL/TDLMESSAGE/COLLECTION with
one FETCH per field) is identical; vouchers add a date range, a
$VoucherTypeName filter, and FETCH lines for nested ledger/inventory entry
lists. Incremental sync (masters and vouchers alike) adds an $AlterID filter.
"""

from __future__ import annotations

from datetime import date

from lxml import etree

from models.entity_spec import EntitySpec

_TALLY_DATE_FMT = "%Y%m%d"


def _sub(parent: etree._Element, tag: str, text: str | None = None) -> etree._Element:
    elem = etree.SubElement(parent, tag)
    if text is not None:
        elem.text = text
    return elem


def build_collection_request(
    spec: EntitySpec,
    *,
    since_alter_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    company: str | None = None,
) -> bytes:
    collection_name = f"{spec.name} Collection"

    envelope = etree.Element("ENVELOPE")

    header = _sub(envelope, "HEADER")
    _sub(header, "VERSION", "1")
    _sub(header, "TALLYREQUEST", "Export")
    _sub(header, "TYPE", "Collection")
    _sub(header, "ID", collection_name)

    body = _sub(envelope, "BODY")
    desc = _sub(body, "DESC")

    static_vars = _sub(desc, "STATICVARIABLES")
    _sub(static_vars, "SVEXPORTFORMAT", "$$SysName:XML")
    if company:
        _sub(static_vars, "SVCURRENTCOMPANY", company)
    if spec.is_voucher:
        if date_from:
            _sub(static_vars, "SVFROMDATE", date_from.strftime(_TALLY_DATE_FMT))
        if date_to:
            _sub(static_vars, "SVTODATE", date_to.strftime(_TALLY_DATE_FMT))

    tdl = _sub(desc, "TDL")
    tdl_message = _sub(tdl, "TDLMESSAGE")

    collection = _sub(tdl_message, "COLLECTION")
    collection.set("NAME", collection_name)
    _sub(collection, "TYPE", spec.tally_object_type)

    filter_names: list[str] = []
    if spec.is_voucher and spec.voucher_type_filter:
        filter_names.append("VchTypeFilter")
    if since_alter_id is not None:
        filter_names.append("AlterIdFilter")
    for filter_name in filter_names:
        _sub(collection, "FILTER", filter_name)

    for fetch_field in spec.fetch_fields:
        _sub(collection, "FETCH", fetch_field)
    if spec.is_voucher and spec.ledger_entries_fields:
        _sub(collection, "FETCH", "ALLLEDGERENTRIES.LIST")
    if spec.is_voucher and spec.inventory_entries_fields:
        _sub(collection, "FETCH", "ALLINVENTORYENTRIES.LIST")

    if spec.is_voucher and spec.voucher_type_filter:
        formula = _sub(tdl_message, "SYSTEM", f'$VoucherTypeName = "{spec.voucher_type_filter}"')
        formula.set("TYPE", "Formulae")
        formula.set("NAME", "VchTypeFilter")

    if since_alter_id is not None:
        formula = _sub(tdl_message, "SYSTEM", f"$AlterID > {since_alter_id}")
        formula.set("TYPE", "Formulae")
        formula.set("NAME", "AlterIdFilter")

    return etree.tostring(envelope, xml_declaration=True, encoding="UTF-8", pretty_print=True)

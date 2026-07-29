"""The entity registry: one EntitySpec per Tally master/voucher type.

This is the single source of truth the generic XML builder, XML parser, and
sync engine all read from. Object-type names for GST Masters and States are
best-effort placeholders (this environment has no live TallyPrime instance
to confirm exact TDL object names against) — verify these two against a real
Tally company and adjust `tally_object_type` if needed before relying on them.
"""

from __future__ import annotations

from models.entity_spec import EntityKind, EntitySpec
from models.masters import TallyMaster
from models.vouchers import TallyVoucher

_COMMON_VOUCHER_FIELDS = [
    "Date",
    "VoucherNumber",
    "GUID",
    "AlterID",
    "PartyLedgerName",
    "Narration",
    "VoucherTypeName",
]
_LEDGER_ENTRY_FIELDS = ["LedgerName", "Amount", "IsDeemedPositive"]
_INVENTORY_ENTRY_FIELDS = ["StockItemName", "ActualQty", "Rate", "Amount", "GodownName"]


def _master(
    name: str,
    tally_object_type: str,
    fetch_fields: list[str],
    depends_on: tuple[str, ...] = (),
    natural_key_field: str = "guid",
) -> EntitySpec:
    return EntitySpec(
        name=name,
        kind=EntityKind.MASTER,
        tally_object_type=tally_object_type,
        fetch_fields=fetch_fields,
        pydantic_model=TallyMaster,
        depends_on=depends_on,
        natural_key_field=natural_key_field,
    )


def _voucher(
    name: str,
    voucher_type_filter: str,
    *,
    has_inventory: bool,
    depends_on: tuple[str, ...],
) -> EntitySpec:
    return EntitySpec(
        name=name,
        kind=EntityKind.VOUCHER,
        tally_object_type="Voucher",
        voucher_type_filter=voucher_type_filter,
        fetch_fields=list(_COMMON_VOUCHER_FIELDS),
        ledger_entries_fields=list(_LEDGER_ENTRY_FIELDS),
        inventory_entries_fields=list(_INVENTORY_ENTRY_FIELDS) if has_inventory else None,
        pydantic_model=TallyVoucher,
        depends_on=depends_on,
    )


_MASTERS: list[EntitySpec] = [
    _master(
        "company",
        "Company",
        ["Name", "GUID", "AlterID", "StateName", "GSTRegistrationNumber"],
        # Company is a container object, not a true Tally master — unlike
        # Ledger/Group/StockItem it may not reliably expose a GUID. Only one
        # company of a given name can be open locally, so Name is a safe
        # natural key here (this is also how the original prototype
        # identified companies — NATIVEMETHOD Name alone, no GUID).
        natural_key_field="name",
    ),
    _master("group", "Group", ["Name", "Parent", "GUID", "AlterID"]),
    _master(
        "ledger",
        "Ledger",
        ["Name", "Parent", "GUID", "AlterID", "OpeningBalance", "GSTIN", "LedgerContact"],
        depends_on=("group",),
    ),
    _master("voucher_type", "VoucherType", ["Name", "Parent", "GUID", "AlterID"]),
    _master("stock_group", "StockGroup", ["Name", "Parent", "GUID", "AlterID"]),
    _master("stock_category", "StockCategory", ["Name", "Parent", "GUID", "AlterID"]),
    _master(
        "stock_item",
        "StockItem",
        ["Name", "Parent", "GUID", "AlterID", "BaseUnits", "OpeningBalance", "OpeningRate"],
        depends_on=("stock_group", "stock_category", "unit"),
    ),
    _master("unit", "Unit", ["Name", "GUID", "AlterID", "Symbol", "DecimalPlaces"]),
    _master("godown", "Godown", ["Name", "Parent", "GUID", "AlterID"]),
    _master(
        "cost_centre",
        "CostCentre",
        ["Name", "Parent", "GUID", "AlterID", "Category"],
        depends_on=("cost_category",),
    ),
    _master("cost_category", "CostCategory", ["Name", "GUID", "AlterID"]),
    _master("currency", "Currency", ["Name", "GUID", "AlterID", "DecimalPlaces"]),
    _master("gst_master", "GSTClassification", ["Name", "GUID", "AlterID", "HSNCode", "GSTRate"]),
    _master("state", "State", ["Name", "GUID", "AlterID"]),
]

_VOUCHERS: list[EntitySpec] = [
    _voucher(
        "sales_voucher",
        "Sales",
        has_inventory=True,
        depends_on=("ledger", "voucher_type", "stock_item", "godown"),
    ),
    _voucher(
        "purchase_voucher",
        "Purchase",
        has_inventory=True,
        depends_on=("ledger", "voucher_type", "stock_item", "godown"),
    ),
    _voucher(
        "receipt_voucher", "Receipt", has_inventory=False, depends_on=("ledger", "voucher_type")
    ),
    _voucher(
        "payment_voucher", "Payment", has_inventory=False, depends_on=("ledger", "voucher_type")
    ),
    _voucher(
        "contra_voucher", "Contra", has_inventory=False, depends_on=("ledger", "voucher_type")
    ),
    _voucher(
        "journal_voucher", "Journal", has_inventory=False, depends_on=("ledger", "voucher_type")
    ),
    _voucher(
        "debit_note_voucher",
        "Debit Note",
        has_inventory=True,
        depends_on=("ledger", "voucher_type", "stock_item", "godown"),
    ),
    _voucher(
        "credit_note_voucher",
        "Credit Note",
        has_inventory=True,
        depends_on=("ledger", "voucher_type", "stock_item", "godown"),
    ),
    _voucher(
        "stock_journal_voucher",
        "Stock Journal",
        has_inventory=True,
        depends_on=("voucher_type", "stock_item", "godown"),
    ),
]

REGISTRY: dict[str, EntitySpec] = {spec.name: spec for spec in [*_MASTERS, *_VOUCHERS]}


def get_entity(name: str) -> EntitySpec:
    try:
        return REGISTRY[name]
    except KeyError as exc:
        raise KeyError(f"Unknown entity '{name}'. Known entities: {sorted(REGISTRY)}") from exc


def list_masters() -> list[EntitySpec]:
    return [spec for spec in REGISTRY.values() if spec.kind is EntityKind.MASTER]


def list_vouchers() -> list[EntitySpec]:
    return [spec for spec in REGISTRY.values() if spec.kind is EntityKind.VOUCHER]


def resolve_sync_order() -> list[EntitySpec]:
    """Topologically sort the registry on `depends_on` (Kahn's algorithm),
    breaking ties by declaration order so the result is deterministic."""
    order = list(REGISTRY.keys())
    position = {name: i for i, name in enumerate(order)}
    remaining = dict(REGISTRY)
    resolved: list[EntitySpec] = []
    resolved_names: set[str] = set()

    while remaining:
        ready = sorted(
            (spec for spec in remaining.values() if set(spec.depends_on) <= resolved_names),
            key=lambda spec: position[spec.name],
        )
        if not ready:
            cyclic = ", ".join(sorted(remaining))
            raise ValueError(f"Cyclic or unresolved dependency among entities: {cyclic}")
        for spec in ready:
            resolved.append(spec)
            resolved_names.add(spec.name)
            del remaining[spec.name]

    return resolved

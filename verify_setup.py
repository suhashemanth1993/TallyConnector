"""Standalone environment sanity check — run this first on a new machine
(e.g. the Windows 7 / Python 3.8 host) before trusting `pytest` or `app.py`.

It isolates *why* something is broken (wrong Python, missing wheel, bad
.env, Tally/Frappe unreachable) instead of you reading a pytest traceback.

    python verify_setup.py
"""

from __future__ import annotations

import sys

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"

_results: list[tuple[str, str, str]] = []


def check(label: str, fn) -> None:
    try:
        status, detail = fn()
    except Exception as exc:  # noqa: BLE001 - this script's whole job is to catch and report
        status, detail = FAIL, f"{type(exc).__name__}: {exc}"
    _results.append((label, status, detail))


def check_python_version():
    v = sys.version_info
    if v < (3, 8):
        return FAIL, f"Python {v.major}.{v.minor} — need 3.8+"
    return PASS, f"Python {v.major}.{v.minor}.{v.micro}"


def check_core_imports():
    import config.settings  # noqa: F401
    import frappe.client  # noqa: F401
    import frappe.dedup  # noqa: F401
    import frappe.mapping  # noqa: F401
    import models.registry  # noqa: F401
    import services.health_check  # noqa: F401
    import services.retry_engine  # noqa: F401
    import services.scheduler  # noqa: F401
    import sync.engine  # noqa: F401
    import sync.state_store  # noqa: F401
    import tally.client  # noqa: F401
    import tally.mapper  # noqa: F401
    import tally.xml_builder  # noqa: F401
    import tally.xml_parser  # noqa: F401
    import utils.exceptions  # noqa: F401
    import utils.logging_setup  # noqa: F401

    return PASS, "all core modules imported"


def check_pydantic_models():
    from datetime import date

    from models.masters import TallyMaster
    from models.vouchers import TallyVoucher

    TallyMaster(guid="g-1", name="Test Ledger")
    TallyMaster(name="Test Company")  # no guid — the real-world Company case
    TallyVoucher(guid="g-2", voucher_type="Sales", date=date(2024, 1, 1))
    return PASS, "pydantic models instantiate (X | None / list[X] resolve correctly)"


def check_registry():
    from models.registry import REGISTRY, resolve_sync_order

    if len(REGISTRY) != 23:
        return FAIL, f"expected 23 entities, found {len(REGISTRY)}"
    order = [s.name for s in resolve_sync_order()]
    if not (order.index("company") < order.index("ledger") < order.index("sales_voucher")):
        return FAIL, f"sync order looks wrong: {order}"
    return PASS, f"23 entities, sync order OK ({order[0]} -> ... -> {order[-1]})"


def check_frappe_mapping():
    from config.settings import get_settings
    from frappe.mapping import load_mapping
    from models.registry import REGISTRY

    mapping = load_mapping(get_settings().frappe_mapping_file)
    missing = set(REGISTRY.keys()) - set(mapping.keys())
    if missing:
        return WARN, f"no mapping entry for: {sorted(missing)}"
    return PASS, f"{len(mapping)} entities mapped"


def check_env_config():
    from config.settings import get_settings

    settings = get_settings()
    problems = []
    if not settings.tally_url:
        problems.append("TALLY_URL is empty")
    if not settings.frappe_base_url:
        problems.append("FRAPPE_BASE_URL is empty (fine to skip Frappe checks for now)")
    if not settings.frappe_api_key or not settings.frappe_api_secret:
        problems.append("FRAPPE_API_KEY/SECRET not set (fine to skip Frappe checks for now)")
    if problems:
        return WARN, "; ".join(problems)
    return PASS, f"tally_url={settings.tally_url} frappe_base_url={settings.frappe_base_url}"


def check_state_store():
    import tempfile
    from pathlib import Path

    from sync.state_store import StateStore

    with tempfile.TemporaryDirectory() as tmp:
        store = StateStore(str(Path(tmp) / "check.db"))
        store.update_last_sync("ledger", last_alter_id=1)
        row = store.get_last_sync("ledger")
        store.close()
        if row is None or row["last_alter_id"] != 1:
            return FAIL, "SQLite round-trip failed"
    return PASS, "SQLite read/write OK"


def check_connectivity():
    from services.health_check import run_health_check

    status = run_health_check()
    detail = f"tally_ok={status.tally_ok} frappe_ok={status.frappe_ok}"
    if not status.tally_ok:
        detail += f" | tally_error={status.tally_error}"
    if not status.frappe_ok:
        detail += f" | frappe_error={status.frappe_error}"
    if status.all_ok:
        return PASS, detail
    return WARN, detail


def main() -> int:
    check("Python version", check_python_version)
    check("Core module imports", check_core_imports)
    check("Pydantic models (the 3.8 compatibility fix)", check_pydantic_models)
    check("Entity registry", check_registry)
    check("Frappe field mapping", check_frappe_mapping)
    check("`.env` configuration", check_env_config)
    check("SQLite state store", check_state_store)
    check("Tally / Frappe connectivity", check_connectivity)

    width = max(len(label) for label, _, _ in _results)
    print()
    for label, status, detail in _results:
        print(f"[{status:4}] {label:<{width}}  {detail}")
    print()

    if any(status == FAIL for _, status, _ in _results):
        print("Result: FAIL — fix the FAIL rows above before running app.py for real.")
        return 1
    if any(status == WARN for _, status, _ in _results):
        print("Result: PASS with warnings — connectivity/config items above need attention.")
        return 0
    print("Result: PASS — environment looks correct.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

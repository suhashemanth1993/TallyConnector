"""Dump the raw Tally XML response for one entity, unparsed — for comparing
real TallyPrime output against the field names assumed in models/registry.py.

    python dump_xml.py company
    python dump_xml.py ledger
    python dump_xml.py sales_voucher --from 2024-01-01 --to 2024-01-31
    python dump_xml.py company --out company_raw.xml
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from config.settings import get_settings
from models.registry import get_entity
from tally.client import TallyClient
from tally.xml_builder import build_collection_request


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("entity", help="entity name from models/registry.py, e.g. 'company'")
    parser.add_argument("--from", dest="date_from", help="YYYY-MM-DD, voucher entities only")
    parser.add_argument("--to", dest="date_to", help="YYYY-MM-DD, voucher entities only")
    parser.add_argument("--out", help="write response XML to this file instead of stdout")
    args = parser.parse_args()

    spec = get_entity(args.entity)
    settings = get_settings()
    date_from = date.fromisoformat(args.date_from) if args.date_from else None
    date_to = date.fromisoformat(args.date_to) if args.date_to else None

    xml_request = build_collection_request(
        spec, date_from=date_from, date_to=date_to, company=settings.tally_company or None
    )
    print(f"--- Request sent to {settings.tally_url} ---", file=sys.stderr)
    print(xml_request.decode("utf-8"), file=sys.stderr)
    print("--- Response ---", file=sys.stderr)

    client = TallyClient(settings)
    response = client.send_request(xml_request)
    text = response.decode("utf-8", errors="replace")

    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"Wrote {len(text)} chars to {args.out}", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

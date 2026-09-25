"""Regenerate data/catalog.json from data/returns_sample.csv.

Run: python scripts/build_catalog.py
This is dummy/synthetic data (see data/README.md) standing in for "the seller's
own catalogue" that identity/completeness checks compare against.
"""
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    rows = list(csv.DictReader(open(ROOT / "data/returns_sample.csv", encoding="utf-8")))
    seen: dict[tuple[str, str], dict] = {}
    for r in rows:
        key = (r["org_id"], r["ordered_sku"])
        if key in seen:
            continue
        parts = [p for p in r["parts_list"].split(";") if p]
        seen[key] = {
            "org_id": r["org_id"],
            "sku": r["ordered_sku"],
            "asin": r["ordered_asin"],
            "title": r["ordered_sku"].replace("SKU-", "").replace("-", " ").title(),
            "expected_parts": parts,
        }

    by_org: dict[str, list[dict]] = defaultdict(list)
    for (org, _sku), entry in sorted(seen.items()):
        by_org[org].append(entry)

    out = {
        "_comment": "Built from data/returns_sample.csv ordered_sku/ordered_asin/parts_list "
        "columns (dummy data, per data/README.md). Keyed by org_id -> list of SKUs. "
        "Regenerate with scripts/build_catalog.py.",
        "orgs": by_org,
    }
    (ROOT / "data/catalog.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {sum(len(v) for v in by_org.values())} entries across {len(by_org)} orgs")


if __name__ == "__main__":
    main()

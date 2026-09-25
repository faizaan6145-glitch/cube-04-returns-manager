"""(Re)build data/catalog.json from data/returns_sample.csv.

Run: python scripts/build_catalog.py
This is dummy/synthetic data (see data/README.md) standing in for "the seller's
own catalogue" that identity/completeness checks compare against.

MERGES onto whatever is already in data/catalog.json -- it never deletes
entries. This matters because scripts/scaffold_eval.py adds extra SKUs (real
household items used for evaluation) that don't come from the sample CSV;
re-running this script must not wipe those out.
"""
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "data" / "catalog.json"


def main() -> None:
    rows = list(csv.DictReader(open(ROOT / "data/returns_sample.csv", encoding="utf-8")))
    from_csv: dict[tuple[str, str], dict] = {}
    for r in rows:
        key = (r["org_id"], r["ordered_sku"])
        if key in from_csv:
            continue
        parts = [p for p in r["parts_list"].split(";") if p]
        from_csv[key] = {
            "org_id": r["org_id"],
            "sku": r["ordered_sku"],
            "asin": r["ordered_asin"],
            "title": r["ordered_sku"].replace("SKU-", "").replace("-", " ").title(),
            "expected_parts": parts,
        }

    existing: dict[tuple[str, str], dict] = {}
    if CATALOG_PATH.exists():
        current = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        for org, entries in current.get("orgs", {}).items():
            for e in entries:
                existing[(e["org_id"], e["sku"])] = e

    merged = {**from_csv, **existing}  # keep any hand-added/scaffolded entries as-is

    by_org: dict[str, list[dict]] = defaultdict(list)
    for (org, _sku), entry in sorted(merged.items()):
        by_org[org].append(entry)

    out = {
        "_comment": "Merged from data/returns_sample.csv (ordered_sku/ordered_asin/parts_list) "
        "plus any extra entries added by scripts/scaffold_eval.py. Keyed by org_id -> list of "
        "SKUs. Rebuild with scripts/build_catalog.py -- it merges, never deletes.",
        "orgs": by_org,
    }
    CATALOG_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {sum(len(v) for v in by_org.values())} entries across {len(by_org)} orgs "
          f"({len(from_csv)} from CSV, {len(existing)} pre-existing/merged)")


if __name__ == "__main__":
    main()

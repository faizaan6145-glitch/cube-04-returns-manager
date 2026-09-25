"""Sets up the evaluation set skeleton: adds household-item catalog entries,
pre-creates every eval/fixtures/<unit_id>/ folder, and writes fully-populated
eval/manifest.csv plus eval/labels_A.csv / eval/labels_B.csv (unit_id filled
in, label columns left blank for the two human raters).

Run once: python scripts/scaffold_eval.py
Safe to re-run -- it won't touch photos you've already dropped into a folder,
and it won't overwrite labels_A.csv/labels_B.csv if you've already started
filling them in.

After running, see the printed instructions (also in eval/PHOTO_PLAN.md) for
exactly what to photograph and where to put it.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = ROOT / "eval"
FIXTURES_DIR = EVAL_DIR / "fixtures"
CATALOG_PATH = ROOT / "data" / "catalog.json"

ORG_ID = "org_demo_alpha"

# (code, sku, asin, title, parts, c_unit_kind) -- c_unit_kind is "missing" if
# the C unit should be missing one part, or "damaged" if the item only has
# one part (so "missing" would mean no item at all -- use visible damage
# instead).
PRODUCTS = [
    ("BOTTLE", "SKU-BOTTLE-750", "B0DUMMY622", "Bottle 750", ["bottle", "lid"], "missing"),
    ("MUG", "SKU-MUG-11", "B0DUMMY351", "Mug 11", ["mug x2"], "damaged"),
    ("CABLE", "SKU-CABLE-USBC", "B0DUMMY261", "Cable Usbc", ["cable"], "damaged"),
    ("LAMP", "SKU-LAMP-LED", "B0DUMMY357", "Lamp Led", ["lamp", "usb cable", "manual"], "missing"),
    ("LEASH", "SKU-LEASH-6FT", "B0DUMMY205", "Leash 6Ft", ["leash"], "damaged"),
    ("TUB", "SKU-PROT-1KG", "B0DUMMY357", "Prot 1Kg", ["tub", "scoop"], "missing"),
    ("PUZZLE", "SKU-PUZZLE-500", "B0DUMMY729", "Puzzle 500", ["puzzle pieces", "poster"], "missing"),
    ("SERUM", "SKU-SERUM-30", "B0DUMMY031", "Serum 30", ["bottle", "dropper", "leaflet"], "missing"),
    ("TOWEL", "SKU-TOWEL-BLU", "B0DUMMY600", "Towel Blu", ["towel"], "damaged"),
    ("CANDLE", "SKU-CANDLE-3", "B0DUMMY964", "Candle 3", ["candle x3", "gift box"], "missing"),
    ("BUDS", "SKU-BUDS-TWS", "B0EVAL0101", "Buds Tws", ["earbuds", "case", "charging cable"], "missing"),
    ("NOTEBOOK", "SKU-NOTEBOOK-A5", "B0EVAL0102", "Notebook A5", ["notebook", "pen"], "missing"),
    ("PHONECASE", "SKU-CASE-CLR", "B0EVAL0103", "Case Clr", ["case"], "damaged"),
    ("UMBRELLA", "SKU-UMBRELLA-BLK", "B0EVAL0104", "Umbrella Blk", ["umbrella"], "damaged"),
    ("ORGANIZER", "SKU-ORGANIZER-DSK", "B0EVAL0105", "Organizer Dsk", ["organizer", "dividers"], "missing"),
    ("SCALE", "SKU-SCALE-KTC", "B0EVAL0106", "Scale Ktc", ["scale", "battery"], "missing"),
]

# (unit_code, reuses_photos_of, claimed_wrong_sku) -- wrong-item cases reuse
# an existing unit's photos under a new unit_id, claimed against a mismatched
# product, to test identity=no without extra photography.
WRONG_ITEM_CASES = [
    ("WRONGITEM-1", "MUG-A", "SKU-LEASH-6FT"),
    ("WRONGITEM-2", "CABLE-A", "SKU-TOWEL-BLU"),
    ("WRONGITEM-3", "TOWEL-A", "SKU-MUG-11"),
]

BAD_PHOTO_UNITS = ["BAD-1", "BAD-2"]

# Units dropped because the available web images did not show the right item
# (see EVAL_REPORT.md). Replaced by EXTRA_UNITS so the total stays above 50.
DROPPED = {"BOTTLE-B", "BOTTLE-C", "LAMP-B", "LEASH-A", "PUZZLE-C", "TOWEL-B", "UMBRELLA-B"}
# (unit_id, product_code, search-hint note): extra variants of products whose Commons
# categories gave clean, on-topic photos.
EXTRA_UNITS = [
    ("NOTEBOOK-D", "NOTEBOOK", "Extra notebook example."),
    ("MUG-D", "MUG", "Extra mug example."),
    ("CABLE-D", "CABLE", "Extra cable example."),
    ("SCALE-D", "SCALE", "Extra kitchen scale example."),
    ("TUB-D", "TUB", "Extra protein tub example."),
    ("BUDS-D", "BUDS", "Extra earbuds example."),
    ("PHONECASE-D", "PHONECASE", "Extra phone case example."),
]


def merge_catalog() -> None:
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    alpha = data["orgs"].setdefault(ORG_ID, [])
    existing_skus = {e["sku"] for e in alpha}
    added = []
    for code, sku, asin, title, parts, _ in PRODUCTS:
        if sku in existing_skus:
            continue
        alpha.append({"org_id": ORG_ID, "sku": sku, "asin": asin, "title": title, "expected_parts": parts})
        added.append(sku)
    if added:
        CATALOG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Catalog: added {len(added)} new SKU(s): {added or '(none, already present)'}")


def unit_rows() -> list[dict]:
    rows = []
    for code, sku, asin, title, parts, c_kind in PRODUCTS:
        rows.append({
            "unit_id": f"{code}-A", "org_id": ORG_ID, "order_id": f"ORD-EVAL-{code}-A",
            "ordered_sku": sku, "ordered_asin": asin, "image_files": "1.jpg",
            "_stage_note": "Complete, looks new / barely used (aim for Like New or Very Good).",
        })
        rows.append({
            "unit_id": f"{code}-B", "org_id": ORG_ID, "order_id": f"ORD-EVAL-{code}-B",
            "ordered_sku": sku, "ordered_asin": asin, "image_files": "1.jpg",
            "_stage_note": "Complete, but visibly used/worn (aim for Good or Acceptable).",
        })
        if c_kind == "missing":
            missing_part = parts[-1]
            rows.append({
                "unit_id": f"{code}-C", "org_id": ORG_ID, "order_id": f"ORD-EVAL-{code}-C",
                "ordered_sku": sku, "ordered_asin": asin, "image_files": "1.jpg",
                "_stage_note": f"Complete-looking EXCEPT deliberately leave out: {missing_part}.",
            })
        else:
            rows.append({
                "unit_id": f"{code}-C", "org_id": ORG_ID, "order_id": f"ORD-EVAL-{code}-C",
                "ordered_sku": sku, "ordered_asin": asin, "image_files": "1.jpg",
                "_stage_note": "Visibly damaged (scratched/dented/torn/stained) -- Acceptable or worse.",
            })
    rows = [r for r in rows if r["unit_id"] not in DROPPED]
    for unit_id, code, note in EXTRA_UNITS:
        product = next(p for p in PRODUCTS if p[0] == code)
        rows.append({
            "unit_id": unit_id, "org_id": ORG_ID, "order_id": f"ORD-EVAL-{unit_id}",
            "ordered_sku": product[1], "ordered_asin": product[2], "image_files": "1.jpg",
            "_stage_note": note,
        })
    for unit_id, reuse_of, wrong_sku in WRONG_ITEM_CASES:
        product = next(p for p in PRODUCTS if reuse_of.startswith(p[0] + "-"))
        wrong_product = next(p for p in PRODUCTS if p[1] == wrong_sku)
        rows.append({
            "unit_id": unit_id, "org_id": ORG_ID, "order_id": f"ORD-EVAL-{unit_id}",
            "ordered_sku": wrong_sku, "ordered_asin": wrong_product[2], "image_files": "1.jpg",
            "_stage_note": f"No new photos -- copy the photo from fixtures/{reuse_of}/ into this folder "
                           f"(same {product[3]}, but this row claims it was ordered as {wrong_product[3]}).",
        })
    for unit_id in BAD_PHOTO_UNITS:
        rows.append({
            "unit_id": unit_id, "org_id": ORG_ID, "order_id": f"ORD-EVAL-{unit_id}",
            "ordered_sku": PRODUCTS[0][1], "ordered_asin": PRODUCTS[0][2], "image_files": "1.jpg",
            "_stage_note": "Take 1 deliberately bad photo of ANYTHING: blurry, very dark, or just "
                           "the closed box/packaging with nothing identifiable inside.",
        })
    return rows


def write_manifest_and_folders(rows: list[dict]) -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = EVAL_DIR / "manifest.csv"
    fieldnames = ["unit_id", "org_id", "order_id", "ordered_sku", "ordered_asin", "image_files"]
    with open(manifest_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row[k] for k in fieldnames})
            (FIXTURES_DIR / row["unit_id"]).mkdir(exist_ok=True)
    print(f"Wrote {manifest_path} ({len(rows)} rows) and created {len(rows)} folders under {FIXTURES_DIR}")


def write_labels_if_absent(rows: list[dict]) -> None:
    fieldnames = ["unit_id", "identity_match", "parts_missing", "condition_grade", "disposition", "notes"]
    for name in ("labels_A.csv", "labels_B.csv"):
        path = EVAL_DIR / name
        if path.exists():
            print(f"{name}: already exists, left untouched")
            continue
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({"unit_id": row["unit_id"], "identity_match": "", "parts_missing": "",
                                  "condition_grade": "", "disposition": "", "notes": ""})
        print(f"Wrote {path} ({len(rows)} blank rows to fill in)")


def write_photo_plan(rows: list[dict]) -> None:
    lines = [
        "# Photo plan\n",
        f"Generated by `scripts/scaffold_eval.py`. {len(rows)} units total. For each row, take 1 photo "
        "(a full view and a closer look at any damage/parts/label) and save it as `1.jpg` "
        "inside the exact folder named -- the folders already exist under `eval/fixtures/`.\n",
        "| Folder (eval/fixtures/...) | What to stage |",
        "|---|---|",
    ]
    for row in rows:
        lines.append(f"| `{row['unit_id']}/` | {row['_stage_note']} |")
    (EVAL_DIR / "PHOTO_PLAN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {EVAL_DIR / 'PHOTO_PLAN.md'}")


def main() -> None:
    merge_catalog()
    rows = unit_rows()
    write_manifest_and_folders(rows)
    write_labels_if_absent(rows)
    write_photo_plan(rows)
    print(f"\nTotal units planned: {len(rows)} (>= 50 required by RULES.md).")


if __name__ == "__main__":
    main()

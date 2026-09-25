"""Turns each unit's images into a coherent pair: 1.jpg = the hand-picked on-topic photo,
2.jpg = a zoomed centre crop of the SAME photo (like a close-up shot of the same item).

Why: the first download gave each unit two unrelated search results (e.g. a mug and coffee
beans), which is nothing like a real return. Here both images always show the same item.
The 2.jpg crop is synthetic and is labelled as such in eval/IMAGE_SOURCES.csv.

CHOICES maps unit -> which of the downloaded files (1 or 2) was judged on-topic when the
contact sheets were reviewed by eye. Relevance-only curation; the agent played no part.
Run once: python scripts/pair_images.py   (skips units already paired)
"""
import csv
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
FX = ROOT / "eval" / "fixtures"
SOURCES = ROOT / "eval" / "IMAGE_SOURCES.csv"

CHOICES = {
    "BOTTLE-A": 1, "BUDS-A": 2, "BUDS-B": 2, "BUDS-C": 2, "CABLE-A": 2, "CABLE-B": 1, "CABLE-C": 2,
    "CANDLE-A": 2, "CANDLE-B": 1, "CANDLE-C": 2, "LAMP-A": 2, "LAMP-C": 2, "LEASH-B": 2, "LEASH-C": 2,
    "MUG-A": 2, "MUG-B": 2, "MUG-C": 1, "NOTEBOOK-A": 1, "NOTEBOOK-B": 1, "NOTEBOOK-C": 1,
    "ORGANIZER-A": 2, "ORGANIZER-B": 1, "ORGANIZER-C": 1, "PHONECASE-A": 2, "PHONECASE-B": 1,
    "PHONECASE-C": 2, "PHONECASE-D": 1, "PUZZLE-A": 1, "PUZZLE-B": 2, "SCALE-A": 1, "SCALE-B": 1,
    "SCALE-C": 1, "SERUM-A": 1, "SERUM-B": 2, "SERUM-C": 2, "TOWEL-A": 1, "TOWEL-C": 1, "TUB-A": 1,
    "TUB-B": 1, "TUB-C": 1, "UMBRELLA-A": 2, "UMBRELLA-C": 1,
    # extras were placed straight into 1.jpg
    "NOTEBOOK-D": 1, "MUG-D": 1, "CABLE-D": 1, "SCALE-D": 1, "TUB-D": 1, "BUDS-D": 1,
}
CROP_NOTE = "SYNTHETIC: zoomed centre crop of 1.jpg (simulates a close-up of the same item)"


def zoom_crop(img: Image.Image, keep: float = 0.55) -> Image.Image:
    w, h = img.size
    cw, ch = int(w * keep), int(h * keep)
    box = ((w - cw) // 2, (h - ch) // 2, (w - cw) // 2 + cw, (h - ch) // 2 + ch)
    return img.crop(box).resize((min(w, 900), int(min(w, 900) * ch / cw)), Image.LANCZOS)


def main() -> None:
    rows = list(csv.DictReader(open(SOURCES, encoding="utf-8")))
    done = {r["unit_id"] for r in rows if r["note"] == CROP_NOTE}
    for unit, k in CHOICES.items():
        if unit in done:
            continue
        chosen = Image.open(FX / unit / f"{k}.jpg").convert("RGB")
        chosen.save(FX / unit / "1.jpg", quality=88)
        zoom_crop(chosen).save(FX / unit / "2.jpg", quality=88)
        kept = [r for r in rows if r["unit_id"] == unit and r["file"] == f"{k}.jpg"] or \
               [r for r in rows if r["unit_id"] == unit and r["file"] == "1.jpg"]
        rows = [r for r in rows if r["unit_id"] != unit]
        if kept:
            rows.append({**kept[0], "file": "1.jpg"})
        rows.append({"unit_id": unit, "file": "2.jpg", "source_title": "(crop of 1.jpg)", "author": "", "licence": "",
                     "page_url": "", "search_query": "", "note": CROP_NOTE})
    fields = ["unit_id", "file", "source_title", "author", "licence", "page_url", "search_query", "note"]
    with open(SOURCES, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"paired {len(CHOICES)} units")


if __name__ == "__main__":
    main()

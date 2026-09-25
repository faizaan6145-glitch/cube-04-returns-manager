"""Fills eval/fixtures/<unit_id>/1.jpg with freely licensed images
from Wikimedia Commons (no API key needed) and records where each one came
from in eval/IMAGE_SOURCES.csv (title, author, licence, URL) so the evaluation
set is properly attributed.

Run: python scripts/fetch_web_images.py
Safe to re-run: units that already have both photos are skipped.

Honest limits of this approach (also stated in EVAL_REPORT.md):
* Web images are not real customer returns. Condition/missing-part cases are
  chosen by search wording ("used", "broken", ...), NOT guaranteed -- the human
  labellers decide the true labels after looking at each image.
* BAD-* units are synthetic: downloaded images, deliberately blurred/darkened.
* WRONGITEM-* units reuse another unit's images under a mismatched order.
"""
from __future__ import annotations

import csv
import io
import re
import shutil
import sys
import time
from pathlib import Path

import httpx
from PIL import Image, ImageEnhance, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scaffold_eval import BAD_PHOTO_UNITS, DROPPED, EXTRA_UNITS, FIXTURES_DIR, PRODUCTS, WRONG_ITEM_CASES  # noqa: E402

EVAL_DIR = FIXTURES_DIR.parent
API = "https://commons.wikimedia.org/w/api.php"
# Wikimedia's robot policy rejects anonymous user agents; identify the project by its repo URL.
HEADERS = {"User-Agent": "ReturnsManagerEval/1.0 (https://github.com/faizaan6145-glitch/cube-04-returns-manager) httpx"}
ALLOWED_LICENCE = re.compile(r"^(cc0|public domain|pd|cc[ -]by)", re.I)

# What to search for per product: a plain noun for the item.
NOUN = {
    "BOTTLE": "stainless steel water bottle", "MUG": "ceramic coffee mug", "CABLE": "USB-C cable",
    "LAMP": "LED desk lamp", "LEASH": "dog leash", "TUB": "protein powder",
    "PUZZLE": "jigsaw puzzle box", "SERUM": "dropper bottle", "TOWEL": "bath towel",
    "CANDLE": "candles", "BUDS": "earbuds",
    "NOTEBOOK": "notebook with pen", "PHONECASE": "smartphone case", "UMBRELLA": "umbrella",
    "ORGANIZER": "desk organizer", "SCALE": "digital kitchen scale",
}
# Commons categories (searched incl. sub-categories) -- far more on-topic than free text.
CATEGORIES = {
    "BOTTLE": ["Water bottles"], "MUG": ["Coffee mugs", "Mugs"], "CABLE": ["USB-C cables", "USB cables"],
    "LAMP": ["Desk lamps"], "LEASH": ["Leashes"], "TUB": ["Protein powders"], "PUZZLE": ["Jigsaw puzzles"],
    "CANDLE": ["Scented candles", "Candles"], "BUDS": ["Wireless earbuds"], "NOTEBOOK": ["Notebooks"],
    "PHONECASE": ["Phone cases", "Mobile phone covers"], "UMBRELLA": ["Umbrellas"],
    "ORGANIZER": ["Letter trays", "Pen stands"], "SCALE": ["Digital kitchen scales", "Kitchen scales"],
    "TOWEL": ["Bath towels", "Towels"],
}
# Search-wording per unit kind. Only a hint; humans label the real truth.
KIND_WORDS = {"A": ["", "product"], "B": ["used", "worn"], "C_damaged": ["broken", "damaged"],
              "C_missing": ["", "single"]}


def search(client: httpx.Client, query: str, limit: int = 40) -> list[dict]:
    r = client.get(API, params={
        "action": "query", "generator": "search", "gsrsearch": f"filetype:bitmap {query}",
        "gsrnamespace": 6, "gsrlimit": limit, "prop": "imageinfo",
        "iiprop": "url|extmetadata|size|mime", "iiurlwidth": 900, "format": "json",
    }, timeout=30)
    r.raise_for_status()
    pages = (r.json().get("query") or {}).get("pages") or {}
    out = []
    for p in sorted(pages.values(), key=lambda x: x.get("index", 0)):
        info = (p.get("imageinfo") or [None])[0]
        if not info or info.get("mime") not in ("image/jpeg", "image/png"):
            continue
        if info.get("width", 0) < 500 or info.get("height", 0) < 400:
            continue
        meta = info.get("extmetadata") or {}
        licence = (meta.get("LicenseShortName") or {}).get("value", "")
        if not ALLOWED_LICENCE.match(licence):
            continue
        author = re.sub(r"<[^>]+>", "", (meta.get("Artist") or {}).get("value", "unknown")).strip()
        out.append({"title": p["title"], "url": info.get("thumburl") or info["url"],
                    "page": info.get("descriptionurl", ""), "licence": licence, "author": author[:120]})
    return out


def download_jpeg(client: httpx.Client, url: str, dest: Path) -> bool:
    for attempt in range(3):
        try:
            r = client.get(url, timeout=40)
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            Image.open(io.BytesIO(r.content)).convert("RGB").save(dest, "JPEG", quality=88)
            return True
        except Exception as exc:  # noqa: BLE001 - skip bad candidates, try the next
            print(f"    download failed ({exc.__class__.__name__}), trying next")
            time.sleep(2)
    return False


def unit_plan() -> list[tuple[str, str, str]]:
    """(unit_id, product_code, kind)"""
    plan = []
    for code, _sku, _asin, _t, _parts, c_kind in PRODUCTS:
        plan += [(f"{code}-A", code, "A"), (f"{code}-B", code, "B"),
                 (f"{code}-C", code, "C_missing" if c_kind == "missing" else "C_damaged")]
    plan = [u for u in plan if u[0] not in DROPPED]
    plan += [(uid, code, "B") for uid, code, _ in EXTRA_UNITS]
    return plan


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sources_path = EVAL_DIR / "IMAGE_SOURCES.csv"
    rows: list[dict] = []
    if sources_path.exists():
        rows = list(csv.DictReader(open(sources_path, encoding="utf-8")))
    rejected_path = EVAL_DIR / "IMAGE_REJECTED.txt"
    rejected = set(rejected_path.read_text(encoding="utf-8").splitlines()) if rejected_path.exists() else set()
    if "--redo" in sys.argv:
        redo = set(sys.argv[sys.argv.index("--redo") + 1].split(","))
        for r in rows:
            if r["unit_id"] in redo:
                rejected.add(r["source_title"])
        rows = [r for r in rows if r["unit_id"] not in redo]
        for u in redo:
            for f in ("1.jpg", "2.jpg"):
                (FIXTURES_DIR / u / f).unlink(missing_ok=True)
        rejected_path.write_text(chr(10).join(sorted(rejected)), encoding="utf-8")
    used_titles = {r["source_title"] for r in rows} | rejected

    try:
      with httpx.Client(headers=HEADERS, follow_redirects=True) as client:
        for unit_id, code, kind in unit_plan():
            folder = FIXTURES_DIR / unit_id
            folder.mkdir(parents=True, exist_ok=True)
            if (folder / "1.jpg").exists():
                continue
            print(f"{unit_id}: searching...")
            got = 0
            queries = [f'deepcategory:"{c}" {w}'.strip() for w in (KIND_WORDS[kind] + [""] if "--plain" not in sys.argv else [""]) for c in CATEGORIES.get(code, [])]
            queries += [f"{w} {NOUN[code]}".strip() for w in KIND_WORDS[kind] + [""]]
            for query in queries:
                if got >= 1:
                    break
                try:
                    candidates = search(client, query)
                except Exception as exc:  # noqa: BLE001
                    print(f"    search failed: {exc}")
                    continue
                time.sleep(1)
                for c in candidates:
                    if got >= 1:
                        break
                    if c["title"] in used_titles:
                        continue
                    if download_jpeg(client, c["url"], folder / f"{got + 1}.jpg"):
                        used_titles.add(c["title"])
                        got += 1
                        rows.append({"unit_id": unit_id, "file": f"{got}.jpg", "source_title": c["title"],
                                     "author": c["author"], "licence": c["licence"], "page_url": c["page"],
                                     "search_query": query, "note": ""})
                        print(f"    {got}.jpg <- {c['title']} ({c['licence']})")
                        time.sleep(0.5)
            if got < 1:
                print(f"    !! only found {got}/1 images for {unit_id}")

        # WRONGITEM-*: copy another unit's images.
        for unit_id, reuse_of, _sku in WRONG_ITEM_CASES:
            src, dst = FIXTURES_DIR / reuse_of, FIXTURES_DIR / unit_id
            dst.mkdir(parents=True, exist_ok=True)
            if (src / "1.jpg").exists() and not (dst / "1.jpg").exists():
                for f in ("1.jpg",):
                    shutil.copy(src / f, dst / f)
                    rows.append({"unit_id": unit_id, "file": f, "source_title": f"(copy of {reuse_of}/{f})",
                                 "author": "", "licence": "", "page_url": "", "search_query": "",
                                 "note": "reused under a mismatched order to test wrong-item detection"})

        # BAD-*: synthetic degraded copies of downloaded images.
        donors = ["MUG-B", "CABLE-B"]  # both images of a BAD unit come from ONE item
        for i, unit_id in enumerate(BAD_PHOTO_UNITS):
            dst = FIXTURES_DIR / unit_id
            dst.mkdir(parents=True, exist_ok=True)
            if (dst / "1.jpg").exists():
                continue
            for n, f in enumerate(("1.jpg",)):
                donor = FIXTURES_DIR / donors[i] / f
                if not donor.exists():
                    continue
                img = Image.open(donor).convert("RGB")
                if i == 0:  # very blurry
                    img = img.filter(ImageFilter.GaussianBlur(28))
                else:  # very dark
                    img = ImageEnhance.Brightness(img).enhance(0.08)
                img.save(dst / f, "JPEG", quality=85)
                rows.append({"unit_id": unit_id, "file": f, "source_title": f"(degraded copy of {donors[i]}/{f})",
                             "author": "", "licence": "", "page_url": "", "search_query": "",
                             "note": "SYNTHETIC: " + ("blurred" if i == 0 else "darkened")})

    finally:
        _save(sources_path, rows)


def _save(sources_path: Path, rows: list[dict]) -> None:
    fields = ["unit_id", "file", "source_title", "author", "licence", "page_url", "search_query", "note"]
    with open(sources_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    complete = sum(1 for d in FIXTURES_DIR.iterdir() if (d / "1.jpg").exists())
    print(f"\n{complete}/{len(list(FIXTURES_DIR.iterdir()))} unit folders have their image. Sources: {sources_path}")


if __name__ == "__main__":
    main()

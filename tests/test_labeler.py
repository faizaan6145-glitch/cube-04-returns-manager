import csv
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from eval.labeler import create_app

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def env(tmp_path):
    eval_dir = tmp_path / "eval"
    (eval_dir / "fixtures" / "BOTTLE-A").mkdir(parents=True)
    (eval_dir / "fixtures" / "MUG-A").mkdir(parents=True)
    for u in ("BOTTLE-A", "MUG-A"):
        for n in (1, 2):
            (eval_dir / "fixtures" / u / f"{n}.jpg").write_bytes(b"\xff\xd8fake")
    (eval_dir / "manifest.csv").write_text(
        "unit_id,org_id,order_id,ordered_sku,ordered_asin,image_files\n"
        "BOTTLE-A,org_demo_alpha,O1,SKU-BOTTLE-750,B0DUMMY622,1.jpg;2.jpg\n"
        "MUG-A,org_demo_alpha,O2,SKU-MUG-11,B0DUMMY351,1.jpg;2.jpg\n", encoding="utf-8")
    catalog = tmp_path / "catalog.json"
    shutil.copy(ROOT / "data" / "catalog.json", catalog)
    client = TestClient(create_app(eval_dir, catalog), follow_redirects=False)
    return client, eval_dir


def rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return {r["unit_id"]: r for r in csv.DictReader(f)}


GOOD = {"identity_match": "yes", "condition_grade": "used_good", "disposition": "refurbish", "notes": "scuffed"}


def test_save_writes_only_that_raters_file_and_advances(env):
    client, eval_dir = env
    r = client.post("/r/A/u/BOTTLE-A", data={**GOOD, "parts_missing": ["lid"]})
    assert r.status_code == 303 and r.headers["location"] == "/r/A/u/MUG-A"
    saved = rows(eval_dir / "labels_A.csv")["BOTTLE-A"]
    assert saved["parts_missing"] == "lid" and saved["disposition"] == "refurbish"
    assert not (eval_dir / "labels_B.csv").exists()  # raters never touch each other's file


def test_unit_page_shows_catalogue_but_no_hints(env):
    client, _ = env
    html = client.get("/r/A/u/BOTTLE-A").text
    assert "Bottle 750" in html and "lid" in html
    assert "IMAGE_SOURCES" not in html and "stage" not in html.lower()


def test_prefills_after_save_and_other_rater_sees_nothing(env):
    client, _ = env
    client.post("/r/A/u/BOTTLE-A", data={**GOOD, "parts_missing": ["lid"]})
    assert "checked" in client.get("/r/A/u/BOTTLE-A").text
    assert "checked" not in client.get("/r/B/u/BOTTLE-A").text.split("Completeness")[1].split("Condition")[0]


def test_rejects_invalid_values_and_unknown_parts(env):
    client, eval_dir = env
    assert client.post("/r/A/u/BOTTLE-A", data={**GOOD, "disposition": "bogus"}).status_code == 400
    assert client.post("/r/C/u/BOTTLE-A", data=GOOD).status_code == 404
    client.post("/r/A/u/BOTTLE-A", data={**GOOD, "parts_missing": ["lid", "not-a-part"]})
    assert rows(eval_dir / "labels_A.csv")["BOTTLE-A"]["parts_missing"] == "lid"


def test_images_only_for_manifest_units(env):
    client, _ = env
    assert client.get("/img/BOTTLE-A/1").status_code == 200
    assert client.get("/img/..%2F..%2Fmanifest.csv/1").status_code == 404
    assert client.get("/img/BOTTLE-A/3").status_code == 404


def test_progress_counts_only_complete_labels(env):
    client, _ = env
    client.post("/r/A/u/BOTTLE-A", data=GOOD)
    assert "1/2 labelled" in client.get("/r/A").text

"""Local labelling page for the evaluation set.

Run:  python -m uvicorn eval.labeler:app --port 8001
Open: http://127.0.0.1:8001

Two people label independently: rater A writes eval/labels_A.csv, rater B writes
eval/labels_B.csv. The page deliberately shows only what a real operator would
know -- the two images, the ordered item and its expected parts list. It does NOT
show the search hints, image sources, the other rater's labels or the agent's
output, since any of those would bias the labels (RULES.md: independent labels).

This is a local tool. It is not mounted on the deployed app, so the fixtures are
never served publicly.
"""
from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from jinja2 import DictLoader, Environment, select_autoescape

from app.catalog import load_catalog
from app.condition_scale import GRADES

ROOT = Path(__file__).resolve().parent.parent
LABEL_FIELDS = ["unit_id", "identity_match", "parts_missing", "condition_grade", "disposition", "notes"]
DISPOSITIONS = ["restock", "refurbish", "liquidate", "dispose", "pending_review"]
IDENTITY = ["yes", "no", "uncertain"]
RATERS = ("A", "B")

DISPOSITION_HELP = {
    "restock": "resell as-is",
    "refurbish": "fix / clean / repackage, then resell",
    "liquidate": "sell cheaply in bulk",
    "dispose": "cannot be resold",
    "pending_review": "you can't decide from the images",
}

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Eval labeller</title>
<style>
:root{color-scheme:light dark;--bg:#fafafa;--fg:#1a1a1a;--card:#0000000d;--line:#8885;--acc:#2563eb}
@media(prefers-color-scheme:dark){:root{--bg:#16181c;--fg:#e6e6e6}}
body{font-family:system-ui,sans-serif;background:var(--bg);color:var(--fg);max-width:1100px;margin:1.2rem auto;padding:0 1rem}
a{color:var(--acc)} .card{background:var(--card);border-radius:10px;padding:.9rem 1.1rem;margin:.8rem 0}
.imgs{display:grid;grid-template-columns:1fr 1fr;gap:.6rem}.imgs a img{width:100%;max-height:60vh;object-fit:contain;border-radius:8px;background:#0002}
@media(max-width:700px){.imgs{grid-template-columns:1fr}}
label{display:block;font-weight:600;margin-top:.8rem} select,input[type=text],textarea{width:100%;padding:.5rem;font-size:1rem;box-sizing:border-box;background:inherit;color:inherit;border:1px solid var(--line);border-radius:6px}
button,.btn{padding:.6rem 1.1rem;border:0;border-radius:6px;background:var(--acc);color:#fff;font-size:1rem;cursor:pointer;text-decoration:none;display:inline-block}
.btn.sec{background:#6b7280}.small{font-size:.85rem;opacity:.8}.bar{height:8px;background:var(--line);border-radius:4px;overflow:hidden}.bar i{display:block;height:100%;background:var(--acc)}
.grid{display:flex;flex-wrap:wrap;gap:.35rem}.chip{padding:.25rem .55rem;border-radius:999px;border:1px solid var(--line);font-size:.85rem;text-decoration:none;color:inherit}.chip.done{background:#16a34a33;border-color:#16a34a}
.parts label{display:inline-block;font-weight:400;margin:.3rem .8rem 0 0} .parts input{width:auto}
details{margin-top:.5rem}
</style></head><body>{% block body %}{% endblock %}</body></html>"""

HOME = """{% extends "page" %}{% block body %}
<h1>Evaluation labeller</h1>
<p>Label each unit <b>independently</b> from the images only. Do not look at the other person's labels or at the agent's results first.</p>
<div class="card"><p>Who are you?</p>
<a class="btn" href="/r/A">I am rater A (writes labels_A.csv)</a> &nbsp; <a class="btn sec" href="/r/B">I am rater B (writes labels_B.csv)</a></div>
{% endblock %}"""

LIST = """{% extends "page" %}{% block body %}
<h1>Rater {{ rater }} &mdash; {{ done }}/{{ total }} labelled</h1>
<div class="bar"><i style="width:{{ pct }}%"></i></div>
<p><a href="/">&larr; switch rater</a> &middot; <a href="{{ next_url }}" class="btn">{{ 'Continue' if done < total else 'Review first unit' }}</a></p>
<div class="grid">{% for u in units %}<a class="chip {{ 'done' if u.done }}" href="/r/{{ rater }}/u/{{ u.id }}">{{ u.id }}</a>{% endfor %}</div>
{% endblock %}"""

UNIT = """{% extends "page" %}{% block body %}
<p><a href="/r/{{ rater }}">&larr; all units</a> &middot; Rater <b>{{ rater }}</b> &middot; unit {{ idx + 1 }}/{{ total }} &middot; {{ done }} labelled</p>
<div class="bar"><i style="width:{{ pct }}%"></i></div>
<h2>{{ unit_id }}{% if saved %} <span class="small">&#10003; saved</span>{% endif %}</h2>
<div class="imgs">{% for n in (1, 2) %}<a href="/img/{{ unit_id }}/{{ n }}" target="_blank"><img src="/img/{{ unit_id }}/{{ n }}" alt="image {{ n }}"></a>{% endfor %}</div>
<div class="card"><b>Ordered:</b> {{ item.title }} <span class="small">({{ item.sku }})</span><br>
<b>Expected parts:</b> {{ item.parts | join(", ") }}</div>
<form method="post" class="card">
<label>1. Identity &mdash; is this the item that was ordered?
<select name="identity_match" required><option value="">choose&hellip;</option>{% for v in identity %}<option value="{{ v }}" {{ 'selected' if lab.identity_match == v }}>{{ v }}</option>{% endfor %}</select></label>
<div class="small">yes = same product; no = clearly something else (or not a product at all); uncertain = images don't show enough to tell.</div>
<label>2. Completeness &mdash; tick every expected part that is <u>NOT visible / missing</u></label>
<div class="parts">{% for p in item.parts %}<label><input type="checkbox" name="parts_missing" value="{{ p }}" {{ 'checked' if p in lab.missing }}> {{ p }}</label>{% endfor %}</div>
<label>3. Condition &mdash; Amazon's scale
<select name="condition_grade" required><option value="">choose&hellip;</option>{% for k, g in grades %}<option value="{{ k }}" {{ 'selected' if lab.condition_grade == k }}>{{ g.label }}</option>{% endfor %}
<option value="uncertain" {{ 'selected' if lab.condition_grade == 'uncertain' }}>Can't grade from these images</option></select></label>
<details><summary class="small">Show grade definitions</summary><ul class="small">{% for k, g in grades %}<li><b>{{ g.label }}</b>: {{ g.definition }}</li>{% endfor %}</ul></details>
<label>4. Disposition &mdash; what should happen to it?
<select name="disposition" required><option value="">choose&hellip;</option>{% for v in dispositions %}<option value="{{ v }}" {{ 'selected' if lab.disposition == v }}>{{ v }} &mdash; {{ help[v] }}</option>{% endfor %}</select></label>
<label>Notes (optional)<textarea name="notes" rows="2">{{ lab.notes }}</textarea></label>
<p><button type="submit">Save &amp; next</button>
{% if prev_url %} <a class="btn sec" href="{{ prev_url }}">&larr; Previous</a>{% endif %}
{% if next_url_plain %} <a class="btn sec" href="{{ next_url_plain }}">Skip &rarr;</a>{% endif %}</p>
</form>{% endblock %}"""

_env = Environment(loader=DictLoader({"page": PAGE, "home": HOME, "list": LIST, "unit": UNIT}),
                   autoescape=select_autoescape(default=True))


def create_app(eval_dir: Path = ROOT / "eval", catalog_path: Path = ROOT / "data" / "catalog.json") -> FastAPI:
    app = FastAPI(title="Eval labeller")
    fixtures = eval_dir / "fixtures"

    def manifest() -> list[dict]:
        path = eval_dir / "manifest.csv"
        if not path.exists():
            raise HTTPException(500, "eval/manifest.csv not found -- run scripts/scaffold_eval.py first.")
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def label_path(rater: str) -> Path:
        if rater not in RATERS:
            raise HTTPException(404, "Rater must be A or B.")
        return eval_dir / f"labels_{rater}.csv"

    def read_labels(rater: str) -> dict[str, dict]:
        path = label_path(rater)
        if not path.exists():
            return {}
        with open(path, newline="", encoding="utf-8") as f:
            return {r["unit_id"]: r for r in csv.DictReader(f)}

    def write_labels(rater: str, units: list[str], labels: dict[str, dict]) -> None:
        path = label_path(rater)
        fd, tmp = tempfile.mkstemp(dir=eval_dir, suffix=".tmp")
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=LABEL_FIELDS)
            w.writeheader()
            for u in units:
                row = labels.get(u, {})
                w.writerow({k: row.get(k, "") if k != "unit_id" else u for k in LABEL_FIELDS})
        os.replace(tmp, path)  # atomic: a crash never leaves a half-written labels file

    def is_done(row: dict | None) -> bool:
        return bool(row and row.get("identity_match") and row.get("disposition") and row.get("condition_grade"))

    def render(name: str, **ctx) -> HTMLResponse:
        return HTMLResponse(_env.get_template(name).render(**ctx))

    @app.get("/", response_class=HTMLResponse)
    def home():
        return render("home")

    @app.get("/r/{rater}", response_class=HTMLResponse)
    def unit_list(rater: str):
        rows, labels = manifest(), read_labels(rater)
        units = [{"id": r["unit_id"], "done": is_done(labels.get(r["unit_id"]))} for r in rows]
        done = sum(u["done"] for u in units)
        first_open = next((u["id"] for u in units if not u["done"]), units[0]["id"])
        return render("list", rater=rater, units=units, done=done, total=len(units),
                      pct=round(100 * done / len(units)), next_url=f"/r/{rater}/u/{first_open}")

    @app.get("/r/{rater}/u/{unit_id}", response_class=HTMLResponse)
    def unit_page(rater: str, unit_id: str, saved: int = 0):
        rows, labels = manifest(), read_labels(rater)
        ids = [r["unit_id"] for r in rows]
        if unit_id not in ids:
            raise HTTPException(404, "Unknown unit.")
        idx, row = ids.index(unit_id), rows[ids.index(unit_id)]
        cat = load_catalog(catalog_path).lookup(row["org_id"], row["ordered_sku"])
        item = {"sku": row["ordered_sku"], "title": cat.title if cat else row["ordered_sku"],
                "parts": cat.expected_parts if cat else []}
        lab = labels.get(unit_id, {})
        lab_ctx = {"identity_match": lab.get("identity_match", ""), "condition_grade": lab.get("condition_grade", ""),
                   "disposition": lab.get("disposition", ""), "notes": lab.get("notes", ""),
                   "missing": [p for p in (lab.get("parts_missing") or "").split(";") if p]}
        done = sum(is_done(labels.get(i)) for i in ids)
        return render("unit", rater=rater, unit_id=unit_id, idx=idx, total=len(ids), done=done,
                      pct=round(100 * done / len(ids)), item=item, lab=lab_ctx, saved=bool(saved),
                      identity=IDENTITY, dispositions=DISPOSITIONS, help=DISPOSITION_HELP,
                      grades=list(GRADES.items()),
                      prev_url=f"/r/{rater}/u/{ids[idx - 1]}" if idx > 0 else None,
                      next_url_plain=f"/r/{rater}/u/{ids[idx + 1]}" if idx < len(ids) - 1 else None)

    @app.post("/r/{rater}/u/{unit_id}")
    def save(rater: str, unit_id: str, identity_match: str = Form(...), condition_grade: str = Form(...),
             disposition: str = Form(...), parts_missing: list[str] = Form(default=[]), notes: str = Form("")):
        rows = manifest()
        ids = [r["unit_id"] for r in rows]
        if unit_id not in ids:
            raise HTTPException(404, "Unknown unit.")
        if identity_match not in IDENTITY or disposition not in DISPOSITIONS or \
                condition_grade not in [*GRADES, "uncertain"]:
            raise HTTPException(400, "Invalid label value.")
        row = rows[ids.index(unit_id)]
        cat = load_catalog(catalog_path).lookup(row["org_id"], row["ordered_sku"])
        allowed = set(cat.expected_parts) if cat else set()
        labels = read_labels(rater)
        labels[unit_id] = {"unit_id": unit_id, "identity_match": identity_match,
                           "parts_missing": ";".join(p for p in parts_missing if p in allowed),
                           "condition_grade": condition_grade, "disposition": disposition,
                           "notes": notes.strip()}
        write_labels(rater, ids, labels)
        after = ids[ids.index(unit_id) + 1:] + ids[:ids.index(unit_id)]
        nxt = next((i for i in after if not is_done(labels.get(i))), None)
        return RedirectResponse(f"/r/{rater}/u/{nxt}" if nxt else f"/r/{rater}", status_code=303)

    @app.get("/img/{unit_id}/{n}")
    def image(unit_id: str, n: int):
        if unit_id not in {r["unit_id"] for r in manifest()} or n not in (1, 2):
            raise HTTPException(404, "Not found.")
        path = fixtures / unit_id / f"{n}.jpg"
        if not path.exists():
            raise HTTPException(404, "Image missing.")
        return FileResponse(path)

    return app


app = create_app()

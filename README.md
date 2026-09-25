# Returns Manager

**Cube Buildathon · 04 · Returns Manager · Round 2 (individual build)**

An agent that looks at photos of a customer-returned item and decides:

1. **Identity** — is this the SKU/ASIN that was actually ordered?
2. **Completeness** — are all the expected parts there?
3. **Condition** — graded on Amazon's own published condition scale.
4. **Disposition** — `restock`, `refurbish`, `liquidate`, `dispose`, or
   `pending_review`.

It returns a structured, traceable evidence record for each return so the
next stage in the chain (Recovery Manager) can consume it. See
[`ARCHITECTURE.md`](ARCHITECTURE.md) for how it's built, [`EVAL_REPORT.md`](EVAL_REPORT.md)
for measured results, and [`FINDINGS.md`](FINDINGS.md) for contradictions
found in the brief and sample data along the way. The original problem
statement/rules from the organisers are still in [`RULES.md`](RULES.md) and
[`GITHUB-GUIDE.md`](GITHUB-GUIDE.md).

## How it works, in one paragraph

Upload 2-3 photos plus the order's SKU/ASIN. One batched call to Gemini
(vision + reasoning) checks identity, completeness and condition together and
returns strict JSON with a verdict, confidence and explanation for each.
Disposition is then decided by fixed Python rules from those three verdicts —
not by the model — so every decision can be explained in one sentence. If the
model call fails or times out, the case is still saved with status
`pending_review` instead of being dropped ("fail open"). Every check that's
too ambiguous to call reliably comes back `UNCERTAIN`, which is treated as a
first-class outcome, not a forced guess.

## Setup

Requires Python 3.11+.

```sh
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:

* `GEMINI_API_KEY` — get a free key at <https://aistudio.google.com/apikey>.
* `ORG_KEYS` — pick your own long random values for the two demo orgs, e.g.
  `org_demo_alpha:some-long-random-string,org_demo_bravo:another-long-string`.

## Run it

```sh
uvicorn app.main:app --reload
```

Open <http://localhost:8000>, paste in one org's API key from `.env`, fill in
a unit/order/SKU/ASIN (see `data/returns_sample.csv` for examples) and upload
2-3 photos. You'll land on the evidence record page.

The API can also be called directly:

```sh
curl -X POST http://localhost:8000/agent \
  -H "X-API-Key: <key from ORG_KEYS>" \
  -F operator_label=op_you -F unit_id=UNIT-0001 -F order_id=ORD-0001 \
  -F ordered_sku=SKU-PUZZLE-500 -F ordered_asin=B0DUMMY729 \
  -F images=@photo1.jpg -F images=@photo2.jpg
```

`GET /health` for a liveness check.

## Test

```sh
pytest
```

Covers: tenant isolation (`tests/test_isolation.py` — org B can't read org A's
records or images, even by guessing an id), fail-open behaviour
(`tests/test_fail_open.py` — a model timeout/error still saves the case),
disposition rules (`tests/test_disposition.py`), the evidence schema
(`tests/test_schema.py`), and the evaluation metrics themselves
(`tests/test_eval_metrics.py`).

## Evaluate

```sh
python eval/run_eval.py
```

Runs the real pipeline over an unseen, two-human-labelled set and reports
per-check accuracy, false positives/negatives, `UNCERTAIN` rate, human
agreement (Cohen's kappa) and latency. See [`eval/README.md`](eval/README.md)
for how to build the evaluation set, and [`EVAL_REPORT.md`](EVAL_REPORT.md)
for the results.

## Project layout

```
app/
  main.py            FastAPI routes: /, /agent, /health, /records/{id}, /images/{id}
  pipeline.py         identity -> completeness -> condition -> disposition
  gemini_client.py    one batched Gemini call, JSON schema, timeout, fail-open
  disposition.py      deterministic disposition rules
  condition_scale.py  Amazon's published condition grades + source
  catalog.py          per-org SKU/ASIN/parts lookup
  store.py            SQLite, every query scoped by organization_id
  schemas.py          the evidence record contract (Pydantic)
  templates/          upload form + evidence record page
data/
  returns_sample.csv  organiser-provided sample data (dummy)
  catalog.json         built from returns_sample.csv (scripts/build_catalog.py)
eval/                 evaluation set tooling (see eval/README.md)
tests/                pytest suite
```

## Deploy

A `render.yaml` is included for [Render](https://render.com)'s free tier:
push to your fork, connect the repo on Render, set `GEMINI_API_KEY` and
`ORG_KEYS` as environment variables in the Render dashboard (don't commit
them), and deploy.

## Status

See the buildathon checklist and dates in [`RULES.md`](RULES.md). This is an
individual Round 2 submission for the **04 · Returns Manager** track.

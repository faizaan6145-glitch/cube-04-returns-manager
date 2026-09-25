# Architecture — Returns Manager

## Overview

```
Browser / curl
     │  POST /agent (photos + order info + API key)
     ▼
FastAPI (app/main.py)
     │  resolves API key -> organization_id
     ▼
app/pipeline.py ──calls──▶ app/gemini_client.py ──▶ Gemini (one batched call)
     │                              │ (identity + completeness + condition,
     │                              │  strict JSON schema, timeout)
     │  ◀── GeminiOutcome (ok / error) ──┘
     │
     ├─ ok=True  → build Check[] from the JSON, downgrade low-confidence
     │              PASS/FAIL to UNCERTAIN
     ├─ ok=False → build Check[] that are all UNCERTAIN, status="error"
     │              (fail open — never drop the case)
     ▼
app/disposition.py — deterministic rules turn the three checks + condition
     grade into one of restock/refurbish/liquidate/dispose/pending_review
     ▼
EvidenceRecord (app/schemas.py) — the official contract shape
     ▼
app/store.py (SQLite, every query filtered by organization_id)
     ▼
HTML record page (app/templates/record.html) — shows checks, outcome,
     lets the operator override a verdict (POST /records/{id}/override)
```

## Why this shape

**One Gemini call per return, not three.** `app/gemini_client.py` sends every
photo plus the catalogue entry and the condition scale in a single request and
gets back one JSON object with all three checks. This satisfies RULES.md
Engineering Rule 2 ("batch model calls") — a return with 3 photos costs one
model call, not three.

**Disposition is a deterministic function of the checks, not another model
call.** `app/disposition.py` is pure Python: given the three verdicts and the
condition grade, it applies a fixed rule table (see the module docstring for
the exact order). This means every disposition can be explained in one
sentence without re-asking the model, and it's trivially unit-testable
(`tests/test_disposition.py`).

**Fail open.** `app/gemini_client.run_checks` never raises — timeouts,
network errors and bad JSON all come back as `GeminiOutcome(ok=False, ...)`.
`app/pipeline.py` turns that into three `UNCERTAIN` checks and status=`error`,
and the record is still saved. See `tests/test_fail_open.py`.

**UNCERTAIN is real.** Two places force it: the model can return `UNCERTAIN`
directly, and `pipeline._downgrade_low_confidence` forces any PASS/FAIL below
`MIN_CONFIDENCE` (default 0.6, `.env`) down to `UNCERTAIN` — a shaky PASS is
not trustworthy enough to act on. Any `UNCERTAIN` check forces the disposition
to `pending_review` (`disposition.py`, rule 2).

**Tenant isolation.** Each org has one API key (`ORG_KEYS` in `.env`).
`app/main.resolve_org` is the only place that turns a key into an
`organization_id`, and every `app/store.py` query takes `organization_id` as a
required filter — there's no query that can return another tenant's row.
Images are saved per-org (`storage/images/<org_id>/`) and served only through
`/images/{id}`, which does the same org check. `tests/test_isolation.py`
proves org B gets a 404 (not a 403 — nothing suggests the row exists) for org
A's records and images, even when guessing a valid id.

**Keyless web UI (optional).** Customers shouldn't have to handle an API key, so if `UI_ORG_ID` is set the
*website* (upload, result, history, images, overrides) acts as that one organisation when no key is sent
(`app.main.resolve_ui_org`). An explicit key always wins, so another org's key still gets 404 on this org's
records. The JSON API (`/api/...`) and scripted `/agent` calls never use the fallback and still need a key
(`tests/test_ui_mode.py`). **Trade-off, stated plainly:** in this mode anyone who can reach the site can see
that org's data -- there is no per-user login. That is acceptable for a local demo; a real deployment needs a
proper login (sessions/SSO) mapping each user to their org. If `UI_ORG_ID` is unset, the site asks for an
access key exactly as before.

**Overrides are additive.** `POST /records/{id}/override` appends an
`Override` (original verdict, revised verdict, reason, who, when) to the
record's `overrides` list. The original `checks` entry is never modified.

## Evidence record

`app/schemas.py` implements the official contract fields named in
README.md/RULES.md: `record_id, schema_version, organization_id, client_id,
agent, subject, captured_at, operator_label, images, checks, outcome,
overrides, status, content_hash`. `content_hash` is a SHA-256 of the record's
JSON (excluding the hash field itself) — it lets a caller verify the record
they received wasn't altered in transit; it is **not** a tamper-evidence or
anchoring claim (see `FINDINGS.md` / Honesty Rules).

## Condition scale

`app/condition_scale.py` hardcodes Amazon's published used-item grades (Like
New / Very Good / Good / Acceptable / Unacceptable), quoted from
sell.amazon.com's condition guidelines page, retrieved 2026-09-25 (URL and
date are in the module). The model is instructed to use exactly these six
keys — it cannot invent a grade name.

## Catalogue

`data/catalog.json` (regenerate with `scripts/build_catalog.py`) stands in for
"the seller's own catalogue" — built from the dummy `ordered_sku` /
`ordered_asin` / `parts_list` columns in `data/returns_sample.csv`. A real
deployment would replace `app/catalog.py` with a call to the seller's actual
product catalogue.

## What's deliberately NOT here

* No auth beyond a static per-org API key — fine for a Round-2 demo, not for
  production (real deployments would want per-user auth, key rotation, etc).
* No queue/async worker — each `/agent` call blocks on one Gemini round trip
  (a few seconds). Fine at demo volume; a real system would queue captures and
  process them asynchronously.
* SQLite, not a hosted database — single-file, zero setup, sufficient for the
  evaluation and demo. `app/store.py` is the only file that would need to
  change to move to Postgres etc.

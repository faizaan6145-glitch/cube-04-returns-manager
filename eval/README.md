# Evaluation set

RULES.md requires an **unseen** evaluation set: at least 50 units the agent has
never been tuned on, labelled independently by **two humans**, with results
reported per check (accuracy, false positives, false negatives, `UNCERTAIN`
rate, failure modes, latency).

## 1. Capture fixtures

For each of ~50 household items, invent a fake "return" (reuse the SKUs in
`data/catalog.json` or make up new ones and add them there) and take 2-3
photos: one of the whole item, one close-up of any damage/parts, one of the
box/labels if relevant. Deliberately include:

* several genuinely different-looking items ("wrong item" cases),
* items with a part missing on purpose,
* a full condition spread: like-new, very good, good, acceptable, unacceptable,
* a few bad photos (blurry, dark, box only) to exercise `UNCERTAIN`.

Save them under `eval/fixtures/<unit_id>/<file>.jpg` and add one row per unit
to `eval/manifest.csv` (copy `manifest_template.csv` to start). `eval/fixtures/`
is gitignored — see `eval/README.md` in your submission for how you're sharing
the images (e.g. a zip alongside the repo), since the images themselves
shouldn't bloat the git history.

## 2. Label independently

Copy `labels_template.csv` to `labels_A.csv` and `labels_B.csv`. You fill in
`labels_A.csv`. A second person — who has **not** seen your labels — fills in
`labels_B.csv` from the same photos. Do this before running the agent on the
set, so neither of you is anchored by the agent's answer.

Columns: `identity_match` (yes/no/uncertain), `parts_missing` (`;`-separated,
matching names in the catalogue's `expected_parts`), `condition_grade` (one of
the keys in `app/condition_scale.py`), `disposition`
(restock/refurbish/liquidate/dispose/pending_review).

### Labelling page (easiest way)

```sh
python -m uvicorn eval.labeler:app --port 8001
```

Open <http://127.0.0.1:8001>, pick rater A or B, and label each unit from its image. It saves
straight into `labels_A.csv` / `labels_B.csv`, remembers your progress, and shows only what an operator
would know (the image, ordered item, expected parts) -- never the search hints, image sources, the other
rater's labels or the agent's output. Rater B should use the page on their own, without seeing A's answers.

## 3. Run the agent and score it

```sh
python eval/run_eval.py
```

This calls the real pipeline (real Gemini calls — costs a little quota) for
every unit in `manifest.csv`, saves the raw output to `eval/results.csv`, and
prints/writes a report to `eval/EVAL_SUMMARY.md` covering:

* per-check accuracy, false positives, false negatives (vs `labels_A.csv`),
* `UNCERTAIN` rate per check,
* Cohen's kappa between `labels_A.csv` and `labels_B.csv` (human agreement),
* condition-grade confusion pairs,
* disposition confusion, with restock-related errors called out specifically
  (a false restock is the costliest mistake this agent can make),
* latency (mean/median/p95).

Paste the printed table into `EVAL_REPORT.md` and write up the failure modes
by hand — the script measures, it doesn't explain.

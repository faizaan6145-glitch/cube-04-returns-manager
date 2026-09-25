# Evaluation Report — Returns Manager

**Status: not run yet.** This is the template to fill in once `eval/manifest.csv`,
`eval/labels_A.csv` and `eval/labels_B.csv` are complete and
`python eval/run_eval.py` has been run. See `eval/README.md` for the full
process.

## Method

* Unseen evaluation set of **N units** (target: ≥50 per RULES.md), photographed
  specifically for evaluation — none were used while building or tuning the
  agent.
* Two humans labelled every unit **independently**, before either saw the
  agent's output: `labels_A.csv` (primary/ground truth) and `labels_B.csv`
  (second opinion, used only to measure human agreement).
* The agent ran once per unit through the real pipeline (`eval/run_eval.py`),
  using the same Gemini call path as production — no separate "eval mode."
* Metrics are computed by `eval/metrics.py` (unit-tested in
  `tests/test_eval_metrics.py`) — accuracy, false positives/negatives per
  check, `UNCERTAIN` rate, Cohen's kappa for human agreement, and latency.

## Evaluation-set limitations (read first)

* Images are **web images from Wikimedia Commons** (`eval/IMAGE_SOURCES.csv` has title, author and licence
  for each), not real customer returns. Condition and missing-part cases are only *hinted* by search wording;
  the true labels come from the two human labellers.
* **Each unit = one photo + a synthetic zoomed crop of the same photo.** A first version paired two unrelated
  search results per unit (e.g. a mug and coffee beans), which is unlike a real return, so it was replaced.
  Because the second image is a crop, the two images of a unit are not independent evidence.
* Seven units whose images did not show the right item were dropped and replaced by extra units from
  categories with clean photos. The remaining photos were **hand-picked for relevance** from contact sheets
  (relevance only -- the agent was never used to choose images). This makes the set cleaner than real returns.
* `BAD-1`/`BAD-2` are synthetic (blurred / darkened) and `WRONGITEM-1..3` reuse existing images under a
  mismatched order, so they are not independent samples.
* Results therefore show how the agent handles clean-ish web product photos, **not** how it performs on real
  warehouse capture conditions.

## Results

_Paste the output of `eval/run_eval.py` (also saved to `eval/EVAL_SUMMARY.md`)
here._

```
<paste eval/EVAL_SUMMARY.md here>
```

## Failure modes

_Fill in after reviewing the confusion pairs and false positives/negatives
above. For each failure mode: how many units, what the photos looked like,
and why the model likely got it wrong._

* Identity:
* Completeness:
* Condition:
* Disposition (especially any false restocks — the costliest error):

## Human agreement

_State the Cohen's kappa for identity/condition/disposition from the report,
and what that implies about how hard these judgments are even for people —
if humans disagree with each other on a chunk of units, the agent shouldn't
be expected to beat that ceiling._

## Latency / cost

_Mean/median/p95 latency per unit (one Gemini call each), and rough cost per
unit at the Gemini pricing tier used._

## What this evaluation does NOT show

* It is not a claim about performance on categories outside the ones
  photographed (be specific about what was and wasn't covered).
* Cohen's kappa and the FP/FN counts above are only as good as N — call out if
  N ended up below 50 and say why.

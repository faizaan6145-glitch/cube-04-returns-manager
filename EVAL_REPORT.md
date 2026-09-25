# Evaluation Report — Returns Manager

**Status: run on 2026-09-25 (53 units, model `gemini-flash-lite-latest`, prompt as committed at that time).**
The prompt/code were **not** changed after seeing these results, so the numbers are a true first-pass result.
See `eval/README.md` for the process.

## Method

* Evaluation set of **53 units** (≥50 per RULES.md), none used while building or tuning the agent
  (only two throw-away test images were used during development). See limitations above.
* **One human (the builder) labelled every unit**, before seeing the agent's output, using the local labelling
  page. **The rules recommend two independent labellers; a second rater was skipped**, so human agreement
  (Cohen's kappa) is *not measured* and label noise is unquantified. The ground truth is one person's judgement.
* The agent ran once per unit through the real pipeline (`eval/run_eval.py`),
  using the same Gemini call path as production — no separate "eval mode."
* Metrics are computed by `eval/metrics.py` (unit-tested in
  `tests/test_eval_metrics.py`) — accuracy, false positives/negatives per
  check, `UNCERTAIN` rate, Cohen's kappa for human agreement, and latency.

## Evaluation-set limitations (read first)

* Images are **web images from Wikimedia Commons** (`eval/IMAGE_SOURCES.csv` has title, author and licence
  for each), not real customer returns. Condition and missing-part cases are only *hinted* by search wording;
  the true labels come from the two human labellers.
* **Each unit is a single photo.** Earlier versions gave two images per unit (first two unrelated search
  results, then a photo plus a synthetic crop); both were dropped because they were confusing or redundant.
  Real returns usually have several photos, so multi-image handling is not exercised by this set.
* Seven units whose images did not show the right item were dropped and replaced by extra units from
  categories with clean photos. The remaining photos were **hand-picked for relevance** from contact sheets
  (relevance only -- the agent was never used to choose images). This makes the set cleaner than real returns.
* `BAD-1`/`BAD-2` are synthetic (blurred / darkened) and `WRONGITEM-1..3` reuse existing images under a
  mismatched order, so they are not independent samples.
* Results therefore show how the agent handles clean-ish web product photos, **not** how it performs on real
  warehouse capture conditions.

## Results

Produced by `python eval/run_eval.py` (raw per-unit output: `eval/results.csv`). Labels: `eval/labels_A.csv`.

Units run: 53. Scored against labels_A: 53.

## Identity
- Accuracy (incl. UNCERTAIN as its own class): 73.6% (n=53)
- False positives (agent PASS, human said no): 2
- False negatives (agent FAIL, human said yes): 12
- UNCERTAIN rate: 7.5%

## Completeness
- Accuracy: 75.5% (n=53)
- False positives (agent says complete, human found missing parts): 0
- False negatives (agent says missing, human says complete): 13
- UNCERTAIN rate: 17.0%

## Condition grade
- Exact-grade accuracy: 24.4% (n=45)
- UNCERTAIN rate (not graded at all): 15.1%
- Confusion (truth -> agent, top mismatches):
  - used_good -> used_very_good: 7
  - unacceptable -> used_good: 5
  - used_good -> used_like_new: 3
  - used_acceptable -> used_like_new: 3
  - unacceptable -> used_like_new: 2
  - new -> used_very_good: 2
  - used_very_good -> used_like_new: 2
  - used_acceptable -> used_good: 2
  - uncertain -> used_like_new: 2
  - used_very_good -> used_good: 2
  - new -> used_like_new: 2
  - uncertain -> used_good: 1
  - used_good -> unacceptable: 1

## Disposition
- Exact-match accuracy: 22.6% (n=53)
- **False restocks** (agent said restock, human disagreed) — costliest error: 5
- Missed restocks (human said restock, agent didn't): 4
- pending_review rate: 49.1%

## Human label agreement (labels_A vs labels_B)
- **Not measured: only one human rater labelled this set (labels_B.csv is empty).** Labels are single-rater, so label noise is unquantified.

## Latency (per unit, one batched call)
- mean 3403ms, median 3184ms, p95 4758ms, max 9875ms

Extra numbers computed from `results.csv` vs `labels_A.csv`:

* Condition grade (n=42 where both agent and human gave a grade): agent **more generous than the human in 24**,
  harsher in 7, identical in 11; within one grade in 26 (62%).
* Of the 26 units sent to `pending_review`: 15 because identity FAILed, 11 because some check was UNCERTAIN.
* Disposition confusion (human → agent) top cells: refurbish→refurbish 7, dispose→pending_review 7,
  liquidate→pending_review 6, liquidate→refurbish 6, dispose→refurbish 5, refurbish→pending_review 5,
  restock→pending_review 4.
* All 53 calls succeeded (0 model errors), so the fail-open path was not exercised by this run (it is covered by
  `tests/test_fail_open.py` and was observed once live during development on a 503 outage).

## Failure modes

* **Identity is stricter than the human labeller (12 false negatives).** The agent compares against catalogue
  *variants*, not just product type: e.g. `Towel Blu` vs a photo of a stack of multicoloured towels,
  `Umbrella Blk`/`Case Clr` vs a differently coloured item. The labeller said "yes" (right kind of product);
  the agent said FAIL at 0.90-0.95 confidence. Unclear which is "right" -- it depends on whether identity means
  same product type or same variant. This is a definition ambiguity, not clearly a model error, and it sends good
  units to human review (safe direction).
* **Wrong-item and bad-photo detection worked:** all 3 `WRONGITEM` units were correctly FAIL, both `BAD` units
  were UNCERTAIN/FAIL rather than confident PASS. Only 2 false positives on identity (`SERUM-C`, `SCALE-D`, where
  the human said "uncertain").
* **Condition grading is weak: 24% exact, and optimistic.** With the 6-grade scale and a single web photo the
  agent tends to over-grade (24 of 42 more generous than the human). Because label noise is unmeasured (one rater),
  part of this may be the labeller's own subjectivity.
* **Costliest error -- false restocks: 5.** BOTTLE-A, NOTEBOOK-C, PHONECASE-A/C/D were restocked by the agent while
  the human chose refurbish/liquidate; every one is the agent grading `used_like_new` on an item the human saw as
  worse. Mitigation not yet implemented: require higher confidence / a second check before `restock`.
* **Completeness: 13 false negatives.** With one photo the agent often cannot see accessories (lid, manual,
  case) and returns FAIL/UNCERTAIN even where the human ticked nothing missing. 0 false positives.
* **Disposition is mostly conservative:** 49% `pending_review`, only 22.6% exact match. That is largely a
  consequence of identity FAILs and UNCERTAIN checks above (safe, but it defeats the "move returns from
  liquidation to restock" business goal).

## Human agreement

**Not measured** -- only one rater labelled this set (see Method). This is a known gap versus the RULES.md recommendation.

## Latency / cost

One batched Gemini call per unit: mean 3.4 s, median 3.2 s, p95 4.8 s, max 9.9 s. Cost: free tier, so $0 for this run; token usage was not recorded, so per-unit cost is not estimated.

## What this evaluation does NOT show

* It is not a claim about performance on categories outside the ones
  photographed (be specific about what was and wasn't covered).
* Cohen's kappa and the FP/FN counts above are only as good as N — call out if
  N ended up below 50 and say why.

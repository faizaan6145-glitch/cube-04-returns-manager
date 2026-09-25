# Evaluation summary

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

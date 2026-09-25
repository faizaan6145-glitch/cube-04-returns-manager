"""Metric helpers for eval/run_eval.py. Kept separate from run_eval.py so they
can be unit-tested without needing real photos or a Gemini key."""
from __future__ import annotations

from collections import Counter


def confusion_counts(pred: list[str], truth: list[str], positive: str) -> dict:
    """Binary FP/FN/TP/TN counts, treating `positive` as the positive class and
    everything else (including e.g. 'uncertain') as negative."""
    tp = fp = fn = tn = 0
    for p, t in zip(pred, truth):
        p_pos, t_pos = p == positive, t == positive
        if p_pos and t_pos:
            tp += 1
        elif p_pos and not t_pos:
            fp += 1
        elif not p_pos and t_pos:
            fn += 1
        else:
            tn += 1
    n = len(pred)
    return {
        "n": n, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "accuracy": (tp + tn) / n if n else 0.0,
    }


def exact_match_accuracy(pred: list[str], truth: list[str]) -> float:
    if not pred:
        return 0.0
    return sum(p == t for p, t in zip(pred, truth)) / len(pred)


def uncertain_rate(verdicts: list[str]) -> float:
    if not verdicts:
        return 0.0
    return sum(v == "UNCERTAIN" for v in verdicts) / len(verdicts)


def confusion_matrix(pred: list[str], truth: list[str]) -> Counter:
    """Counter of (truth, pred) -> count, for printing a confusion table."""
    return Counter(zip(truth, pred))


def cohens_kappa(a: list[str], b: list[str]) -> float:
    """Human-vs-human agreement, chance-corrected. 1.0 = perfect agreement,
    0.0 = no better than chance. Standard formula: (po - pe) / (1 - pe)."""
    n = len(a)
    if n == 0:
        return 0.0
    po = sum(x == y for x, y in zip(a, b)) / n

    labels = set(a) | set(b)
    count_a = Counter(a)
    count_b = Counter(b)
    pe = sum((count_a[label] / n) * (count_b[label] / n) for label in labels)

    if pe == 1.0:
        return 1.0  # every rater agreed on one label -> no room for chance disagreement
    return (po - pe) / (1 - pe)


def latency_stats(latencies_ms: list[int]) -> dict:
    if not latencies_ms:
        return {"mean_ms": 0, "median_ms": 0, "p95_ms": 0, "max_ms": 0}
    s = sorted(latencies_ms)
    n = len(s)
    p95_idx = min(n - 1, int(round(0.95 * (n - 1))))
    return {
        "mean_ms": round(sum(s) / n),
        "median_ms": s[n // 2],
        "p95_ms": s[p95_idx],
        "max_ms": s[-1],
    }

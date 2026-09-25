import pytest

from eval.metrics import cohens_kappa, confusion_counts, exact_match_accuracy, uncertain_rate


def test_confusion_counts_basic():
    pred = ["PASS", "PASS", "FAIL", "FAIL"]
    truth = ["PASS", "FAIL", "FAIL", "PASS"]
    c = confusion_counts(pred, truth, positive="PASS")
    assert c == {"n": 4, "tp": 1, "fp": 1, "fn": 1, "tn": 1, "accuracy": 0.5}


def test_exact_match_accuracy():
    assert exact_match_accuracy(["a", "b", "c"], ["a", "b", "x"]) == pytest.approx(2 / 3)


def test_uncertain_rate():
    assert uncertain_rate(["PASS", "UNCERTAIN", "FAIL", "UNCERTAIN"]) == 0.5


def test_cohens_kappa_perfect_agreement():
    assert cohens_kappa(["a", "b", "a"], ["a", "b", "a"]) == 1.0


def test_cohens_kappa_chance_level():
    # With only two equally-likely labels and independent picks, kappa should
    # land near 0, not near 1.
    a = ["yes", "no"] * 10
    b = ["no", "yes"] * 10
    k = cohens_kappa(a, b)
    assert k < 0.1

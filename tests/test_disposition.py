from app.disposition import decide_disposition
from app.schemas import Check


def _check(key, verdict, confidence=0.9, detail="ok"):
    return Check(
        check_key=key, verdict=verdict, confidence=confidence, detail=detail,
        model_version="test", latency_ms=1,
    )


def test_identity_fail_forces_pending_review():
    checks = [_check("identity", "FAIL"), _check("completeness", "PASS"), _check("condition", "PASS")]
    disposition, _ = decide_disposition(checks, "used_like_new")
    assert disposition == "pending_review"


def test_any_uncertain_forces_pending_review():
    checks = [_check("identity", "PASS"), _check("completeness", "UNCERTAIN"), _check("condition", "PASS")]
    disposition, _ = decide_disposition(checks, "used_like_new")
    assert disposition == "pending_review"


def test_like_new_and_complete_restocks():
    checks = [_check("identity", "PASS"), _check("completeness", "PASS"), _check("condition", "PASS")]
    disposition, _ = decide_disposition(checks, "used_like_new")
    assert disposition == "restock"


def test_missing_parts_refurbishes_when_condition_ok():
    checks = [_check("identity", "PASS"), _check("completeness", "FAIL"), _check("condition", "PASS")]
    disposition, _ = decide_disposition(checks, "used_good")
    assert disposition == "refurbish"


def test_acceptable_condition_liquidates():
    checks = [_check("identity", "PASS"), _check("completeness", "PASS"), _check("condition", "PASS")]
    disposition, _ = decide_disposition(checks, "used_acceptable")
    assert disposition == "liquidate"


def test_unacceptable_condition_disposes():
    checks = [_check("identity", "PASS"), _check("completeness", "PASS"), _check("condition", "PASS")]
    disposition, _ = decide_disposition(checks, "unacceptable")
    assert disposition == "dispose"


def test_missing_parts_plus_bad_condition_disposes():
    checks = [_check("identity", "PASS"), _check("completeness", "FAIL"), _check("condition", "PASS")]
    disposition, _ = decide_disposition(checks, "used_acceptable")
    assert disposition == "dispose"

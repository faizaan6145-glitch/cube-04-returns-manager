"""Disposition is decided by deterministic rules, not by the model, so every
decision is explainable from the three check verdicts (RULES.md: 'do not make
important decisions impossible to explain').

Rule order (first match wins):
  1. Identity FAIL                          -> pending_review (wrong item)
  2. Any check UNCERTAIN                    -> pending_review (need a human)
  3. Completeness FAIL + condition unacceptable -> dispose
  4. Completeness FAIL (missing parts)      -> refurbish
  5. Condition unacceptable                 -> dispose
  6. Condition used_acceptable              -> liquidate
  7. Condition used_good / used_very_good   -> refurbish
  8. Condition new / used_like_new + complete -> restock
  9. Anything else                          -> pending_review (safe default)
"""
from __future__ import annotations

from app.schemas import Check, Disposition

_LIQUIDATE_GRADES = {"used_acceptable"}
_REFURBISH_GRADES = {"used_good", "used_very_good"}
_RESTOCK_GRADES = {"new", "used_like_new"}
_DISPOSE_GRADES = {"unacceptable"}


def _find(checks: list[Check], key: str) -> Check | None:
    return next((c for c in checks if c.check_key == key), None)


def decide_disposition(
    checks: list[Check], condition_grade: str | None
) -> tuple[Disposition, str]:
    identity = _find(checks, "identity")
    completeness = _find(checks, "completeness")
    condition = _find(checks, "condition")

    if identity is not None and identity.verdict == "FAIL":
        return "pending_review", "Identity check failed: item does not match the order."

    uncertain = [c.check_key for c in checks if c.verdict == "UNCERTAIN"]
    if uncertain:
        return (
            "pending_review",
            f"Evidence was insufficient for a reliable judgment on: {', '.join(uncertain)}.",
        )

    completeness_fail = completeness is not None and completeness.verdict == "FAIL"

    if condition_grade in _DISPOSE_GRADES:
        return "dispose", "Condition graded unacceptable; item cannot be resold."

    if completeness_fail and condition_grade in (_LIQUIDATE_GRADES | _DISPOSE_GRADES):
        return "dispose", "Parts missing and condition is poor; not worth refurbishing."

    if completeness_fail:
        return "refurbish", "Item is genuine and in usable condition, but parts are missing."

    if condition_grade in _LIQUIDATE_GRADES:
        return "liquidate", "Condition graded Acceptable; sell through liquidation channel."

    if condition_grade in _REFURBISH_GRADES:
        return "refurbish", "Condition graded Good/Very Good; refurbish before resale."

    if condition_grade in _RESTOCK_GRADES:
        return "restock", "Item matches the order, complete, and in sellable condition."

    return "pending_review", "Condition grade did not map to a known disposition rule."

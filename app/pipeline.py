"""Runs one return through: identity -> completeness -> condition -> disposition,
and assembles the evidence record. See RULES.md Engineering Rules 3 and 4:
fail open on any dependency failure, and UNCERTAIN is a first-class outcome,
never forced into PASS or FAIL.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from app.catalog import Catalog
from app.condition_scale import GRADE_KEYS
from app.config import Settings
from app.disposition import decide_disposition
from app.gemini_client import GeminiOutcome, run_checks
from app.schemas import Check, EvidenceRecord, Outcome, Subject


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _downgrade_low_confidence(check: Check, min_confidence: float) -> Check:
    """A PASS/FAIL the model itself wasn't confident about is not a reliable
    judgment -- treat it as UNCERTAIN rather than trusting a shaky verdict."""
    if check.verdict != "UNCERTAIN" and check.confidence < min_confidence:
        return check.model_copy(
            update={
                "verdict": "UNCERTAIN",
                "detail": f"{check.detail} (confidence {check.confidence:.2f} below "
                f"threshold {min_confidence:.2f}; downgraded to UNCERTAIN.)",
            }
        )
    return check


def _error_checks(model_version: str, latency_ms: int, error: str) -> list[Check]:
    """Fail-open path: the model call failed entirely. Every check becomes
    UNCERTAIN with the error recorded, and the case is preserved, not dropped."""
    detail = f"Automated check unavailable: {error}"
    return [
        Check(
            check_key=key,
            verdict="UNCERTAIN",
            confidence=0.0,
            detail=detail,
            model_version=model_version or "unavailable",
            latency_ms=latency_ms,
        )
        for key in ("identity", "completeness", "condition")
    ]


def _checks_from_gemini(outcome: GeminiOutcome, min_confidence: float) -> list[Check]:
    data = outcome.raw or {}
    checks: list[Check] = []

    ident = data.get("identity", {})
    checks.append(
        Check(
            check_key="identity",
            verdict=ident.get("verdict", "UNCERTAIN"),
            confidence=float(ident.get("confidence", 0.0)),
            detail=ident.get("detail", ""),
            model_version=outcome.model_version,
            latency_ms=outcome.latency_ms,
        )
    )

    comp = data.get("completeness", {})
    parts_missing = comp.get("parts_missing", [])
    comp_detail = comp.get("detail", "")
    if parts_missing:
        comp_detail = f"{comp_detail} Missing: {', '.join(parts_missing)}.".strip()
    checks.append(
        Check(
            check_key="completeness",
            verdict=comp.get("verdict", "UNCERTAIN"),
            confidence=float(comp.get("confidence", 0.0)),
            detail=comp_detail,
            model_version=outcome.model_version,
            latency_ms=outcome.latency_ms,
        )
    )

    cond = data.get("condition", {})
    grade = cond.get("grade", "unknown")
    checks.append(
        Check(
            check_key="condition",
            verdict=cond.get("verdict", "UNCERTAIN"),
            confidence=float(cond.get("confidence", 0.0)),
            detail=cond.get("detail", ""),
            model_version=outcome.model_version,
            latency_ms=outcome.latency_ms,
        )
    )

    return [_downgrade_low_confidence(c, min_confidence) for c in checks]


def process_return(
    *,
    settings: Settings,
    catalog: Catalog,
    organization_id: str,
    client_id: str,
    operator_label: str,
    unit_id: str,
    order_id: str,
    ordered_sku: str,
    ordered_asin: str,
    image_bytes: list[bytes],
    image_paths: list[str],
) -> EvidenceRecord:
    item = catalog.lookup(organization_id, ordered_sku)

    outcome = run_checks(
        api_key=settings.gemini_api_key or "",
        model=settings.gemini_model,
        timeout_s=settings.gemini_timeout_s,
        image_bytes=image_bytes,
        item=item,
        ordered_sku=ordered_sku,
        ordered_asin=ordered_asin,
    )

    status = "complete"
    if outcome.ok:
        checks = _checks_from_gemini(outcome, settings.min_confidence)
    else:
        # Fail open: never lose the case. Save it as pending_review with the
        # error preserved instead of discarding the submission.
        checks = _error_checks(outcome.model_version, outcome.latency_ms, outcome.error or "unknown error")
        status = "error"

    identity_check = next(c for c in checks if c.check_key == "identity")
    completeness_check = next(c for c in checks if c.check_key == "completeness")
    condition_check = next(c for c in checks if c.check_key == "condition")

    raw_condition = (outcome.raw or {}).get("condition", {}) if outcome.ok else {}
    grade = raw_condition.get("grade")
    if condition_check.verdict != "PASS" or grade not in GRADE_KEYS:
        grade = None

    identity_match = {"PASS": "yes", "FAIL": "no"}.get(identity_check.verdict, "uncertain")

    raw_completeness = (outcome.raw or {}).get("completeness", {}) if outcome.ok else {}
    parts_missing = raw_completeness.get("parts_missing", []) if outcome.ok else []

    disposition, reason = decide_disposition(checks, grade)
    if status == "error":
        disposition, reason = "pending_review", (
            f"Automated checks could not run ({outcome.error}); preserved for manual review."
        )

    final_status = "pending_review" if disposition == "pending_review" and status != "error" else status

    record_id = f"RTN-{uuid.uuid4().hex[:10]}"
    captured_at = _now_iso()

    outcome_block = Outcome(
        identity_match=identity_match,
        parts_expected=item.expected_parts if item else [],
        parts_missing=parts_missing,
        condition_grade=grade,
        disposition=disposition,
        disposition_reason=reason,
    )

    record = EvidenceRecord(
        record_id=record_id,
        organization_id=organization_id,
        client_id=client_id,
        subject=Subject(
            unit_id=unit_id,
            order_id=order_id,
            ordered_sku=ordered_sku,
            ordered_asin=ordered_asin,
        ),
        captured_at=captured_at,
        operator_label=operator_label,
        images=image_paths,
        checks=checks,
        outcome=outcome_block,
        overrides=[],
        status=final_status,
        content_hash="",
    )

    digest = hashlib.sha256(record.model_dump_json(exclude={"content_hash"}).encode()).hexdigest()
    return record.model_copy(update={"content_hash": digest})

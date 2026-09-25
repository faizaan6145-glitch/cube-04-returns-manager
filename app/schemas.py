"""The evidence record shape, following the official Buildathon contract fields
listed in README.md / RULES.md:
record_id, schema_version, organization_id, client_id, agent, subject, captured_at,
operator_label, images, checks, outcome, overrides, status, content_hash.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Verdict = Literal["PASS", "FAIL", "UNCERTAIN"]
Disposition = Literal["restock", "refurbish", "liquidate", "dispose", "pending_review"]
Status = Literal["complete", "pending_review", "error"]

SCHEMA_VERSION = "1.0.0"
AGENT_NAME = "returns-manager"


class Check(BaseModel):
    check_key: Literal["identity", "completeness", "condition"]
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    detail: str
    model_version: str
    latency_ms: int


class Outcome(BaseModel):
    identity_match: Literal["yes", "no", "uncertain"]
    parts_expected: list[str]
    parts_missing: list[str]
    condition_grade: str | None  # one of app.condition_scale.GRADE_KEYS, or None if uncertain
    disposition: Disposition
    disposition_reason: str


class Override(BaseModel):
    check_key: str
    original_verdict: str
    revised_verdict: str
    reason: str
    operator_label: str
    overridden_at: str


class Subject(BaseModel):
    unit_id: str
    order_id: str
    ordered_sku: str
    ordered_asin: str


class EvidenceRecord(BaseModel):
    record_id: str
    schema_version: str = SCHEMA_VERSION
    organization_id: str
    client_id: str
    agent: str = AGENT_NAME
    subject: Subject
    captured_at: str
    operator_label: str
    images: list[str]
    checks: list[Check]
    outcome: Outcome
    overrides: list[Override] = Field(default_factory=list)
    status: Status
    content_hash: str

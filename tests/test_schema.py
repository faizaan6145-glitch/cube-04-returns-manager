"""Every evidence record produced by the pipeline must satisfy the official
contract fields, whether the model call succeeded or failed."""
from app.catalog import load_catalog
from app.config import load_settings
from app.gemini_client import GeminiOutcome
from app.pipeline import process_return
from app.schemas import EvidenceRecord

CONTRACT_FIELDS = {
    "record_id", "schema_version", "organization_id", "client_id", "agent", "subject",
    "captured_at", "operator_label", "images", "checks", "outcome", "overrides",
    "status", "content_hash",
}


def _run(monkeypatch, tmp_env, outcome: GeminiOutcome):
    monkeypatch.setattr("app.pipeline.run_checks", lambda **kw: outcome)
    settings = load_settings()
    catalog = load_catalog(settings.catalog_path)
    return process_return(
        settings=settings,
        catalog=catalog,
        organization_id="org_demo_alpha",
        client_id="test-client",
        operator_label="op_test",
        unit_id="UNIT-TEST",
        order_id="ORD-TEST",
        ordered_sku="SKU-PUZZLE-500",
        ordered_asin="B0DUMMY729",
        image_bytes=[b"fake-jpeg-bytes"],
        image_paths=["/images/fake"],
    )


def test_successful_record_has_all_contract_fields(monkeypatch, tmp_env):
    outcome = GeminiOutcome(
        ok=True, latency_ms=500, model_version="gemini-flash-lite-latest",
        raw={
            "identity": {"verdict": "PASS", "confidence": 0.95, "detail": "matches"},
            "completeness": {"verdict": "PASS", "confidence": 0.9, "detail": "all there",
                              "parts_seen": ["puzzle pieces", "poster"], "parts_missing": []},
            "condition": {"verdict": "PASS", "confidence": 0.85, "detail": "looks new",
                          "grade": "used_like_new"},
        },
    )
    record = _run(monkeypatch, tmp_env, outcome)
    assert CONTRACT_FIELDS <= set(record.model_dump().keys())
    assert record.outcome.disposition == "restock"
    assert record.status == "complete"
    assert len(record.content_hash) == 64  # sha256 hex


def test_content_hash_is_deterministic_for_same_content():
    a = EvidenceRecord.model_validate(
        {
            "record_id": "RTN-1", "organization_id": "o", "client_id": "c",
            "subject": {"unit_id": "u", "order_id": "o", "ordered_sku": "s", "ordered_asin": "a"},
            "captured_at": "2026-01-01T00:00:00Z", "operator_label": "op", "images": [],
            "checks": [], "outcome": {
                "identity_match": "yes", "parts_expected": [], "parts_missing": [],
                "condition_grade": None, "disposition": "restock", "disposition_reason": "r",
            },
            "status": "complete", "content_hash": "x",
        }
    )
    assert a.schema_version == "1.0.0"

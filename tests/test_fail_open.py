"""Engineering Rule 3 (RULES.md): a model/dependency failure must not silently
discard the return. The case must still be saved, with status pending_review/
error and UNCERTAIN checks explaining what failed."""
from app.catalog import load_catalog
from app.config import load_settings
from app.gemini_client import GeminiOutcome
from app.pipeline import process_return


def test_model_timeout_preserves_the_case(monkeypatch, tmp_env):
    monkeypatch.setattr(
        "app.pipeline.run_checks",
        lambda **kw: GeminiOutcome(ok=False, latency_ms=5000, error="Model call timed out after 5.0s"),
    )
    settings = load_settings()
    catalog = load_catalog(settings.catalog_path)

    record = process_return(
        settings=settings, catalog=catalog, organization_id="org_demo_alpha",
        client_id="test", operator_label="op_test", unit_id="UNIT-X", order_id="ORD-X",
        ordered_sku="SKU-PUZZLE-500", ordered_asin="B0DUMMY729",
        image_bytes=[b"fake"], image_paths=["/images/fake"],
    )

    # The record still exists and is usable -- nothing was dropped.
    assert record.status == "error"
    assert record.outcome.disposition == "pending_review"
    assert all(c.verdict == "UNCERTAIN" for c in record.checks)
    assert "timed out" in record.checks[0].detail


def test_malformed_model_reply_falls_back_to_uncertain(monkeypatch, tmp_env):
    # ok=True but missing fields -- pipeline must not crash on a shaky reply.
    monkeypatch.setattr(
        "app.pipeline.run_checks",
        lambda **kw: GeminiOutcome(ok=True, latency_ms=200, model_version="gemini-2.5-flash", raw={}),
    )
    settings = load_settings()
    catalog = load_catalog(settings.catalog_path)

    record = process_return(
        settings=settings, catalog=catalog, organization_id="org_demo_alpha",
        client_id="test", operator_label="op_test", unit_id="UNIT-Y", order_id="ORD-Y",
        ordered_sku="SKU-PUZZLE-500", ordered_asin="B0DUMMY729",
        image_bytes=[b"fake"], image_paths=["/images/fake"],
    )
    assert all(c.verdict == "UNCERTAIN" for c in record.checks)
    assert record.outcome.disposition == "pending_review"


def test_no_images_is_preserved_not_dropped(tmp_env):
    settings = load_settings()
    catalog = load_catalog(settings.catalog_path)
    record = process_return(
        settings=settings, catalog=catalog, organization_id="org_demo_alpha",
        client_id="test", operator_label="op_test", unit_id="UNIT-Z", order_id="ORD-Z",
        ordered_sku="SKU-PUZZLE-500", ordered_asin="B0DUMMY729",
        image_bytes=[], image_paths=[],
    )
    assert record.status == "error"
    assert record.outcome.disposition == "pending_review"

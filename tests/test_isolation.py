"""Engineering Rule 1 (RULES.md): tenancy isolation. org_demo_bravo must see
zero rows or images belonging to org_demo_alpha, even by guessing an id."""
from unittest.mock import patch

from app.gemini_client import GeminiOutcome

FAKE_OUTCOME = GeminiOutcome(
    ok=True, latency_ms=100, model_version="gemini-2.5-flash",
    raw={
        "identity": {"verdict": "PASS", "confidence": 0.9, "detail": "matches"},
        "completeness": {"verdict": "PASS", "confidence": 0.9, "detail": "complete",
                          "parts_seen": [], "parts_missing": []},
        "condition": {"verdict": "PASS", "confidence": 0.9, "detail": "new",
                      "grade": "used_like_new"},
    },
)


def _submit(client, api_key, unit_id):
    with patch("app.pipeline.run_checks", return_value=FAKE_OUTCOME):
        resp = client.post(
            "/agent",
            data={
                "api_key": api_key, "operator_label": "op_test", "unit_id": unit_id,
                "order_id": "ORD-1", "ordered_sku": "SKU-PUZZLE-500", "ordered_asin": "B0DUMMY729",
            },
            files={"images": ("photo.jpg", b"fake-bytes", "image/jpeg")},
            headers={"Accept": "application/json"},
        )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_org_cannot_read_another_orgs_record(client):
    alpha_record = _submit(client, "alpha-key", "UNIT-ALPHA-1")
    record_id = alpha_record["record_id"]

    # alpha can read its own record
    ok = client.get(f"/api/records/{record_id}", headers={"X-API-Key": "alpha-key"})
    assert ok.status_code == 200

    # bravo guessing the same record_id gets nothing, not a 403 leak
    leaked = client.get(f"/api/records/{record_id}", headers={"X-API-Key": "bravo-key"})
    assert leaked.status_code == 404


def test_org_cannot_list_another_orgs_records(client):
    _submit(client, "alpha-key", "UNIT-ALPHA-2")
    _submit(client, "bravo-key", "UNIT-BRAVO-2")

    from app.main import get_store

    alpha_records = get_store().list_records("org_demo_alpha")
    bravo_records = get_store().list_records("org_demo_bravo")

    assert all(r.organization_id == "org_demo_alpha" for r in alpha_records)
    assert all(r.organization_id == "org_demo_bravo" for r in bravo_records)
    assert not any(r.subject.unit_id == "UNIT-BRAVO-2" for r in alpha_records)


def test_org_cannot_fetch_another_orgs_image(client):
    alpha_record = _submit(client, "alpha-key", "UNIT-ALPHA-3")
    image_path = alpha_record["images"][0]  # "/images/<id>"

    ok = client.get(image_path, headers={"X-API-Key": "alpha-key"})
    assert ok.status_code == 200

    leaked = client.get(image_path, headers={"X-API-Key": "bravo-key"})
    assert leaked.status_code == 404


def test_invalid_api_key_rejected(client):
    resp = client.get("/api/records/anything", headers={"X-API-Key": "not-a-real-key"})
    assert resp.status_code == 401

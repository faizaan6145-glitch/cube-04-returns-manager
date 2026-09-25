"""The website can run keyless (UI_ORG_ID) without weakening tenant isolation or opening the API."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.gemini_client import GeminiOutcome
from tests.test_isolation import FAKE_OUTCOME

FORM = {"operator_label": "op", "unit_id": "U1", "order_id": "O1",
        "ordered_sku": "SKU-PUZZLE-500", "ordered_asin": "B0DUMMY729"}
FILES = {"images": ("p.jpg", b"fake", "image/jpeg")}
HTML = {"Accept": "text/html"}


def submit(client, headers, **extra):
    with patch("app.pipeline.run_checks", return_value=FAKE_OUTCOME):
        return client.post("/agent", data={**FORM, **extra}, files=FILES, headers=headers)


@pytest.fixture()
def ui_client(tmp_env, monkeypatch):
    monkeypatch.setenv("UI_ORG_ID", "org_demo_alpha")
    tmp_env._settings = None
    return TestClient(tmp_env.app, follow_redirects=False)


def test_browser_form_works_without_a_key_and_lands_on_the_ui_org(ui_client, tmp_env):
    r = submit(ui_client, HTML)
    assert r.status_code == 303 and "api_key" not in r.headers["location"]
    page = ui_client.get(r.headers["location"], headers=HTML)
    assert page.status_code == 200
    rid = r.headers["location"].rsplit("/", 1)[1]
    assert tmp_env.get_store().get_record(rid, "org_demo_alpha") is not None
    assert tmp_env.get_store().get_record(rid, "org_demo_bravo") is None
    assert ui_client.get("/records", headers=HTML).status_code == 200  # history, no key prompt


def test_scripts_and_api_still_need_a_key_in_ui_mode(ui_client):
    assert submit(ui_client, {"Accept": "application/json"}).status_code == 401
    r = submit(ui_client, {"Accept": "application/json", "X-API-Key": "alpha-key"})
    assert r.status_code == 200
    rid = r.json()["record_id"]
    assert ui_client.get(f"/api/records/{rid}").status_code == 401  # JSON API never uses the fallback


def test_explicit_other_org_key_still_cannot_see_ui_orgs_records(ui_client):
    rid = submit(ui_client, HTML).headers["location"].rsplit("/", 1)[1]
    assert ui_client.get(f"/records/{rid}", params={"api_key": "bravo-key"}, headers=HTML).status_code == 404
    assert ui_client.get(f"/records/{rid}", params={"api_key": "wrong"}, headers=HTML).status_code == 401


def test_without_ui_org_the_browser_form_still_requires_a_key(tmp_env):
    client = TestClient(tmp_env.app, follow_redirects=False)  # UI_ORG_ID not set
    assert submit(client, HTML).status_code == 401
    assert "Access key" in client.get("/", headers=HTML).text
    assert "Enter your access key" in client.get("/records", headers=HTML).text


def test_ui_page_hides_key_field_in_ui_mode(ui_client):
    html = ui_client.get("/", headers=HTML).text
    assert 'name="api_key"' not in html and 'name="operator_label"' in html


def test_ui_org_must_be_a_known_org(tmp_env, monkeypatch):
    monkeypatch.setenv("UI_ORG_ID", "org_typo")
    tmp_env._settings = None
    with pytest.raises(RuntimeError, match="UI_ORG_ID"):
        tmp_env.get_settings()

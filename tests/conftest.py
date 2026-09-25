import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture()
def tmp_env(tmp_path, monkeypatch):
    """Isolated settings for each test: its own DB, image dir, and dummy org keys."""
    monkeypatch.setenv("ORG_KEYS", "org_demo_alpha:alpha-key,org_demo_bravo:bravo-key")
    monkeypatch.setenv("GEMINI_API_KEY", "dummy-not-used-because-mocked")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("GEMINI_TIMEOUT_S", "5")
    monkeypatch.setenv("MIN_CONFIDENCE", "0.6")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("IMAGE_DIR", str(tmp_path / "images"))
    monkeypatch.setenv("CATALOG_PATH", str(ROOT / "data" / "catalog.json"))

    import app.main as main_module

    main_module._settings = None
    main_module._store = None
    yield main_module
    main_module._settings = None
    main_module._store = None


@pytest.fixture()
def client(tmp_env):
    from fastapi.testclient import TestClient

    return TestClient(tmp_env.app)

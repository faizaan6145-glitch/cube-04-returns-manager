"""Settings, read from environment variables (or a local .env file)."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


@dataclass
class Settings:
    org_keys: dict[str, str]  # api_key -> org_id
    gemini_api_key: str | None
    gemini_model: str
    gemini_timeout_s: float
    min_confidence: float
    db_path: Path
    image_dir: Path
    catalog_path: Path
    ui_org_id: str | None = None  # org the keyless web UI acts as (see UI_ORG_ID in .env.example)


def parse_org_keys(raw: str) -> dict[str, str]:
    """'org_a:key1,org_b:key2' -> {'key1': 'org_a', 'key2': 'org_b'}"""
    keys = {}
    for pair in filter(None, (p.strip() for p in raw.split(","))):
        org_id, _, key = pair.partition(":")
        if not org_id or not key:
            raise ValueError(f"Bad ORG_KEYS entry {pair!r}; expected org_id:api_key")
        keys[key] = org_id
    return keys


def _path(name: str, default: str) -> Path:
    p = Path(os.getenv(name, default))
    return p if p.is_absolute() else ROOT / p


def load_settings() -> Settings:
    raw_keys = os.getenv("ORG_KEYS", "")
    if not raw_keys:
        raise RuntimeError("ORG_KEYS is not set. Copy .env.example to .env and fill it in.")
    org_keys = parse_org_keys(raw_keys)
    ui_org_id = os.getenv("UI_ORG_ID") or None
    if ui_org_id and ui_org_id not in org_keys.values():
        raise RuntimeError(f"UI_ORG_ID={ui_org_id!r} is not one of the orgs in ORG_KEYS.")
    return Settings(
        org_keys=org_keys,
        ui_org_id=ui_org_id,
        gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest"),
        gemini_timeout_s=float(os.getenv("GEMINI_TIMEOUT_S", "60")),
        min_confidence=float(os.getenv("MIN_CONFIDENCE", "0.6")),
        db_path=_path("DB_PATH", "storage/returns.db"),
        image_dir=_path("IMAGE_DIR", "storage/images"),
        catalog_path=_path("CATALOG_PATH", "data/catalog.json"),
    )

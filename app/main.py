"""FastAPI app. Routes:
  GET  /                          upload form (HTML)
  POST /agent                     main Returns Manager operation (JSON or browser form)
  GET  /health                    liveness check
  GET  /records/{record_id}       evidence record page (HTML) -- org-scoped
  POST /records/{record_id}/override   operator override on one check
  GET  /images/{image_id}         serves an uploaded photo -- org-scoped

Every route that touches stored data resolves the caller's organization_id from
their API key first (see resolve_org below) and passes only that org_id into
app.store -- there is no code path that can read another tenant's data.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.catalog import load_catalog
from app.config import Settings, load_settings
from app.pipeline import process_return
from app.schemas import EvidenceRecord, Override
from app.store import Store

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Returns Manager")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

_settings: Settings | None = None
_store: Store | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store(get_settings().db_path)
    return _store


def resolve_org(api_key: str | None) -> str:
    """Turns an API key into an organization_id. Unknown/missing key -> 401.
    This is the one place tenant identity is decided; every route below must
    call this instead of trusting any org_id supplied in the request body."""
    settings = get_settings()
    if not api_key or api_key not in settings.org_keys:
        raise HTTPException(status_code=401, detail="Missing or invalid API key.")
    return settings.org_keys[api_key]


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


def _wants_html(request: Request) -> bool:
    return "text/html" in (request.headers.get("accept") or "")


@app.exception_handler(HTTPException)
async def friendly_errors(request: Request, exc: HTTPException):
    """Browsers get a readable error page; API callers still get JSON."""
    if not _wants_html(request):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    hints = {401: "Check that you pasted the right API key (the value after the colon in ORG_KEYS).",
             404: "That record or image doesn't exist for your organisation."}
    return templates.TemplateResponse(
        request, "error.html",
        {"code": exc.status_code, "message": exc.detail, "hint": hints.get(exc.status_code, "")},
        status_code=exc.status_code,
    )


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    items = load_catalog(get_settings().catalog_path).all_items()
    catalog = [{"sku": i.sku, "asin": i.asin, "title": i.title, "parts": i.expected_parts} for i in items]
    return templates.TemplateResponse(request, "index.html", {"catalog": catalog})


@app.get("/records", response_class=HTMLResponse)
def history_page(request: Request, api_key: str | None = None):
    """Recent returns for the caller's organisation. Without a key we just ask for one."""
    if not api_key:
        return templates.TemplateResponse(request, "history.html", {"need_key": True, "records": [], "api_key": ""})
    org_id = resolve_org(api_key)
    records = get_store().list_records(org_id, limit=100)
    return templates.TemplateResponse(
        request, "history.html", {"need_key": False, "records": records, "api_key": api_key, "org_id": org_id}
    )


@app.post("/agent")
async def agent(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    api_key: str | None = Form(default=None),
    client_id: str = Form(default="web-ui"),
    operator_label: str = Form(...),
    unit_id: str = Form(...),
    order_id: str = Form(...),
    ordered_sku: str = Form(...),
    ordered_asin: str = Form(...),
    images: list[UploadFile] = [],
):
    """Main Returns Manager operation. Accepts multipart/form-data (used by the
    browser upload form and by curl/API callers). Auth is by API key, sent as
    either the X-API-Key header or an api_key form field."""
    org_id = resolve_org(x_api_key or api_key)
    settings = get_settings()
    catalog = load_catalog(settings.catalog_path)
    store = get_store()

    record_id_placeholder = f"tmp-{uuid.uuid4().hex[:8]}"
    org_image_dir = settings.image_dir / org_id
    org_image_dir.mkdir(parents=True, exist_ok=True)

    image_bytes: list[bytes] = []
    image_ids: list[str] = []
    for upload in images:
        content = await upload.read()
        if not content:
            continue
        image_bytes.append(content)
        image_id = uuid.uuid4().hex
        dest = org_image_dir / f"{image_id}.jpg"
        dest.write_bytes(content)
        image_ids.append(image_id)

    record = process_return(
        settings=settings,
        catalog=catalog,
        organization_id=org_id,
        client_id=client_id,
        operator_label=operator_label,
        unit_id=unit_id,
        order_id=order_id,
        ordered_sku=ordered_sku,
        ordered_asin=ordered_asin,
        image_bytes=image_bytes,
        image_paths=[f"/images/{iid}" for iid in image_ids],
    )

    store.save_record(record)
    for iid in image_ids:
        store.register_image(iid, org_id, record.record_id, str(org_image_dir / f"{iid}.jpg"))

    if "text/html" in (request.headers.get("accept") or ""):
        used_key = x_api_key or api_key
        return HTMLResponse(
            status_code=303,
            headers={"Location": f"/records/{record.record_id}?api_key={used_key}"},
        )
    return JSONResponse(record.model_dump())


@app.get("/records/{record_id}", response_class=HTMLResponse)
def get_record_page(request: Request, record_id: str, api_key: str | None = None):
    org_id = resolve_org(api_key or request.headers.get("X-API-Key"))
    record = get_store().get_record(record_id, org_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found.")
    return templates.TemplateResponse(
        request, "record.html", {"record": record, "api_key": api_key}
    )


@app.get("/api/records/{record_id}")
def get_record_json(record_id: str, x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    org_id = resolve_org(x_api_key)
    record = get_store().get_record(record_id, org_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found.")
    return record.model_dump()


@app.post("/records/{record_id}/override")
def override_check(
    record_id: str,
    check_key: str = Form(...),
    revised_verdict: str = Form(...),
    reason: str = Form(...),
    operator_label: str = Form(...),
    api_key: str | None = Form(default=None),
):
    """Overrides never replace the original check -- they are appended
    (RULES.md, Evidence Rule 3: 'Overrides Are Data')."""
    org_id = resolve_org(api_key)
    store = get_store()
    record = store.get_record(record_id, org_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found.")

    original = next((c for c in record.checks if c.check_key == check_key), None)
    if original is None:
        raise HTTPException(status_code=400, detail=f"Unknown check_key {check_key!r}.")

    override = Override(
        check_key=check_key,
        original_verdict=original.verdict,
        revised_verdict=revised_verdict,
        reason=reason,
        operator_label=operator_label,
        overridden_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    updated = record.model_copy(update={"overrides": [*record.overrides, override]})
    store.save_record(updated)
    return HTMLResponse(status_code=303, headers={"Location": f"/records/{record_id}?api_key={api_key}"})


@app.get("/images/{image_id}")
def get_image(image_id: str, api_key: str | None = None, x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    org_id = resolve_org(x_api_key or api_key)
    path = get_store().get_image_path(image_id, org_id)
    if path is None or not Path(path).exists():
        raise HTTPException(status_code=404, detail="Image not found.")
    return FileResponse(path)

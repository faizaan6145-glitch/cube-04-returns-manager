"""One batched Gemini call per return (RULES.md, Engineering Rule 2: batch model
calls). We send every photo plus the catalogue entry and the condition scale in
a single request and ask for one structured JSON reply covering identity,
completeness and condition together, instead of three separate calls.

Fail-open (RULES.md, Engineering Rule 3): any exception, timeout or malformed
reply is caught here and turned into a GeminiOutcome with ok=False. Callers
must never let this raise past them -- the caller decides what "safe" state
(pending_review) to save instead.
"""
from __future__ import annotations

import concurrent.futures
import json
import time
from dataclasses import dataclass, field

from google import genai
from google.genai import types

from app.catalog import CatalogItem
from app.condition_scale import GRADE_KEYS, prompt_text

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "identity": {
            "type": "object",
            "properties": {
                "verdict": {"type": "string", "enum": ["PASS", "FAIL", "UNCERTAIN"]},
                "confidence": {"type": "number"},
                "detail": {"type": "string"},
            },
            "required": ["verdict", "confidence", "detail"],
        },
        "completeness": {
            "type": "object",
            "properties": {
                "verdict": {"type": "string", "enum": ["PASS", "FAIL", "UNCERTAIN"]},
                "confidence": {"type": "number"},
                "detail": {"type": "string"},
                "parts_seen": {"type": "array", "items": {"type": "string"}},
                "parts_missing": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["verdict", "confidence", "detail", "parts_seen", "parts_missing"],
        },
        "condition": {
            "type": "object",
            "properties": {
                "verdict": {"type": "string", "enum": ["PASS", "FAIL", "UNCERTAIN"]},
                "confidence": {"type": "number"},
                "detail": {"type": "string"},
                "grade": {"type": "string", "enum": [*GRADE_KEYS, "unknown"]},
            },
            "required": ["verdict", "confidence", "detail", "grade"],
        },
    },
    "required": ["identity", "completeness", "condition"],
}


def _build_prompt(item: CatalogItem | None, ordered_sku: str, ordered_asin: str) -> str:
    if item is not None:
        catalog_block = (
            f"Ordered catalogue entry: SKU={item.sku}, ASIN={item.asin}, "
            f"title=\"{item.title}\", expected parts={item.expected_parts}."
        )
    else:
        catalog_block = (
            f"No catalogue entry was found for SKU={ordered_sku} / ASIN={ordered_asin}. "
            "Treat identity as impossible to confirm positively; you may still note if "
            "the photos clearly show a completely different kind of product."
        )
    return f"""You are inspecting photos of a customer-returned product for a warehouse
operator. Answer strictly from what is visible in the photos. Never guess or invent
information you cannot see.

{catalog_block}

Perform three checks and return ONLY the JSON object matching the given schema:

1. identity: does the item in the photos match the ordered catalogue entry above
   (same product type/design, not just "a similar item")? PASS if it clearly matches,
   FAIL if it clearly does not, UNCERTAIN if the photos do not show enough to tell
   (e.g. box only, blurry, wrong angle).

2. completeness: compare what is visible against the expected parts list. List the
   parts you can positively see (parts_seen) and the expected parts that are not
   visible in any photo (parts_missing). verdict is PASS if all expected parts are
   visible, FAIL if one or more expected parts are clearly absent, UNCERTAIN if you
   cannot tell whether a part is present or not from the photos given.

3. condition: grade the item using EXACTLY this scale (use the key, e.g.
   "used_like_new"), do not invent another scale:
{prompt_text()}
   verdict is PASS if you can confidently assign a grade, UNCERTAIN if photos are too
   poor/ambiguous to grade reliably. FAIL is not a valid condition verdict; use
   UNCERTAIN instead if you cannot grade it. If verdict is UNCERTAIN, set grade to
   "unknown".

For every check, confidence is your own 0.0-1.0 estimate of how sure you are, and
detail is one or two sentences a human reviewer can read to see why you decided that."""


@dataclass
class GeminiOutcome:
    ok: bool
    latency_ms: int
    raw: dict | None = None
    error: str | None = None
    model_version: str = ""


def _call(
    client: genai.Client,
    model: str,
    prompt: str,
    image_bytes: list[bytes],
) -> dict:
    parts: list[types.Part] = [types.Part.from_text(text=prompt)]
    for b in image_bytes:
        parts.append(types.Part.from_bytes(data=b, mime_type="image/jpeg"))

    response = client.models.generate_content(
        model=model,
        contents=[types.Content(role="user", parts=parts)],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
            temperature=0.1,
        ),
    )
    text = response.text
    if not text:
        raise ValueError("Empty response from model")
    return json.loads(text)


def run_checks(
    api_key: str,
    model: str,
    timeout_s: float,
    image_bytes: list[bytes],
    item: CatalogItem | None,
    ordered_sku: str,
    ordered_asin: str,
) -> GeminiOutcome:
    """Run the single batched vision call. Never raises: failures come back as
    GeminiOutcome(ok=False, error=...) so callers can fail open."""
    if not image_bytes:
        return GeminiOutcome(ok=False, latency_ms=0, error="No images were provided.")
    if not api_key:
        return GeminiOutcome(ok=False, latency_ms=0, error="GEMINI_API_KEY is not configured.")

    prompt = _build_prompt(item, ordered_sku, ordered_asin)
    client = genai.Client(api_key=api_key)
    start = time.monotonic()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_call, client, model, prompt, image_bytes)
            data = future.result(timeout=timeout_s)
        latency_ms = int((time.monotonic() - start) * 1000)
        return GeminiOutcome(ok=True, latency_ms=latency_ms, raw=data, model_version=model)
    except concurrent.futures.TimeoutError:
        latency_ms = int((time.monotonic() - start) * 1000)
        return GeminiOutcome(
            ok=False, latency_ms=latency_ms, error=f"Model call timed out after {timeout_s}s",
            model_version=model,
        )
    except Exception as exc:  # noqa: BLE001 - deliberately broad: fail open, never crash the pipeline
        latency_ms = int((time.monotonic() - start) * 1000)
        return GeminiOutcome(ok=False, latency_ms=latency_ms, error=str(exc), model_version=model)

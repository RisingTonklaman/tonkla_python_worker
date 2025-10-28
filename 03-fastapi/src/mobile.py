from typing import Any, Dict, List, Optional
import os
import json

from fastapi import APIRouter, HTTPException

try:
    # local/dev: load .env if present
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import httpx

router = APIRouter()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
TABLE = os.environ.get("SUPABASE_TABLE", "mobile01")

if not SUPABASE_URL or not SUPABASE_KEY:
    # Will raise at request-time if not provided, but we keep variables None-friendly here
    pass


def _headers():
    return {
        "apikey": SUPABASE_KEY or "",
        "Authorization": f"Bearer {SUPABASE_KEY or ''}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def _supabase_get(path: str, params: Optional[Dict[str, Any]] = None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url, params=params or {}, headers=_headers())
    if r.status_code >= 400:
        raise HTTPException(status_code=500, detail={"supabase_error": r.text})
    return r.json()


async def _supabase_post(path: str, payload: Dict[str, Any]):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    headers = _headers()
    headers["Prefer"] = "return=representation"
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(url, headers=headers, content=json.dumps(payload))
    if r.status_code >= 400:
        raise HTTPException(status_code=500, detail={"supabase_error": r.text})
    return r.json()


async def _supabase_patch(path: str, pk: Any, payload: Dict[str, Any]):
    url = f"{SUPABASE_URL}/rest/v1/{path}?id=eq.{pk}"
    headers = _headers()
    headers["Prefer"] = "return=representation"
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.patch(url, headers=headers, content=json.dumps(payload))
    if r.status_code >= 400:
        raise HTTPException(status_code=500, detail={"supabase_error": r.text})
    return r.json()


async def _supabase_delete(path: str, pk: Any):
    url = f"{SUPABASE_URL}/rest/v1/{path}?id=eq.{pk}"
    headers = _headers()
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.delete(url, headers=headers)
    if r.status_code >= 400:
        raise HTTPException(status_code=500, detail={"supabase_error": r.text})
    return {"deleted": True}


@router.get("/")
async def list_items() -> List[Dict[str, Any]]:
    """List rows from the Supabase table."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(status_code=500, detail="SUPABASE_URL or SUPABASE_KEY not configured")
    return await _supabase_get(TABLE)


@router.get("/{item_id}")
async def get_item(item_id: int) -> Dict[str, Any]:
    items = await _supabase_get(TABLE, params={"id": f"eq.{item_id}"})
    if not items:
        raise HTTPException(status_code=404, detail="item not found")
    return items[0]


@router.post("/")
async def create_item(payload: Dict[str, Any]):
    """Create a row. Payload is JSON matching table columns."""
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="invalid payload")
    row = await _supabase_post(TABLE, payload)
    # Supabase returns array of created rows when using return=representation
    return row[0] if isinstance(row, list) and row else row


@router.put("/{item_id}")
async def update_item(item_id: int, payload: Dict[str, Any]):
    row = await _supabase_patch(TABLE, item_id, payload)
    return row[0] if isinstance(row, list) and row else row


@router.delete("/{item_id}")
async def delete_item(item_id: int):
    await _supabase_delete(TABLE, item_id)
    return {"deleted": True}

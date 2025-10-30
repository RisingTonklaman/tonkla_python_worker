from typing import Any, Dict, List, Optional
import os
import json
import time

from fastapi import APIRouter, HTTPException, Body, Query, Request
from pydantic import BaseModel
from datetime import date, time as dt_time

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
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")
TABLE = os.environ.get("SUPABASE_TABLE", "mobile01")

if not SUPABASE_URL or not SUPABASE_KEY:
    # Will raise at request-time if not provided, but we keep variables None-friendly here
    pass


def _headers(auth_token: Optional[str] = None):
    """Build headers for Supabase requests.

    If auth_token is provided (e.g. 'Bearer <jwt>'), use that as Authorization
    and do NOT expose the service role key. Otherwise fall back to the
    SUPABASE_KEY from env (intended for server-side local dev/service-role).
    """
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    # Always include apikey header when available (helps Supabase accept requests)
    if SUPABASE_ANON_KEY:
        headers["apikey"] = SUPABASE_ANON_KEY

    if auth_token:
        # allow caller to pass either 'Bearer <token>' or raw jwt
        token = auth_token.strip()
        if not token.lower().startswith("bearer "):
            token = "Bearer " + token
        headers["Authorization"] = token
    else:
        # server-side fallback key (service role) used when no auth header provided
        if SUPABASE_KEY:
            # include both apikey and Authorization for server calls
            headers["Authorization"] = f"Bearer {SUPABASE_KEY}"
    return headers


async def _supabase_get(path: str, params: Optional[Dict[str, Any]] = None, auth_token: Optional[str] = None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url, params=params or {}, headers=_headers(auth_token))
    if r.status_code >= 400:
        raise HTTPException(status_code=500, detail={"supabase_error": r.text})
    return r.json()


async def _supabase_post(path: str, payload: Dict[str, Any], auth_token: Optional[str] = None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    headers = _headers(auth_token)
    headers["Prefer"] = "return=representation"
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(url, headers=headers, content=json.dumps(payload))
    if r.status_code >= 400:
        raise HTTPException(status_code=500, detail={"supabase_error": r.text})
    return r.json()


async def _supabase_patch(path: str, pk: Any, payload: Dict[str, Any], auth_token: Optional[str] = None):
    url = f"{SUPABASE_URL}/rest/v1/{path}?id=eq.{pk}"
    headers = _headers(auth_token)
    headers["Prefer"] = "return=representation"
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.patch(url, headers=headers, content=json.dumps(payload))
    if r.status_code >= 400:
        raise HTTPException(status_code=500, detail={"supabase_error": r.text})
    return r.json()


async def _supabase_delete(path: str, pk: Any, auth_token: Optional[str] = None):
    url = f"{SUPABASE_URL}/rest/v1/{path}?id=eq.{pk}"
    headers = _headers(auth_token)
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.delete(url, headers=headers)
    if r.status_code >= 400:
        raise HTTPException(status_code=500, detail={"supabase_error": r.text})
    return {"deleted": True}


async def _supabase_rpc(function: str, args: Dict[str, Any], auth_token: Optional[str] = None):
    """Call a Supabase Postgres function via RPC.

    POST {SUPABASE_URL}/rest/v1/rpc/{function}
    Body is a JSON object mapping to function parameters.
    """
    # If no explicit auth_token provided, try to obtain a dev JWT from
    # environment (SUPABASE_DEV_EMAIL / SUPABASE_DEV_PASSWORD) so local UI
    # can call authenticated RPCs without manual token entry.
    # This only runs in local/dev when those env vars are set.
    if not auth_token:
        try:
            dev_token = await _get_dev_jwt()
            if dev_token:
                auth_token = dev_token
        except Exception:
            # ignore dev-token failures and continue (calls may fail with P0001)
            auth_token = None

    url = f"{SUPABASE_URL}/rest/v1/rpc/{function}"
    headers = _headers(auth_token)
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(url, headers=headers, content=json.dumps(args or {}))
        # If function not found (PGRST202) try retrying with p_ prefixed parameter names
        if r.status_code >= 400:
            text = r.text or ""
            if "PGRST202" in text or "Could not find the function" in text:
                # attempt to retry with p_ prefixed keys
                if args:
                    # First, try simple p_ prefixed mapping
                    alt_args = {f"p_{k}": v for k, v in (args or {}).items()}

                    # If the server provided a hint with an expected signature, parse it
                    # and try to map parameters (use sensible defaults for missing params)
                    text_lower = text.lower()
                    hint_idx = text.find("Perhaps you meant to call the function")
                    if hint_idx != -1:
                        # extract parenthesized param list from hint if present
                        start = text.find("(", hint_idx)
                        end = text.find(")", start) if start != -1 else -1
                        if start != -1 and end != -1:
                            params_raw = text[start+1:end]
                            # split by comma and clean
                            params = [p.strip() for p in params_raw.split(",") if p.strip()]
                            mapped = {}
                            for p in params:
                                # remove optional schema prefix
                                p_name = p.split()[-1]
                                # try to find corresponding key in args (without p_)
                                key = p_name
                                if key.startswith('p_'):
                                    base = key[2:]
                                else:
                                    base = key
                                if base in (args or {}):
                                    mapped[p_name] = (args or {})[base]
                                elif base in (alt_args or {}):
                                    mapped[p_name] = (alt_args or {})[base]
                                else:
                                    # sensible defaults: numeric position -> 0, else null
                                    if 'position' in base or 'order' in base or 'pos' in base:
                                        mapped[p_name] = 0
                                    else:
                                        mapped[p_name] = None
                            # use mapped as alt_args override
                            alt_args = mapped

                    async with httpx.AsyncClient(timeout=15.0) as client:
                        r2 = await client.post(url, headers=_headers(auth_token), content=json.dumps(alt_args))
                    if r2.status_code < 400:
                        try:
                            return r2.json()
                        except Exception:
                            return r2.text
                    # fallthrough to error
            raise HTTPException(status_code=500, detail={"supabase_error": r.text, "function": function})

    # Some RPCs return scalar, array or object; return parsed JSON or raw text
    try:
        return r.json()
    except Exception:
        return r.text


_DEV_JWT_CACHE: Dict[str, Any] = {"token": None, "expires_at": 0}


async def _get_dev_jwt() -> Optional[str]:
    """Return a cached dev JWT or request one using SUPABASE_DEV_EMAIL/PASSWORD.

    Environment variables used:
      - SUPABASE_DEV_EMAIL
      - SUPABASE_DEV_PASSWORD

    Security: storing credentials in env is only for local dev. Do NOT put
    these into production or public repos. If you prefer, create a dedicated
    test user and rotate its password regularly.
    """
    email = os.environ.get("SUPABASE_DEV_EMAIL")
    password = os.environ.get("SUPABASE_DEV_PASSWORD")
    if not email or not password:
        return None

    now = int(time.time())
    if _DEV_JWT_CACHE.get("token") and _DEV_JWT_CACHE.get("expires_at", 0) - 10 > now:
        return _DEV_JWT_CACHE["token"]

    # Request a token from Supabase Auth (grant_type=password)
    auth_url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    headers = {"apikey": SUPABASE_ANON_KEY or "", "Content-Type": "application/json"}
    body = {"email": email, "password": password}
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(auth_url, headers=headers, content=json.dumps(body))
    if r.status_code >= 400:
        # don't raise — return None so callers can fall back
        return None
    try:
        data = r.json()
        token = data.get("access_token")
        expires_in = int(data.get("expires_in") or 3600)
        if token:
            _DEV_JWT_CACHE["token"] = token
            _DEV_JWT_CACHE["expires_at"] = now + expires_in
            return token
    except Exception:
        return None
    return None


@router.get("/")
@router.get("")
async def list_items() -> List[Dict[str, Any]]:
    """List rows from the Supabase table."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(status_code=500, detail="SUPABASE_URL or SUPABASE_KEY not configured")
    return await _supabase_get(TABLE)


@router.get("/items/{item_id}")
async def get_item(item_id: str) -> Dict[str, Any]:
    items = await _supabase_get(TABLE, params={"id": f"eq.{item_id}"})
    if not items:
        raise HTTPException(status_code=404, detail="item not found")
    return items[0]


@router.post("/")
@router.post("")
async def create_item(payload: Dict[str, Any]):
    """Create a row. Payload is JSON matching table columns."""
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="invalid payload")
    row = await _supabase_post(TABLE, payload)
    # Supabase returns array of created rows when using return=representation
    return row[0] if isinstance(row, list) and row else row


@router.put("/items/{item_id}")
async def update_item(item_id: str, payload: Dict[str, Any]):
    row = await _supabase_patch(TABLE, item_id, payload)
    return row[0] if isinstance(row, list) and row else row


@router.delete("/items/{item_id}")
async def delete_item(item_id: str):
    await _supabase_delete(TABLE, item_id)
    return {"deleted": True}


# Convenience endpoints backed by RPC functions you created in Supabase

@router.get("/lists")
async def lists_read():
    """Return user's lists via RPC lists_read()."""
    return await _supabase_rpc("lists_read", {})


@router.post("/lists")
async def lists_create(request: Request, payload: Dict[str, Any] = Body(...)):
    """Create a list by calling the Supabase RPC `lists_create(p_title, p_color, p_position)`.

    This endpoint accepts either the friendly keys (title, color, position) or the
    RPC-style keys (p_title, p_color, p_position). The handler validates the
    friendly fields using a Pydantic model and then maps them to the `p_`-prefixed
    parameter names required by the PostgREST RPC.

    Example request body (friendly form):
      { "title": "inbox", "color": "#ff0000", "position": 0 }

    Example request body (RPC form):
      { "p_title": "inbox", "p_color": "#ff0000", "p_position": 0 }
    """
    auth = request.headers.get("authorization")

    # Normalize incoming payload to friendly names before validation
    try:
        title = payload.get("title") if isinstance(payload, dict) else None
        color = payload.get("color") if isinstance(payload, dict) else None
        position = payload.get("position") if isinstance(payload, dict) else None
        # accept p_ prefixed keys too
        if title is None:
            title = payload.get("p_title") if isinstance(payload, dict) else None
        if color is None:
            color = payload.get("p_color") if isinstance(payload, dict) else None
        if position is None:
            position = payload.get("p_position") if isinstance(payload, dict) else None
    except Exception:
        raise HTTPException(status_code=400, detail="invalid payload")

    class ListsCreateModel(BaseModel):
        title: str
        color: Optional[str] = None
        position: Optional[int] = 0

    # validate
    try:
        model = ListsCreateModel(title=title, color=color, position=position)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"validation error: {e}")

    # Map to RPC parameter names expected by PostgREST
    rpc_args = {
        "p_title": model.title,
        "p_color": model.color,
        "p_position": model.position,
    }
    # If client did not provide Authorization, do NOT insert into the table
    # directly. Instead, if a developer wants a local override, they should
    # create a DB-side wrapper RPC named `lists_create_dev(p_title,p_color,p_position,p_user)`
    # and enable overrides by setting DEV_ALLOW_RPC_OVERRIDES=1. This avoids
    # the server touching `mobile01` table schema directly.
    dev_user = os.environ.get("DEV_STATIC_USER_ID")
    dev_override_allowed = os.environ.get("DEV_ALLOW_RPC_OVERRIDES") == "1"
    if not auth and dev_user and dev_override_allowed:
        # call the dev RPC with p_user override (server will attach SUPABASE_KEY)
        rpc_args_with_user = {**rpc_args, "p_user": dev_user}
        return await _supabase_rpc("lists_create_dev", rpc_args_with_user, auth_token=None)

    # Default: call the RPC and forward any auth token
    return await _supabase_rpc("lists_create", rpc_args, auth_token=auth)


@router.put("/lists/{list_id}")
async def lists_update(list_id: str, payload: Dict[str, Any] = Body(default_factory=dict)):
    args = {"id": list_id, **(payload or {})}
    return await _supabase_rpc("lists_update", args)


@router.delete("/lists/{list_id}")
async def lists_delete(list_id: str):
    return await _supabase_rpc("lists_delete", {"id": list_id})


@router.get("/tasks")
async def tasks_read(p_list_id: str = Query(..., alias="list_id")):
    return await _supabase_rpc("tasks_read", {"p_list_id": p_list_id})


@router.get("/tasks/{task_id}")
async def task_read_one(task_id: str):
    return await _supabase_rpc("task_read_one", {"p_task_id": task_id})


@router.post("/tasks")
async def tasks_create(request: Request, payload: Dict[str, Any] = Body(...)):
    """Create a task via RPC `tasks_create(p_due_date,p_due_time,p_is_important,p_list_id,p_notes,p_priority,p_sort_order,p_title)`.

    Accepts either friendly keys (title, list_id, notes, due_date, due_time, is_important, priority, sort_order)
    or RPC-style keys (p_title, p_list_id, p_notes, p_due_date, p_due_time, p_is_important, p_priority, p_sort_order).
    """
    auth = request.headers.get("authorization")

    # Normalize incoming payload to friendly names
    try:
        title = payload.get("title") if isinstance(payload, dict) else None
        list_id = payload.get("list_id") if isinstance(payload, dict) else None
        notes = payload.get("notes") if isinstance(payload, dict) else None
        due_date = payload.get("due_date") if isinstance(payload, dict) else None
        due_time = payload.get("due_time") if isinstance(payload, dict) else None
        is_important = payload.get("is_important") if isinstance(payload, dict) else None
        priority = payload.get("priority") if isinstance(payload, dict) else None
        sort_order = payload.get("sort_order") if isinstance(payload, dict) else None

        # accept p_ prefixed keys too
        if title is None:
            title = payload.get("p_title") if isinstance(payload, dict) else None
        if list_id is None:
            list_id = payload.get("p_list_id") if isinstance(payload, dict) else None
        if notes is None:
            notes = payload.get("p_notes") if isinstance(payload, dict) else None
        if due_date is None:
            due_date = payload.get("p_due_date") if isinstance(payload, dict) else None
        if due_time is None:
            due_time = payload.get("p_due_time") if isinstance(payload, dict) else None
        if is_important is None:
            is_important = payload.get("p_is_important") if isinstance(payload, dict) else None
        if priority is None:
            priority = payload.get("p_priority") if isinstance(payload, dict) else None
        if sort_order is None:
            sort_order = payload.get("p_sort_order") if isinstance(payload, dict) else None
    except Exception:
        raise HTTPException(status_code=400, detail="invalid payload")

    class TasksCreateModel(BaseModel):
        title: str
        list_id: str
        notes: Optional[str] = None
        due_date: Optional[date] = None
        due_time: Optional[dt_time] = None
        is_important: Optional[bool] = False
        priority: Optional[int] = 3
        sort_order: Optional[float] = 0

    # Validate
    try:
        model = TasksCreateModel(
            title=title,
            list_id=list_id,
            notes=notes,
            due_date=due_date,
            due_time=due_time,
            is_important=is_important,
            priority=priority,
            sort_order=sort_order,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"validation error: {e}")

    # Map to RPC params expected by DB
    rpc_args: Dict[str, Any] = {
        "p_title": model.title,
        "p_list_id": model.list_id,
        "p_notes": model.notes,
        "p_due_date": model.due_date.isoformat() if model.due_date else None,
        "p_due_time": model.due_time.isoformat() if model.due_time else None,
        "p_is_important": model.is_important,
        "p_priority": model.priority,
        "p_sort_order": model.sort_order,
    }

    return await _supabase_rpc("tasks_create", rpc_args, auth_token=auth)


@router.put("/tasks/{task_id}")
async def tasks_update(task_id: str, payload: Dict[str, Any] = Body(default_factory=dict)):
    args = {"id": task_id, **(payload or {})}
    return await _supabase_rpc("tasks_update", args)


@router.delete("/tasks/{task_id}")
async def tasks_delete(task_id: str):
    return await _supabase_rpc("tasks_delete", {"id": task_id})


@router.get("/tags")
async def tags_read_all():
    return await _supabase_rpc("tags_read_all", {})


@router.post("/tags")
async def tags_create(request: Request, payload: Dict[str, Any] = Body(...)):
    """Create a tag by calling the Supabase RPC `tags_create(p_name, p_color)`.

    Accepts friendly keys (name, color) or RPC-style keys (p_name, p_color).
    """
    auth = request.headers.get("authorization")

    # Normalize incoming payload
    try:
        name = payload.get("name") if isinstance(payload, dict) else None
        color = payload.get("color") if isinstance(payload, dict) else None
        if name is None:
            name = payload.get("p_name") if isinstance(payload, dict) else None
        if color is None:
            color = payload.get("p_color") if isinstance(payload, dict) else None
    except Exception:
        raise HTTPException(status_code=400, detail="invalid payload")

    class TagsCreateModel(BaseModel):
        name: str
        color: Optional[str] = None

    try:
        model = TagsCreateModel(name=name, color=color)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"validation error: {e}")

    rpc_args = {
        "p_name": model.name,
        "p_color": model.color,
    }

    return await _supabase_rpc("tags_create", rpc_args, auth_token=auth)


@router.put("/tags/{tag_id}")
async def tags_update(tag_id: str, payload: Dict[str, Any] = Body(default_factory=dict)):
    args = {"id": tag_id, **(payload or {})}
    return await _supabase_rpc("tags_update", args)


@router.delete("/tags/{tag_id}")
async def tags_delete(tag_id: str):
    return await _supabase_rpc("tags_delete", {"id": tag_id})


@router.post("/tags/assign")
async def tags_assign(request: Request, payload: Dict[str, Any] = Body(...)):
    auth = request.headers.get("authorization")
    return await _supabase_rpc("tags_assign", payload, auth_token=auth)


@router.post("/tags/unassign")
async def tags_unassign(request: Request, payload: Dict[str, Any] = Body(...)):
    auth = request.headers.get("authorization")
    return await _supabase_rpc("tags_unassign", payload, auth_token=auth)


@router.post("/reminders")
async def reminders_create(request: Request, payload: Dict[str, Any] = Body(...)):
    # expects {"p_task_id": ..., "p_remind_at": ...}
    auth = request.headers.get("authorization")
    return await _supabase_rpc("reminders_create", payload, auth_token=auth)


@router.put("/reminders/{reminder_id}")
async def reminders_update(reminder_id: str, payload: Dict[str, Any] = Body(default_factory=dict)):
    args = {"id": reminder_id, **(payload or {})}
    return await _supabase_rpc("reminders_update", args)


@router.delete("/reminders/{reminder_id}")
async def reminders_delete(reminder_id: str):
    return await _supabase_rpc("reminders_delete", {"id": reminder_id})


# Generic RPC passthrough for flexibility during development
@router.post("/rpc/{function}")
async def rpc_call(function: str, request: Request, payload: Dict[str, Any] = Body(default_factory=dict)):
    auth = request.headers.get("authorization")
    return await _supabase_rpc(function, payload, auth_token=auth)


# Debug: list registered routes in this router (development only)
@router.get("/_routes")
async def _routes():
    out = []
    for r in router.routes:
        try:
            out.append({
                "path": r.path,
                "methods": list(getattr(r, "methods", []) or []),
                "name": getattr(r, "name", None),
            })
        except Exception:
            pass
    return out


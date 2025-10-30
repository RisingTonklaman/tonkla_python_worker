import jinja2
import os
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse

# The `workers` package (WorkerEntrypoint) is provided by the Cloudflare Python
# runtime. When running locally with uvicorn it won't be available, so import
# it conditionally and provide a small local fallback so the module can be
# imported for local development and testing.
try:
    from workers import WorkerEntrypoint  # type: ignore
except Exception:
    # Local fallback - not used by uvicorn but lets the module import cleanly.
    class WorkerEntrypoint:  # pragma: no cover - local dev shim
        def __init__(self, *args, **kwargs):
            self.env = {}

        async def fetch(self, request):
            raise RuntimeError("WorkerEntrypoint.fetch should not be called in local dev")
from fastapi import APIRouter

# Import router from mobile.py. When running under Cloudflare's pyodide
# packaging the module may be executed as a top-level script (no package)
# so a relative import (from .mobile) can fail with "no known parent package".
# Try the relative import first (normal local dev), then fall back to an
# absolute import which works in the packaged worker bundle.
try:
    from .mobile import router as mobile_router  # local/dev import
except Exception:
    # Fallback for the Cloudflare packaged environment where files are top-level
    from mobile import router as mobile_router

environment = jinja2.Environment()
template = environment.from_string("Hello, {{ name }}!")

app = FastAPI()

# mount mobile01 router for Supabase-backed CRUD
app.include_router(mobile_router, prefix="/mobile01")

# Optional: serve a tiny static UI for local testing at /web
try:
    from fastapi.staticfiles import StaticFiles
    static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
    app.mount("/web", StaticFiles(directory=os.path.abspath(static_dir), html=True), name="web")
except Exception:
    # On Workers, StaticFiles may not be available; ignore in production
    pass


# Serve or redirect /web explicitly to the static index file. This ensures the
# SPA is reachable even in environments where StaticFiles mounting behaves
# differently (for example the Cloudflare packaged worker bundle).
@app.get("/web", include_in_schema=False)
async def web_index():
    static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
    index_path = os.path.abspath(os.path.join(static_dir, "index.html"))
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    # fallback: redirect to root
    return RedirectResponse("/")


@app.get("/")
async def root():
    message = "This is an example of FastAPI with Jinja2 - go to /hi/<name> to see a template rendered"
    return {"message": message}


@app.get("/health")
async def health():
    """Simple health endpoint for uptime checks and post-deploy smoke tests.

    Returns HTTP 200 with a small JSON payload.
    """
    return {"status": "ok"}


@app.get("/hi/{name}")
async def say_hi(name: str):
    message = template.render(name=name)
    return {"message": message}


@app.get("/env")
async def env(req: Request):
    env = req.scope["env"]
    message = f"Here is an example of getting an environment variable: {env.MESSAGE}"
    return {"message": message}


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        import asgi

        return await asgi.fetch(app, request.js_object, self.env)

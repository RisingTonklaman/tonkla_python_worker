import jinja2
from fastapi import FastAPI, Request

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
from .mobile import router as mobile_router

environment = jinja2.Environment()
template = environment.from_string("Hello, {{ name }}!")

app = FastAPI()

# mount mobile01 router for Supabase-backed CRUD
app.include_router(mobile_router, prefix="/mobile01")

# Optional: serve a tiny static UI for local testing at /web
try:
    from fastapi.staticfiles import StaticFiles
    import os

    static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
    app.mount("/web", StaticFiles(directory=os.path.abspath(static_dir), html=True), name="web")
except Exception:
    # On Workers, StaticFiles may not be available; ignore in production
    pass


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


# Development helper: list all registered routes (safe to remove before production)
@app.get("/_dev_routes")
async def dev_routes():
    out = []
    for r in app.routes:
        try:
            methods = list(getattr(r, "methods", []) or [])
            out.append({"path": r.path, "methods": methods, "name": getattr(r, "name", None)})
        except Exception:
            pass
    return out


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        import asgi

        return await asgi.fetch(app, request.js_object, self.env)

import jinja2
import os
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
import pkgutil
import importlib
import importlib.resources as importlib_resources

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
    # Try multiple strategies to load the static index.html so this works
    # both in local uvicorn and in Cloudflare's pyodide packaged environment.
    filename = "index.html"
    content = None

    # 1) filesystem (local dev)
    static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
    index_path = os.path.abspath(os.path.join(static_dir, filename))
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")

    # 2) try importlib.resources (package data)
    try:
        # attempt to read from a package named 'static' or relative to this package
        try:
            data = pkgutil.get_data(__package__ or __name__, os.path.join("..", "static", filename))
            if data:
                content = data
        except Exception:
            pass

        if content is None:
            # try importlib.resources.files for common package layouts
            try:
                pkg = importlib.import_module(__package__ or 'src')
                res = importlib_resources.files(pkg).joinpath('..').joinpath('static').joinpath(filename)
                content = res.read_bytes()
            except Exception:
                # last attempt: package named 'static'
                try:
                    data = pkgutil.get_data('static', filename)
                    if data:
                        content = data
                except Exception:
                    content = None
    except Exception:
        content = None

    if content:
        return Response(content, media_type='text/html')

    # fallback: redirect to root
    return RedirectResponse("/")


# Serve static assets explicitly under /web/ so assets work whether
# the URL is /web or /web/. These handlers try the same package/resource
# lookup strategy used above.
def _load_static_bytes(filename: str) -> bytes | None:
    # 1) filesystem
    static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
    path = os.path.abspath(os.path.join(static_dir, filename))
    if os.path.exists(path):
        try:
            return open(path, 'rb').read()
        except Exception:
            pass

    # 2) pkgutil relative
    try:
        data = pkgutil.get_data(__package__ or __name__, os.path.join('..', 'static', filename))
        if data:
            return data
    except Exception:
        pass

    # 3) importlib.resources
    try:
        pkg = importlib.import_module(__package__ or 'src')
        res = importlib_resources.files(pkg).joinpath('..').joinpath('static').joinpath(filename)
        return res.read_bytes()
    except Exception:
        pass

    # 4) try package named 'static'
    try:
        data = pkgutil.get_data('static', filename)
        if data:
            return data
    except Exception:
        pass

    return None


@app.get('/web/app.css', include_in_schema=False)
async def web_css():
    data = _load_static_bytes('app.css')
    if data is None:
        return RedirectResponse('/')
    return Response(content=data, media_type='text/css')


@app.get('/web/app.js', include_in_schema=False)
async def web_js():
    data = _load_static_bytes('app.js')
    if data is None:
        return RedirectResponse('/')
    return Response(content=data, media_type='application/javascript')


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

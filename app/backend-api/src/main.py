import logging
import os
import uuid
from contextvars import ContextVar
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

trace_id_ctx: ContextVar[str] = ContextVar("trace_id", default="")


class TraceIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "trace_id", None):
            ctx_tid = trace_id_ctx.get()
            if ctx_tid:
                record.trace_id = ctx_tid
            else:
                record.trace_id = ""
        return True


def setup_json_logging():
    try:
        from pythonjsonlogger import jsonlogger

        logger = logging.getLogger()
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        handler = logging.StreamHandler()
        formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(name)s %(levelname)s %(message)s %(trace_id)s"
        )
        handler.setFormatter(formatter)
        handler.addFilter(TraceIdFilter())
        logger.addHandler(handler)
        logger.addFilter(TraceIdFilter())
        logger.setLevel(logging.INFO)
    except ImportError:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )


setup_json_logging()

from .database import (  # noqa: E402
    DAA_DB_PROVIDER,
    Base,
    engine,
    run_db_migrations,
)
from .routers import (  # noqa: E402
    alerts,
    applications,
    auth,
    dashboard,
    fixes,
    incidents,
    ingest,
    logs,
    mcp_gateway,
    projects,
    status,
    telemetry,
)

_DB_ACTIVE = DAA_DB_PROVIDER not in ("none", "internal-redis", "external-redis")

if engine is not None:
    Base.metadata.create_all(bind=engine)
    run_db_migrations(engine)

app = FastAPI(
    title="DAA v2.0 — Autonomous SRE Platform",
    description="Open-source autonomous SRE incident diagnosis and remediation platform.",
    version="2.0.0",
)

# Startup validation for Cloud Run / Serverless constraints
if "K_SERVICE" in os.environ:
    queue_mode = os.environ.get("DAA_QUEUE_MODE", "rabbitmq").lower()
    always_on_cpu = os.environ.get("DAA_ALWAYS_ON_CPU", "false").lower() == "true"
    if queue_mode != "sync" and not always_on_cpu:
        raise RuntimeError(
            f"Invalid configuration: DAA_QUEUE_MODE={queue_mode} is not supported on Google Cloud Run "
            "without always-on CPU allocation (DAA_ALWAYS_ON_CPU=true). "
            "Cloud Run request-scoped containers suspend CPU between requests, which breaks persistent "
            "background worker threads ('python -m agent_src.main &') and long-running consumers. "
            "Please set DAA_QUEUE_MODE=sync, enable always-on CPU (DAA_ALWAYS_ON_CPU=true), or deploy to a standard container environment."
        )

cors_origins = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:3000,http://localhost:5003,http://127.0.0.1:3000,http://127.0.0.1:5003",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    tid = (
        request.headers.get("trace_id")
        or request.headers.get("x-trace-id")
        or str(uuid.uuid4())
    )
    token = trace_id_ctx.set(tid)
    try:
        response = await call_next(request)
        response.headers["trace_id"] = tid
        return response
    finally:
        trace_id_ctx.reset(token)


app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(logs.router, prefix="/logs", tags=["logs"])
app.include_router(fixes.router, prefix="/fixes", tags=["fixes"])
app.include_router(status.router, prefix="/status", tags=["status"])
app.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
app.include_router(projects.router, prefix="/projects", tags=["projects"])
app.include_router(applications.router, prefix="/applications", tags=["applications"])
app.include_router(applications.router, prefix="/apps", tags=["applications"])
app.include_router(incidents.router, prefix="/incidents", tags=["incidents"])
app.include_router(dashboard.router, tags=["dashboard"])
app.include_router(ingest.router, tags=["ingest"])
app.include_router(telemetry.router, tags=["telemetry"])
app.include_router(mcp_gateway.router, prefix="/api/v1/mcp", tags=["mcp"])


@app.get("/")
def read_root():
    return {"Hello": "World"}


# ── Baked-in minimal admin panel (served from the single Docker image) ─────────
# DAA_SERVE_PANEL=true  → serve /admin (default for single-image mode)
# DAA_SERVE_PANEL=false → disable (set this in docker-compose backend service
#                          when a dedicated admin-panel container is running)
_SERVE_PANEL = os.environ.get("DAA_SERVE_PANEL", "true").lower() == "true"
_ADMIN_HTML_PATH = Path(__file__).parent / "static" / "admin.html"
_ADMIN_HTML: str = (
    _ADMIN_HTML_PATH.read_text(encoding="utf-8")
    if _SERVE_PANEL and _ADMIN_HTML_PATH.exists()
    else ""
)


@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
def serve_admin_panel():
    """Minimal admin panel baked into the backend image.

    Enabled only when DAA_SERVE_PANEL=true (default).
    Set DAA_SERVE_PANEL=false in docker-compose to disable this route
    when a dedicated React admin-panel container is already running on :5003.

    Security: the HTML itself is public, but every data endpoint it calls
    (/dashboard, /incidents/, etc.) enforces get_current_user() — so no
    data leaks even if this route is reachable. When DAA_AUTH_ENABLED=true
    the panel will not auto-login and all API calls will return 401.
    """
    if not _SERVE_PANEL:
        from fastapi.responses import Response

        return Response(status_code=404)
    return HTMLResponse(content=_ADMIN_HTML)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/mock-jira/rest/api/3/issue", status_code=201)
def mock_create_jira_issue(payload: dict):
    # Log the payload for visibility
    print(f"[Mock Jira] Created issue with payload: {payload}")
    # Return a mock issue key
    return {"key": "INC-1234"}


@app.get("/mock-jira/browse/{issue_key}")
def mock_browse_jira_issue(issue_key: str):
    return {
        "status": "ok",
        "issue_key": issue_key,
        "message": "This is a mock Jira ticket page.",
    }

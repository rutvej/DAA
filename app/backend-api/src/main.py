import os
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from .database import (
    DAA_DB_PROVIDER,
    Application,
    Base,
    SessionLocal,
    engine,
    run_db_migrations,
)
from .routers import (
    alerts,
    applications,
    auth,
    dashboard,
    fixes,
    incidents,
    ingest,
    logs,
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

# Startup validation for Cloud Run constraints
if (
    os.environ.get("DAA_QUEUE_MODE", "rabbitmq").lower() == "rabbitmq"
    and "K_SERVICE" in os.environ
):
    raise RuntimeError(
        "Invalid configuration: DAA_QUEUE_MODE=rabbitmq is not supported on Google Cloud Run. "
        "Cloud Run request-scoped containers suspend CPU, which breaks long-running RabbitMQ consumers. "
        "Please use DAA_QUEUE_MODE=sync or deploy to a standard container environment."
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

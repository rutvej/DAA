import os
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine, SessionLocal, Application, run_db_migrations
from .routers import auth, fixes, logs, status, alerts, projects, applications, incidents, dashboard, ingest, telemetry

if engine is not None:
    Base.metadata.create_all(bind=engine)
    run_db_migrations(engine)

app = FastAPI(
    title="DAA v2.0 — Autonomous SRE Platform",
    description="Open-source autonomous SRE incident diagnosis and remediation platform.",
    version="2.0.0",
)

# Startup validation for Cloud Run constraints
if os.environ.get("DAA_QUEUE_MODE", "rabbitmq").lower() == "rabbitmq" and "K_SERVICE" in os.environ:
    raise RuntimeError(
        "Invalid configuration: DAA_QUEUE_MODE=rabbitmq is not supported on Google Cloud Run. "
        "Cloud Run request-scoped containers suspend CPU, which breaks long-running RabbitMQ consumers. "
        "Please use DAA_QUEUE_MODE=sync or deploy to a standard container environment."
    )

cors_origins = [origin.strip() for origin in os.environ.get(
    "CORS_ALLOW_ORIGINS",
    "http://localhost:3000,http://localhost:5003,http://127.0.0.1:3000,http://127.0.0.1:5003"
).split(",") if origin.strip()]

# Allow LAN access from devices on private 192.168.x.x addresses when the UI is opened remotely.
cors_origin_regex = os.environ.get(
    "CORS_ALLOW_ORIGIN_REGEX",
    r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3})(:\d+)?$"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def dynamic_cors_middleware(request: Request, call_next):
    origin = request.headers.get("origin")
    if origin:
        try:
            parsed = urlparse(origin)
            origin_host = parsed.hostname
            if origin_host:
                db = SessionLocal()
                try:
                    matched = db.query(Application).filter(Application.allowed_ip == origin_host).first()
                    if matched:
                        if request.method == "OPTIONS":
                            from fastapi.responses import Response
                            response = Response()
                            response.headers["Access-Control-Allow-Origin"] = origin
                            response.headers["Access-Control-Allow-Credentials"] = "true"
                            response.headers["Access-Control-Allow-Methods"] = "*"
                            response.headers["Access-Control-Allow-Headers"] = "*"
                            return response
                        
                        response = await call_next(request)
                        response.headers["Access-Control-Allow-Origin"] = origin
                        response.headers["Access-Control-Allow-Credentials"] = "true"
                        response.headers["Access-Control-Allow-Methods"] = "*"
                        response.headers["Access-Control-Allow-Headers"] = "*"
                        return response
                finally:
                    db.close()
        except Exception:
            pass
    return await call_next(request)

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
    return {"status": "ok", "issue_key": issue_key, "message": "This is a mock Jira ticket page."}


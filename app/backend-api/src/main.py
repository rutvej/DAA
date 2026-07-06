import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .routers import auth, fixes, logs, status, alerts, projects, applications, incidents, dashboard

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="DAA v2.0 — Autonomous SRE Platform",
    description="Open-source autonomous SRE incident diagnosis and remediation platform.",
    version="2.0.0",
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

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(logs.router, prefix="/logs", tags=["logs"])
app.include_router(fixes.router, prefix="/fixes", tags=["fixes"])
app.include_router(status.router, prefix="/status", tags=["status"])
app.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
app.include_router(projects.router, prefix="/projects", tags=["projects"])
app.include_router(applications.router, prefix="/applications", tags=["applications"])
app.include_router(incidents.router, prefix="/incidents", tags=["incidents"])
app.include_router(dashboard.router, tags=["dashboard"])


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


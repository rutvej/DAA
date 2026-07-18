# DAA Pluggable Single-Image Architecture Implementation Plan

> **Status:** DRAFT — v0.1  
> **Date:** 2026-07-09  
> **Goal:** Step-by-step concrete engineering plan to implement the unified pluggable architecture, allowing DAA to toggle between stateless serverless (API-only, DB-free) and full datacenter (worktree, Postgres, RabbitMQ) modes.

---

## 1. Phase 1: Database & Configuration Refactoring (`backend-api`)

### 1.1 Config Parsing
We will update `app/backend-api/src/database.py` (and the config loader) to expose the following variables:
*   `DAA_POLICY_ENABLED` (boolean, default `false`)
*   `DAA_AUTH_ENABLED` (boolean, default `false`)
*   `DAA_DB_PROVIDER` (default `sqlite`)
    *   `none`: Bypasses engine creation, returning mock session objects for database reads/writes.
    *   `sqlite`: Uses standard SQLite with WAL mode (`journal_mode=WAL` and `timeout=30.0` to prevent concurrent write locks).
    *   `internal-postgres` / `external-postgres`: Normal SQLalchemy Postgres connections.
    *   `internal-redis` / `external-redis`: Sets up key-value operations for cooldown and rate counters (instead of a SQL database).

### 1.2 Database Engine Fallback
Update SQLAlchemy initialization:
```python
# app/backend-api/src/database.py

db_provider = os.environ.get("DAA_DB_PROVIDER", "sqlite")

if db_provider == "none":
    # Bypasses Postgres/SQLite and runs completely stateless
    engine = None
    SessionLocal = None
elif db_provider == "sqlite":
    DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./daa.db")
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": 30.0}
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
else:
    # Standard Postgres setup
    DATABASE_URL = os.environ.get("DATABASE_URL")
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

---

## 2. Phase 2: Webhook Alert Adapters & Outbound Dispatcher

### 2.1 Webhook Router (`app/backend-api/src/routers/ingest.py`)
Create a new router endpoint `/ingest` that maps webhook payloads to the DAA agent:
*   `POST /ingest/prometheus`: Normalizes Prometheus alert payloads into the generic `InvestigationJob` schema.
*   `POST /ingest/sentry`: Normalizes Sentry webhook payloads.
*   `POST /ingest/custom`: Decodes custom JSON payloads using declarative mapping rules configured in `daa-webhook-mappings.yaml`.
*   **Security:** Verify webhook HMAC signatures (e.g. `X-Sentry-Signature` or matching static token `DAA_API_KEY`).

### 2.2 Outbound Notifications (`app/backend-api/src/notifications/webhook.py`)
Add an outbound HTTP webhook dispatcher. When an agent finishes an investigation:
*   Fires a POST request to `DAA_OUTBOUND_WEBHOOK_URL` containing the `postmortem` markdown, `status` (fixed/escalated), and `pr_url`.
*   Sends an HMAC-SHA256 signature in the `X-DAA-Signature` header using `DAA_OUTBOUND_WEBHOOK_SECRET`.

---

## 3. Phase 3: Stateless Git REST API Engine (`python-agent`)

### 3.1 Pluggable Git Operations (`app/python-agent/src/tools/git_tool.py`)
Refactor the file read/write tools to bypass local disk cloning when `DAA_GIT_MODE=api` is selected.

```python
# app/python-agent/src/tools/git_tool.py

git_mode = os.environ.get("DAA_GIT_MODE", "local")

@tool
def read_file_content(app_name: str, file_path: str) -> str:
    """Reads a file either from local disk or via Git REST API."""
    if git_mode == "api":
        # Call GitHub/GitLab repository contents API
        return fetch_file_via_api(app_name, file_path)
    else:
        # Standard local file read
        with open(os.path.join(f"/tmp/{app_name}", file_path), "r") as f:
            return f.read()
```

### 3.2 Commit/Push via API
If `DAA_GIT_MODE=api` is enabled, the `commit` and `push` tools will create blobs, tree listings, and reference updates directly using the GitHub/GitLab Git Data REST APIs instead of spawning local git CLI commands.

---

## 4. Phase 4: Supervisor Entrypoint & Single-Image Build

### 4.1 Entrypoint Supervisor (`entrypoint.sh`)
Create `entrypoint.sh` to manage services in single-container mode:
1.  **Postgres Daemon:** Check `DAA_DB_PROVIDER`. If set to `internal-postgres`, initialize a PG database cluster on `/var/lib/postgresql/data` and run `pg_ctl start`.
2.  **Redis Daemon:** Check `DAA_DB_PROVIDER`. If set to `internal-redis`, run `redis-server --daemonize yes`.
3.  **FastAPI Server:** Run `uvicorn app.backend-api.src.main:app --host 0.0.0.0 --port 8080`.
4.  **Worker Process:** If `DAA_QUEUE_MODE=sync` (inline background task), do not start a worker process. If `DAA_QUEUE_MODE=rabbitmq` or custom thread queue is selected, start the background worker process `python -m app.python-agent.src.main`.

### 4.2 Single Dockerfile
Install git client, python dependencies, postgresql, and redis-server inside the unified base image:
```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl postgresql postgresql-contrib redis-server && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
```

---

## 5. Verification Checklist

To verify changes sequentially:
1.  **Stateless Run Verification:** Run the container with `DAA_DB_PROVIDER=none`, `DAA_GIT_MODE=api`, and `DAA_QUEUE_MODE=sync`. Send a mock webhook alert to `/ingest/prometheus` and verify the agent creates a PR without cloning the repo locally.
2.  **Internal DB Verification:** Run the container with `DAA_DB_PROVIDER=internal-postgres` and verify Postgres starts automatically inside the container and SQLite/JWT tables are initialized correctly.
3.  **Outbound Webhook Verification:** Ensure that when a job finishes, DAA triggers the outbound POST webhook with a valid signature.
4.  **Backward Compatibility Check:** Run the standard `docker-compose up` setup to ensure multi-container scaling mode remains unaffected.

# Backend API System Overview

This document details the software architecture, modular components, and core routing logic of the FastAPI Backend API.

## 1. Module Structure

The backend application is written in Python using FastAPI and is located under `/home/rutvej/Desktop/DAA/app/backend-api/`.

```
app/backend-api/
├── src/
│   ├── main.py              # Main FastAPI application startup, CORS, and JIRA mocks
│   ├── database.py          # SQLAlchemy models, sessions, database migrations
│   └── routers/             # REST Routers
│       ├── auth.py          # Authentication and token management
│       ├── logs.py          # Log ingestion and escalation sliding-window checks
│       ├── fixes.py         # Fix retrieval, approvals, and execution log streams
│       ├── status.py        # Service status checks
│       ├── alerts.py        # Outage alerts queries
│       ├── projects.py      # Git & Jira repository connections
│       ├── applications.py  # Application registration, logs/metrics/changes endpoints
│       ├── incidents.py     # Incident query and manual escalation
│       ├── dashboard.py     # Metrics feeding the SRE admin dashboard
│       ├── ingest.py        # Sentry, Prometheus, and custom webhook ingestion
│       └── telemetry.py     # Platform telemetry tracking
```

---

## 2. Ingestion Routing & Spawning Workflow

The backend API is the telemetry gateway. It receives exception payloads and executes the following operations:
1. **Dynamic CORS Middleware**: Located in [main.py](file:///home/rutvej/Desktop/DAA/app/backend-api/src/main.py#L40-L71). It intercepts options/cors requests and checks if the requesting host matches the `allowed_ip` of any registered `Application` in the database.
2. **Log Submission**: Processes incoming exceptions in [logs.py](file:///home/rutvej/Desktop/DAA/app/backend-api/src/routers/logs.py#L40-L210) or webhooks in [ingest.py](file:///home/rutvej/Desktop/DAA/app/backend-api/src/routers/ingest.py#L228-L345).
3. **Escalation Decision**: Runs sliding window metrics queries. If an alert is triggered, it creates an `Incident` and enqueues a job.
4. **Queue Dispatches**:
   - In **RabbitMQ** mode, it publishes job JSON to the `fix_jobs` queue.
   - In **Sync** mode, it imports the Python Agent core inline and runs `process_job` via FastAPI `BackgroundTasks`.

---

## 3. Serverless Integration Hacks & Quirks

When deployed on serverless hosting (e.g. GCP Cloud Run), the backend often runs in stateless mode (`DAA_QUEUE_MODE=sync`):
- **Dynamic File Duplication**: To run the Python Agent inline, [logs.py](file:///home/rutvej/Desktop/DAA/app/backend-api/src/routers/logs.py#L160-L174) copies the agent directory to `/app/app/agent_src` using `shutil.copytree`.
- **Dynamic Module Popping**: In [ingest.py](file:///home/rutvej/Desktop/DAA/app/backend-api/src/routers/ingest.py#L191-L209), the backend imports from `src.main` (from python-agent path). To avoid namespace collisions, it extracts and temporarily deletes all `src` modules from `sys.modules`, performs the agent import, and restores them.
- **Mock Database Session**: Bypasses relational engines. If `DAA_DB_PROVIDER=none`, `SessionLocal` maps to `MockSession` in [database.py](file:///home/rutvej/Desktop/DAA/app/backend-api/src/database.py#L59-L102), which returns empty lists and ignores mutations.

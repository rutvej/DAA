# Backend API Business Logic Specification

This document details the webhook integration formats, escalation sliding-windows, and process execution hacks in the Backend API.

## 1. Webhook Ingestion & Parsing Logic

Webhooks are parsed in [ingest.py](file:///home/rutvej/Desktop/DAA/app/backend-api/src/routers/ingest.py):

### A. Sentry webhook
- **Authentication**: Validates signature using `SENTRY_WEBHOOK_SECRET` and HMAC-SHA256 of payload body against `X-Sentry-Signature` header.
- **Parsing**:
  - Matches project slug or name to `app_name`.
  - Maps metadata type to `exception_type`.
  - Maps metadata filename or culinary culprit to `error_file`.
  - Maps error stack trace details to `stack_trace`.

### B. Prometheus alertmanager webhook
- **Authentication**: Uses standard `X-API-Key` or Bearer Token matched to `DAA_API_KEY`.
- **Parsing**:
  - Extracts alert items where status is `firing`.
  - Maps labels `service`/`job`/`app` to `app_name`.
  - Maps label `alertname` to `exception_type`.
  - Maps annotations `description` or `summary` to `stack_trace`.

### C. Custom Webhooks
- Matches path `/ingest/custom/{integration_name}`.
- Loads mapping definitions from `daa-webhook-mappings.yaml` (utilizes dynamic JSONPath expressions).
- If yaml is missing, defaults to identity mapping (e.g. payload field `app_name` maps to `app_name`).

---

## 2. Sliding Window Escalation Logic

Logs are evaluated in [logs.py](file:///home/rutvej/Desktop/DAA/app/backend-api/src/routers/logs.py#L88-L123) to decide if they warrant escalation to the agent:
1. **Fetch Escalation Policy**: Queries the active `EscalationPolicy` for the target `Application` name. If not defined, defaults to a sliding window of `120 seconds` and a threshold of `15 errors`.
2. **Immediate Keyword Match**: Checks if `log.content` contains immediate keywords (`"FATAL"`, `"OOMKill"`, `"PANIC"`, `"DatabaseDeadlock"`). If a match occurs, the sliding window is bypassed, and the log is escalated immediately.
3. **Sliding Window Query**:
   ```sql
   SELECT COUNT(*) FROM logs 
   WHERE app_name = :app_name 
   AND timestamp >= (CURRENT_TIMESTAMP - :window_sec)
   ```
4. **Trigger Decision**: If `error_count >= threshold`, an `Incident` is generated, and a remediation job is dispatched. Otherwise, the log status is saved as `"Logged (Threshold not reached)"` and the API returns HTTP 202.

---

## 3. Dynamic Inline Agent Spawning Hacks (Sync Mode)

When `DAA_QUEUE_MODE=sync` is enabled:
- **Collision Avoidance**: Both the Backend API and the Python Agent modules have root packages named `src`. To avoid namespace collision when running the agent inside FastAPI's event loop:
  - In `ingest.py`:
    1. Temporarily extracts all modules matching `"src"` or starting with `"src."` from `sys.modules`.
    2. Modifies `sys.path` to include the `python-agent` folder.
    3. Imports the agent runner `from src.main import process_job`.
    4. Restores the original backend modules back to `sys.modules`.
  - In `logs.py`:
    1. Adds `/app/app/python-agent` to `sys.path` and handles module isolation dynamically.
    2. Imports the agent runner `process_job`.
- **Background Dispatch**: Enqueues `process_job(job)` inside a FastAPI `BackgroundTasks` thread pool.
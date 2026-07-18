# DAA Global API Contract Specification

This document details the REST API contract exposed by the DAA Backend API, including request/response models and authentication requirements.

## 1. Authentication

The DAA platform supports JWT Bearer Authentication.
- **HTTP Header**: `Authorization: Bearer <JWT_TOKEN>`
- **Application Tokens**: Applications use specific API tokens generated during registration. If `DAA_AUTH_ENABLED=false` (e.g. serverless stateless mode with no database), authentication checks are bypassed.

---

## 2. Ingest & Telemetry APIs

### Submit Log
* **Endpoint**: `POST /logs/`
* **Authentication**: Application Token
* **Request Payload (`LogCreate`)**:
```json
{
  "content": "RedisTimeoutError: Connection timed out connecting to redis-master:6379...",
  "app_name": "checkout-service",
  "exception_type": "RedisTimeoutError",
  "trace_id": "otlp-trace-id-12345",
  "correlation_id": "corr-uuid-987",
  "metadata_json": "{\"env\": \"production\"}"
}
```
* **Response (Breached/Escalated - 202 Accepted)**:
```json
{
  "logId": "log-uuid-111",
  "status": "Escalated to Agent",
  "incidentId": "incident-uuid-222",
  "fingerprint": "8d3e2a0f1b"
}
```
* **Response (Logged/Below Threshold - 202 Accepted)**:
```json
{
  "logId": "log-uuid-111",
  "status": "Logged (Threshold not reached)",
  "error_count": 2,
  "threshold": 15,
  "window_seconds": 120
}
```

### Ingest Prometheus Alert
* **Endpoint**: `POST /ingest/prometheus`
* **Request Payload**: Standard Prometheus Alertmanager webhook format.
* **Response**: `{"status": "accepted", "jobs": 1}`

### Ingest Sentry Issue
* **Endpoint**: `POST /ingest/sentry`
* **Headers**: `X-Sentry-Signature: <hmac-signature>`
* **Request Payload**: Standard Sentry Issue Created webhook payload.
* **Response**: `{"status": "accepted"}`

---

## 3. Fixes & Agent Execution APIs

### Query Fix by Fingerprint
* **Endpoint**: `GET /fixes/fingerprint/{fingerprint}`
* **Response**:
```json
{
  "status": "fix_open",
  "pr_url": "https://github.com/org/repo/pull/12",
  "fix_id": "fix-uuid-abc"
}
```

### Append Execution Log
* **Endpoint**: `POST /fixes/{id}/append-log`
* **Request**:
```json
{
  "log_line": "🤖 **Thought:** Need to read connection pool settings..."
}
```
* **Response**: `{"status": "ok"}`

### Approve Fix
* **Endpoint**: `POST /fixes/{id}/approve`
* **Response**: `{"status": "approved", "pr_url": "..."}`

---

## 4. Application & Policy Configuration APIs

### Register Application
* **Endpoint**: `POST /applications/` or `POST /apps/`
* **Request**:
```json
{
  "name": "checkout-service",
  "language": "python",
  "repository_url": "https://github.com/org/checkout-service.git"
}
```
* **Response**:
```json
{
  "id": "app-uuid-888",
  "name": "checkout-service",
  "token": "daa-client-token-xyz123",
  "created_at": "2026-07-10T19:00:00Z"
}
```

### Configure Escalation Policy
* **Endpoint**: `POST /applications/{id}/escalation-policies`
* **Request**:
```json
{
  "rule_type": "error_rate_threshold",
  "condition_value": 3,
  "window_seconds": 60,
  "cooldown_minutes": 30,
  "severity_keywords": "[\"FATAL\", \"OOMKill\"]"
}
```
* **Response**: Standard escalation policy object with ID.

---

## 5. Observability Hydration APIs (Internal)

These endpoints are queried by the agent's `LogHydrator` during Phase 1 (Pre-flight) to assemble context:
- `GET /apps/{app_name}/logs?before={timestamp}&limit=500` -> returns application logs preceding the incident.
- `GET /apps/{app_name}/metrics?timestamp={timestamp}` -> returns CPU, Memory, and application specific metric gauges.
- `GET /apps/{app_name}/recent-changes` -> returns the last 10 git commits (SHA, author, message).

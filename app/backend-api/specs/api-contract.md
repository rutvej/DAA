# Backend API Contract Specification

This document describes all API endpoints exposed by the FastAPI backend module.

## 1. Authentication Endpoints (`/auth`)

### Register User
* **Method**: `POST /auth/register`
* **Request Body**:
```json
{
  "username": "sre_user",
  "password": "sre_password",
  "role": "User"
}
```
* **Response (200 OK)**: `{"message": "User created successfully"}`
* **Response (400 Bad Request)**: `{"detail": "Username already registered"}`

### Login User
* **Method**: `POST /auth/login`
* **Request Body**:
```json
{
  "username": "sre_user",
  "password": "sre_password"
}
```
* **Response (200 OK)**:
```json
{
  "access_token": "jwt-token-string",
  "token_type": "bearer"
}
```

---

## 2. Ingestion & Log Endpoints (`/logs`, `/ingest`)

### Submit Outage Log
* **Method**: `POST /logs/`
* **Authentication**: Authorization Bearer Token
* **Request Body**:
```json
{
  "content": "RedisConnectionError: timed out",
  "app_name": "checkout-service",
  "exception_type": "RedisConnectionError",
  "trace_id": "12345",
  "correlation_id": "67890",
  "metadata_json": "{}"
}
```
* **Response (202 Accepted)**:
  - If escalated: `{"logId": "uuid", "status": "Escalated to Agent", "incidentId": "uuid", "fingerprint": "hash"}`
  - If below threshold: `{"logId": "uuid", "status": "Logged (Threshold not reached)", "error_count": 1, ...}`
* **Response (403 Forbidden)**: `{"detail": "This token is only authorized to submit logs for application..."}`

### Ingest Prometheus Alert
* **Method**: `POST /ingest/prometheus`
* **Request Body**: Alertmanager payload.
* **Response (200 OK)**: `{"status": "accepted", "jobs": 1}`

### Ingest Sentry Webhook
* **Method**: `POST /ingest/sentry`
* **Headers**: `X-Sentry-Signature`
* **Response (200 OK)**: `{"status": "accepted"}`

---

## 3. Incident Management Endpoints (`/incidents`)

### List Incidents
* **Method**: `GET /incidents/`
* **Query Parameters**: `status` (optional), `limit` (default: 10)
* **Response (200 OK)**: List of Incident records.

### Fetch Incident Details
* **Method**: `GET /incidents/{id}`
* **Response (200 OK)**: Complete incident payload, including confidence scores and postmortems.

---

## 4. Fix Review Endpoints (`/fixes`)

### Fetch Fix by Fingerprint
* **Method**: `GET /fixes/fingerprint/{fingerprint}`
* **Response (200 OK)**:
```json
{
  "status": "fix_open",
  "pr_url": "https://github.com/...",
  "fix_id": "uuid"
}
```

### Append Agent Trace Log
* **Method**: `POST /fixes/{id}/append-log`
* **Request Body**: `{"log_line": "string"}`
* **Response (200 OK)**: `{"status": "ok"}`

### Approve Agent Fix
* **Method**: `POST /fixes/{id}/approve`
* **Response (200 OK)**: `{"status": "approved", "pr_url": "..."}`

---

## 5. Mock JIRA Endpoints (Testing)

These mock endpoints are provided in `main.py` to bypass JIRA Cloud authentication during local dry runs:
- `POST /mock-jira/rest/api/3/issue` (returns HTTP 201 Created and `{"key": "INC-1234"}`).
- `GET /mock-jira/browse/{issue_key}` (returns HTTP 200 OK mock browse page).

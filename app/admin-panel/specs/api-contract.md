# Admin Panel API Contract Specification

This document details the backend API routes and client-side payload models consumed by the React Admin Panel.

## 1. Client-Side API Consumables

All requests are dispatched to the host configured at `REACT_APP_API_URL`.

| Operation | HTTP Method & Path | Request Payload Structure | Expected Response Shape |
| :--- | :--- | :--- | :--- |
| **Authenticate** | `POST /auth/login` | `{"username": "...", "password": "..."}` | `{"access_token": "...", "token_type": "bearer"}` |
| **Register User** | `POST /auth/register` | `{"username": "...", "password": "...", "role": "..."}` | `{"message": "User created successfully"}` |
| **Dashboard Metrics** | `GET /dashboard` | None | `{"active_incidents": 0, "fix_rate_percent": 0.0, "recent_incidents": [...]}` |
| **Incidents Query** | `GET /incidents/` | None (Query: `?page=1&limit=10`) | `[{"id": "...", "fingerprint": "...", "status": "..."}]` |
| **Logs Query** | `GET /logs/` | None | `[{"id": "...", "status": "...", "timestamp": "..."}]` |
| **Traceback Details**| `GET /logs/{id}` | None | `{"id": "...", "content": "Stack trace text...", "status": "..."}` |
| **Fix Metrics** | `GET /fixes/{id}` | None | `{"id": "...", "generatedFix": "diff text", "postmortem": "markdown", "isApproved": false}` |
| **Execution Logs** | `GET /fixes/{id}/logs` | None | `{"logs": ["log line 1", "log line 2"]}` |
| **Approve Resolution**| `POST /fixes/{id}/approve`| None | `{"status": "approved", "pr_url": "..."}` |
| **Microservices List**| `GET /applications/`| None | `[{"id": "...", "name": "...", "allowed_ip": "..."}]` |
| **Register Service**| `POST /applications/`| `{"name": "...", "language": "...", "repository_url": "..."}` | `{"id": "...", "name": "...", "token": "..."}` |
| **Update Policies** | `POST /applications/{id}/escalation-policies` | `{"rule_type": "...", "condition_value": 0}` | `{"id": "...", "rule_type": "..."}` |
| **System Diagnostics**| `GET /status` | None | `{"services": {"postgres": "running", "rabbitmq": "running"}}` |

---

## 2. Response Mappings & Error Interceptors

The frontend uses Axios interceptors to parse API errors:
- **HTTP 401 Unauthorized**: Wipes stored token credentials from `localStorage` and triggers a client-side redirect to the `/login` view.
- **HTTP 403 Forbidden**: Displays an alert modal notifying the SRE operator of insufficient user rights.
- **HTTP 503 Service Unavailable**: Displays an inline banner warning that the background broker (RabbitMQ) is disconnected.

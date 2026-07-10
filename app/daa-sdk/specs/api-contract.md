# DAA SDK API Contract Specification

This document details the telemetry ingestion payload structure and HTTP headers used by the SDK clients when sending exception logs to the DAA backend.

## 1. Transmission Details

- **Protocol**: HTTP/1.1 or HTTP/2
- **Endpoint**: `{DAA_BACKEND_API_URL}/logs/`
- **Method**: `POST`
- **Headers**:
  - `Content-Type: application/json`
  - `Authorization: Bearer <DAA_TOKEN>` (token is loaded from environment variables).

---

## 2. Ingestion Request Schema

The payload submitted by each SDK instance has the following fields:

- **`content`** (string): A JSON-serialized string enclosing traceback specifics.
- **`app_name`** (string): Logical microservice name. Maps to the registered application name.
- **`exception_type`** (string, Optional): The class type of the captured exception.

### Nested `content` JSON Structure
Inside the `content` string field, the SDK serializes a nested object:

```json
{
  "message": "Connection timed out connecting to redis-master:6379",
  "stack_trace": "Traceback (most recent call last):\n  File \"app.py\", line 15, in index\n    db.get('key')\n...",
  "context": {
    "user_id": "usr-12345",
    "request_path": "/checkout"
  },
  "timestamp": "2026-07-10T19:00:00Z"
}
```

---

## 3. Client Resiliency Requirements

- **Non-blocking Dispatch**: SDK calls should execute asynchronously or handle network exceptions gracefully.
- **Error Swallow**: If the backend API is unreachable or returns HTTP errors (such as HTTP 503 database lock or timeout), the SDK MUST catch the error internally and fail silently to prevent crashing the host client application.
- **SDK Debug Log**: Print failures to system standard error logs if client-side debug flags are enabled.

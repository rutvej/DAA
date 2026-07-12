# DAA SDK Data Model Specification

This document details the configuration structures and in-memory payload models utilized by the DAA SDK clients.

## 1. SDK Configuration Model

SDK clients load configurations from the environment of the target microservice:

- **`DAA_BACKEND_API_URL`**: HTTP address of the API service. Defaults to `http://localhost:8000`.
- **`DAA_TOKEN`**: Bearer token payload.
- **`REPO_NAME`** (or `AppName` fallback): Identifies the microservice (e.g. `checkout-service`). Defaults to `default-app` if not configured.

---

## 2. In-Memory Exception Models

The SDK maps native runtime exception fields to serializable telemetry attributes:

### A. Python (`DaaSdk.capture_exception`)
- **Exception Class**: `Exception` (or inheriting classes).
- **traceback.format_exc()**: Unwinds call stacks to generate the plain-text traceback string.

### B. NodeJS (`DaaSdk.captureException`)
- **Error Class**: Native `Error` object.
- **error.stack**: Captures javascript stack trace.

### C. Go (`Client.CaptureException`)
- **Error Type**: Native `error` interface.
- **runtime/debug.Stack()**: Unwinds goroutine stack frames to extract binary trace details.

### D. Java (`DaaClient.captureException`)
- **Exception Type**: `Throwable` class.
- **throwable.printStackTrace(printWriter)**: Captures class scopes and line offsets.

---

## 3. Serialization Formats per Language

The SDK client formats payloads into standard JSON prior to API dispatch:
- **Python**: `json.dumps()`
- **NodeJS**: `JSON.stringify()`
- **Go**: `json.Marshal()`
- **Ruby**: `JSON.generate()`
- **Java**: Jackson/Gson serialization mappings.
- **.NET**: `JsonConvert.SerializeObject()`.

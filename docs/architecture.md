# Architecture Overview

## High-Level Flow
1. Client app sends an error log to the backend API.
2. Backend API stores the log and queues a job in RabbitMQ.
3. Python agent consumes the job, inspects code, and produces a fix.
4. Python agent updates fix status in the backend API.
5. Admin panel reads logs and fixes from the backend API.

## Services and Roles
- **backend-api** (`app/backend-api`): Auth, log ingestion, fix tracking.
- **python-agent** (`app/python-agent`): LLM-driven analysis and merge request creation.
- **admin-panel** (`app/admin-panel`): Web UI for logs and fixes.
- **daa-sdk** (`app/daa-sdk`): Client SDK for sending logs.
- **test-app** (`app/test-app`): Sample app that generates errors.

## Specs and Deep Dives
Detailed specs are in the following folders:
- `app/backend-api/specs`
- `app/python-agent/specs`
- `app/admin-panel/specs`
- `app/daa-sdk/specs`
- `app/test-app/specs`

## Security & Authentication Architecture (`v3.0`)
For comprehensive documentation on External IAM pass-through (`[P0-SEC-3]`), machine-to-machine webhook HMAC verification, CORS origin restrictions (`[P0-SEC-2]`), and container volume isolation (`[P0-SEC-1]`), refer directly to the [Security Policy & Hardening Guide](../SECURITY.md) (`SECURITY.md`).

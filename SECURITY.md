# Security Policy & Hardening Guide (`v3.0`)

## Supported Versions
This project currently supports the latest `main` and `audit/*` branches (`v3.0+`).

## Reporting a Vulnerability
Please report security issues privately by emailing maintainers@example.com.

Include:
- A detailed description of the issue
- Steps to reproduce
- Potential impact
- Any possible mitigations

We will acknowledge reports within 7 days and work with you on a fix and disclosure timeline.

---

# 🛡️ DAA v3.0 Security Architecture & Authentication Model

As part of the **v3.0 Forensic Security & Operational Audit**, three core architectural protections (`[P0-SEC-1]`, `[P0-SEC-2]`, and `[P0-SEC-3]`) were established to guarantee secure deployments across bare-metal, Docker, and Cloud Native Kubernetes/Cloud Run environments.

---

## 1. External IAM & Reverse Proxy Pass-Through (`[P0-SEC-3]`)

When deploying DAA behind an enterprise Identity-Aware Proxy (`IAP`), Reverse Proxy, or API Gateway (such as **Google Cloud IAP**, **OAuth2 Proxy**, **Keycloak**, **Okta**, or **AWS ALB IAM**), internal JWT authentication can be disabled via `DAA_AUTH_ENABLED=false`.

To prevent privilege escalation when `DAA_AUTH_ENABLED=false`, DAA implements **External IAM Pass-Through Delegation** with a **Strict Least-Privilege Fallback**:

### Identity & Role Headers
DAA inspects incoming HTTP requests for trusted identity headers injected by your reverse proxy:
- **Identity Header:** `X-Forwarded-User` or `X-DAA-User` (e.g., `alice@company.com`)
- **Role Header:** `X-Forwarded-Role` or `X-DAA-Role` (`admin`, `user`, or `readonly`)

If valid IAM headers are present, DAA assigns the user's explicit role (`role: iam_role`).

### Unauthenticated & Local Development Fallback
If no IAM headers are present and `DAA_AUTH_ENABLED=false` (e.g. direct VPC traffic or local Docker development without external auth), DAA assigns a fallback role controlled by environment variable:
- **`DAA_DEFAULT_ROLE_WHEN_NO_AUTH`** (Defaults to `"readonly"`)
  - Out of the box, unauthenticated requests receive `"readonly"` authority (`{"username": "anonymous", "role": "readonly"}`). This prevents untrusted internal network actors from approving automated code fixes (`POST /fixes/{id}/approve`) or accessing third-party integration secrets.
  - For isolated local development where a developer wants administrative capabilities without login, set `DAA_DEFAULT_ROLE_WHEN_NO_AUTH=admin` in your local `.env`.

---

## 2. Machine-to-Machine Webhook Authentication (`[P0-SEC-3]`)

Automated error logs (`POST /ingest/{app_id}`), Prometheus/Sentry webhooks (`POST /sentry`, `/prometheus`), and internal crash self-reports (`POST /api/v1/self-report`) are executed by server-to-server monitoring pipelines that do **not** use human browser authentication.

In DAA v3.0, webhook routes are decoupled from human dashboard authentication (`DAA_AUTH_ENABLED`):
- **Unconditional API Key Enforcement:** Whenever `DAA_API_KEY` is configured in the environment, all ingestion and self-reporting endpoints require exact verification via `X-API-Key: <key>` or `Authorization: Bearer <key>` unconditionally.
- **Sentry Cryptographic HMAC Verification:** Whenever `SENTRY_WEBHOOK_SECRET` is configured, DAA verifies incoming Sentry payloads by computing an HMAC-SHA256 digest (`hmac.new(secret, body, sha256)`) and verifying it against the `X-Sentry-Signature` header via constant-time comparison (`hmac.compare_digest`).

---

## 3. Strict Origin Allowlist & CORS Protection (`[P0-SEC-2]`)

Because DAA uses session cookies and credentials (`allow_credentials=True` on `backend-api`), overly permissive LAN regular expressions (e.g., `r"^https?://(192\.168\.\d+\.\d+)(:\d+)?$"`) or dynamic origin reflections allow attackers on the same subnet (or malicious applications) to perform Cross-Origin Resource Sharing (`CORS`) hijacking and steal administrative tokens.

### Configuration
DAA v3.0 enforces a strict, explicit origin allowlist managed via `.env`:
```bash
DAA_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080,https://daa.yourdomain.com
```
In `backend-api/src/main.py`, CORSMiddleware strictly checks request origins against `DAA_ALLOWED_ORIGINS` via exact string matching (`os.getenv("DAA_ALLOWED_ORIGINS").split(",")`), rejecting unauthorized cross-origin requests immediately.

---

## 4. Container Isolation & Host Credential Protection (`[P0-SEC-1]`)

The autonomous `python-agent` container executes AI-driven tool calls (`read_file`, `subprocess`, `git` commands) to investigate error logs and synthesize patches. Because Large Language Models can be exposed to prompt injections via malicious error logs or git commits, **the agent container must never have access to host system credentials**.

### Volume Mount Hardening (`docker-compose.yml`)
- **Prohibited Mounts:** Never mount host developer personal credentials (`auth.json`), entire AI configuration directories (`~/.gemini`), host Docker sockets (`/var/run/docker.sock`), or host CLI binaries (`/usr/local/bin/agy`) into running containers.
- **Clean Environment Delegation:** The containerized agent receives only explicit, scoped API keys (`GEMINI_API_KEY`, `DAA_GIT_TOKEN`, `DAA_RABBITMQ_QUEUE`) defined via environment variables, ensuring container escape or prompt injection attacks cannot compromise the host developer's personal identity or local machine.

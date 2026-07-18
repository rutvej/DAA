# DAA — Debugging Autonomous Agent

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)](https://fastapi.tiangolo.com/)
[![LangChain](https://img.shields.io/badge/LangChain-agent-orange.svg)](https://python.langchain.com/)

> **DAA watches your application errors, deduplicates them, and autonomously investigates root causes — then opens a pull request with a suggested fix.**

---

## What DAA does in one diagram

```
Your App throws an error
        ↓
DAA SDK sends it to DAA  (one line of code in your app)
        ↓
SHA-256 deduplication   (same error twice? silent. new error? escalate.)
        ↓
AI Agent investigates   (reads your git commits, logs, and traces)
        ↓
Opens a Pull Request    (with a code fix + root-cause postmortem)
        ↓
You review & merge      (or auto-merge with HITL approval)
```

---

## 🎬 See It In Action — E2E Demo

The [`daa-e2e-demo`](https://github.com/rutvej/daa_e2e_demo) repo contains a full realistic scenario:

- **PayFlow** — a Python (FastAPI) payment API + Go worker, backed by Redis, Postgres, RabbitMQ
- Redis is intentionally capped at **50MB** to trigger an OOM crash under load
- `run_demo.py` orchestrates the entire flow end-to-end: spins up infrastructure, registers services with DAA, runs a load test that triggers the crash, then polls for the AI-generated PR fix

```bash
git clone https://github.com/rutvej/daa_e2e_demo
cd daa-e2e-demo
python run_demo.py   # Sit back and watch the agent fix it
```

> The demo also includes Scenario B (schema break) and Scenario C (cache TTL tuning) for additional failure modes.

---

## 60-Second Quickstart

**Requirements:** Docker, an LLM API key (Gemini is free)

```bash
# 1. Clone and configure
git clone https://github.com/rutvej/DAA && cd DAA
./install.sh && source ~/.bashrc

# 2. Run the guided setup (picks your LLM, git provider, deployment mode)
daa init

# 3. Start DAA
daa redeploy

# 4. Send a test error to verify the pipeline
daa test
```

Then open **http://localhost:8000/admin** to see the incident and the AI's investigation.

---

## How to connect your app

Add **one environment variable** to your service:

```bash
DAA_TOKEN=<token from `daa register`>
DAA_LOGS_URL=http://your-daa-host:8000/logs/
```

Then send errors via HTTP — or use the SDK:

```python
# Python SDK
from daa_sdk import DAAClient

daa = DAAClient()  # reads DAA_TOKEN + DAA_LOGS_URL from env
daa.report_exception(exception, app_name="my-service")
```

SDKs: [Python](./app/daa-sdk/daa_sdk/) · Node.js · Go · Java · Ruby · .NET *(community alpha)*

---

## Deployment Modes

| Mode | Command | Best for |
|------|---------|----------|
| **Single container** *(default)* | `docker run -p 8000:8080 --env-file .env daa:latest` | Try it out, small teams |
| **Docker Compose** | `daa redeploy` | Self-hosted, persistent data |
| **Serverless** | Cloud Run / Fargate with `DAA_DB_PROVIDER=none` | Auto-scaling, zero-ops |

---

## Key Features

| Feature | Description |
|---------|-------------|
| 🔁 **Zero alert fatigue** | SHA-256 fingerprint deduplication + sliding-window cooldowns |
| 🧠 **4-dimension investigation** | Git commits · Logs · Traces · AST code navigation |
| 🔒 **Agent safety** | Hard 8-tool-call budget cap prevents runaway LLM costs |
| 🔀 **Universal LLM routing** | Gemini · GPT-4o · Claude · Vertex · Ollama (local/air-gapped) |
| 👤 **Human-in-the-Loop** | Approve AI fixes before the PR is merged |
| 🔧 **Multi-forge** | GitHub · GitLab · Gitea · Bitbucket |

---

## CLI Commands

```bash
daa init              # Guided setup wizard
daa register          # Register an application with DAA
daa policy            # Configure escalation policies
daa status            # Health check all services
daa test              # Send a synthetic error to verify the pipeline
daa logs              # View recent incidents
daa redeploy          # Rebuild and restart DAA containers
daa config set-model  # Switch LLM provider/model
```

---

## Architecture

```
DAA/
├── app/
│   ├── backend-api/      ← FastAPI — ingest, dedup, incident tracking
│   ├── python-agent/     ← LangChain ReAct SRE agent
│   ├── admin-panel/      ← React dashboard (or use baked-in /admin)
│   └── daa-sdk/          ← Client SDKs
├── docs/                 ← Documentation
│   └── internal/         ← Internal audit reports & roadmaps
└── daa                   ← CLI tool
```

Full architecture: [`docs/architecture.md`](./docs/architecture.md)

---

## Security

DAA is designed for self-hosted or private cloud deployment.

- Secrets are passed via environment variables only — never mounted as files
- CORS is restricted to an explicit allowlist (`CORS_ALLOW_ORIGINS`)
- Webhook endpoints verify `DAA_API_KEY` + HMAC-SHA256 for Sentry
- Agent tool-call budget is hard-capped to prevent runaway LLM loops
- See [`SECURITY.md`](./SECURITY.md) for full hardening guide

---

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) · [SECURITY.md](./SECURITY.md) · [LICENSE](./LICENSE)

PRs welcome. For major features, open an issue first to discuss the design.

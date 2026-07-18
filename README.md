<div align="center">

# DAA — Debugging Autonomous Agent

**Your app breaks at 3am. DAA investigates the root cause and opens a pull request — while you sleep.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)](https://fastapi.tiangolo.com/)
[![LangChain](https://img.shields.io/badge/LangChain-ReAct%20Agent-orange.svg)](https://python.langchain.com/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED.svg)](./Dockerfile)

</div>

---

<!-- DEMO VIDEO — replace this comment with your 30s video embed once uploaded -->
<!-- Option A: YouTube embed (recommended)
[![DAA Demo](https://img.youtube.com/vi/YOUR_VIDEO_ID/maxresdefault.jpg)](https://www.youtube.com/watch?v=YOUR_VIDEO_ID)
-->
<!-- Option B: GitHub-hosted GIF/MP4
<video src="https://github.com/rutvej/DAA/assets/YOUR_ASSET_ID/demo.mp4" controls width="100%"></video>
-->

---

## How it works

```
Error fires in your app at 3am
          ↓
DAA SDK catches it → sends to DAA (one line of code)
          ↓
SHA-256 deduplication — same error again? Suppressed silently.
New pattern? Agent wakes up.
          ↓
AI Agent investigates across 4 dimensions:
   • Git commits  →  what changed recently?
   • App logs     →  what's the stack trace?
   • Traces       →  which request triggered it?
   • Source code  →  AST navigation to the exact line
          ↓
Opens a Pull Request with:
   • A code fix
   • Root-cause explanation
   • Postmortem summary
          ↓
You wake up, review the PR, and merge.
```

---

## 🎬 See it live — E2E Demo

> A Python + Go payment system. Redis is deliberately capped at 50MB to OOM under load.  
> Watch DAA catch the crash, investigate it, and open the fix as a PR — fully automatically.

```bash
git clone https://github.com/rutvej/daa_e2e_demo
cd daa_e2e_demo
python run_demo.py
```

Three built-in failure scenarios:
- **Scenario A** — Redis OOM (cache exhaustion under load)
- **Scenario B** — Schema break (Go consumer crashes after Python API change)
- **Scenario C** — Cache TTL misconfiguration (high eviction warnings)

---

## ⚡ Quickstart — up in 4 commands

**Requirements:** Docker + a free [Gemini API key](https://aistudio.google.com/app/apikey)

```bash
git clone https://github.com/rutvej/DAA && cd DAA
./install.sh && source ~/.bashrc
daa init        # guided wizard: pick your LLM, git provider, deployment mode
daa redeploy    # starts everything
```

Then trigger a test incident:
```bash
daa test
# → open http://localhost:8000/admin to watch the agent work
```

---

## Connect your app — one line

```python
# pip install daa-sdk
from daa_sdk import DAAClient

daa = DAAClient()  # reads DAA_TOKEN + DAA_LOGS_URL from env
daa.report_exception(exception, app_name="my-service")
```

Or send errors directly over HTTP — no SDK required:
```bash
curl -X POST http://your-daa-host:8000/logs/ \
  -H "Authorization: Bearer $DAA_TOKEN" \
  -d '{"app_name": "my-service", "content": "...", "exception_type": "RedisTimeoutError"}'
```

---

## What makes DAA different

| | Traditional alerting | DAA |
|--|--|--|
| **When it fires** | Every time the error happens | Once per unique error pattern |
| **What it tells you** | "Error occurred" | Root cause + code fix |
| **What you do** | Investigate manually | Review a PR |
| **3am pages** | Every time | Only for genuinely new problems |

---

## Features

| | |
|--|--|
| 🔁 **Zero alert fatigue** | SHA-256 fingerprint dedup + sliding-window cooldowns |
| 🧠 **4-dimension investigation** | Git history · Logs · Traces · AST code navigation |
| 🔒 **Agent safety** | Hard 8-tool-call budget cap — no runaway LLM costs |
| 🔀 **Any LLM** | Gemini · GPT-4o · Claude · Vertex · Ollama (air-gapped) |
| 👤 **Human-in-the-Loop** | Approve AI fixes before the PR lands |
| 🔧 **Any git forge** | GitHub · GitLab · Gitea · Bitbucket |
| 🌐 **MCP compatible** | Use DAA as a tool inside Claude Desktop or Cursor |

---

## Deployment

| Mode | Best for | How |
|------|----------|-----|
| **Single Docker container** | Try it out, small teams | `docker run -p 8000:8080 --env-file .env daa:latest` |
| **Docker Compose** | Self-hosted, persistent | `daa redeploy` |
| **Serverless** | Cloud Run / Fargate, zero-ops | `DAA_DB_PROVIDER=none DAA_GIT_MODE=api` |

Full guide: [DEPLOYMENT.md](./DEPLOYMENT.md)

---

## Architecture

```
DAA/
├── app/
│   ├── backend-api/    ← FastAPI: ingest, dedup, incident tracking
│   ├── python-agent/   ← LangChain ReAct SRE agent (the brain)
│   ├── admin-panel/    ← React dashboard
│   └── daa-sdk/        ← Python SDK (Node/Go/Java/Ruby/.NET community)
├── daa                 ← CLI tool (daa init / register / test / logs)
└── docs/               ← Documentation
```

---

## CLI

```bash
daa init              # Guided setup: LLM key, git token, deployment mode
daa register          # Register an app and get its DAA_TOKEN
daa policy            # Set escalation threshold (e.g. 3 errors in 60s)
daa test              # Fire a synthetic error and watch the pipeline
daa logs              # View recent incidents
daa status            # Health check all containers
daa redeploy          # Rebuild and restart everything
daa config set-model  # Switch LLM provider/model without restarting
```

---

## Security

Self-hosted and private by design. See [SECURITY.md](./SECURITY.md) for the full hardening guide.

- Credentials via environment variables only — never mounted as files into containers
- CORS restricted to an explicit allowlist (`CORS_ALLOW_ORIGINS`)  
- Webhook endpoints verify `DAA_API_KEY` + HMAC-SHA256 (Sentry)
- LLM agent tool-call budget is hard-capped (no unbounded loops)
- Report vulnerabilities: [GitHub Security Advisories](https://github.com/rutvej/DAA/security/advisories/new)

---

## Contributing

[CONTRIBUTING.md](./CONTRIBUTING.md) · [SECURITY.md](./SECURITY.md) · [LICENSE](./LICENSE)

PRs welcome. For large changes, open an issue first to align on the approach.

---

<div align="center">

**Built for engineers who are tired of being paged at 3am for the same error twice.**

⭐ Star this repo if it's useful · [Report a bug](https://github.com/rutvej/DAA/issues) · [Request a feature](https://github.com/rutvej/DAA/issues)

</div>

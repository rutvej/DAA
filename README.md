<div align="center">

![DAA — Autonomous SRE Platform](./docs/daa_hero.jpg)

<h1>DAA — Deduplicated Autonomous SRE Platform</h1>

<p><strong>Stop waking up engineers at 3AM. Let AI triage it first.</strong></p>

[![License: MIT](https://img.shields.io/badge/License-MIT-6366f1.svg?style=flat-square)](./LICENSE)
[![Docker Hub](https://img.shields.io/docker/v/rutvej1/daa-standalone?label=Docker%20Hub&color=06b6d4&style=flat-square&logo=docker)](https://hub.docker.com/r/rutvej1/daa-standalone)
[![Python](https://img.shields.io/badge/Python-3.11+-a855f7.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-10b981.svg?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangChain](https://img.shields.io/badge/LangChain-ReAct-f59e0b.svg?style=flat-square)](https://www.langchain.com)
[![GitHub Stars](https://img.shields.io/github/stars/rutvej/DAA?style=flat-square&color=f59e0b&label=Stars)](https://github.com/rutvej/DAA/stargazers)

</div>

---

## What is DAA?

**DAA** is a pluggable, open-source **Autonomous SRE Platform** that automates the first **30–60 minutes of manual triage toil** when production microservices break.

It ingests exception logs (via client SDKs or Sentry/Prometheus webhooks), deduplicates them with **SHA-256 fingerprints**, matches them against **sliding-window escalation policies**, and dispatches a **LangChain SRE Agent** that runs a 4-dimension diagnostic investigation across:

| Dimension | What it checks |
|:---|:---|
| **1. Change Horizon** | Recent git commits that could have caused the regression |
| **2. Infrastructure** | Redis, PostgreSQL, RabbitMQ — OOM, timeouts, lock contention |
| **3. Correlated Traces** | OpenTelemetry trace IDs across dependent microservices |
| **4. Surgical Code Nav** | AST-level grep, file slicing, repo map to pinpoint the exact line |

Then it **applies a fix**, runs **verification tests**, and opens a **Pull/Merge Request** with a generated postmortem — or creates a Jira ticket when human review is needed.

---

## 🚀 30-Second Quickstart — Prebuilt Docker Image

Zero setup. Zero databases. Scales to zero on Cloud Run / Fargate.

```bash
docker pull rutvej1/daa-standalone:latest

docker run -d --name daa \
  -p 8000:8080 \
  -e LLM_PROVIDER=google \
  -e GEMINI_API_KEY=your-gemini-key \
  -e DAA_DB_PROVIDER=none \
  -e DAA_GIT_MODE=api \
  -e DAA_QUEUE_MODE=sync \
  -e DAA_AUTH_ENABLED=false \
  -e DAA_POLICY_ENABLED=false \
  -e GIT_HOST=https://github.com \
  -e GIT_ORG=your-github-org \
  -e GITHUB_TOKEN=ghp_xxxxxxxxxxxx \
  rutvej1/daa-standalone:latest

curl http://localhost:8000/health
# → {"status": "ok"}
```

Point your **Sentry** or **Prometheus** webhooks at `http://<host>:8000/ingest/sentry` and DAA starts triaging immediately. No code changes in your services.

For all supported deployment profiles (with Postgres, with RabbitMQ, Compose vs. single image, auth on/off) → **[`DEPLOYMENT.md`](./DEPLOYMENT.md)**.

---

## 🧩 Pluggable Architecture — One Image, All Modes

The **same Docker image** runs from fully stateless serverless to distributed multi-container clusters — controlled by three environment variables:

| Mode | `DAA_DB_PROVIDER` | `DAA_GIT_MODE` | `DAA_QUEUE_MODE` | Best For |
|:---|:---|:---|:---|:---|
| **Stateless Serverless** | `none` | `api` | `sync` | Cloud Run · Fargate · Lambda |
| **Self-Contained Edge** | `sqlite` | `api` or `local` | `sync` | Single VM · Raspberry Pi |
| **Distributed Scale-Out** | `postgres` | `local` | `rabbitmq` | Datacenter · Kubernetes |

Full 6-combination tested matrix → **[`DEPLOYMENT.md §5`](./DEPLOYMENT.md#5-full-combination-matrix)**.

---

## ✨ Key Features

<table>
<tr>
<td width="50%">

### 🛡️ Zero Alert Fatigue
SHA-256 error fingerprinting + sliding-window escalation policies suppress duplicates before the agent even runs.

### 🔄 Three-Phase Hybrid Flow
**Pre-flight** (repo cache, log hydration, dedup) → **Agent Core** (free ReAct reasoning) → **Post-flight** (diff apply, PR creation, postmortem).

### 🔒 Context Safety System
Enforces a JSON planning step and a hard 8-call budget cap to prevent context explosion and costly hallucinations.

### 🤖 Universal LLM Routing
Gemini · OpenAI · Claude · Vertex AI · Ollama · LiteLLM proxy. Switch models without code changes.

</td>
<td width="50%">

### 🎫 Git & Ticket Automation
Auto-creates GitHub/GitLab/Gitea PRs and Jira tickets. Falls back to GitHub Issues when Jira isn't configured.

### 🚦 Circuit Breakers
Stops making commits and opens a Jira ticket if tests fail twice, or if deadlocks/race conditions are detected.

### 👤 Human-in-the-Loop (HITL)
Set `DAA_HITL_MODE=true` to defer PR creation. Review AI agent traces and postmortems in the dashboard, then approve with one click.

### 🔌 MCP Integration
Expose DAA SRE tools to Cursor, Claude Desktop, or any coding copilot via the stdio MCP Server. Or configure DAA to consume external MCP tools.

</td>
</tr>
</table>

---

## 🛠️ Local Installation & Setup

### 1. Clone & Install
```bash
git clone https://github.com/rutvej/DAA.git
cd DAA
./install.sh
sudo ln -sf $(pwd)/daa /usr/local/bin/daa
```

### 2. Configure with the Wizard
```bash
daa init
```
Configures Git tokens, LLM provider keys, and deployment profile. Populates `.env` and `.env.daa`.

### 3. Deploy

**Stateless (single image, built locally):**
```bash
docker build -t daa-stateless:latest .
docker run -d --name daa-stateless -p 8080:8080 --env-file .env daa-stateless:latest
```

**Distributed / Stateful (Docker Compose):**
```bash
docker compose up -d --build
```

**Prebuilt image:** See the [Quick Start](#-30-second-quickstart--prebuilt-docker-image) above.

---

## 🔑 Git Provider Minimum Scopes

| Provider | Required Scopes |
|:---|:---|
| **GitHub** | Classic PAT: `repo` · Fine-grained: `Contents: R/W`, `Pull requests: R/W` |
| **GitLab** | `api` (or `read_repository` + `write_repository`) |
| **Gitea** | `write:repository`, `write:issue`, `read:user` |
| **Bitbucket** | App Password: `Repositories: Write`, `Pull requests: Write` |

Full detail + Gitea branch endpoint quirks → **[`DEPLOYMENT.md §4`](./DEPLOYMENT.md#4-git-provider-token-permissions)**.

---

## 📂 Codebase Layout

```
DAA/
├── daa                          # Main CLI helper (daa init, daa register, daa policy…)
├── entrypoint.sh                # Single-container entrypoint (stateless image)
├── install.sh                   # Unified installer (venv + deps + CLI link)
├── requirements.txt             # Root-level platform dependencies
├── .env.example                 # Full environment variable reference
├── DEPLOYMENT.md                # Env vars · deployment matrix · token permissions
├── app/
│   ├── backend-api/             # FastAPI REST backend (ingest, dedup, escalation, auth)
│   │   └── src/                 # Routers, DB session, models, mock Jira
│   ├── python-agent/            # LangChain SRE Agent (Three-Phase orchestrator)
│   │   └── agent_src/           # Worker, LLM config, ReAct tools, safety system
│   ├── admin-panel/             # React dashboard (incidents, fixes, HITL approval)
│   └── daa-sdk/                 # Multi-language telemetry SDKs (Python, Go, JS…)
└── specs/                       # Per-module architecture specifications
```

---

## 📣 How to Get Visibility (Grow DAA's Audience)

> [!TIP]
> These are the most effective channels to make DAA discoverable in 2026.

### GitHub Discovery
- ⭐ **Star the repo** — GitHub's trending algorithm weights recent star velocity. Ask early users, friends, and colleagues to star.
- **Tag releases properly** — Use semantic versioning (`v3.0.1`) and write detailed release notes so GitHub features the release in feeds.
- **Fill out the About section** — Add relevant topics: `sre`, `autonomous-agent`, `llm`, `langchain`, `devops`, `incident-response`, `fastapi`, `observability`.

### Community Channels
- **Hacker News** — Post under "Show HN: DAA – an open-source autonomous SRE agent that auto-fixes production bugs". Best time: Tuesday–Thursday, 8–10am ET.
- **Reddit** — Post in `r/devops`, `r/SRE`, `r/MachineLearning`, `r/selfhosted` with a demo GIF.
- **Dev.to / Hashnode** — Write a deep-dive: *"How we built an AI that fixes production bugs automatically"*. Links back to the repo.

### Content Strategy
- **Record a demo video** — A 2-minute Loom/YouTube video showing DAA catching a Redis OOM, running the agent, and opening a PR is worth 100 README paragraphs.
- **Tweet/X threads** — Break down the Three-Phase flow in a 5-tweet thread with code snippets. Tag `#buildinpublic`, `#LangChain`, `#SRE`, `#DevOps`.

### LLM & AI Search Visibility (SEO for AI)
- The `index.html` portal (GitHub Pages) is already optimized with structured JSON-LD, Open Graph tags, and rich `<meta>` descriptions so LLM web-search tools (Perplexity, ChatGPT Browse, Gemini) pick it up.
- Keep **DEPLOYMENT.md** and **README.md** verbose and keyword-rich — LLM crawlers index GitHub markdown.

### Integrations & Partnerships
- **Submit to awesome lists** — `awesome-sre`, `awesome-langchain`, `awesome-devops`.
- **ProductHunt launch** — Schedule a ProductHunt post on a Tuesday. Prepare a maker comment explaining the problem space.
- **Docker Hub** — Keep `rutvej1/daa-standalone` up-to-date with descriptive labels. Docker Hub is a search engine for infrastructure tools.

---

## 📄 License

MIT — See [`LICENSE`](./LICENSE).

---

<div align="center">

**Built with ❤️ for on-call engineers who deserve to sleep.**

[⭐ Star on GitHub](https://github.com/rutvej/DAA) · [🐳 Docker Hub](https://hub.docker.com/r/rutvej1/daa-standalone) · [📖 Full Docs](./DEPLOYMENT.md)

</div>
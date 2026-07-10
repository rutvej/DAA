# DAA — Deduplicated Autonomous SRE Platform

DAA is a pluggable, open-source **Autonomous SRE Platform** designed to automate the first 30–60 minutes of manual triage toil when production microservices break. 

The platform ingests exception logs (via client SDKs or Sentry/Prometheus webhooks), groups them using SHA256 fingerprints to deduplicate runs, matches them against sliding-window escalation policies, and deploys a LangChain SRE Agent. The agent performs a 4-dimension diagnostic investigation (logs, metrics, commits, and codebase navigation), applies dynamic hotfixes, runs verification tests, and opens Merge/Pull Requests with generated postmortem reports.

---

## 🚀 Pluggable Deployment Combinations

DAA is built as a **single-image pluggable architecture** that can scale from a stateless, zero-disk serverless container up to a distributed multi-container cluster.

| Deployment Mode | `DAA_DB_PROVIDER` | `DAA_GIT_MODE` | `DAA_QUEUE_MODE` | Description |
| :--- | :--- | :--- | :--- | :--- |
| **1. Stateless Serverless** | `none` | `api` (Git REST calls) | `sync` (Inline background) | **Zero-disk, scales-to-zero.** Queries and commits files directly via GitHub/GitLab REST APIs. Bypasses local DB and enqueues inline in FastAPI background tasks. Best for Google Cloud Run / AWS Fargate. |
| **2. Self-Contained Edge** | `sqlite` | `api` or `local` | `sync` | **Single VM.** Uses SQLite with WAL mode for local policy tracking and JWT session storage. |
| **3. Distributed Scale-Out** | `postgres` | `local` (Worktree clones) | `rabbitmq` (Distributed) | **Datacenter.** Separates FastAPI API container, RabbitMQ broker, PostgreSQL database, and dedicated agent worker pools. |

---

## 🛡️ Secure Multi-Repository Context Access

To allow DAA to safely diagnose issues stemming from shared libraries or upstream microservices without introducing security vulnerabilities or workspace bloat:

1. **Authorization via Registration:** The SRE Agent can only pull code from repositories explicitly pre-registered in the DAA database (preventing SSRF and exfiltration attacks via dynamically injected URLs).
2. **Work Isolation:** The agent only clones, checks out, and executes code modifications/tests on the primary target repository (e.g., `/tmp/daa/<incident_id>`).
3. **Read-Only API Queries:** Any auxiliary repositories registered as dependencies are accessed in a read-only manner. Instead of cloning them to disk, the agent dynamically queries specific files via the GitLab/GitHub Git Data REST APIs.

---

## 🛠️ Unified Installation & Quickstart

### 1. Run the Installer
Set up Python virtual environments, pip dependencies, and link the DAA CLI tool:
```bash
./install.sh
```

### 2. Run the Configuration Wizard
Initialize Git tokens, LLM providers (Gemini, OpenAI, or Claude), and select your deployment profile:
```bash
daa init
```

### 3. Deploy DAA Services
* **For Distributed Stateful Mode (Docker Compose):**
  ```bash
  docker compose up -d --build
  ```
* **For Stateless Serverless Mode:**
  ```bash
  docker build -t daa-stateless:latest .
  docker run -d --name daa-stateless -p 8080:8080 --env-file .env daa-stateless:latest
  ```

---

## 📂 Codebase Layout

```
/home/rutvej/Desktop/DAA/
├── daa                          # main python CLI helper
├── entrypoint.sh                # entrypoint shell script for single-container
├── install.sh                   # shell script installer
├── requirements.txt             # platform dependencies
├── app/
│   ├── backend-api/             # FastAPI REST backend & JIRA mock
│   │   ├── src/                 # REST endpoints & Database session local
│   │   └── tests/               # 17 pytest suites (SQLite based)
│   ├── python-agent/            # LangChain SRE Agent
│   │   ├── agent_src/           # Worker main, LLM models & ReAct tools
│   │   └── tests/               # 27 unittest suites (Mocks based)
│   ├── admin-panel/             # React dashboard frontend
│   └── daa-sdk/                 # Multi-language telemetry SDKs (Node, Go, Python...)
└── specs/                       # Platform specifications
```

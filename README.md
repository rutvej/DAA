# DAA — Deduplicated Autonomous SRE Platform

DAA is a pluggable, open-source **Autonomous SRE Platform** that automates
the first 30–60 minutes of manual triage toil when production microservices
break.

It ingests exception logs (via client SDKs or Sentry/Prometheus webhooks),
deduplicates them with SHA256 fingerprints, matches them against
sliding-window escalation policies, and dispatches a LangChain SRE Agent that
runs a 4-dimension diagnostic investigation (logs, metrics, commits, and
codebase navigation), applies fixes, runs verification tests, and opens a
Pull/Merge Request with a generated postmortem report.

Full environment-variable reference, the tested deployment matrix, and git
provider token permissions live in **[`DEPLOYMENT.md`](./DEPLOYMENT.md)** —
this README covers just enough to get running in under a minute.

---

## 🚀 Quick Start — Prebuilt Image

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
```

That's the fully stateless profile: zero databases, zero queues, scales to
zero on Cloud Run / Fargate. Point your Sentry/Prometheus webhooks at
`http://<host>:8000/ingest/...` and DAA starts triaging immediately.

For every other supported profile (with Postgres, with RabbitMQ, Compose vs.
single image, auth on/off) see the **[Deployment Matrix in `DEPLOYMENT.md`](./DEPLOYMENT.md#5-full-combination-matrix)**.

---

## 🧩 Pluggable Deployment Combinations

DAA is a **single-image pluggable architecture** — the same container image
runs everything from a stateless, zero-disk serverless container up to a
distributed multi-container cluster, controlled entirely by three env vars.

| Deployment Mode | `DAA_DB_PROVIDER` | `DAA_GIT_MODE` | `DAA_QUEUE_MODE` | Description |
| :--- | :--- | :--- | :--- | :--- |
| **1. Stateless Serverless** | `none` | `api` (Git REST calls) | `sync` (inline background) | Zero-disk, scales-to-zero. Reads/writes files directly via GitHub/GitLab/Gitea/Bitbucket REST APIs. Best for Cloud Run / Fargate. |
| **2. Self-Contained Edge** | `sqlite` | `api` or `local` | `sync` | Single VM. SQLite in WAL mode handles policy tracking and sessions. |
| **3. Distributed Scale-Out** | `postgres` | `local` (worktree clones) | `rabbitmq` (distributed) | Datacenter. Separate API, broker, database, and dedicated agent worker pool. |

This is a simplified view — the full tested matrix (6 combinations,
including which pair with Image vs. Compose staging) is in
[`DEPLOYMENT.md` §5](./DEPLOYMENT.md#5-full-combination-matrix).

---

## 🔑 Git Provider Access

DAA needs a token with permission to read files, create a branch, commit, and
open a PR. Minimum scopes:

| Provider | Required Scopes |
| :--- | :--- |
| **GitHub** | Classic PAT: `repo`. Fine-grained: `Contents: Read/Write`, `Pull requests: Read/Write` |
| **GitLab** | `api` (or `read_repository` + `write_repository`, though MR creation generally needs `api`) |
| **Gitea** | `write:repository`, `write:issue`, `read:user` |
| **Bitbucket** | App Password with `Repositories: Write`, `Pull requests: Write` |

Full detail, including Gitea's non-GitHub-compatible branch-creation endpoint,
is in [`DEPLOYMENT.md` §4](./DEPLOYMENT.md#4-git-provider-token-permissions).

---

## 🛠️ Unified Installation & Local Quickstart

### 1. Run the Installer
Sets up the Python virtualenv, installs dependencies, and links the `daa` CLI:
```bash
./install.sh
```

### 2. Run the Configuration Wizard
Configures Git tokens, LLM provider keys (Gemini/OpenAI/Claude/Ollama), and
your deployment profile:
```bash
daa init
```
This populates `.env` and `.env.daa`.

### 3. Deploy DAA Services
- **Distributed / Stateful (Docker Compose):**
  ```bash
  docker compose up -d --build
  ```
- **Stateless Serverless (single image, built locally):**
  ```bash
  docker build -t daa-stateless:latest .
  docker run -d --name daa-stateless -p 8080:8080 --env-file .env daa-stateless:latest
  ```
- **Prebuilt image from Docker Hub:** see [Quick Start](#-quick-start--prebuilt-image) above.

Full step-by-step for both staging modes is in
[`DEPLOYMENT.md` §6–7](./DEPLOYMENT.md#6-setup-steps--image-mode).

---

## 📂 Codebase Layout

```
/DAA/
├── daa                          # main python CLI helper
├── entrypoint.sh                # single-container entrypoint
├── install.sh                   # unified installer
├── requirements.txt             # platform dependencies
├── DEPLOYMENT.md                # full env var / matrix / token reference
├── app/
│   ├── backend-api/             # FastAPI REST backend & mock Jira
│   │   ├── src/                 # REST endpoints, DB session, mocks
│   │   └── tests/
│   ├── python-agent/            # LangChain SRE Agent
│   │   ├── agent_src/           # Worker main, LLM models, ReAct tools
│   │   └── tests/
│   ├── admin-panel/             # React dashboard frontend
│   └── daa-sdk/                 # Multi-language telemetry SDKs
└── specs/                       # Per-module architecture specs
```

---

## 📄 License

MIT. See `LICENSE`.
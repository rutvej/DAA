# DAA v3.0 — Debugging Autonomous Agent

[![Deploy to Google Cloud Run](https://deploy.cloud.run/button.svg)](https://deploy.cloud.run/?git_repo=https://github.com/rutvej/DAA.git)
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template?template=https://github.com/rutvej/DAA)

DAA (Debugging Autonomous Agent) is an open-source, self-hosted **Debugging Autonomous Agent** platform that replaces the first 30–60 minutes of manual triage toil when production microservices break. It detects anomalies, deduplicates incidents by error fingerprint, executes a 4-dimension diagnostic investigation, automatically opens pull requests with code fixes, and generates structured postmortem reports.

---

## 🚀 What's New in v3.0

DAA 3.0 introduces a **three-phase hybrid architecture** that dramatically reduces LLM token costs (~65% reduction) while giving the agent full investigative freedom:

```
Phase 1 (Orchestrator)       Phase 2 (Agent — free)       Phase 3 (Orchestrator)
────────────────────────       ──────────────────────       ─────────────────────
✓ Clone/pull repo (cached)    ✓ Read files freely           ✓ Apply unified diff
✓ Hydrate all 4 log dims      ✓ Correlate code+logs+metrics ✓ Branch/commit (idempotent)
✓ Fingerprint dedup           ✓ Trace commits                ✓ Create PR (idempotent)
✓ Package structured prompt   ✓ Decide: fix or escalate      ✓ Generate postmortem
```

### Key Improvements

| Feature | DAA 2.0 | DAA 3.0 |
|---|---|---|
| Repo clone | Per-incident (LLM tool call) | Once, git-cached + worktree |
| Git/branch/PR ops | LLM tool calls | Deterministic orchestrator |
| Token cost (avg) | ~10,000/incident | ~3,000–4,000/incident |
| Repeat incident cost | ~10,000 | **0** (fingerprint dedup) |
| Context explosion | Uncapped tool loops | Planning step + 8-call hard cap |
| Idempotent PR | Crashes on duplicate | Returns existing PR URL |

---

## ⚡ Key Features

* **Fingerprint Deduplication:** SHA256 error fingerprinting prevents redundant agent jobs. Same bug triggering 100× costs 1× LLM call.
* **Persistent Repo Cache:** Clone once, `git fetch` on reuse. Per-incident isolation via `git worktree`. Zero bandwidth waste on repeated incidents.
* **4-Dimension SRE Investigation Loop:**
  1. **Change (Dim-4):** Pre-fetched recent Git commits surfaced to agent before investigation starts.
  2. **Infra (Dim-3):** Pre-fetched Prometheus/CloudWatch metrics snapshot.
  3. **Traces (Dim-2):** Pre-fetched application logs from cloud providers (CloudWatch/GCP/Datadog/Loki).
  4. **Diagnostics:** Agent reads files, cross-references code + logs, traces bugs to commits.
* **Context Safety System (3 Layers):**
  1. **Planning Step:** Agent must declare a JSON investigation plan before calling any tools.
  2. **Hard Cap:** 8 tool call maximum. Warning injected at 5. Force-escalation at 8.
  3. **RAG Index:** *(DAA 3.1)* Vector search over repo replaces raw file reads for large codebases.
* **Idempotent Git/PR Flow:** Branch already exists? Reuse. PR already open? Return existing URL. No more crashes on re-runs.
* **Universal LLM Routing:** Google Gemini, OpenAI, Anthropic Claude, Ollama (local/air-gapped), LiteLLM, OpenAI-compatible proxies.
* **MCP Server + Client:** Expose DAA tools to other coding agents via JSON-RPC MCP protocol. Dynamically consume external MCP tools (BigQuery, Cloud Logging, etc.).
* **Human-in-the-Loop (HITL):** Review diagnoses and approve fixes before PR creation via React dashboard.
* **Multi-Language SDKs:** Go, Node.js, Python, Java, Ruby, .NET telemetry SDKs.

---

## 📁 Repository Layout

```
DAA/
├── app/
│   ├── python-agent/          # DAA 3.0 SRE Agent
│   │   └── src/
│   │       ├── main.py            # Three-phase process_job loop
│   │       ├── orchestrator.py    # 🆕 Phase 1 & 3: Repo cache, log hydration, PR automation
│   │       ├── agent_safety.py    # 🆕 Planning step + hard cap enforcement
│   │       ├── llm_config.py      # Multi-LLM routing (Gemini/OpenAI/Claude/Ollama/...)
│   │       └── tools/             # Read-only investigation tools
│   ├── backend-api/           # FastAPI backend (REST, dedup, escalation)
│   ├── admin-panel/           # React dashboard (HITL approval, live traces)
│   ├── daa-sdk/               # Multi-language telemetry SDKs
│   └── daa_mcp_server.py      # MCP Server (exposes DAA tools to other agents)
├── docker-compose.yml
├── README.md
└── SETUP.md
```

---

## 🔧 LLM Configuration

Set `LLM_PROVIDER` in your `.env`:

| Provider | `LLM_PROVIDER` | Required Env Vars |
|---|---|---|
| Google Gemini | `google` | `GEMINI_API_KEY` |
| OpenAI | `openai` | `OPENAI_API_KEY` |
| Anthropic Claude | `anthropic` | `ANTHROPIC_API_KEY` |
| Ollama (local) | `ollama` | `LLM_BASE_URL` (e.g. `http://localhost:11434/v1`) |
| LiteLLM proxy | `litellm` | `LLM_BASE_URL`, `LLM_API_KEY` |
| Agy CLI | `agy` | Agy CLI installed |
| Custom OpenAI-compatible | `custom` | `LLM_BASE_URL`, `LLM_API_KEY` |

Optionally set `LLM_MODEL` to override the default model name.

---

## 🧩 MCP Integration

### DAA as an MCP Server

DAA exposes its tools via JSON-RPC MCP so other agents (Cursor, Copilot, custom) can trigger incident analysis and approve fixes:

```json
// .mcp.json (in your project or agent config)
{
  "mcpServers": {
    "daa-sre": {
      "command": "python3",
      "args": ["path/to/DAA/app/daa_mcp_server.py"],
      "env": {
        "DAA_BACKEND_API_URL": "http://localhost:8000",
        "DAA_TOKEN": "your-token"
      }
    }
  }
}
```

Available MCP tools:
- `get_fixes_awaiting_approval` — List fixes pending human review
- `get_incident_postmortem` — Get postmortem for a fix ID
- `approve_remediation_fix` — Approve a fix and trigger PR creation
- `get_active_incidents` — List currently processing incidents
- `get_fix_by_fingerprint` — Check if a bug was previously fixed
- `list_registered_apps` — List apps registered in DAA
- `trigger_manual_incident` — Manually trigger analysis for an app

### DAA Consuming External MCP Tools

DAA can dynamically consume external MCP tools (e.g., BigQuery, Cloud Logging):

```json
// mcp_config.json (in agent container)
{
  "mcpServers": {
    "bigquery": {
      "command": "npx",
      "args": ["-y", "@google-cloud/mcp-bigquery"],
      "env": { "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/sa.json" }
    }
  }
}
```

---

## 🚀 Pluggable Deployment Modes (Serverless to Datacenter)

DAA can be deployed as a single, lightweight container or scaled out as a full-scale multi-service cluster. Toggle the modes via environment variables to match your infrastructure requirements:

*   **Stateless Serverless (Cloud Run / Fargate):** Zero databases, zero message queues. DAA parses incoming alerts via Sentry or Prometheus webhooks and manages code changes directly via Git REST APIs. Offloads auth to Cloud IAM.
*   **Self-Contained Edge (Single VM):** A single container deployment that spins up lightweight internal Postgres/Redis databases to handle policy deduplication and user logins.
*   **Datacenter Scale (Kubernetes / Compose):** Standard multi-container deployment splitting the FastAPI web server, background workers, Postgres DB, and RabbitMQ queue.

| Mode | `DAA_DB_PROVIDER` | `DAA_GIT_MODE` | `DAA_QUEUE_MODE` | Description |
|---|---|---|---|---|
| **Stateless** | `none` | `api` (REST API) | `sync` (Async task) | Zero local disk usage. Scales to zero. |
| **Self-Contained** | `internal-postgres` | `api` or `local` | `sync` (Threaded worker) | Boots PG DB inside the container automatically. |
| **Scale Out** | `external-postgres` | `local` (Workspace clone) | `rabbitmq` (Distributed) | Dedicated worker pool, local test execution. |

---

## ⚡ Quickstart

```bash
# 1. Run the unified 1-line installation script
./install.sh

# 2. Link the DAA CLI globally to your PATH (recommended)
sudo ln -sf $(pwd)/daa /usr/local/bin/daa

# 3. Initialize SRE platform configuration (API keys, Git settings, model selection)
daa init

# 4. Spin up local backend & agent services in Docker
daa redeploy

# 5. Register your first application and set up SRE policies
daa register --name my-service --repo-url http://host.docker.internal:3000/owner/my-service.git --language python
daa policy --app my-service --threshold 3 --window 60
```

For the full E2E demo walkthrough: **[daa-e2e-demo](https://github.com/rutvej/Desktop/daa-e2e-demo)**

---

## 🛡️ Context Safety & Token Optimization

DAA 3.0 enforces a **three-layer context safety system** to prevent hallucinations and runaway token costs:

1. **Planning Step** — Before calling any tool, the agent must produce a JSON investigation plan declaring its hypothesis and exactly which evidence it will look at. This binds the agent to a focused investigation path.

2. **Hard Cap (8 tool calls)** — Warning injected at call 5. Force-escalation at call 8. Prevents infinite diagnostic loops.

3. **RAG Index** *(DAA 3.1)* — ChromaDB vector index over each repo. Agent queries semantically instead of reading raw files, reducing per-tool-call context by ~80%.

**Estimated token costs:**
- Repeat incident (same fingerprint): **0 tokens**
- Typical Redis OOM / missing TTL bug: **~2,500 tokens**
- Complex multi-file bug: **~4,000 tokens**
- Escalated (agent couldn't fix): **~2,000 tokens**

---

## 📦 Supported Languages & SDKs

| Language | SDK Location |
|---|---|
| Go | `app/daa-sdk/go/` |
| Python | `app/daa-sdk/python/` |
| Node.js | `app/daa-sdk/nodejs/` |
| Java | `app/daa-sdk/java/` |
| Ruby | `app/daa-sdk/ruby/` |
| .NET | `app/daa-sdk/dotnet/` |

---

## 📄 License

MIT. See `LICENSE`.

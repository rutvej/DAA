# DAA v3.0 Setup & Configuration Guide

This guide details the end-to-end installation, local infrastructure setup, LLM provider onboarding, and test verification for the **DAA Autonomous SRE Platform**.

## 📦 0. Unified 1-Line Installer

To quickly setup your DAA SRE environment, install all dependencies, and run the configuration setup wizard:
```bash
curl -fsSL https://raw.githubusercontent.com/rutvej/DAA/main/install.sh | bash
```
This script will check your operating system's requirements, install Python dependencies, configure the `daa` CLI client, and prompt the wizard to initialize connection configs.

---

## 🛠️ 1. Local Testing Infrastructure

DAA is pre-configured with a complete offline testing suite, including a local code forge, local database, and mock integrations.

### Local Services & Ports
- **FastAPI Backend-API:** `http://localhost:8000` (Swagger UI at `/docs`)
- **React Admin Dashboard:** `http://localhost:5003`
- **Local Gitea Instance:** `http://localhost:3000` (for E2E demo walkthrough)
- **PostgreSQL Database:** `localhost:5433` (Docker internal: `5432`)
- **RabbitMQ Broker:** `localhost:5672` (Management panel: `http://localhost:15672`)
- **Mock Checkout Service:** `http://localhost:8001`
- **Mock Payment Service:** `http://localhost:8002`

### Mock Jira Endpoint
To avoid requiring a live Jira Cloud subscription for testing, the DAA backend serves a local mock Jira REST API:
- **Jira Issue Creator:** `POST http://localhost:8000/mock-jira/rest/api/3/issue`
- **Jira Browser URL:** `http://localhost:8000/mock-jira/browse/{issue_key}`

---

## 🌐 2. Onboarding LLM Providers

The agent routes its ReAct decision loops through the LangChain models defined in `app/python-agent/src/llm_config.py`. Configure your provider in the `.env` file:

```ini
LLM_PROVIDER=google  # Options: google, vertex, openai, anthropic, ollama, codex, agy
LLM_MODEL=gemini-1.5-flash
```

### 1. Google Gemini API (Recommended)
Fastest setup using a standard API Key.
```ini
LLM_PROVIDER=google
LLM_MODEL=gemini-1.5-flash  # or gemini-2.5-flash
GEMINI_API_KEY=AIzaSy...
```

### 2. Google Cloud Vertex AI
Enterprise setups using Google Cloud IAM credentials.
```ini
LLM_PROVIDER=vertex
LLM_MODEL=gemini-1.5-flash
# Make sure your container/host environment is authenticated via:
# gcloud auth application-default login
```

### 3. Anthropic Claude
```ini
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_API_KEY=sk-ant-...
```

### 4. OpenAI GPT
```ini
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...
```

### 5. Codex Login / API
Uses your authenticated Codex configuration mounted from host to container:
```ini
LLM_PROVIDER=codex
LLM_MODEL=gpt-5.4-mini
# Auth token is mounted into python-agent container from /home/rutvej/snap/codex/34/auth.json
```

### 6. Local Air-Gapped Ollama
Run model reasoning entirely locally and offline:
```ini
LLM_PROVIDER=ollama
LLM_MODEL=llama3
OLLAMA_BASE_URL=http://localhost:11434
```

### 7. Host Agent CLI Proxy (`agy`)
Uses the local user's active session CLI proxy to make calls. Excellent for avoiding hardcoded API keys:
```ini
LLM_PROVIDER=agy
LLM_MODEL="Gemini 3.5 Flash (Medium)"
```

---

## 🚀 3. Multi-Service Microservice Setup

The platform includes two mock microservices: `payment-api` and `payment-worker`. In our E2E environment, code repositories are hosted on Gitea and managed/configured via the DAA platform CLI.

### CLI Registration & Policy Configuration
Instead of manual API calls, SREs register applications and define escalation rules directly via the DAA CLI client:

1. **Register the Applications:**
   ```bash
   daa register --name payment-api --repo-url http://host.docker.internal:3000/daa-admin/payment-api.git --language python
   daa register --name payment-worker --repo-url http://host.docker.internal:3000/daa-admin/payment-worker.git --language go
   ```
   *This commands automatically registers the apps and creates the corresponding repository connections in the backend database.*

2. **Define SRE Escalation Policies:**
   ```bash
   daa policy --app payment-api --threshold 3 --window 60
   daa policy --app payment-worker --threshold 3 --window 60
   ```
   *This creates an SRE policy rule where an analysis job will automatically trigger if 3 exception events are logged within a 60-second window.*

3. **Deploy Microservices locally (Injecting Tokens):**
   ```bash
   # Run Payment API
   DAA_BACKEND_API_URL=http://localhost:8000 DAA_TOKEN="<payment_api_token>" uvicorn app:app --host 0.0.0.0 --port 8001
   
   # Run Payment Worker
   DAA_BACKEND_API_URL=http://localhost:8000 DAA_TOKEN="<payment_worker_token>" ./payment-worker
   ```

---

## 💥 4. Triggering Outage Scenarios

Simulate real microservice incident outages to witness the ReAct agent's 4-dimension diagnosis loop.

### Scenario A: Redis Cache Timeout (Infrastructure Cascade)
Simulates a Redis connection pool exhaustion on the checkout service:
```bash
curl -X POST 'http://localhost:8001/checkout' \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "fail_redis", "cart_total": 150.0}'
```

### Scenario B: Payment Gateway Failures (Client/External Dependency)
Simulates a transaction failure due to declined cards or gateway error:
```bash
curl -X POST 'http://localhost:8001/checkout' \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "user-123", "cart_total": 6000.0}'
```

---

## 🕵️ 5. What Happens Next: The 4-Dimension Loop

Once escalated, the SRE agent automatically:
1. **Queries database logs and distributed traces** (`query_correlated_logs`) matching the `trace_id`.
2. **Searches git logs** (`check_recent_changes`) over the last 24h to see if a recent commit caused the issue.
3. **Inspects active environment metrics** (`check_alerts`) to check if Redis or Postgres services are down.
4. **Performs surgical code diagnostics** (`read_repomap`, `find_symbol`, `view_file_slice`) to locate code flaws.
5. **Creates a fix branch, commits, pushes, opens a Gitea/GitLab/GitHub Pull/Merge Request,** and creates an offline **Postmortem report** summarizing the root cause!

---

## ☁️ 6. Pull-Based SRE Cloud Investigation Workflow

In addition to the SDK pushing logs directly to DAA, the platform supports a **pull-based SRE investigation workflow**. This is critical for legacy systems or microservices where the DAA telemetry SDK cannot be installed, or when you are notified of a generic `500 Internal Server Error` without direct telemetry indicators.

### How the Agent Investigates (Pull Flow)
1. **Trigger Alert:** A generic system alert or developer notification reports: *"Service XYZ is crashing with 500 errors"*.
2. **Cloud Log Retrieval:** The SRE agent connects to your cloud logging provider (configured during `daa init` - e.g., AWS CloudWatch, GCP Cloud Logging, or Datadog) using the credentials saved in the configuration to pull the raw logs and extract the stack trace.
3. **Architecture Mapping:** The SRE agent inspects the service dependency tree and architecture map (stored in the database under `projects` and `applications` tables) to identify upstream and downstream systems.
4. **Code Navigation & Code Nav Triage:** The agent clones the target repository, maps the classes and symbols, and locates the root cause.
5. **Code Resolution:** The agent applies the fix, runs validation tests, and opens a Merge/Pull Request.

---

## 🤝 7. Human-in-the-Loop (HITL) Validation Mode

By default, the SRE Agent automatically opens a Merge/Pull Request upon generating a successful fix. To enable human validation and approval safety guardrails:

1. **Enable HITL Mode:** Set the environment variable `DAA_HITL_MODE=true` in your `.env` configuration.
2. **Agent Workflow:** When a fix is found and validated, the SRE agent pushes the remediation branch but defers PR/MR creation. It sets the incident fix status to `Awaiting Approval` in the database.
3. **Admin Panel Review:** SREs can open the **React Admin Panel** at `http://localhost:5003/fixes/<id>` to review:
   - Complete step-by-step **AI Agent Execution Traces** showing exactly what the LLM thought, what tools it called, and what it observed.
   - The proposed code changes and target branch.
   - The full root-cause Postmortem Report.
4. **One-Click Approval:** Click **"Approve Fix & Create PR/MR"** to trigger the Gitea/GitLab/GitHub API and open the pull/merge request immediately.

---

## 🔌 8. Model Context Protocol (MCP) Server & Client

DAA v3.0 natively integrates with the **Model Context Protocol (MCP)** to support tool extensibility and cross-agent collaboration.

### A. Exposing DAA tools to other AI Agents (Server)
Other software engineering agents (like Cursor, Claude Desktop, or custom coding copilots) can connect to DAA using the stdio transport to review and approve incident fixes.

#### 1. Running natively on Host
You can run the server directly on your host machine:
```bash
python3 app/daa_mcp_server.py
```

#### 2. Running via Docker (Default Service)
By default, the MCP server is configured as a Docker Compose service (`mcp-server`) in `docker-compose.yml`. It runs automatically when you spin up the infrastructure:
```bash
docker-compose up -d
```
Other coding agents on your host can query the Docker-packaged MCP server using standard Docker execution wrappers. For example, in your host's **Claude Desktop** config (`claude_desktop_config.json`), you can add:
```json
{
  "mcpServers": {
    "daa-sre-mcp": {
      "command": "docker",
      "args": ["compose", "exec", "-T", "mcp-server", "python", "-u", "app/daa_mcp_server.py"]
    }
  }
}
```

**Exposed Tools:**
* `get_fixes_awaiting_approval`: Returns all incident fixes waiting for human validation.
* `get_incident_postmortem(fix_id)`: Fetches the postmortem text, status, and execution logs.
* `approve_remediation_fix(fix_id)`: Approves the fix and triggers the Gitea/GitLab/GitHub PR/MR creation.

---

### B. Allowing the DAA Agent to use external MCP Tools (Client)
Place an `mcp_config.json` file in the root directory. DAA will automatically launch any configured stdio-based MCP servers and append their tools to the agent's LangChain toolset.

#### 1. Integrating Local / Database MCP Servers
For example, to expose a Postgres database directly to the DAA SRE agent:
```json
{
  "mcpServers": {
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres", "postgresql://youruser:password@localhost:5433/yourdb"]
    }
  }
}
```

#### 2. Integrating Cloud MCP & BigQuery MCP Servers
You can easily plug enterprise cloud data warehouses and cloud APIs into the agent. For example, to integrate **BigQuery MCP** (`@modelcontextprotocol/server-bigquery`) or cloud logging, mount your credentials and set the command environment in `mcp_config.json`:
```json
{
  "mcpServers": {
    "bigquery": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-bigquery",
        "--project-id", "your-gcp-project-id"
      ],
      "env": {
        "GOOGLE_APPLICATION_CREDENTIALS": "/app/secrets/gcp-key.json"
      }
    }
  }
}
```
*Note: Ensure the credentials file is accessible inside the `python-agent` container by mounting it to `/app/secrets/` or equivalent shared volume in `docker-compose.yml`.*

---

### C. Automatic Preference: Choosing MCP over Direct REST APIs (Jira & Git)
If the DAA SRE Agent detects that custom MCP tools are loaded for interacting with code repositories or ticketing systems (such as GitHub/GitLab tools or Jira Cloud tools), it will **automatically choose the MCP tools** instead of its direct local API tools (`create_pull_request`, `create_incident_ticket`, `clone_repo`, `commit`, etc.).

This allows seamless, standardized integration of enterprise Git/Jira configurations without rewriting the agent's Python code, simply by declaring the appropriate MCP servers in `mcp_config.json`.


---

## DAA 3.0 Configuration

### Agent Mode

Set `DAA_AGENT_MODE` in your `.env`:

| Mode | Value | Description |
|---|---|---|
| Full 4-dimension (DAA 3.0) | `full` (default) | Orchestrator pre-flight + free agent + post-flight |
| Fast mode (legacy) | `fast` | Minimal tools, quick fix path |

### Repo Cache

DAA 3.0 caches cloned repositories at `/var/daa/repo-cache/` inside the agent container. Mount a volume to persist across container restarts:

```yaml
# docker-compose.yml addition:
volumes:
  - daa_repo_cache:/var/daa/repo-cache
```

### Multi-LLM Setup

```bash
# Google Gemini (default)
LLM_PROVIDER=google
LLM_MODEL=gemini-2.5-flash
GEMINI_API_KEY=your-key

# Anthropic Claude
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_API_KEY=your-key

# Local Ollama
LLM_PROVIDER=ollama
LLM_MODEL=llama3
LLM_BASE_URL=http://host.docker.internal:11434/v1

# LiteLLM proxy (multi-model gateway)
LLM_PROVIDER=litellm
LLM_BASE_URL=http://litellm:4000
LLM_API_KEY=your-proxy-key
```

### MCP Server Setup

The DAA MCP server is available as the `mcp-server` Docker service. To connect it to your coding agent:

1. Ensure the `mcp-server` container is running: `docker-compose up -d mcp-server`
2. Find its socket/stdio endpoint in `docker-compose.yml`
3. Add it to your agent's MCP config (`.mcp.json` for Cursor/Copilot/Antigravity)

To consume external MCP tools from within DAA, create `mcp_config.json` in the agent container:

```json
{
  "mcpServers": {
    "cloud-logging": {
      "command": "npx",
      "args": ["-y", "@google-cloud/mcp-logging"],
      "env": {
        "GOOGLE_APPLICATION_CREDENTIALS": "/app/sa.json"
      }
    }
  }
}
```

### Context Safety Tuning

```bash
# Maximum agent tool calls before force-escalation (default: 8)
DAA_MAX_TOOL_CALLS=8

# Tool call count at which warning is injected (default: 5)
DAA_TOOL_CALL_WARNING_AT=5

# Max LangChain iterations (default: 10)
DAA_MAX_ITERATIONS=10
```

---

## 🌐 4. Serverless & Pluggable Configurations

DAA supports running in a lightweight, single-container, stateless serverless mode without requiring Postgres or RabbitMQ databases. Toggle these behaviors via environment variables.

### 4.1 Master Configurations

| Environment Variable | Allowed Values | Default | Description |
|---|---|---|---|
| `DAA_POLICY_ENABLED` | `true`, `false` | `false` | Enable/disable error thresholds, deduplication, and cooldowns. |
| `DAA_AUTH_ENABLED` | `true`, `false` | `false` | Enable/disable user login authentication (JWT web portal). |
| `DAA_DB_PROVIDER` | `none`, `sqlite`, `internal-postgres`, `external-postgres`, `internal-redis`, `external-redis` | `sqlite` | Select state database engine. |
| `DAA_GIT_MODE` | `api`, `local` | `local` | `api` uses GitHub/GitLab REST APIs (no local cloning). `local` clones repository workspace. |
| `DAA_QUEUE_MODE` | `sync`, `rabbitmq` | `sync` | `sync` processes jobs inline/background tasks. `rabbitmq` uses external queue broker. |

> [!NOTE]
> If `DAA_POLICY_ENABLED=false` and `DAA_AUTH_ENABLED=false`, you can run DAA in completely **stateless mode (`DAA_DB_PROVIDER=none`)** with zero databases. This is the recommended configuration for Google Cloud Run and AWS Fargate deployments.

---

### 4.2 Webhook Alert Ingestion (SDK-Free Mode)

Instead of instrumenting your code with the DAA telemetry SDK, you can route Sentry or Prometheus Alertmanager webhooks directly to the DAA endpoint.

#### 1. Sentry Webhook Setup
1. In Sentry, go to **Settings** → **Integrations** → **Internal Integration** → **Webhooks**.
2. Set the Webhook URL to `https://your-daa-service.run.app/ingest/sentry`.
3. Select the `issue.created` event trigger.

#### 2. Prometheus Alertmanager Webhook Setup
Add the DAA endpoint to your `alertmanager.yml` configurations:
```yaml
receivers:
  - name: 'daa-webhook'
    webhook_configs:
      - url: 'https://your-daa-service.run.app/ingest/prometheus'
        send_resolved: false
```

#### 3. Securing Webhooks
Set the `DAA_API_KEY` environment variable in the DAA container. Your webhook requests must pass this key in the `X-DAA-API-Key` or `Authorization` header to authenticate.

---

### 4.3 Serverless Cloud Run Deployment

Deploy DAA to Google Cloud Run in under 60 seconds with zero-database configurations:

```bash
gcloud run deploy daa-minimal \
  --image rutvej/daa:latest \
  --port 8080 \
  --allow-unauthenticated \
  --set-env-vars="\
    LLM_PROVIDER=google,\
    GEMINI_API_KEY=your-gemini-key,\
    GITHUB_TOKEN=your-github-token,\
    DAA_POLICY_ENABLED=false,\
    DAA_AUTH_ENABLED=false,\
    DAA_DB_PROVIDER=none,\
    DAA_GIT_MODE=api,\
    DAA_QUEUE_MODE=sync"
```
Once deployed, point your alerting systems (Sentry/Prometheus) to the generated Cloud Run service URL.


# DAA v2.0 Setup & Configuration Guide

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
- **Local GitLab Instance:** `http://localhost:8082` (SSH: `2224`)
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

The platform includes two mock microservices: `checkout-service` and `payment-service`. The automated registration pushes them to your local GitLab instance and registers them with DAA.

### Automated Setup
1. **Initialize the local GitLab repository:**
   Run the automated setup script to push the code repositories to GitLab, set up project connections, and define SRE escalation policies:
   ```bash
   python3 setup_microservices.py
   ```
2. **Start the microservices locally:**
   Running the microservices locally on the host ensures instant startups and direct code file diagnostic modifications:
   ```bash
   # Run Payment Service
   DAA_LOGS_URL=http://localhost:8000/logs/ DAA_TOKEN="<your_daa_token>" .venv/bin/uvicorn app:app --host 0.0.0.0 --port 8002
   
   # Run Checkout Service
   DAA_LOGS_URL=http://localhost:8000/logs/ PAYMENT_SERVICE_URL=http://localhost:8002/pay REDIS_HOST=localhost REDIS_PORT=6379 DAA_TOKEN="<your_daa_token>" .venv/bin/uvicorn app:app --host 0.0.0.0 --port 8001
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
5. **Creates a fix branch, commits, pushes, opens a GitLab Merge Request,** and creates an offline **Postmortem report** summarizing the root cause!

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
4. **One-Click Approval:** Click **"Approve Fix & Create PR/MR"** to trigger the GitLab/GitHub API and open the merge request immediately.

---

## 🔌 8. Model Context Protocol (MCP) Server & Client

DAA v2.0 natively integrates with the **Model Context Protocol (MCP)** to support tool extensibility and cross-agent collaboration:

### A. Allowing the DAA Agent to use external MCP Tools (Client)
Place an `mcp_config.json` file in the root directory. DAA will automatically launch any configured stdio-based MCP servers and append their tools to the agent's LangChain toolset:
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

### B. Exposing DAA tools to other AI Agents (Server)
Other software engineering agents (like Cursor, Claude Desktop, or custom coding copilots) can connect to DAA using the stdio transport to review and approve incident fixes:
```bash
python3 app/daa_mcp_server.py
```
**Exposed Tools:**
* `get_fixes_awaiting_approval`: Returns all incident fixes waiting for human validation.
* `get_incident_postmortem(fix_id)`: Fetches the postmortem text, status, and execution logs.
* `approve_remediation_fix(fix_id)`: Approves the fix and triggers the GitLab/GitHub PR/MR creation.


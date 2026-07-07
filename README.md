# DAA v2.0 — Autonomous SRE Incident Diagnosis Platform

[![Deploy to Google Cloud Run](https://deploy.cloud.run/button.svg)](https://deploy.cloud.run/?git_repo=https://github.com/rutvej/DAA.git)
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template?template=https://github.com/rutvej/DAA)
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://deploy.cloud.run/?git_repo=https://github.com/rutvej/DAA.git)

DAA is an open-source, self-hosted **Autonomous SRE Incident Diagnosis Platform** that replaces the first 30–60 minutes of manual triage toil when production microservices break. It detects anomalies, aggregates similar events into deduplicated incidents, executes a 4-dimension diagnostic run, and automatically opens draft pull requests or Jira tickets.

---

## 🚀 Key Features in V2.0

* **Zero Alert Fatigue:** sliding-window escalation thresholds (e.g. only wake up the agent if an error fires 3 times in 60s) and SHA256 error fingerprinting prevent redundant agent jobs and duplicate tickets.
* **4-Dimension SRE Investigation Loop:**
  1. **Change:** Queries recent Git commit logs over the last 24h to see if a deployment caused the failure.
  2. **Infra:** Checks Prometheus/Alertmanager webhooks and database status alerts.
  3. **Traces:** Correlates OpenTelemetry trace IDs across other microservices to find upstream/downstream failures.
  4. **Diagnostics:** Surgically navigates and fixes the codebase.
* **Surgical Code Navigation (No Context Flooding):** AST repository mapping (`read_repomap`) compresses a 50,000-line codebase into a ~1,500-token skeleton. Combined with symbol searches (`find_symbol`) and strict file slicing limiters (100-line maximum), it keeps token costs low and avoids LLM hallucinations.
* **Universal LLM Routing (`llm_config.py`):** Plugs natively into Google Gemini, OpenAI, Anthropic Claude, OpenClaw, LiteLLM, or local air-gapped models via Ollama.
* **Ticketing & Git Integration:** Real-time Jira Cloud, GitHub Issues, and GitLab Merge Request creators.
* **Circuit Breaker Guardrails:** If sandbox verification tests fail twice, or if it detects a complex stateful deadlock, the agent halts code modification, opens a Jira/GitHub ticket, and generates a structured SRE Postmortem report.
* **Human-in-the-Loop (HITL) Validation:** Set `DAA_HITL_MODE=true` to review SRE diagnoses and AI execution traces on the React Dashboard and approve fixes before PR/MR creation.
* **Model Context Protocol (MCP) Support:** Expose platform tools to other coding agents via a Docker-packaged MCP Server (`mcp-server` service), or configure DAA to dynamically consume external cloud/database MCP tools (such as BigQuery or Cloud Logging MCP) and prefer them over direct REST APIs (Jira & Git) automatically.

---

## 📁 Repository Layout

* `app/backend-api`: FastAPI backend providing REST endpoints, sliding-window log escalation, and SHA256 error deduplication.
* `app/python-agent`: ReAct SRE agent powered by LangChain that executes 4-dimension investigations and code remediation.
* `app/admin-panel`: React admin dashboard providing live SRE telemetry, incident status trackers, and app configuration management.
* `app/daa-sdk`: Multi-language SRE telemetry SDKs (Go, Node.js, Python, Java, Ruby, .NET).
* `docs/DEMO_SPEC.md`: Complete End-to-End Walkthrough design and security specifications.

---

## ⚡ Quickstart & E2E Walkthrough

To run the complete automated SRE diagnosis loop, use our independent walkthrough demo repository:

👉 **[daa_e2e_demo Git Repository](https://github.com/rutvej/daa_e2e_demo.git)**

### Run E2E Walkthrough:
1. Navigate to the demo repository directory:
   ```bash
   cd /home/rutvej/Desktop/daa-e2e-demo
   ```
2. Clean up any previous runs and databases:
   ```bash
   docker-compose down -v
   docker exec daa-postgres-1 bash -c "psql -U \$POSTGRES_USER \$POSTGRES_DB -c 'TRUNCATE users, applications, logs, alerts, incidents, fixes, project_connections, escalation_policies RESTART IDENTITY CASCADE;'"
   ```
3. Execute the walkthrough orchestrator script:
   ```bash
   python3 run_demo.py
   ```
   This will spin up a local GitLab, register apps and escalation policies, trigger the checkout `AttributeError` outage, run the ReAct agent, apply the code hotfix, run verification tests, and open the Merge Request!

For a full breakdown of the security design, JWT token model, and architecture specs, refer to:
👉 **[docs/DEMO_SPEC.md](docs/DEMO_SPEC.md)**

---

## 🛠️ Testing the Code

### Backend API (FastAPI)
```bash
DATABASE_URL=sqlite:///./test.db RABBITMQ_HOST=localhost PYTHONPATH=app/backend-api .venv/bin/pytest app/backend-api/tests/
```

### Python Agent
```bash
PYTHONPATH=app/python-agent/src .venv/bin/pytest app/python-agent/tests/
```

---

## 📄 License
MIT. See `LICENSE`.

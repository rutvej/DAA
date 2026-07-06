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

---

## 📁 Repository Layout

* `app/backend-api`: FastAPI backend providing REST endpoints, sliding-window log escalation, and SHA256 error deduplication.
* `app/python-agent`: ReAct SRE agent powered by LangChain that executes 4-dimension investigations and code remediation.
* `app/admin-panel`: React admin dashboard providing live SRE telemetry, incident status trackers, and app configuration management.
* `app/daa-sdk`: Multi-language SRE telemetry SDKs (Go, Node.js, Python, Java, Ruby, .NET).
* `examples/`: Mock checkout and payment services to run local simulations.
* `scripts/simulate_outage.py`: Standalone demo simulation script.

---

## ⚡ Quickstart & Setup Guide

For detailed guides on setting up local testing infrastructure, configuring LLM providers (Gemini, Vertex, Claude, OpenAI, Ollama, Codex, agy), and running automated multi-service tests, please refer to:

👉 **[SETUP.md](SETUP.md)**

### Brief Quickstart

1. **Start Local Infrastructure:**
   ```bash
   docker-compose up -d
   ```
2. **Initialize Local Microservices:**
   ```bash
   python3 setup_microservices.py
   ```
3. **Run Microservices Locally:**
   Refer to [SETUP.md](SETUP.md#3-multi-service-microservice-setup) to start the `checkout-service` and `payment-service` instances locally.
4. **Trigger Outages:**
   Refer to [SETUP.md](SETUP.md#4-triggering-outage-scenarios) to execute Curl triggers.

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

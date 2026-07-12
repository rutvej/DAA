# DAA Platform Setup Guide

This guide details the steps to install, configure, deploy, and verify the DAA platform in both Stateless Serverless and Stateful Full-Stack environments.

---

## 📦 1. Installation

To install all platform dependencies, create the Python virtual environment, and link the DAA CLI globally:
```bash
./install.sh
```

To configure Git tokens, LLM API keys (Gemini, Claude, GPT, or Ollama), and select the target deployment profile:
```bash
daa init
```
This script populates `.env` and `.env.daa` configuration files in the root directory.

---

## 🚀 2. Deploying Different Combinations

DAA's architecture uses environment variables to trigger different operational flows:

### A. Stateless Serverless Mode (Cloud Run / AWS Fargate)
* **Configuration:**
  ```env
  DAA_DB_PROVIDER=none
  DAA_GIT_MODE=api
  DAA_QUEUE_MODE=sync
  DAA_AUTH_ENABLED=false
  DAA_POLICY_ENABLED=false
  ```
* **How it works:** 
  1. Exception log is posted to `/logs/` or webhook `/ingest/`.
  2. Because `DAA_QUEUE_MODE=sync` is active, the Backend API directly imports the agent logic from `agent_src.main` (no RabbitMQ needed).
  3. It enqueues the job inline as a FastAPI `BackgroundTask`.
  4. The SRE Agent runs in-process. It uses `CloneFreeGitClient` to fetch/modify files directly via Git REST APIs (no local disk clones).
  5. PR/MR is created via Git provider API. Database sessions are stubbed using `MockSession`.

### B. Stateful Edge Mode (Single VM SQLite)
* **Configuration:**
  ```env
  DAA_DB_PROVIDER=sqlite
  DAA_GIT_MODE=local
  DAA_QUEUE_MODE=sync
  DAA_AUTH_ENABLED=true
  DAA_POLICY_ENABLED=true
  ```
* **How it works:**
  1. Uses local SQLite WAL database `daa.db` in the container to track JWT logins and sliding-window error policies.
  2. Enqueues jobs inline in background tasks.
  3. Clones the target repository locally on-disk and creates isolated worktrees under `/tmp/daa/` to modify code and run local verification tests.

### C. Scale-Out Stateful Mode (Postgres + RabbitMQ)
* **Configuration:**
  ```env
  DAA_DB_PROVIDER=postgres
  DATABASE_URL=postgresql://daa:daa_pass@localhost:5432/daa_db
  DAA_GIT_MODE=local
  DAA_QUEUE_MODE=rabbitmq
  RABBITMQ_HOST=rabbitmq
  ```
* **How it works:**
  1. The Backend API container registers user logs, runs policy checks on Postgres, and publishes a job to RabbitMQ.
  2. The standalone worker container (`python -m agent_src.main`) consumes the job from RabbitMQ.
  3. The worker clones the codebase, creates worktrees, triages the bug, runs tests, and pushes fix branches to create Pull Requests.

---

## 🧪 3. E2E Verification & Outage Triggers

To test that DAA is functioning correctly in your environment, you can trigger mock microservice outages using these commands:

### Trigger Redis Timeout Outage
```bash
curl -X POST 'http://localhost:8001/checkout' \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "fail_redis", "cart_total": 150.0}'
```

### Trigger Payment Gateway Outage
```bash
curl -X POST 'http://localhost:8001/checkout' \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "user-123", "cart_total": 6000.0}'
```

Monitor the SRE diagnostic logs and postmortems in the React Admin panel at `http://localhost:5003`.

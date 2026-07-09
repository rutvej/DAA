# DAA — Deduplicated Autonomous SRE Platform

DAA is an open-source, pluggable **Autonomous SRE Platform** that replaces the first 30–60 minutes of manual triage toil when production microservices break. It ingests alerts (via Sentry, Prometheus Alertmanager, or custom webhooks), deduplicates incident runs, performs a 4-dimension diagnostic investigation (code, commits, logs, metrics), applies code remedies, and opens pull/merge requests with generated postmortems.

---

## 🚀 Pluggable Deployment Combinations

DAA is built as a **single-image pluggable architecture**. It can run from a single lightweight serverless container (DB-free, clone-free) up to a dedicated multi-container datacenter environment.

You can mix and match configuration modes depending on your infrastructure requirements:

| Deployment Mode | `DAA_DB_PROVIDER` | `DAA_GIT_MODE` | `DAA_QUEUE_MODE` | Description |
| :--- | :--- | :--- | :--- | :--- |
| **1. Stateless Serverless** | `none` | `api` (Git REST calls) | `sync` (Inline background) | **Zero-disk, scales-to-zero.** Resolves files and commits via GitHub/GitLab REST APIs. Offloads authentication. Best for Google Cloud Run / AWS Fargate. |
| **2. Self-Contained Edge** | `internal-postgres` | `local` (Workspace clone) | `sync` (Threaded worker) | **Single VM.** Automatically boots internal Postgres & Redis databases inside the single container for policy tracking and JWT login support. |
| **3. Distributed Scale-Out** | `external-postgres` | `local` (Workspace clone) | `rabbitmq` (Distributed) | **Datacenter.** Splits web service, RabbitMQ broker, external Postgres database, and dedicated SRE agent worker pools. |

---

## 🛠️ Unified Installation & Setup

### 1. Run the Unified Installer
Install python virtualenv, dependencies, and configure CLI rights locally:
```bash
./install.sh
```

### 2. Run the Guided Setup Wizard
Initialize LLM provider choices (Gemini, Claude, GPT, or Ollama), Git tokens, and cloud logging connectors:
```bash
./daa init
```

### 3. Deploy/Redeploy DAA Services
```bash
./daa redeploy
```

---

## 🐳 Universal Docker Registry Upload

To distribute DAA universally on your servers, Kubernetes, or cloud containers, build and push the single unified Docker image:

```bash
# 1. Build and tag the single unified Docker image
docker build -t your-docker-registry-username/daa:latest .

# 2. Login to your container registry (Docker Hub, GitHub Packages, or GCP Artifact Registry)
docker login

# 3. Push the image
docker push your-docker-registry-username/daa:latest
```

---

## ☁️ One-Line Serverless Cloud Deployments

You can deploy the single DAA image directly to serverless cloud environments in stateless mode:

### Google Cloud Run (One-liner)
```bash
gcloud run deploy daa-service --image your-docker-registry-username/daa:latest --port 8080 --allow-unauthenticated --set-env-vars="LLM_PROVIDER=google,GEMINI_API_KEY=your-gemini-key,GITHUB_TOKEN=your-github-token,DAA_POLICY_ENABLED=false,DAA_AUTH_ENABLED=false,DAA_DB_PROVIDER=none,DAA_GIT_MODE=api,DAA_QUEUE_MODE=sync"
```

### AWS Fargate (using AWS Copilot)
```bash
copilot init --name daa --type "Request-Driven Web Service" --image your-docker-registry-username/daa:latest --port 8080
```

---

## 🧪 Triggering Outage Scenarios

Simulate microservice outages in the sandbox environment to test DAA's 4-dimension diagnostic loops:

### Scenario A: Redis Cache Timeout (Infrastructure Cascade)
Simulates connection pool exhaustion on the checkout service:
```bash
curl -X POST 'http://localhost:8001/checkout' \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "fail_redis", "cart_total": 150.0}'
```

### Scenario B: Payment Gateway Failures (Client/External Decline)
Simulates a transaction failure due to declined cards or gateway error:
```bash
curl -X POST 'http://localhost:8001/checkout' \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "user-123", "cart_total": 6000.0}'
```

---

## 🛡️ Context Safety & Token Optimization
*   **Planning Step:** Agent writes a JSON investigation plan before calling tools.
*   **Hard Cap:** Forced escalation after 8 tool calls (warning at 5) to prevent runaways.
*   **Token efficiency:** Under 4,000 tokens per incident (65% reduction from v2.0). Duplicate runs consume **0 tokens** via fingerprint deduplication.

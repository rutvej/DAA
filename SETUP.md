# DAA Setup & Deployment Guide

This guide details the installation, deployment combinations, registry upload, and cloud deployment methods for the **DAA Autonomous SRE Platform**.

---

## 📦 1. Installation

To setup your SRE workspace, install virtualenv dependencies, and grant CLI rights:
```bash
./install.sh
```

To initialize LLM API keys (Gemini, Claude, GPT, or Ollama), Git repository access tokens, and cloud logging integration:
```bash
./daa init
```

---

## 🚀 2. Pluggable Deployment Combinations

DAA's architecture is fully pluggable and runs off a single unified Docker image. Configure DAA using these variables to customize database, Git, and worker execution paths:

### Environment Settings Matrix

| Mode | `DAA_DB_PROVIDER` | `DAA_GIT_MODE` | `DAA_QUEUE_MODE` | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Stateless (Serverless)** | `none` | `api` | `sync` | No local database, Git clone, or queues. Operates via Webhooks and Git REST APIs. |
| **Self-Contained Edge** | `internal-postgres` | `api` or `local` | `sync` | Spins up PostgreSQL and Redis internally inside the container. |
| **Scale-Out Distributed** | `external-postgres` | `local` | `rabbitmq` | Standard multi-container datacenter scale with RabbitMQ broker and worker pools. |

---

## 🐳 3. Docker Registry Upload Guide

To prepare DAA for cloud deployment or Kubernetes cluster rollouts, build and push the single unified Docker image to a registry (Docker Hub, GitHub Packages, or GCP Artifact Registry):

```bash
# 1. Build and tag the single unified Docker image
docker build -t your-docker-registry-username/daa:latest .

# 2. Login to your container registry
docker login

# 3. Push the image
docker push your-docker-registry-username/daa:latest
```

---

## ☁️ 4. One-Line Cloud Deployments (Stateless Serverless)

DAA can be deployed to serverless container runtimes with zero-database dependencies:

### Google Cloud Run (One-liner)
```bash
gcloud run deploy daa-service --image your-docker-registry-username/daa:latest --port 8080 --allow-unauthenticated --set-env-vars="LLM_PROVIDER=google,GEMINI_API_KEY=your-gemini-key,GITHUB_TOKEN=your-github-token,DAA_POLICY_ENABLED=false,DAA_AUTH_ENABLED=false,DAA_DB_PROVIDER=none,DAA_GIT_MODE=api,DAA_QUEUE_MODE=sync"
```

### AWS Fargate (using AWS Copilot)
```bash
copilot init --name daa --type "Request-Driven Web Service" --image your-docker-registry-username/daa:latest --port 8080
```

---

## 💥 5. Triggering Outage Scenarios

To verify your DAA installation, trigger sandbox microservice outage incidents using the curls below:

### Scenario A: Redis Cache Timeout (Infrastructure Cascade)
Simulates a Redis connection pool exhaustion on the checkout service:
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

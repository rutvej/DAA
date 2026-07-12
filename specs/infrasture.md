# DAA Global Infrastructure & Deployment Specification

This document details the environment configurations, container specifications, network layouts, and unified deployment instructions for the DAA platform.

## 1. System Components & Port Mapping

| Service | Container Image / Dockerfile | Exposed Ports | Internal Port | Key Volumes |
| :--- | :--- | :--- | :--- | :--- |
| **PostgreSQL** | `postgres:13` | `5433:5432` | `5432` | `postgres_data` -> `/var/lib/postgresql/data` |
| **RabbitMQ** | `rabbitmq:3-management` | `5672:5672`, `15672:15672` | `5672`, `15672` | None |
| **Backend API**| `./app/backend-api/Dockerfile` | `8000:80` | `80` | `secrets` -> `/var/run/secrets` |
| **Python Agent**| `./app/python-agent/Dockerfile` | None (worker) | N/A | mounts `/var/run/docker.sock`, `.git` directory, `/root/.gemini` |
| **Admin Panel** | `./app/admin-panel/Dockerfile` | `5003:5002` | `5002` | None |
| **MCP Server**  | `python:3.11-slim` running `app/daa_mcp_server.py` | None (stdio) | N/A | mounts workspace directory |

---

## 2. Infrastructure Combinations

### A. Full-Stack / Stateful Mode (Docker Compose / Kubernetes)
- **Database**: PostgreSQL container running on port `5433` (externally) with volume mount persistence.
- **Queue**: RabbitMQ broker for asynchronous message delivery.
- **Worker**: Standalone agent worker container processing jobs via durable queue hooks.
- **Git Actions**: Read/write clones performed locally on worker block storage under `/var/daa/repo-cache`.
- **Pre-requisites**: Docker, Docker Compose, Python 3.10+ (for CLI local wrappers).

### B. Serverless / Stateless Mode (GCP Cloud Run / AWS Fargate)
- **Database**: Bypassed or mapped to an external Cloud SQL instance. If bypassed (`DAA_DB_PROVIDER=none`), SQLAlchemy is replaced by a local mock session `MockSession`.
- **Queue**: Bypassed. Jobs run inline via FastAPI `BackgroundTasks`.
- **Worker**: Redundant. The agent runs inside the Backend API container.
- **Git Actions**: Bypassed. Uses GitLab/GitHub APIs via HTTPS REST client, resolving code without cloning on-disk.

---

## 3. Terraform Cloud Run Configuration Misfits

The current Terraform script in `terraform/main.tf` defines `google_cloud_run_service.python_agent` as a serverless container that runs the blocking queue consumer script (`main.py` which executes `channel.start_consuming()`).
- **Misfit Details**: Since Cloud Run scales to zero and throttles containers with no active HTTP requests, the background queue consumer will fail to consume RabbitMQ messages or will receive no CPU, hanging the execution of any tasks.
- **Resolution**: In serverless environments, the queue consumer configuration must be disabled, and the agent must be triggered via HTTP webhook calls or run inline inside the Backend API process using `BackgroundTasks`.

---

## 4. Unified Installation & Startup Instructions

### Step 1: Install Dependencies
Run the unified installer script which sets up Python virtual environments, pip dependencies, executable permissions, and globally links the DAA CLI:
```bash
./install.sh
```

### Step 2: Guided System Initialization
Run the setup wizard to configure Git providers, LLM API keys (Gemini, OpenAI, or Claude), and select deployment profiles:
```bash
daa init
```
This wizard automatically populates `.env` and `.env.daa` config files.

### Step 3: Run the Services
- **For Full-Stack (Stateful) Mode**:
  ```bash
  docker compose up -d --build
  ```
- **For Serverless (Stateless) Mode (run locally for test)**:
  Build and start the single unified container containing the Backend API and inline worker:
  ```bash
  docker build -t daa-stateless:latest .
  docker run -d --name daa-stateless -p 8000:8080 --env-file .env daa-stateless:latest
  ```

### Step 4: Verification and Test Outage Ingestion
Ensure all containers are running and send a test outage alert to confirm pipeline execution:
```bash
daa status
daa test
```
The admin panel is accessible at `http://localhost:5003`.

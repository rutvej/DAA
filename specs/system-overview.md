# DAA Global System Overview

This document provides a comprehensive overview of the DAA (Autonomous SRE Platform) architecture, key modules, components, and execution modes.

## 1. System Architecture

DAA is a distributed autonomous SRE platform designed to ingest error logs/telemetry from microservices, match them against escalation policies, run an LLM-based ReAct agent to diagnose the root cause, apply code changes to resolve the issue, and create a Pull Request/Incident Ticket.

The platform consists of four primary components:
1. **CLI Engine (`daa` script)**: A command-line utility used to initialize, configure, and inspect the DAA services.
2. **Backend API (`app/backend-api`)**: A FastAPI-based REST service that exposes endpoints for log ingestion, application registration, incident querying, metrics snapshot, and authentication.
3. **Python Agent (`app/python-agent`)**: An autonomous agent engine using LangChain that runs ReAct loops, executes system/git tools, queries external APIs, and determines code resolutions.
4. **Admin Panel (`app/admin-panel`)**: A React-based web interface for SRE teams to visualize incidents, approve fixes, monitor system health, and manage applications/policies.
5. **DAA SDK (`app/daa-sdk`)**: Multi-language SDKs (Python, Node, Go, Java, Ruby, .NET) injected into user applications to capture exceptions and stream them to the Backend API.

```mermaid
graph TD
    ClientApp[Client Application with DAA SDK] -->|POST /logs/| Backend[Backend API (FastAPI)]
    Webhook[Sentry / Prometheus Webhooks] -->|POST /ingest/| Backend
    Backend -->|Push Job| Queue[RabbitMQ / Sync Queue]
    Queue -->|Consume Job| Agent[Python Agent (LangChain)]
    Agent -->|Code Fix / PR| GitRepo[Git Remote (GitHub/GitLab/Gitea)]
    Agent -->|Jira Ticket| Jira[Jira Mock Service]
    Admin[Admin Panel (React)] -->|Query / Control| Backend
    CLI[DAA CLI] -->|Register / Health| Backend
```

---

## 2. Deployment Combinations (Stateless vs. Full-Stack)

DAA supports two primary architectural modes configurable via environmental variables or the `daa init` wizard:

### A. Stateless / Serverless Mode
* **Target Platforms**: Google Cloud Run, AWS Fargate.
* **Database (`DAA_DB_PROVIDER=none`)**: No persistent database. Authentication and escalation policies are bypassed. Database sessions are mocked using `MockSession` and `MockQuery` which return empty states or perform no-ops.
* **Git Mode (`DAA_GIT_MODE=api`)**: Code interactions use the `CloneFreeGitClient`. The agent does not clone the repository onto disk; it fetches file contents and pushes changes back via GitLab/GitHub REST API endpoints.
* **Background Queue (`DAA_QUEUE_MODE=sync`)**: Jobs are dispatched inline in the same FastAPI container process using FastAPI `BackgroundTasks`. RabbitMQ is bypassed.
* **Namespace Collision Hack**: Since the python-agent is loaded in the backend FastAPI process in `sync` mode, and both modules have a root folder named `src`, DAA uses dynamic `sys.modules` popping (in `/ingest`) and dynamic runtime folder duplication `/app/app/agent_src` (in `/logs`) to avoid namespace conflicts.

### B. Full-Stack / Stateful Mode
* **Target Platforms**: Multi-container Docker Compose, Virtual Machines, Kubernetes.
* **Database (`DAA_DB_PROVIDER=sqlite` or `postgres`)**: Persistent database with fully enabled User Authentication and Escalation Policies.
* **Git Mode (`DAA_GIT_MODE=local`)**: Uses the `RepoCacheManager` to clone bare git repositories to `/var/daa/repo-cache` and create isolated git worktrees at `/tmp/daa/<incident_id>` for the agent's workspace.
* **Background Queue (`DAA_QUEUE_MODE=rabbitmq`)**: Jobs are published to a durable RabbitMQ queue (`fix_jobs`), which are consumed asynchronously by the standalone python-agent container.

---

## 3. Codebase File Structure

```
/home/rutvej/Desktop/DAA/
├── daa                          # Main Python CLI entrypoint
├── requirements.txt             # Global python dependencies
├── docker-compose.yml           # Full-stack orchestrator setup
├── entrypoint.sh                # Container entry point script
├── install.sh                   # Platform installation script
├── app/
│   ├── backend-api/             # FastAPI Backend
│   │   ├── src/
│   │   │   ├── main.py          # FastAPI application & JIRA mock
│   │   │   ├── database.py      # SQLAlchemy models & Mock DB Session
│   │   │   └── routers/         # REST API Routers
│   ├── python-agent/            # LangChain Autonomous SRE Agent
│   │   ├── src/
│   │   │   ├── main.py          # Queue consumer & LangChain initialization
│   │   │   ├── orchestrator.py  # Pre-flight / Post-flight pipeline
│   │   │   ├── agent_safety.py  # Safety layers (Planning & Hard cap)
│   │   │   ├── llm_config.py    # LLM wrappers & Codex/Agy chat models
│   │   │   └── tools/           # Custom ReAct tools
│   ├── admin-panel/             # React dashboard UI
│   └── daa-sdk/                 # Multi-language telemetry SDKs
```

---

## 4. Current Implementation Deviations & Limitations

- **Codex Hardcoded Prompts & Hacks**: The `CodexChatModel` calls an internal ChatGPT endpoint and uses hardcoded default arguments (specifically targetting `checkout-service` and a typo fix `RedisCache.connec`) if the model output fails ReAct formats.
- **Dynamic Module Loading**: The sync mode uses dynamic import paths (`agent_src` vs `src` with `sys.modules` pops) to prevent conflicts, showing a lack of packaging structure.
- **Jira Mock Endpoint**: A local mock API endpoint `/mock-jira/rest/api/3/issue` is hardcoded in the backend to simulate ticket creation.
- **Single-Thread Ingestion Database Bottlenecks**: No Kafka/Flink telemetry buffering is implemented, causing database lock potentials on high volume error surges.

# Backend API Infrastructure Specification

This document details the Docker configuration, system requirements, and network topology for the DAA Backend API container.

## 1. Container Configuration & Dockerfile

The backend container is defined by the Dockerfile at `/home/rutvej/Desktop/DAA/app/backend-api/Dockerfile`.

### Base Image
- **Image**: `python:3.11-slim` (lightweight Debian-based Python image).
- **System Dependencies**:
  - `git`: Required to run `git ls-remote` checks for remote branch-based deduplication when DAA is run in stateless mode.
  - `patch`: Required to run file patching operations inline when executing the agent inside `BackgroundTasks` in stateless sync mode.
  - `build-essential` and `libpq-dev` (or precompiled packages like `psycopg2-binary`) to compile database adapters.

### Key Environment Variables
- `DATABASE_URL`: Connection string to PostgreSQL or SQLite.
- `RABBITMQ_HOST`: Hostname of the RabbitMQ container (`rabbitmq`).
- `DAA_QUEUE_MODE`: `"sync"` (runs inline in FastAPI) or `"rabbitmq"` (pushes to queue broker).
- `DAA_DB_PROVIDER`: `"postgres"`, `"sqlite"`, or `"none"` (mock).
- `CORS_ALLOW_ORIGINS` & `CORS_ALLOW_ORIGIN_REGEX`: CORS allowed clients list.

---

## 2. Dependencies & Requirements

Python libraries required by the backend API:
- `fastapi` and `uvicorn`: Web frame and server.
- `sqlalchemy` and `psycopg2-binary`: Relational ORM and PostgreSQL drivers.
- `pika`: RabbitMQ connector client.
- `requests`: Outgoing API requests (Jira endpoints, dynamic GitLab queries).
- `pydantic`: Payload model validations.

---

## 3. Network Topology

In the full-stack compose network:
- **Exposed Port**: Maps port `8000` on the host to port `80` inside the container.
- **Link Dependencies**:
  - `postgres` (on internal port `5432`).
  - `rabbitmq` (on internal port `5672`).
- **Extra Hosts**:
  - Includes `host.docker.internal:host-gateway` and `gitlab:host-gateway` to allow the backend to contact git repos running on the host machine loopback interfaces.
- **Scale Out Policies**:
  - Multiple backend instances can be deployed behind an HTTP Load Balancer. Since database connections are managed via SQLAlchemy pool limits and logs are buffered or run inline, the backend is fully stateless when `DAA_QUEUE_MODE=rabbitmq` is configured.

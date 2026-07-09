# DAA Unified Deployment Plan — Single-Image Multi-Process & Compose Integration

> **Status:** DRAFT — v0.1  
> **Date:** 2026-07-09  
> **Goal:** Design a unified single Docker image that can auto-configure itself for stateless serverless runs, self-contained multi-process runs (internal Postgres/Redis), and standard multi-container Docker Compose scales.

---

## 1. Feature Flags & Database Requirement Rules

To simplify runtime behavior, we introduce two master switches:
*   `DAA_POLICY_ENABLED=true|false` (Deduplication, sliding thresholds, cooldowns)
*   `DAA_AUTH_ENABLED=true|false` (Custom JWT User registration and login portal)

### State Matrix & DB Requirements

If **either** flag is set to `true`, a state database is required to store policy state (cooldowns, counts) or authentication credentials. DAA automatically resolves the database location based on the `DAA_DB_PROVIDER` flag.

```
                  ┌─────────────────────────────────────────┐
                  │      POLICY=true OR AUTH=true ?         │
                  └────────────────────┬────────────────────┘
                                       │
                     ┌─────────────────┴─────────────────┐
                     ▼ YES                               ▼ NO
          ┌─────────────────────┐             ┌─────────────────────┐
          │ Database Required   │             │ Stateless Mode      │
          └──────────┬──────────┘             │ (No DB required)    │
                     │                        └─────────────────────┘
         ┌───────────┴───────────┐
         ▼                       ▼
 ┌────────────────────────────────────────────────────────┐
 │                      DB Providers                      │
 └──────────────────────────┬─────────────────────────────┘
                            ├─ sqlite (local file)
                            ├─ internal-postgres (in-image)
                            ├─ external-postgres (cloud)
                            ├─ internal-redis (in-image)
                            └─ external-redis / upstash (cloud)
```

---

## 2. Pluggable Database Providers

### 2.1 DB Providers (`DAA_DB_PROVIDER`)

| Provider | Type | Setup Complexity | Persistence | Best For |
|---|---|---|---|---|
| `none` | N/A | None | None | Pure stateless Cloud Run / Fargate |
| `sqlite` | **SQL** (Internal) | Zero | Persistent file | Single VM, local testing |
| `internal-postgres` | **SQL** (Internal) | Zero (auto-started) | Internal data directory | Self-contained single-image Postgres DB |
| `external-postgres` | **SQL** (External) | Manual | Cloud Managed | High availability production DB |
| `internal-redis` | **NoSQL** (Internal) | Zero (auto-started) | Volatile | Self-contained single-image Redis DB |
| `external-redis` / `upstash` | **NoSQL** (External) | Manual | Cloud Managed / Upstash | Serverless stateful runs DB |

*Note: Redis/Upstash is used directly as a key-value database for policy state, cooldown tracking, and error counter tables. There is no cache layer in DAA.*

---

## 3. Single-Image Multi-Process Architecture

To allow users to run a full stack (with API, Agent, and internal database) using a single `docker run` command, the DAA image uses an intelligent shell entrypoint (`entrypoint.sh`) that acts as a lightweight process supervisor.

### 3.1 Dockerfile with Postgres & Redis Installed

The unified Dockerfile installs lightweight Postgres and Redis servers directly into the image:

```dockerfile
FROM python:3.11-slim

# Install system dependencies, git, postgres, and redis
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    postgresql \
    postgresql-contrib \
    redis-server \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and scripts
COPY . .

# Setup default environment variables
ENV DAA_DB_PROVIDER=sqlite
ENV PORT=8080

EXPOSE 8080

RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]
```

### 3.2 The Supervisor Entrypoint (`entrypoint.sh`)

When the container boots, `entrypoint.sh` parses the environment variables and starts internal database processes if requested, before running the FastAPI server and background worker:

```bash
#!/bin/bash
set -e

echo "=== DAA Bootstrapping ==="

# ── 1. Handle Internal Postgres ──
if [ "$DAA_DB_PROVIDER" = "internal-postgres" ]; then
    echo "Starting internal Postgres server..."
    # Initialize DB cluster if not exists
    DB_DATA="/var/lib/postgresql/data"
    if [ ! -d "$DB_DATA/base" ]; then
        chown -R postgres:postgres /var/lib/postgresql
        su - postgres -c "/usr/lib/postgresql/*/bin/initdb -D $DB_DATA"
    fi
    # Start Postgres daemon
    su - postgres -c "/usr/lib/postgresql/*/bin/pg_ctl -D $DB_DATA -l /tmp/postgres.log start"
    
    # Wait for database availability
    until pg_isready -h localhost; do
        sleep 1
    done
    
    # Configure DAA default database user & table
    su - postgres -c "psql -c \"CREATE USER daa WITH PASSWORD 'daa_pass';\" || true"
    su - postgres -c "psql -c \"CREATE DATABASE daa_db OWNER daa;\" || true"
    export DATABASE_URL="postgresql://daa:daa_pass@localhost:5432/daa_db"
fi

# ── 2. Handle Internal Redis ──
if [ "$DAA_DB_PROVIDER" = "internal-redis" ]; then
    echo "Starting internal Redis server..."
    redis-server --daemonize yes
    export REDIS_URL="redis://localhost:6379/0"
fi

# ── 3. Start DAA FastAPI Server & Worker ──
echo "Starting DAA API..."
if [ "$DAA_QUEUE_MODE" = "sync" ]; then
    # In serverless/sync mode, running the API server is enough (worker runs inline or as thread)
    exec uvicorn daa_minimal.server:app --host 0.0.0.0 --port "$PORT"
else
    # In distributed mode, run API and Agent worker as concurrent background processes
    echo "Starting DAA Agent Worker..."
    python -m daa_minimal.agent &
    exec uvicorn daa_minimal.server:app --host 0.0.0.0 --port "$PORT"
fi
```

---

## 4. Single-Image Docker Run Examples

This architecture enables seamless deployment profiles using the **exact same image**:

### A. Pure Serverless (Stateless, Zero-DB)
```bash
docker run -p 8080:8080 \
  -e DAA_POLICY_ENABLED=false \
  -e DAA_AUTH_ENABLED=false \
  -e DAA_DB_PROVIDER=none \
  -e DAA_GIT_MODE=api \
  -e GITHUB_TOKEN=ghp_xxx \
  rutvej/daa:latest
```

### B. Self-Contained SQLite Run
```bash
docker run -p 8080:8080 \
  -v daa-data:/var/daa/sqlite \
  -e DAA_POLICY_ENABLED=true \
  -e DAA_AUTH_ENABLED=true \
  -e DAA_DB_PROVIDER=sqlite \
  -e DAA_SQLITE_PATH=/var/daa/sqlite/daa.db \
  -e DAA_GIT_MODE=api \
  -e GITHUB_TOKEN=ghp_xxx \
  rutvej/daa:latest
```

### C. Self-Contained Full Stack (Internal Postgres)
```bash
docker run -p 8080:8080 \
  -v daa-db-data:/var/lib/postgresql/data \
  -e DAA_POLICY_ENABLED=true \
  -e DAA_AUTH_ENABLED=true \
  -e DAA_DB_PROVIDER=internal-postgres \
  -e DAA_GIT_MODE=api \
  -e GITHUB_TOKEN=ghp_xxx \
  rutvej/daa:latest
```

---

## 5. Integrating with Docker Compose (Multi-Container Scaling)

When deploying to production, running Postgres or Redis inside the same container as the API limits scalability and fault tolerance. 

To scale up, DAA uses the **same Docker image** in a multi-container `docker-compose.yml` topology, turning off internal services and delegating them to external containers:

```yaml
version: '3.8'

services:
  # 1. External Postgres Database (Relational Store)
  postgres:
    image: postgres:15
    restart: always
    environment:
      POSTGRES_DB: daa_prod
      POSTGRES_USER: daa_admin
      POSTGRES_PASSWORD: secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  # 2. External Redis Database (Key-Value State Store)
  redis:
    image: redis:7-alpine
    restart: always

  # 3. DAA FastAPI Web API Instance
  daa-api:
    image: rutvej/daa:latest
    ports:
      - "8080:8080"
    environment:
      - DAA_DB_PROVIDER=external-postgres
      - DATABASE_URL=postgresql://daa_admin:secure_password@postgres:5432/daa_prod
      - DAA_QUEUE_MODE=rabbitmq # or kafka
      - DAA_POLICY_ENABLED=true
      - DAA_AUTH_ENABLED=true
    depends_on:
      - postgres

  # 4. DAA Agent Workers (Can scale independently)
  daa-worker:
    image: rutvej/daa:latest
    command: python -m daa_minimal.agent
    environment:
      - DAA_DB_PROVIDER=external-postgres
      - DATABASE_URL=postgresql://daa_admin:secure_password@postgres:5432/daa_prod
      - DAA_QUEUE_MODE=rabbitmq
      - DAA_GIT_MODE=local # Allow local workspace clones for compiling/testing code
    depends_on:
      - postgres

volumes:
  postgres_data:
```

### Key Compose Advantages
* **Single Image Maintenance**: You build and maintain only one image (`rutvej/daa:latest`).
* **Scale Workers Independently**: Scale the background worker tasks with `docker-compose scale daa-worker=5` to handle high incident rates without impacting web server latency.
* **Separation of Concerns**: Database data is safely persistent in a dedicated container volume.


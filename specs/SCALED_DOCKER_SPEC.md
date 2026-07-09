# DAA Scaled Edition — Single Docker Image with SQLite + Embedded Queue

> **Status:** DRAFT — v0.1  
> **Date:** 2026-07-09  
> **Goal:** A middle-ground architecture: single Docker image with SQLite persistence, embedded job queue, and full admin panel — for users who want persistence and the dashboard experience without running 6 containers.

---

## 1. Problem Statement

The current DAA `docker-compose.yml` requires **6 containers**:

| Container | Purpose | Why it's heavy |
|---|---|---|
| `postgres` | Persistent state (incidents, fixes, apps) | Needs volume, tuning, backups |
| `rabbitmq` | Job queue between API and agent | Extra port, healthchecks, memory |
| `backend-api` | FastAPI REST API | Depends on Postgres + RabbitMQ |
| `python-agent` | LLM agent worker | Depends on RabbitMQ + Postgres |
| `admin-panel` | React dashboard | Depends on backend-api |
| `mcp-server` | MCP protocol server | Depends on Postgres + backend-api |

This works for production SRE teams but is **too complex** for:
- Individual developers trying DAA for the first time
- Small teams without DevOps expertise
- Conference demos and proof-of-concept deployments

---

## 2. Architecture: Single Container with Embedded State

```
┌─────────────────────────────────────────────────┐
│           Single Docker Container               │
│                                                 │
│  ┌───────────────────────────────────────────┐  │
│  │   FastAPI (backend-api + static UI)       │  │ :8080
│  │   - All REST API endpoints                │  │
│  │   - Serves React admin-panel build        │  │
│  │   - SQLite database (file on volume)      │  │
│  │   - SQLite job queue (replaces RabbitMQ)  │  │
│  └──────────────┬────────────────────────────┘  │
│                 │ in-process                     │
│  ┌──────────────▼────────────────────────────┐  │
│  │   Agent Worker (background thread)        │  │
│  │   - Polls SQLite job queue                │  │
│  │   - Runs 3-phase investigation            │  │
│  │   - Writes results back to SQLite         │  │
│  └───────────────────────────────────────────┘  │
│                                                 │
│  ┌───────────────────────────────────────────┐  │
│  │   MCP Server (optional stdio mode)        │  │
│  └───────────────────────────────────────────┘  │
│                                                 │
│  Volume: /data/daa.db (persistent SQLite)       │
└─────────────────────────────────────────────────┘
```

### Key design decisions

| Decision | Rationale |
|---|---|
| **SQLite instead of Postgres** | `database.py` already falls back to SQLite — zero code change needed for the data layer |
| **SQLite job queue instead of RabbitMQ** | A `jobs` table with `status` column replaces the entire message broker |
| **Background thread instead of separate container** | `threading.Thread` polls the job queue, processes one job at a time |
| **Static React build inside FastAPI** | `npm run build` → copy to `/app/static/` → `StaticFiles` mount |
| **Same API surface** | Admin panel and SDKs work without modification |

---

## 3. How SQLite Replaces RabbitMQ

### 3.1 Job queue table

```sql
CREATE TABLE IF NOT EXISTS job_queue (
    id TEXT PRIMARY KEY,
    payload JSON NOT NULL,
    status TEXT DEFAULT 'pending',  -- pending, processing, done, failed
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    completed_at DATETIME,
    result JSON,
    error TEXT
);
```

### 3.2 Enqueue (replaces `channel.basic_publish`)

```python
def enqueue_job(db, job_id: str, payload: dict):
    db.execute(
        "INSERT INTO job_queue (id, payload, status) VALUES (?, ?, 'pending')",
        (job_id, json.dumps(payload))
    )
    db.commit()
```

### 3.3 Dequeue (replaces `channel.basic_consume`)

```python
def dequeue_job(db) -> Optional[dict]:
    """Atomically claim the next pending job."""
    row = db.execute(
        "UPDATE job_queue SET status='processing', started_at=CURRENT_TIMESTAMP "
        "WHERE id = (SELECT id FROM job_queue WHERE status='pending' ORDER BY created_at LIMIT 1) "
        "RETURNING *"
    ).fetchone()
    db.commit()
    return dict(row) if row else None
```

### 3.4 Worker loop

```python
import threading, time

def worker_loop(db_path: str):
    while True:
        db = sqlite3.connect(db_path)
        job = dequeue_job(db)
        if job:
            try:
                result = process_job(Job(**json.loads(job["payload"])))
                db.execute(
                    "UPDATE job_queue SET status='done', completed_at=CURRENT_TIMESTAMP, result=? WHERE id=?",
                    (json.dumps(result), job["id"])
                )
            except Exception as e:
                db.execute(
                    "UPDATE job_queue SET status='failed', error=? WHERE id=?",
                    (str(e), job["id"])
                )
            db.commit()
            db.close()
        else:
            db.close()
            time.sleep(2)  # Poll every 2 seconds

# Start worker on app startup
threading.Thread(target=worker_loop, args=("daa.db",), daemon=True).start()
```

---

## 4. Persistence Model

All existing SQLAlchemy models work as-is with SQLite:

- `User`, `Log`, `Fix`, `Incident`, `Application`, `EscalationPolicy`, `Alert`, `ProjectConnection`

The existing code in `database.py` already handles the SQLite fallback:

```python
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./test.db")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
```

### User's choice at deploy time

```bash
# Option A: SQLite (default — zero config)
docker run -p 8080:8080 -v daa-data:/data \
  -e LLM_PROVIDER=google \
  -e GEMINI_API_KEY=xxx \
  rutvej/daa-scaled:latest

# Option B: External Postgres (for users who want full persistence)
docker run -p 8080:8080 \
  -e DATABASE_URL=postgresql://user:pass@host/daa \
  -e LLM_PROVIDER=google \
  -e GEMINI_API_KEY=xxx \
  rutvej/daa-scaled:latest
```

---

## 5. When to Use This vs. the Minimal (Zero-DB) Edition

| | Minimal (zero-db) | Scaled (SQLite) | Full (docker-compose) |
|---|---|---|---|
| **State** | Ephemeral (Git is memory) | Persistent (SQLite) | Persistent (Postgres) |
| **Dashboard history** | Last 100 jobs (in-memory) | Full history | Full history |
| **Dedup** | Git branch check | Postgres-style fingerprint table | Postgres fingerprint table |
| **Auth** | Cloud IAM / API key | JWT (existing) | JWT (existing) |
| **Scaling** | Cloud auto-scale | Single instance | Multi-container |
| **Best for** | Serverless deploy (Cloud Run) | Self-hosted single server | Production SRE platform |

---

## 6. Relationship to Minimal Edition

This "Scaled" edition and the "Minimal" edition solve different use cases:

- **Minimal** = stateless, no database, Cloud Run native, dedup via Git. Best for serverless.
- **Scaled** = stateful, SQLite, self-hosted, full dashboard with history. Best for single-server deployments.

Both ship as a single Docker image. Both leave the existing `docker-compose.yml` untouched.

The codebase can support both via a single build with a startup flag:

```bash
# Minimal mode (no DB, git-only dedup)
docker run -e DAA_EDITION=minimal ...

# Scaled mode (SQLite, full persistence)
docker run -e DAA_EDITION=scaled -v daa-data:/data ...
```

---

## 7. Implementation Notes

### What changes from the existing codebase

| Component | Change |
|---|---|
| `backend-api/src/main.py` | Mount static files, start worker thread |
| `backend-api/src/database.py` | Add `job_queue` table model |
| `python-agent/src/main.py` | New `process_job_standalone()` that doesn't need RabbitMQ |
| Admin panel | `npm run build` → embed static files |
| Docker | Single `Dockerfile` instead of 4 separate ones |

### What stays the same

- All SQLAlchemy models
- All API routers
- All agent tools
- LLM configuration
- MCP server
- SDK interface

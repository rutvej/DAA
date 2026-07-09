# DAA Minimal — Single Container, Zero-Infrastructure Agent

> **Status:** DRAFT — v0.1  
> **Date:** 2026-07-09  
> **Goal:** Ship a single Docker image (`daa-minimal`) to Docker Hub / GHCR that anyone can deploy to Cloud Run, Fargate, or `docker run` in under 60 seconds.

---

## 1. How Modern Agents Are Built in 2026

Before designing the minimal DAA, it's worth understanding where the industry has landed.

### 1.1 The shift from "microservices for agents" to "agent-as-a-function"

In 2024–25, teams copied their backend microservice habits into AI agents:
separate Postgres, separate message queues, separate API gateway, separate worker.
That works for **platform teams** running agents at scale, but it killed adoption for
individual developers and small SRE teams.

**2026 consensus:**

| Pattern | When to use |
|---|---|
| **Agent-as-a-function** (single container, HTTP-triggered, stateless) | Solo devs, small teams, quick deploy. Cloud Run / Lambda scales for you. |
| **Durable agent orchestration** (LangGraph / Restate / Temporal) | Long-running multi-step workflows with human-in-the-loop, retries, checkpoints. |
| **Multi-agent supervisor** (supervisor + specialized workers) | Enterprise — dedicated agents for code analysis, log analysis, ticketing, etc. |

**DAA already has the "durable multi-agent" architecture (the current `docker-compose.yml`).**
The minimal version targets the **agent-as-a-function** pattern.

### 1.2 The "no database" philosophy

Modern cloud-native agents in 2026 follow a principle:

> **Don't store what you can derive. Don't persist what already lives somewhere else.**

For DAA:
- The **fix** lives in the **Git PR** — not in a Postgres row.
- The **postmortem** lives in the **PR description / Jira ticket** — not in a `fixes` table.
- The **incident history** lives in the **Git branch names** — `fix/<fingerprint>` is the dedup key.
- **Auth** is handled by the **cloud platform** (Cloud Run IAM, Fargate task roles, API Gateway keys).
- **Queuing** is handled by the **cloud platform** (Cloud Pub/Sub, SQS, or Cloud Run's built-in request queue).

**The only thing that *needs* memory is dedup.** And Git is already the memory.

### 1.3 Key insight: Git IS your state store

Current DAA dedup works like this:
```
SDK sends error → Backend API → stores in Postgres → enqueues to RabbitMQ
                                  ↓
                  Agent checks Postgres for fingerprint
                  If exists → skip
                  If new → investigate → create branch fix/<fingerprint[:12]>
```

For the minimal version, Git replaces Postgres:
```
SDK sends error → DAA Minimal (single container)
                     ↓
   1. Compute fingerprint = SHA256(app|exception|file|line)
   2. Check: does branch `fix/<fingerprint[:12]>` exist on remote?
      - YES → return existing PR URL, skip investigation
      - NO  → investigate → create fix → push branch → create PR
```

**No database needed. The Git remote IS the dedup store.**

---

## 2. Architecture

```
┌──────────────────────────────────────────────────────────┐
│              DAA Minimal (Single Container)               │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │  FastAPI                                  :8080    │  │
│  │  ├── POST /webhook     (SDK error intake)         │  │
│  │  ├── POST /analyze     (manual trigger)           │  │
│  │  ├── GET  /health      (Cloud Run liveness)       │  │
│  │  ├── GET  /status/:id  (check job result)         │  │
│  │  └── /*  static files  (admin panel SPA)          │  │
│  └────────────────┬───────────────────────────────────┘  │
│                   │ in-process (asyncio)                  │
│  ┌────────────────▼───────────────────────────────────┐  │
│  │  Agent Core                                        │  │
│  │  ├── FingerprintDedup (git ls-remote)              │  │
│  │  ├── RepoCacheManager (clone once, fetch on stale) │  │
│  │  ├── 3-phase investigation (orchestrator.py)       │  │
│  │  ├── LLM call (Gemini/OpenAI/Claude/Ollama)       │  │
│  │  └── PR creation / Jira ticket                    │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │  MCP Server (optional, stdio mode via flag)        │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  No Postgres. No RabbitMQ. No external state.            │
│  Auth: Cloud IAM / simple API key header.                │
│  Scale: Cloud Run concurrency / Fargate auto-scale.      │
│  Dedup: git ls-remote checks for fix/<fingerprint>.      │
│  Repo cache: /var/daa/repo-cache (ephemeral or volume).  │
└──────────────────────────────────────────────────────────┘
```

### What's included vs. what's delegated to the cloud

| Concern | Current (docker-compose) | Minimal (single image) |
|---|---|---|
| Database | Postgres container | **None** (Git is state store) |
| Message queue | RabbitMQ container | **None** (HTTP-triggered, Cloud Run queues requests) |
| Auth | Custom JWT (`python-jose`) | **Cloud IAM** or simple `X-API-Key` header |
| Scaling | Manual (docker-compose scale) | **Cloud auto-scale** (Cloud Run concurrency, Fargate tasks) |
| Dedup | Postgres `incidents` table | **Git remote** (`git ls-remote` checks branch existence) |
| Admin panel | Separate React container | **Embedded** (static build served by FastAPI) |
| MCP server | Separate container | **Embedded** (same process, optional flag) |

---

## 3. How Dedup Works Without a Database

### 3.1 The fingerprint

Same as current DAA 3.0 — deterministic SHA-256 of `(app_name, exception_type, error_file, line_number)`:

```python
fingerprint = hashlib.sha256(
    f"{app_name}|{exception_type}|{error_file}|{line_number}".encode()
).hexdigest()
```

### 3.2 Git-based dedup check

Instead of querying Postgres, check if the branch already exists on the remote:

```python
import subprocess

def check_dedup(repo_url: str, fingerprint: str, token: str = None) -> dict:
    """Check if a fix branch already exists on the remote."""
    branch_name = f"fix/{fingerprint[:12]}"
    
    # Build authenticated URL if token provided
    if token:
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(repo_url)
        auth_url = urlunparse(parsed._replace(
            netloc=f"{token}@{parsed.hostname}"
        ))
    else:
        auth_url = repo_url
    
    result = subprocess.run(
        ["git", "ls-remote", "--heads", auth_url, f"refs/heads/{branch_name}"],
        capture_output=True, text=True, timeout=15,
    )
    
    if result.stdout.strip():
        # Branch exists — find the PR URL
        return {"status": "fix_exists", "branch": branch_name}
    
    return {"status": "no_fix"}
```

### 3.3 In-memory LRU for hot-path dedup

To avoid hitting the Git remote on every duplicate burst (e.g., same error 100× in 1 minute),
add a simple in-memory LRU cache:

```python
from datetime import datetime, timedelta

# In-memory cache: fingerprint → (status, timestamp)
# Entries expire after 30 minutes (matches current cooldown_minutes)
_dedup_cache: dict[str, tuple[str, datetime]] = {}
COOLDOWN = timedelta(minutes=30)

def is_duplicate(fingerprint: str) -> bool:
    """Hot-path check before hitting Git remote."""
    if fingerprint in _dedup_cache:
        status, ts = _dedup_cache[fingerprint]
        if datetime.utcnow() - ts < COOLDOWN:
            return True
        del _dedup_cache[fingerprint]
    return False

def mark_processed(fingerprint: str):
    _dedup_cache[fingerprint] = ("processed", datetime.utcnow())
```

### 3.4 Why this is sufficient

| Scenario | How it's handled |
|---|---|
| Same error fires 100× in 1 min | In-memory LRU catches it after the 1st processing |
| Container restarts, same error fires again | `git ls-remote` finds existing `fix/<fingerprint>` branch |
| Two Cloud Run instances get the same error simultaneously | Both compute same fingerprint, both try to push same branch — Git's atomic push ensures only one succeeds, second gets "branch already exists" |
| Error is fixed, branch merged & deleted | Fingerprint won't match `ls-remote` — agent re-investigates (correct behavior: old fix may not apply to new occurrence) |

---

## 4. Container Internals

### 4.1 What lives inside the image

```
/app/
├── daa_minimal/
│   ├── __init__.py
│   ├── server.py           # FastAPI app (webhook, analyze, health, static)
│   ├── agent.py             # Agent core (process_job, 3-phase)
│   ├── dedup.py             # Git-based fingerprint dedup + LRU cache
│   ├── repo_cache.py        # RepoCacheManager (adapted from orchestrator.py)
│   ├── llm_config.py        # Multi-LLM routing (reuse existing)
│   ├── mcp_server.py        # MCP stdio server (optional mode)
│   ├── tools/               # Investigation tools (reuse existing)
│   └── static/              # Pre-built React admin panel
├── requirements.txt
└── Dockerfile
```

### 4.2 Dockerfile

```dockerfile
FROM python:3.11-slim

# Install git (needed for repo operations)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-built admin panel static files
COPY static/ ./daa_minimal/static/

# Application code
COPY daa_minimal/ ./daa_minimal/

# Create repo cache directory
RUN mkdir -p /var/daa/repo-cache

# Cloud Run expects PORT env var
ENV PORT=8080
EXPOSE 8080

# Health check for container orchestrators
HEALTHCHECK --interval=30s --timeout=5s \
  CMD curl -f http://localhost:${PORT}/health || exit 1

# Single entry point — no supervisor, no multi-process
CMD ["python", "-m", "uvicorn", "daa_minimal.server:app", \
     "--host", "0.0.0.0", "--port", "8080"]
```

### 4.3 Environment variables

Only these are required:

```bash
# ── Required ──────────────────────────────────────
LLM_PROVIDER=google          # or openai, anthropic, ollama
GEMINI_API_KEY=xxx            # (or OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)

# ── Git (at least one) ────────────────────────────
GITHUB_TOKEN=ghp_xxx          # For GitHub repos
# OR
GITLAB_PRIVATE_TOKEN=xxx      # For GitLab repos

# ── Optional ──────────────────────────────────────
DAA_API_KEY=my-secret-key     # Simple API key auth (if not using Cloud IAM)
PORT=8080                     # Cloud Run sets this automatically
DAA_MODE=mcp                  # Set to "mcp" to run as MCP stdio server instead
LLM_MODEL=gemini-2.5-flash   # Override default model
```

**Notice: No `DATABASE_URL`, no `RABBITMQ_HOST`, no `POSTGRES_PASSWORD`.**

---

## 5. API Surface

### 5.1 Webhook endpoint (SDK integration)

```
POST /webhook
Content-Type: application/json
X-API-Key: <DAA_API_KEY>   (or Cloud IAM auth)

{
  "app_name": "my-service",
  "repo_url": "https://github.com/owner/my-service.git",
  "exception_type": "NullPointerException",
  "error_file": "src/main/java/com/example/Handler.java",
  "line_number": 42,
  "stack_trace": "...",
  "log_content": "...",
  "metadata": {}
}
```

**Response (immediate):**
```json
{
  "job_id": "uuid",
  "status": "accepted",
  "fingerprint": "a1b2c3..."
}
```
or (if dedup hit):
```json
{
  "job_id": null,
  "status": "duplicate",
  "fingerprint": "a1b2c3...",
  "existing_branch": "fix/a1b2c3d4e5f6"
}
```

The investigation runs asynchronously in a background task. Cloud Run keeps the
container alive until the response is sent + the background task completes.

### 5.2 Status check

```
GET /status/<job_id>

Response:
{
  "status": "investigating" | "fixed" | "escalated" | "duplicate",
  "pr_url": "https://github.com/...",
  "postmortem": "..."
}
```

### 5.3 Admin panel

```
GET /                → serves the React SPA
GET /static/*        → static assets
```

The admin panel connects to the same FastAPI backend on the same origin
(no CORS issues).

---

## 6. Deployment Examples

### 6.1 Docker Hub (one-liner)

```bash
docker run -p 8080:8080 \
  -e LLM_PROVIDER=google \
  -e GEMINI_API_KEY=xxx \
  -e GITHUB_TOKEN=ghp_xxx \
  rutvej/daa-minimal:latest
```

### 6.2 Google Cloud Run

```bash
gcloud run deploy daa-minimal \
  --image rutvej/daa-minimal:latest \
  --port 8080 \
  --set-env-vars="LLM_PROVIDER=google,GEMINI_API_KEY=xxx,GITHUB_TOKEN=ghp_xxx" \
  --allow-unauthenticated   # or use IAM for auth
```

### 6.3 AWS Fargate

```bash
# Push image to ECR, then create task definition with env vars
# Cloud Run and Fargate both support the same container contract:
#   - Listen on PORT
#   - Respond to /health
#   - Process HTTP requests
```

### 6.4 MCP mode (for coding agents)

```bash
docker run -i --rm \
  -e DAA_MODE=mcp \
  -e LLM_PROVIDER=google \
  -e GEMINI_API_KEY=xxx \
  rutvej/daa-minimal:latest
```

Or in `.mcp.json`:
```json
{
  "mcpServers": {
    "daa": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "-e", "DAA_MODE=mcp", "rutvej/daa-minimal:latest"],
      "env": {
        "GEMINI_API_KEY": "xxx",
        "GITHUB_TOKEN": "ghp_xxx"
      }
    }
  }
}
```

---

## 7. SDK Publishing Plan

The SDKs in `app/daa-sdk/` need to be published as standalone packages:

| Language | Registry | Package Name | Install Command |
|---|---|---|---|
| Python | **PyPI** | `daa-sdk` | `pip install daa-sdk` |
| Node.js | **npm** | `daa-sdk` | `npm install daa-sdk` |
| Go | **Go Modules** | `github.com/rutvej/daa-sdk-go` | `go get github.com/rutvej/daa-sdk-go` |
| Java | **Maven Central** | `io.daa:daa-sdk` | Maven/Gradle dependency |
| Ruby | **RubyGems** | `daa-sdk` | `gem install daa-sdk` |
| .NET | **NuGet** | `Daa.Sdk` | `dotnet add package Daa.Sdk` |

### SDK publish workflow (GitHub Actions)

```yaml
# .github/workflows/publish-sdk.yml
on:
  push:
    tags: ['sdk-v*']

jobs:
  publish-python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: cd app/daa-sdk/daa_sdk && pip install build twine
      - run: python -m build
      - run: twine upload dist/* --username __token__ --password ${{ secrets.PYPI_TOKEN }}

  publish-npm:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: cd app/daa-sdk/node-sdk && npm publish --access public
        env:
          NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}

  publish-docker:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build -t rutvej/daa-minimal:latest -f minimal/Dockerfile .
      - run: docker push rutvej/daa-minimal:latest
```

---

## 8. What We Reuse vs. What We Write New

| Module | Source | Changes needed |
|---|---|---|
| `llm_config.py` | `app/python-agent/src/llm_config.py` | **Reuse as-is** |
| `orchestrator.py` (repo cache, context packaging, post-flight) | `app/python-agent/src/orchestrator.py` | **Adapt** — remove backend API calls, use git-dedup |
| `agent_safety.py` | `app/python-agent/src/agent_safety.py` | **Reuse as-is** |
| `tools/*` | `app/python-agent/src/tools/` | **Reuse as-is** |
| `mcp_server.py` | `app/daa_mcp_server.py` | **Adapt** — remove Postgres queries, use in-memory state |
| Admin panel | `app/admin-panel/` | **Build & embed** — `npm run build`, copy to `static/` |
| `server.py` (FastAPI HTTP layer) | — | **New** — thin webhook + status + static file server |
| `dedup.py` (git-based dedup) | — | **New** — `git ls-remote` + in-memory LRU |
| `agent.py` (simplified process_job) | `app/python-agent/src/main.py` | **New** — strip out RabbitMQ, wire directly to FastAPI |

---

## 9. Handling Edge Cases

### 9.1 "What if two requests hit simultaneously?"

Cloud Run can handle concurrent requests to the same container instance.
Use `asyncio.Lock` keyed on fingerprint to ensure only one investigation runs per fingerprint:

```python
_locks: dict[str, asyncio.Lock] = {}

async def process_webhook(payload):
    fp = compute_fingerprint(payload)
    
    if fp not in _locks:
        _locks[fp] = asyncio.Lock()
    
    async with _locks[fp]:
        if is_duplicate(fp):
            return {"status": "duplicate"}
        # ... run investigation
        mark_processed(fp)
```

### 9.2 "What if the container restarts mid-investigation?"

Cloud Run / Fargate will spin up a new instance. The next time the same error arrives:
- `git ls-remote` will check if `fix/<fingerprint>` branch was pushed
- If yes (investigation completed before crash) → dedup hit
- If no (crashed before pushing) → re-investigate (correct behavior)

### 9.3 "What about the admin panel state?"

The admin panel in the minimal version shows:
- **Live investigation logs** (via Server-Sent Events from the in-process agent)
- **Recent results** (in-memory, last 100 jobs — lost on restart, but that's fine for minimal)
- **Job status** (query by job_id)

For persistent history, users can upgrade to the full `docker-compose` setup.

### 9.4 "SQLite as optional middle ground?"

If users want some persistence without the full Postgres setup:

```bash
docker run -p 8080:8080 \
  -e DATABASE_URL=sqlite:///data/daa.db \
  -v daa-data:/data \
  rutvej/daa-minimal:latest
```

This gives persistent incident history, dedup via DB, and survives restarts.
The code should support both modes: **no-db (git-only dedup)** and **sqlite (full persistence)**.

---

## 10. Implementation Plan

### Phase 1: Core (estimated: 1–2 days)
1. Create `minimal/` directory in the DAA repo
2. Write `server.py` (FastAPI webhook + status + health)
3. Write `dedup.py` (git-based dedup + LRU)
4. Write `agent.py` (adapted `process_job` without RabbitMQ)
5. Copy and adapt `llm_config.py`, `orchestrator.py`, `agent_safety.py`, `tools/`
6. Write `Dockerfile`
7. Test locally: `docker build && docker run`

### Phase 2: Admin Panel (estimated: 1 day)
1. Build admin panel: `cd app/admin-panel && npm run build`
2. Copy `build/` to `minimal/static/`
3. Mount static files in FastAPI
4. Add SSE endpoint for live investigation logs

### Phase 3: MCP Server (estimated: 0.5 day)
1. Adapt `daa_mcp_server.py` to work without Postgres
2. Add `DAA_MODE=mcp` entry point that runs stdio MCP instead of HTTP

### Phase 4: SDK Publishing (estimated: 1 day)
1. Add `setup.py` / `pyproject.toml` for Python SDK
2. Add `package.json` publish config for Node.js SDK
3. Write GitHub Actions workflow for automated publishing

### Phase 5: Docker Registry (estimated: 0.5 day)
1. Push to Docker Hub: `rutvej/daa-minimal`
2. Push to GHCR: `ghcr.io/rutvej/daa-minimal`
3. Add deploy buttons to README (Cloud Run, Railway)

---

## 11. File Structure (final)

```
DAA/
├── app/                          # ← EXISTING (untouched)
│   ├── backend-api/
│   ├── python-agent/
│   ├── admin-panel/
│   └── daa-sdk/
├── minimal/                      # ← NEW
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── daa_minimal/
│   │   ├── __init__.py
│   │   ├── server.py             # FastAPI entry point
│   │   ├── agent.py              # Agent core (no RabbitMQ)
│   │   ├── dedup.py              # Git-based dedup
│   │   ├── repo_cache.py         # Repo cache manager
│   │   ├── llm_config.py         # LLM routing (copied)
│   │   ├── orchestrator.py       # Adapted orchestrator
│   │   ├── agent_safety.py       # Safety system (copied)
│   │   ├── mcp_server.py         # MCP stdio mode
│   │   ├── tools/                # Investigation tools (copied)
│   │   └── static/               # Pre-built admin panel
│   └── README.md                 # Minimal-specific docs
├── docker-compose.yml            # ← EXISTING (untouched)
└── README.md
```

---

## 12. Summary: Current vs. Minimal

| | Current (`docker-compose`) | Minimal (single image) |
|---|---|---|
| **Target user** | Platform / SRE teams | Individual devs, small teams |
| **Containers** | 6 (Postgres, RabbitMQ, API, Agent, Panel, MCP) | **1** |
| **Database** | Postgres (required) | **None** (or optional SQLite) |
| **Queue** | RabbitMQ (required) | **None** (HTTP-triggered) |
| **Dedup** | Postgres fingerprint lookup | **Git branch existence** |
| **Auth** | Custom JWT | **Cloud IAM / API key** |
| **Deploy** | `docker-compose up` | `docker run` / Cloud Run / Fargate |
| **Scaling** | Manual | Cloud auto-scale |
| **Persistence** | Full (Postgres) | Ephemeral (Git is the record) |
| **Image size** | ~2GB total (all containers) | **~300MB** (single slim image) |

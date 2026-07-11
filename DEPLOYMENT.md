# DAA Deployment Guide

This document covers everything needed to deploy DAA from the published Docker
image or via Docker Compose, across every supported configuration. It's meant
to be merged into `README.md` / `SETUP.md` — the details here are pulled
directly from the source (`Dockerfile`, `entrypoint.sh`, `database.py`,
`git_api_providers.py`, `ingest.py`, `git_tool.py`) rather than restated from
memory, so treat this as the source of truth over older prose in the repo.

> **Note on inferred details:** anywhere below marked ⚠️ is my best read of
> the code's *behavior*, not a value I found stated explicitly in a comment —
> worth a quick sanity check against your own deployment before publishing.

---

## 1. Quick Start — Docker Hub Image

The published image bundles the Backend API and Agent into a single
container (`entrypoint.sh` runs `uvicorn` and, in non-`sync` queue modes, the
agent worker alongside it).

```bash
docker pull rutvej1/daa-standalone:latest
```

**Fastest possible run — fully stateless, zero infra, GitHub-backed:**

```bash
docker run -d --name daa \
  -p 8000:8080 \
  -e LLM_PROVIDER=google \
  -e GEMINI_API_KEY=your-gemini-key \
  -e DAA_DB_PROVIDER=none \
  -e DAA_GIT_MODE=api \
  -e DAA_QUEUE_MODE=sync \
  -e DAA_AUTH_ENABLED=false \
  -e DAA_POLICY_ENABLED=false \
  -e GIT_HOST=https://github.com \
  -e GIT_ORG=your-github-org \
  -e GITHUB_TOKEN=ghp_xxxxxxxxxxxx \
  rutvej1/daa-standalone:latest
```

Point Sentry / Prometheus Alertmanager / your webhook source at
`http://<host>:8000/ingest/...` and you're done — no database, no queue, no
registration step. See §3 for what each variable does and §5 for every other
combination this image supports.

**Check it's alive:**
```bash
curl http://localhost:8000/health
docker logs -f daa
```

**Stop / remove:**
```bash
docker stop daa && docker rm daa
```

---

## 2. Two Deployment Shapes

| | **Image mode** (`rutvej1/daa-standalone`) | **Compose mode** (`docker-compose.yml`) |
|---|---|---|
| What it is | Single container running API + (optionally) agent worker inline | Multi-container: `backend-api`, `python-agent`, `postgres`, `rabbitmq`, `admin-panel` |
| Best for | Cloud Run, Fargate, ECS, any scale-to-zero PaaS | VMs, Kubernetes, always-on servers, teams wanting the admin UI |
| Persistence | Optional — usually `DAA_DB_PROVIDER=none` or an external Postgres | Local Postgres volume, durable by default |
| Queue | `sync` (inline `BackgroundTasks`) is normal here | `rabbitmq` is normal here, `sync` also works for single-VM setups |
| Git access | `DAA_GIT_MODE=api` (no on-disk clone) is the intended mode | `DAA_GIT_MODE=local` (clone + worktree) is the intended mode, `api` also works |

Both modes read the exact same environment variables — the only structural
difference is how many containers you run and whether the agent is a
separate process or runs in-process via `BackgroundTasks`.

---

## 3. Environment Variable Reference

### Core / LLM
| Variable | Values | Default | Notes |
|---|---|---|---|
| `LLM_PROVIDER` | `google`, `openai`, `anthropic`, `ollama`, `litellm`, `agy`, `codex`, `custom`, `mock` | — | `mock` is for local/CI testing (no real LLM calls) |
| `LLM_MODEL` | provider-specific model name | — | e.g. `gemini-2.5-flash`, `claude-3-5-sonnet-20241022` |
| `GEMINI_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | key string | — | matches `LLM_PROVIDER` |
| `LLM_BASE_URL` | URL | — | required for `ollama`, `litellm`, `custom` |
| `LLM_API_KEY` | key string | — | for `litellm`/`custom` proxies |

### Deployment Profile (the "big three" toggles)
| Variable | Values | Default | Effect |
|---|---|---|---|
| `DAA_DB_PROVIDER` | `none`, `sqlite`, `postgres` / `internal-postgres` / `external-postgres`, `internal-redis`, `external-redis` | `sqlite` | `none` swaps in `MockSession`/`MockQuery` (all queries return empty, all writes no-op) — this is what makes true scale-to-zero possible |
| `DAA_GIT_MODE` | `api`, `local` | `local` | `api` talks to the provider's REST API directly (no clone); `local` clones to `/var/daa/repo-cache` + worktrees under `/tmp/daa/<incident_id>` |
| `DAA_QUEUE_MODE` | `sync`, `rabbitmq` | `rabbitmq` | `sync` runs the agent inline via FastAPI `BackgroundTasks` in the same process; `rabbitmq` publishes to the `fix_jobs` queue for a separate worker to consume |

### Auth & Policy
| Variable | Values | Default | Effect |
|---|---|---|---|
| `DAA_AUTH_ENABLED` | `true`/`false` | `true` if DB provider persists, else `false` | `false` makes `get_current_user()` return a synthetic `admin-id` user and skips JWT checks entirely |
| `DAA_POLICY_ENABLED` | `true`/`false` | same rule as above | `false` disables sliding-window thresholding — every ingested error escalates immediately |
| `SECRET_KEY` | string | `demo_secret_key` | JWT signing key — **set a real value in anything beyond local testing** |
| `DAA_API_KEY` | string | — | shared secret for `/ingest/*` webhook auth (checked via `X-API-Key` or `Authorization`) |
| `SENTRY_WEBHOOK_SECRET` | string | — | if set, `/ingest/sentry` verifies `X-Sentry-Signature` HMAC instead of falling back to `DAA_API_KEY` |

### Database / Queue Connection
| Variable | Values | Default | Notes |
|---|---|---|---|
| `DATABASE_URL` | connection string | `sqlite:///./daa.db` or `postgresql://daa:daa_pass@localhost:5432/daa_db` | ignored entirely if `DAA_DB_PROVIDER=none` |
| `RABBITMQ_HOST` | hostname | `localhost` | only used when `DAA_QUEUE_MODE=rabbitmq` |
| `DAA_BACKEND_API_URL` | URL | `http://backend-api:80` | in **Image mode**, the agent calls back into its *own* container — use `http://localhost:8080` (in-container port), not the host-mapped `8000` |

### Git Provider Access
| Variable | Values | Default | Notes |
|---|---|---|---|
| `DAA_GIT_TOKEN` | token string | — | checked first, before `GITHUB_TOKEN`/`GITLAB_PRIVATE_TOKEN` |
| `GITHUB_TOKEN` / `GITLAB_PRIVATE_TOKEN` | token string | — | fallbacks if `DAA_GIT_TOKEN` unset |
| `GIT_HOST` + `GIT_ORG` | e.g. `https://github.com` + `your-org` | — | builds `repo_url` dynamically as `{GIT_HOST}/{GIT_ORG}/{app_name}.git` — no per-app DB record needed |
| `GIT_REPO_URL` | full URL to one example repo | — | legacy fallback: host+org are parsed out of this and reused per app name |
| `DAA_REPO_URL` | full URL | — | generic single-repo override (all apps resolve to this) |
| `DAA_REPO_PROVIDER` | `github`, `gitlab`, `gitea`, `bitbucket` | auto-detected from URL | force this if your Gitea/GitLab instance doesn't have a recognizable hostname |
| `DAA_REPO_URL_<APP_NAME>` / `DAA_REPO_TOKEN_<APP_NAME>` / `DAA_REPO_PROVIDER_<APP_NAME>` | — | — | per-app overrides; `<APP_NAME>` is uppercased with `-` → `_` |
| `DAA_TARGET_APP` | app name | — | pins tool calls to a single app in single-tenant deployments; also gates `DAA_ALLOWED_REPOS` |
| `DAA_ALLOWED_REPOS` | comma-separated app names | — | allow-list checked when `DAA_TARGET_APP` is set |

### Agent Behavior
| Variable | Values | Default | Notes |
|---|---|---|---|
| `DAA_AGENT_MODE` | `full`, `fast` | `full` | `fast` uses a trimmed toolset + local prompt cache |
| `DAA_HITL_MODE` | `true`/`false` | `false` | `true` makes `create_pull_request` return `AWAITING_APPROVAL:<branch>` instead of opening the PR immediately |
| `DAA_MAX_TOOL_CALLS` | integer | `8` | hard ceiling before forced escalation |
| `DAA_TOOL_CALL_WARNING_AT` | integer | `5` | budget warning injected into the ReAct loop |
| `DAA_MAX_ITERATIONS` | integer | `10` | LangChain executor iteration cap |
| `DAA_WEBHOOK_MAPPINGS_FILE` | path | `daa-webhook-mappings.yaml` | custom JSONPath field mapping for `/ingest/custom/{integration}` |
| `DAA_OUTBOUND_WEBHOOK_URL` / `DAA_OUTBOUND_WEBHOOK_SECRET` | URL / secret | — | fires on investigation completion; HMAC-signed if secret set |
| `DAA_SELF_REPORT` / `DAA_MASTER_MODE` / `DAA_MASTER_URL` | bool / bool / URL | `false` / `false` / `https://master.daa.dev` | opt-in crash telemetry about DAA's *own* code — never sends your app data ⚠️ *(confirm `master.daa.dev` is a domain you actually control/intend to point at before enabling this in anyone else's deployment)* |

---

## 4. Git Provider Token Permissions

DAA needs to: read files, create a branch, commit/write a file, and open a
pull/merge request. Minimum scopes per provider:

### GitHub
- **Classic PAT:** `repo` scope (full control of private repos — covers
  contents read/write, branches, and PRs). There's no finer classic scope
  that covers all four operations.
- **Fine-grained PAT:** repository access limited to the target repo(s),
  with permissions:
  - `Contents: Read and write`
  - `Pull requests: Read and write`
  - `Metadata: Read-only` (required, auto-included)

### GitLab
- **Personal or Project Access Token** with the `api` scope, *or* the
  narrower pair `read_repository` + `write_repository` — but note MR
  creation via the REST API generally requires `api`, so most setups just
  use `api`.

### Gitea
- Token scopes: `write:repository`, `write:issue` (Gitea files PR
  permissions under the "issue" scope group), `read:user`. This matches
  exactly what `daa-e2e-demo/run_matrix_tests.py`'s `seed_gitea()` requests
  when provisioning a token via `POST /users/{user}/tokens`.
- ⚠️ Branch creation on Gitea goes through `POST /repos/{owner}/{repo}/branches`,
  **not** the GitHub-style `POST /git/refs` — if you're running against an
  older Gitea version, verify that endpoint accepts `old_branch_name` (some
  versions use `old_ref_name` instead; DAA's provider client sends both for
  compatibility).

### Bitbucket
- **App Password** (or OAuth consumer) with:
  - `Repositories: Write`
  - `Pull requests: Write`
  (`Read` is implied by `Write` on both.)

---

## 5. Full Combination Matrix

This is the tested matrix from `daa-e2e-demo/run_matrix_tests.py` — every row
here is a combination the project's own E2E suite exercises, so it's the
most reliable "these definitely work together" reference available.

| # | Staging | `DAA_DB_PROVIDER` | `DAA_QUEUE_MODE` | `DAA_GIT_MODE` | `DAA_AUTH_ENABLED` | `DAA_POLICY_ENABLED` | Use case |
|---|---|---|---|---|---|---|---|
| 1 | Image | `none` | `sync` | `api` | `false` | `false` | True serverless — zero infra, Cloud Run/Fargate scale-to-zero |
| 2 | Image | `postgres` | `sync` | `api` | `true` | `true` | Serverless + external DB, auth/policy on |
| 3 | Image | `postgres` | `sync` | `api` | `false` | `false` | Serverless + external DB, auth/policy off (simpler, less safe) |
| 4 | Image | `postgres` | `rabbitmq` | `api` | `true` | `true` | Async serverless — external DB + queue, still no on-disk clones |
| 5 | Compose | `postgres` | `rabbitmq` | `local` | `true` | `true` | Full-stack, standard production setup |
| 6 | Compose | `postgres` | `rabbitmq` | `local` | `false` | `false` | Full-stack, auth/policy off (internal/trusted networks only) |

**How to read this for your own deploy:**
- **Row 1** is what the quick-start command in §1 runs.
- **Row 5** is the default `docker-compose.yml` profile — just `docker compose up -d --build`.
- Rows 2–4 are the middle ground: you get a real Postgres for incident
  history/dedup without running RabbitMQ or a separate worker container.

---

## 6. Setup Steps — Image Mode

```bash
# 1. Pull
docker pull rutvej1/daa-standalone:latest

# 2. Write your env file (see §3 for the full variable list; pick a row from §5)
cat > .env <<'EOF'
LLM_PROVIDER=google
LLM_MODEL=gemini-2.5-flash
GEMINI_API_KEY=your-key
DAA_DB_PROVIDER=none
DAA_QUEUE_MODE=sync
DAA_GIT_MODE=api
DAA_AUTH_ENABLED=false
DAA_POLICY_ENABLED=false
GIT_HOST=https://github.com
GIT_ORG=your-org
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
DAA_BACKEND_API_URL=http://localhost:8080
EOF

# 3. Run
docker run -d --name daa -p 8000:8080 --env-file .env rutvej1/daa-standalone:latest

# 4. Verify
curl http://localhost:8000/health
```

⚠️ Note `DAA_BACKEND_API_URL=http://localhost:8080` — in Image mode the agent
and API share one container, so the agent must call back on the
*in-container* port (`8080`), not the host-mapped port (`8000`) you use from
outside.

---

## 7. Setup Steps — Compose Mode

```bash
# 1. Clone / open the repo, then run the installer once
./install.sh

# 2. Run the config wizard — writes .env / .env.daa
daa init

# 3. Bring the stack up
docker compose up -d --build

# 4. Register an app + policy (skipped automatically if DAA_DB_PROVIDER=none)
daa register --name my-service \
  --repo-url https://github.com/your-org/my-service.git \
  --language python
daa policy --app my-service --threshold 3 --window 60

# 5. Verify
daa status
```

Admin panel: `http://localhost:5003` · Backend API docs: `http://localhost:8000/docs`

---

## Deploying to Cloud Run / Fargate (Default Stateless Profile)

### Google Cloud Run
```bash
gcloud run deploy daa \
  --image rutvej1/daa-standalone:latest \
  --port 8080 \
  --allow-unauthenticated \
  --set-env-vars="\
LLM_PROVIDER=google,\
LLM_MODEL=gemini-2.5-flash,\
GEMINI_API_KEY=your-gemini-key,\
DAA_DB_PROVIDER=none,\
DAA_GIT_MODE=api,\
DAA_QUEUE_MODE=sync,\
DAA_AUTH_ENABLED=false,\
DAA_POLICY_ENABLED=false,\
GIT_HOST=https://github.com,\
GIT_ORG=your-github-org,\
GITHUB_TOKEN=ghp_xxxxxxxxxxxx,\
DAA_BACKEND_API_URL=http://localhost:8080"
```
`DAA_BACKEND_API_URL=http://localhost:8080` is required here even though the service is remote — the agent runs *inside* the same container and calls back on the container's own port, not the public Cloud Run URL.

### AWS Fargate
Same environment variables, set via your task definition's `containerDefinitions[].environment`:
```json
{
  "containerDefinitions": [{
    "name": "daa",
    "image": "rutvej1/daa-standalone:latest",
    "portMappings": [{ "containerPort": 8080 }],
    "environment": [
      { "name": "LLM_PROVIDER", "value": "google" },
      { "name": "GEMINI_API_KEY", "value": "your-gemini-key" },
      { "name": "DAA_DB_PROVIDER", "value": "none" },
      { "name": "DAA_GIT_MODE", "value": "api" },
      { "name": "DAA_QUEUE_MODE", "value": "sync" },
      { "name": "DAA_AUTH_ENABLED", "value": "false" },
      { "name": "DAA_POLICY_ENABLED", "value": "false" },
      { "name": "GIT_HOST", "value": "https://github.com" },
      { "name": "GIT_ORG", "value": "your-github-org" },
      { "name": "GITHUB_TOKEN", "value": "ghp_xxxxxxxxxxxx" },
      { "name": "DAA_BACKEND_API_URL", "value": "http://localhost:8080" }
    ]
  }]
}
```
Put `GITHUB_TOKEN`/`GEMINI_API_KEY` in Secrets Manager and reference via `secrets` rather than plaintext `environment` for anything beyond a demo.

---

## Log Ingestion — Two Paths

DAA never scrapes logs itself; something has to push an exception to it. There are two ways in:

**1. SDK push** — `POST /logs/`
Your instrumented service calls the DAA SDK, which POSTs directly. This goes through the sliding-window escalation policy (`DAA_POLICY_ENABLED`) — a single error is logged but not escalated until the threshold in `daa policy --app ... --threshold ... --window ...` is breached, unless the content matches an immediate keyword (`FATAL`, `OOMKill`, `PANIC`, `DatabaseDeadlock`).

**2. Webhook push** — `POST /ingest/{sentry|prometheus|custom}`
For services you can't instrument (legacy systems, third-party services), point your existing alerting at DAA instead:
- `/ingest/sentry` — Sentry issue-created webhook. Verify with `SENTRY_WEBHOOK_SECRET` (HMAC on `X-Sentry-Signature`), or falls back to `DAA_API_KEY`.
- `/ingest/prometheus` — Alertmanager webhook. Auth via `DAA_API_KEY` (`X-API-Key` header or `Authorization`).
- `/ingest/custom/{integration_name}` — arbitrary JSON, field-mapped via `daa-webhook-mappings.yaml` (JSONPath), falls back to identity mapping if no file is found.

Webhook-ingested alerts skip the sliding window and escalate on the first firing event — the external system is assumed to have already thresholded before calling DAA. This is the path used in the stateless quick-start from earlier, since there's no database to hold a sliding-window count anyway.

---

## SDK — What It Does

The SDK is a thin instrumentation layer dropped into your microservice. It:
1. Wraps your exception handler / global error hook.
2. Captures the exception message, stack trace, and any context you pass in.
3. Serializes it and POSTs it to `{DAA_BACKEND_API_URL}/logs/`.
4. **Never throws** — if DAA is unreachable, it logs to stderr and swallows the failure so your app never crashes because the monitoring layer is down.

Config (env vars read by the SDK inside your app's container, not DAA's):
| Variable | Purpose |
|---|---|
| `DAA_BACKEND_API_URL` | where to POST logs (default `http://localhost:8000`) |
| `DAA_TOKEN` | app-specific bearer token from `daa register` |
| `REPO_NAME` | logical app name — must match what you registered |

Python example:
```python
from daa_sdk import DaaSdk

daa = DaaSdk()  # reads DAA_BACKEND_API_URL / DAA_TOKEN / REPO_NAME from env

try:
    process_payment(order)
except Exception as e:
    daa.capture_exception(e, context={"order_id": order.id})
    raise  # DAA doesn't swallow *your* exception, only its own send failures
```
Same pattern across the Node, Go, Java, Ruby, and .NET SDKs — capture on the native exception type, send async, fail silent.

⚠️ **One thing worth verifying before you publish this:** your SDK spec (`app/daa-sdk/specs/api-contract.md`) describes the payload as `content` being a JSON string wrapping `message`/`stack_trace`/`context`/`timestamp`. Your backend spec (`app/backend-api/specs/api-contract.md`) describes `LogCreate` as `content` being the raw traceback plus separate top-level `app_name`/`exception_type`/`trace_id` fields. Those are two different payload shapes for the same endpoint — I've written the example above to match the backend's version since that's what actually validates the request, but check your real `LogCreate` Pydantic model and pick one spec to fix.

## 8. Troubleshooting Quick Reference

| Symptom | Likely cause |
|---|---|
| PR creation 404s but branch/file reads work | Provider write-endpoint mismatch (e.g. Gitea branch creation via GitHub-style `git/refs` — see §4) |
| `dim2/dim3/dim4 fetch failed: 404` in logs | `DAA_DB_PROVIDER=none` — the `/apps/{app}/logs|metrics|recent-changes` endpoints are DB-backed and expected to 404 in stateless mode; this is cosmetic, not fatal |
| Agent can't call itself | Wrong `DAA_BACKEND_API_URL` in Image mode — must be the in-container port, not the host-mapped one |
| Auth suddenly required after switching DB provider | `DAA_AUTH_ENABLED`/`DAA_POLICY_ENABLED` default to `true` for any *persistent* `DAA_DB_PROVIDER`; set them explicitly if you want stateless-style auth behavior with a real database |
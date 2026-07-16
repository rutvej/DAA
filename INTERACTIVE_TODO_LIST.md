# DAA Master Interactive Implementation To-Do List (`v3.0`)

This interactive checklist organizes all code remediation tasks from our 10-phase forensic audit into a sequential, checkable implementation backlog. Each item includes exact target files and the **"Why It Is Needed"** justification (explaining the security risk or operational crash that occurs without the fix).

We will iterate through these **one by one**: discussing the design and exact code diff before applying changes, then checking `[x]` once verified and moving to the next task.

---

## Sprint 1: Phase 0 P0 Security & Operational Blockers (Immediate Priority)

### 🛡️ Security Blockers (P0)

- [x] **Task 1 (`[P0-SEC-1]`): Remove Host Developer Credentials & CLI Binary Volume Mounts**
  - **Target Files:** [docker-compose.yml](file:///home/rutvej/Desktop/DAA/docker-compose.yml#L80-L83) (Lines 80–83)
  - **Exact Changes:** Delete lines mounting `- /var/run/docker.sock:/var/run/docker.sock`, `- ${CODEX_AUTH_JSON_PATH}:/app/auth.json`, `- /home/rutvej/.gemini:/root/.gemini`, and `- /home/rutvej/.local/bin/agy:/usr/local/bin/agy`. Replace with isolated, container-scoped volume definitions or explicit API key environment variables (`GEMINI_API_KEY`, `DAA_GIT_TOKEN`).
  - **Why It Is Needed:** Currently, the `python-agent` container mounts the host developer's live personal OAuth tokens (`auth.json`), entire Google Antigravity configuration directory (`.gemini`), and host CLI binary (`agy`). Because the AI agent executes arbitrary tool calls (`read_file`, `subprocess`), any prompt injection from a malicious git commit or webhook allows complete exfiltration of the developer's personal credentials and full command execution on the host machine.

- [x] **Task 2 (`[P0-SEC-2]`): Restrict Overly Permissive LAN CORS Subnet Regex & Dynamic Origin Injection**
  - **Target Files:** [app/backend-api/src/main.py](file:///home/rutvej/Desktop/DAA/app/backend-api/src/main.py#L64-L67) (Lines 64–67, 93–116)
  - **Exact Changes:** Replace `CORS_ALLOW_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+)(:\d+)?$"` with a strict, configurable allowlist (`os.getenv("DAA_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080").split(",")`). Remove or harden `dynamic_cors_middleware` to prevent reflecting arbitrary registered application domains when `allow_credentials=True`.
  - **Why It Is Needed:** The LAN regex (`192.168.d+.d+`) matches any device on a local network or shared cloud VPC. Because `allow_credentials=True` is enabled, any untrusted device on the same subnet (or any attacker who registers an `application.hostname` matching `evil.com`) can steal administrative session cookies and forge cross-origin API requests against `backend-api`.

- [x] **Task 3 (`[P0-SEC-3]`): Eliminate Synthetic `admin-id` Privilege Escalation Bypasses**
  - **Target Files:** [app/backend-api/src/routers/auth.py](file:///home/rutvej/Desktop/DAA/app/backend-api/src/routers/auth.py#L69-L70) (Lines 69–70), [app/backend-api/src/routers/telemetry.py](file:///home/rutvej/Desktop/DAA/app/backend-api/src/routers/telemetry.py#L46-L61), [app/backend-api/src/routers/ingest.py](file:///home/rutvej/Desktop/DAA/app/backend-api/src/routers/ingest.py#L53)
  - **Exact Changes:** Modify `get_current_user` when `not DAA_AUTH_ENABLED` to return `"role": "readonly"` (or `"user"`) instead of `"role": "admin"`. Enforce mandatory API key / Sentry HMAC webhook verification on `POST /api/v1/self-report` and `POST /ingest/{app_id}` unconditionally.
  - **Why It Is Needed:** When authentication is toggled off (`DAA_AUTH_ENABLED=false`), the API seeds a synthetic user with `"role": "admin"`. Every protected endpoint across `/incidents`, `/fixes`, and `/applications` trusts this dictionary, granting unauthenticated network requests full administrative authority to approve automated code fixes (`/fixes/{id}/approve`), modify incident ownership, and extract third-party integration tokens.

- [x] **Task 4 (`[P0-SEC-4]`): Replace `shell=True` Command Injection Vulnerabilities with Safe Tokenized Arrays**
  - **Target Files:** [app/python-agent/agent_src/tools/execution_tool.py](file:///home/rutvej/Desktop/DAA/app/python-agent/agent_src/tools/execution_tool.py#L76-L84) (Lines 76–84), [daa](file:///home/rutvej/Desktop/DAA/daa#L752-L787) CLI
  - **Exact Changes:** In `run_tests()`, enforce `shlex.split(command)` when invoking `subprocess.run(..., shell=False, check=False)`. For all Git subprocess executions across `git_tool.py` and `orchestrator.py`, prefix arguments with the `--` end-of-options separator (`["git", "ls-remote", "--heads", "--", auth_url]`).
  - **Why It Is Needed:** `execution_tool.py` directly interpolates user/LLM-provided `test_command` strings into `subprocess.run(command, shell=True)`. If an LLM is fed a prompt injection inside a bug report (`test_command: "pytest; echo RCE && bash -c '...'"`), the shell executes the injected command with full container privileges. Similarly, missing `--` in Git commands allows Remote Code Execution via option injection (`--upload-pack=...`) (**CVE-2022-24439**).

---

### ⚙️ Operational & Production Blockers (P0)

- [x] **Task 5 (`[P0-OPS-1]`): Fix Cloud Run `K_SERVICE` Fatal Startup Crash & SQLite WAL Lock Corruption**
  - **Target Files:** [terraform/main.tf](file:///home/rutvej/Desktop/DAA/terraform/main.tf#L61-L74), [app/backend-api/src/database.py](file:///home/rutvej/Desktop/DAA/app/backend-api/src/database.py#L140-L166), [app/backend-api/src/main.py](file:///home/rutvej/Desktop/DAA/app/backend-api/src/main.py#L44-L50)
  - **Exact Changes:** In `terraform/main.tf`, add `DAA_QUEUE_MODE = "sync"` (or `"pubsub"`) and configure Cloud Run concurrency settings. In `database.py`, disable `journal_mode=WAL` when operating on ephemeral/cloud storage and enforce explicit `pool_timeout=30`. In `main.py`, prevent spawning persistent background worker threads (`python -m agent_src.main &`) inside serverless containers without `always-on` CPU allocation.
  - **Why It Is Needed:** When deployed to GCP Cloud Run (`terraform/main.tf`), the `backend-api` container starts background Python worker threads (`agent_src.main`) and attempts to write to a local instance-scoped SQLite disk (`./daa.db`). Because Cloud Run throttles CPU allocation between HTTP requests and does not support POSIX advisory locks on cloud mounts, background workers freeze mid-execution and SQLite crashes with fatal `SQLITE_BUSY: database is locked` or permanent database corruption on first scale-out.

- [x] **Task 6 (`[P0-OPS-2]`): Standardize RabbitMQ Queue Names (`fix_jobs` vs `DAA_RABBITMQ_QUEUE`)**
  - **Target Files:** [app/backend-api/src/routers/ingest.py](file:///home/rutvej/Desktop/DAA/app/backend-api/src/routers/ingest.py#L270), [app/backend-api/src/main.py](file:///home/rutvej/Desktop/DAA/app/backend-api/src/main.py#L33), [app/python-agent/agent_src/main.py](file:///home/rutvej/Desktop/DAA/app/python-agent/agent_src/main.py#L65)
  - **Exact Changes:** Replace hardcoded `"fix_jobs"` string in `ingest.py:270` with `os.getenv("DAA_RABBITMQ_QUEUE", "fix_jobs")` so both producer (`backend-api`) and consumer (`python-agent`) read/write to the exact same queue channel unconditionally.
  - **Why It Is Needed:** `ingest.py` hardcodes `channel.basic_publish(..., routing_key="fix_jobs")` when publishing incidents from log ingestion, whereas `main.py` and the Python Agent declare and listen on `os.getenv("DAA_RABBITMQ_QUEUE", "daa_jobs")`. If a user overrides `DAA_RABBITMQ_QUEUE=my_custom_queue`, incident tasks published by `ingest.py` are routed to a dead-letter `fix_jobs` queue and are permanently lost without ever triggering the AI agent.

- [x] **Task 7 (`[P0-OPS-3]`): Remove `MockSession` Silent Database Drop Mode & Enforce Fail-Fast Persistence**
  - **Target Files:** [app/backend-api/src/database.py](file:///home/rutvej/Desktop/DAA/app/backend-api/src/database.py#L54-L135) (Lines 54–135)
  - **Exact Changes:** Remove `MockSession` (`DAA_DB_PROVIDER=none`). When database credentials or paths are invalid or set to `none`, raise a hard `RuntimeError("Valid database provider required (sqlite or postgresql)")` at application startup (`get_db`).
  - **Why It Is Needed:** When `DAA_DB_PROVIDER=none` (the default in `.env.example` when Postgres/Redis are down), `MockSession` interceptors silently discard `.add()`/`.commit()` data and return `None` for all queries. Users who register (`POST /auth/register`) or submit production error logs (`POST /logs`) receive HTTP 200/202 responses indicating success, but all data is silently dropped into the void without any warning, making debugging and user onboarding impossible.

- [x] **Task 8 (`[P0-OPS-4]`): Fix MCP Client JSON-RPC Protocol Violation (`initialize` vs `tools/list`)**
  - **Target Files:** [app/backend-api/src/main.py](file:///home/rutvej/Desktop/DAA/app/backend-api/src/main.py#L155-L163) (Lines 155–163), [app/daa_mcp_server.py](file:///home/rutvej/Desktop/DAA/app/daa_mcp_server.py#L80)
  - **Exact Changes:** Modify `sync_mcp_tools()` in `main.py` to send `{"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2024-11-05", ...}}` and await `{"method": "notifications/initialized"}` *before* invoking `tools/list`.
  - **Why It Is Needed:** At startup, `sync_mcp_tools()` directly posts `{"method": "tools/list"}` to any registered external MCP server URI (`DAA_MCP_SERVER_URL`). Under the Model Context Protocol (`MCP`) specification (`2024-11-05`), all compliant servers immediately reject any request prior to handshake with `-32002 Server not initialized`, causing `sync_mcp_tools` to fail on startup.

---

## Sprint 2: Core Resilience & Architectural Unification (Phase 1 Priority)

- [x] **Task 9 (`[P1-ARCH-1]`): Unify Database Engine Configurations Across `backend-api` and `python-agent`**
  - **Target Files:** [app/backend-api/src/database.py](file:///home/rutvej/Desktop/DAA/app/backend-api/src/database.py), [app/python-agent/agent_src/tools/database_tool.py](file:///home/rutvej/Desktop/DAA/app/python-agent/agent_src/tools/database_tool.py#L30-L50), [app/daa_mcp_server.py](file:///home/rutvej/Desktop/DAA/app/daa_mcp_server.py#L40)
  - **Exact Changes:** Create a shared, unifiable connection utility (`common/db_factory.py` or standardized environment variables) enforcing identical SQLAlchemy connection pooling (`pool_pre_ping=True`, `pool_recycle=3600`) across all three Python modules.
  - **Why It Is Needed:** Currently, `backend-api`, `database_tool.py`, and `daa_mcp_server.py` each declare independent `create_engine()` pools. In SQLite mode (`./daa.db`), three uncoordinated connection pools competing over the same file cause frequent `SQLITE_BUSY` lock contentions. In PostgreSQL mode, they consume triple the required database connections, leading to `MaxConnectionsExceeded` errors.

- [x] **Task 10 (`[P1-ARCH-2]`): Consolidate Duplicated SHA-256 Fingerprinting & Ast-Deduplication Engines**
  - **Target Files:** [app/backend-api/src/routers/logs.py](file:///home/rutvej/Desktop/DAA/app/backend-api/src/routers/logs.py#L34-L55), [app/python-agent/agent_src/orchestrator.py](file:///home/rutvej/Desktop/DAA/app/python-agent/agent_src/orchestrator.py#L180-L210)
  - **Exact Changes:** Extract the normalization logic (`re.sub(r'0x[0-9a-fA-F]+', ...)`, timestamp stripping, stack frame canonicalization) into a single, canonical utility function inside `app/daa-sdk/python/` or a shared `common/fingerprint.py` module.
  - **Why It Is Needed:** Both `logs.py` (`compute_fingerprint`) and `orchestrator.py` (`RepoCacheManager` / `FingerprintDedup`) independently implement regex-based exception normalization and SHA-256 hashing. Because the regexes slightly diverge on handling hex memory addresses and Python traceback paths, the same exception can generate Hash A in `backend-api` and Hash B when re-evaluated in `python-agent`, breaking deduplication and triggering duplicate PR fixes.

- [x] **Task 10B (`[P1-ARCH-3]`): Implement Redis & Upstash Persistent Storage Provider (`DAA_DB_PROVIDER=redis`)**
  - **Target Files:** [app/backend-api/src/database.py](file:///home/rutvej/Desktop/DAA/app/backend-api/src/database.py), new `app/backend-api/src/redis_storage.py`
  - **Exact Changes:** Implement a Redis session adapter (`StatelessRedisSession` or hash/JSON storage engine using `redis-py` or Upstash HTTP REST SDK) when `DAA_DB_PROVIDER` is set to `internal-redis`, `external-redis`, or `upstash`. Ensure persistent storage operations (`add`, `query`, `commit`) serialize and retrieve entity records (Applications, Incidents, Logs, Policies) using Redis key-value/hash structures (`daa:app:{id}`, `daa:incident:{fingerprint}`).
  - **Why It Is Needed:** For serverless and high-throughput stateless container deployments (such as Cloud Run or AWS Lambda), SQLite suffers from disk locks and PostgreSQL connection pools can saturate. Providing a native Redis/Upstash backend option allows ultra-low-latency persistent state storage across distributed, stateless container replicas without requiring heavy relational database infrastructure.

- [x] **Task 11 (`[P1-RES-1]`): Add Exponential Backoff & Circuit Breakers to LLM & Git API Providers**
  - **Target Files:** [app/python-agent/agent_src/llm_config.py](file:///home/rutvej/Desktop/DAA/app/python-agent/agent_src/llm_config.py#L45-L90), [app/python-agent/agent_src/git_api_providers.py](file:///home/rutvej/Desktop/DAA/app/python-agent/agent_src/git_api_providers.py#L110-L160)
  - **Exact Changes:** Wrap `get_chat_completion()` and all `CloneFreeGitClient` HTTP requests (`requests.post/get`) with `tenacity` retry decorators (`@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(requests.exceptions.RequestException))`).
  - **Why It Is Needed:** Network calls to Google Gemini, GitHub API, and GitLab API currently execute without automatic retries or circuit breakers. A transient 502 Bad Gateway from Google Cloud or GitHub rate-limit (`403 Secondary Rate Limit`) instantly kills the long-running ReAct agent loop mid-thought, wasting all consumed input tokens and leaving the ticket in an unrecoverable `investigating` zombie state.

- [x] **Task 12 (`[P1-SEC-5]`): Restrict Arbitrary Host Path Traversal in `file_system_tool.py` & `code_nav_tool.py`**
  - **Target Files:** [app/python-agent/agent_src/tools/file_system_tool.py](file:///home/rutvej/Desktop/DAA/app/python-agent/agent_src/tools/file_system_tool.py#L43-L53), [app/python-agent/agent_src/tools/code_nav_tool.py](file:///home/rutvej/Desktop/DAA/app/python-agent/agent_src/tools/code_nav_tool.py#L51-L55)
  - **Exact Changes:** In `get_full_path(relative_path)`, enforce `real_path = os.path.realpath(os.path.join(WORKSPACE_DIR, relative_path))` and verify `if not real_path.startswith(os.path.realpath(WORKSPACE_DIR)): raise PermissionError("Path traversal denied")`.
  - **Why It Is Needed:** `get_full_path` currently checks if `file_path.startswith("/tmp") or file_path.startswith("/home")` and returns the raw path directly without checking for directory traversal (`..`). Any tool call requesting `../../etc/passwd` or `/home/rutvej/.ssh/id_rsa` can read or overwrite any file across the entire container or host filesystem.

---

## Sprint 3: Observability, UI Polish & WOW Factor Enhancement (Phase 2 Priority)

- [ ] **Task 13 (`[P2-OBS-1]`): Standardize Structured JSON Logging & OpenTelemetry Trace Propagation**
  - **Target Files:** [app/backend-api/src/main.py](file:///home/rutvej/Desktop/DAA/app/backend-api/src/main.py), [app/python-agent/agent_src/orchestrator.py](file:///home/rutvej/Desktop/DAA/app/python-agent/agent_src/orchestrator.py)
  - **Exact Changes:** Configure `python-json-logger` as the default log formatter and inject `trace_id` (UUIDv4 generated at log ingestion or webhook receipt) into `ReActThought` log payloads and RabbitMQ message headers (`properties=pika.BasicProperties(headers={'trace_id': trace_id})`).
  - **Why It Is Needed:** Logs across `backend-api` and `python-agent` currently output as uncoordinated, multi-line plaintext console prints (`print(f"[{time}] Running...")`). When multiple concurrent incident jobs run across scaled container instances, console logs interleave chaotically, making it impossible to correlate an incoming log alert (`POST /logs`) to its corresponding AI thought steps or final Git PR.

- [ ] **Task 14 (`[P2-WOW-1]`): Build Real-Time ReAct Thought Streaming WebSocket Terminal (`ReAct Streamer`)**
  - **Target Files:** [app/backend-api/src/routers/status.py](file:///home/rutvej/Desktop/DAA/app/backend-api/src/routers/status.py), [app/admin-panel/src/pages/IncidentsPage.js](file:///home/rutvej/Desktop/DAA/app/admin-panel/src/pages/IncidentsPage.js)
  - **Exact Changes:** Add a WebSocket endpoint `WS /api/v1/incidents/{id}/stream` in `status.py` that subscribes to RabbitMQ `thought_stream` events or redis/db thought updates. In `IncidentsPage.js`, render a dark-mode "Live ReAct Terminal" drawer that streams each step (`[Thought] -> [Tool Call] -> [Observation]`) with syntax highlighting and latency timers.
  - **Why It Is Needed:** Currently, the Admin Panel (`IncidentsPage.js`) only polls `GET /incidents/` every 10 seconds and displays static text (`status: investigating`). By making the AI's internal reasoning loop visible in real-time, developers and SREs gain immediate trust in what the agent is doing and experience the true **"WOW Factor"** of autonomous self-healing.

- [ ] **Task 15 (`[P2-WOW-2]`): Implement Interactive Human-in-the-Loop (`HITL`) Intercept & Patch Editor**
  - **Target Files:** [app/admin-panel/src/pages/FixesPage.js](file:///home/rutvej/Desktop/DAA/app/admin-panel/src/pages/FixesPage.js) (or `IncidentsPage.js`), [app/backend-api/src/routers/fixes.py](file:///home/rutvej/Desktop/DAA/app/backend-api/src/routers/fixes.py#L191)
  - **Exact Changes:** In the Admin Panel UI, add an "Intercept / Edit Patch" button on active incident drawers that opens a split-screen diff editor (`Monaco` or `Prism.js`). In `fixes.py`, add `PATCH /api/v1/fixes/{id}/modify` allowing developers to tweak the AI-generated patch before clicking "Approve & Merge".
  - **Why It Is Needed:** When DAA generates a code fix (`/fixes/{id}`), developers currently only have binary options: `Approve` or `Reject`. Giving engineers the ability to perform minor tweaks (e.g. updating a comment or adjusting a timeout threshold) directly inside the DAA UI without checking out the branch locally dramatically reduces time-to-resolution.

- [ ] **Task 15B (`[P2-MCP-1]`): Build External-Facing Hybrid MCP Server (`stdio + HTTP/SSE`) for Multi-Agent Collaboration & PR Continuation**
  - **Target Files:** [app/daa_mcp_server.py](file:///home/rutvej/Desktop/DAA/app/daa_mcp_server.py), new `app/backend-api/src/routers/mcp_gateway.py`
  - **Exact Changes:**
    1. **Tool Exposure:** Expose specialized tools for external AI agents (Claude Desktop, Cursor, external review agents) to connect and continue work on an existing issue/PR: `get_incident_context_for_pr(pr_url)` (returns 4-DIM preflight telemetry & postmortem), `fetch_pull_request_diff(pr_url)` (returns current patch diff), `submit_pr_review_comments(pr_url, comments)` (posts surgical feedback), and `trigger_reinvestigation(pr_url, additional_context)`.
    2. **Dual-Mode Transport:** In Full-Stack Mode, run as a stdio server (`python -m app.daa_mcp_server`). In Serverless Mode (Cloud Run), expose an HTTP/SSE bridge (`POST /api/v1/mcp/message` & `GET /api/v1/mcp/sse`) in `backend-api` via FastAPI `EventSourceResponse` so external agents connect over standard REST/SSE endpoints without needing local container access.
    3. **No-Auth Security Safeguards:** When `DAA_AUTH_ENABLED=false` (or on public serverless instances), enforce a strict **Read-Only by Default** model. Inspection tools (`get_incident_context_for_pr`, `fetch_pull_request_diff`) are accessible publicly for triage, but mutating tools (`approve_remediation_fix`, `submit_pr_review_comments`, `trigger_reinvestigation`) require a signed HMAC action token (`?hmac=...` generated at incident ingestion) or explicit UI approval. Never expose arbitrary filesystem or shell tools over the external MCP gateway.
  - **Why It Is Needed:** Currently, DAA operates as a siloed AI agent that pushes a PR and stops. By providing a secure, hybrid MCP server with explicit PR continuation tools, external coding agents or developers using Claude/Cursor can seamlessly attach to an ongoing DAA investigation, review its 4-DIM diagnostic context, and collaborate iteratively on the fix across both local and serverless deployments without introducing unauthenticated remote execution risks.

---

## Sprint 4: Technical Debt Cleanup & Comprehensive Test Suite (Phase 3 Priority)

- [ ] **Task 16 (`[P3-DEBT-1]`): Remove Dead Code & Deprecated Router/Tool Stubs**
  - **Target Files:** [app/backend-api/src/routers/projects.py](file:///home/rutvej/Desktop/DAA/app/backend-api/src/routers/projects.py#L24-L33) (`cleartext token serialization`), [app/python-agent/agent_src/tools/search_tool.py](file:///home/rutvej/Desktop/DAA/app/python-agent/agent_src/tools/search_tool.py)
  - **Exact Changes:** Remove `repo_token` and `jira_token` cleartext fields from `GET /projects` JSON schemas (`ProjectResponse`). Delete unused or broken tool stubs that return hardcoded `NotImplemented` or mock data.
  - **Why It Is Needed:** Serializing `repo_token` and `jira_token` in cleartext on `GET /projects` leaks sensitive third-party integration secrets to any authenticated user viewing the dashboard. Furthermore, retaining dead or placeholder tools clutters the LLM's tool definition schema, increasing token costs and causing hallucinations during tool selection.

- [ ] **Task 17 (`[P3-TEST-1]`): Implement Comprehensive Zero-Cloud Pytest Test Suite (`test_v3_platform.py`)**
  - **Target Files:** [app/backend-api/tests/test_v2_platform.py](file:///home/rutvej/Desktop/DAA/app/backend-api/tests/test_v2_platform.py), new `app/backend-api/tests/test_v3_platform.py`
  - **Exact Changes:** Create `test_v3_platform.py` using `pytest` fixtures with in-memory SQLite (`sqlite:///:memory:`), mock RabbitMQ (`unittest.mock.MagicMock` for `pika.BlockingConnection`), wiremocked Gemini API (`responses` or `respx`), and mock Git subprocess calls (`git.Repo.init`). Test:
    1. Authentication enforcement (`DAA_AUTH_ENABLED=true` rejecting unauthenticated requests with `401`).
    2. CORS allowlist verification (`Origin: http://evil.com` rejected with `400/403`).
    3. End-to-end cryptographic deduplication (`compute_fingerprint` matching).
    4. Safe subprocess argument splitting (`shlex.split` verification).
  - **Why It Is Needed:** Existing unit tests (`test_v2_platform.py`) cover only ~21.7% of core routing logic and rely on external services (`mock_pika`). A comprehensive, deterministic, zero-cloud integration test suite guarantees that none of the P0/P1 security and operational regressions ever recur.

---

## 🚀 How We Will Proceed

We will start with **Task 1 (`[P0-SEC-1]`: Remove Host Developer Credentials & CLI Binary Volume Mounts from `docker-compose.yml`)**.

Before writing code for Task 1, let's discuss:
1. **The exact lines to remove (`docker-compose.yml:L80-L83`):** `- /var/run/docker.sock`, `- ${CODEX_AUTH_JSON_PATH}:/app/auth.json`, `- /home/rutvej/.gemini:/root/.gemini`, and `- /home/rutvej/.local/bin/agy:/usr/local/bin/agy`.
2. **How to pass required API tokens safely instead:** We will verify that `docker-compose.yml` passes `${GEMINI_API_KEY}` and `${DAA_GIT_TOKEN}` cleanly via `environment:` rather than mounting entire host directories or system binaries.

**Are you ready to discuss and execute Task 1 (`[P0-SEC-1]`)?**

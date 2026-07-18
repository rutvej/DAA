# Phase 3: Comprehensive DAA Repository Integration Audit Matrix

**Audit Date:** July 14, 2026  
**Auditor:** SRE Integration Audit Specialist (Phase 3)  
**Target Repository:** `/home/rutvej/Desktop/DAA`  
**Methodology:** Strict code and configuration inspection. No assumptions made from docstrings, README files, or architectural diagrams. All entries verified directly against the underlying Python implementation (`llm_config.py`, `git_api_providers.py`, `git_tool.py`, `database.py`, `log_connectors.py`, `main.py`, `daa_mcp_server.py`, `webhook.py`, `auth.py`, `auth_helper.py`, and `docker-compose.yml`).

---

## Executive Summary & Architectural Overview

The DAA (Dynamic Autonomous SRE Agent) platform operates via a multi-tier, hybrid integration architecture designed to ingest real-time error telemetry, triage incidents using artificial intelligence, execute deterministic SRE diagnostics across local worktrees or remote Git APIs, and deliver actionable remediation pull requests and tickets.

During this Phase 3 audit, exactly **27 distinct integrations** across **8 core categories** were identified and inspected. Below is a summary of verified integration health and confidence across the codebase:

| Category | Total Integrations | Fully Functional / High Confidence | Medium Confidence (Config/Transport Caveats) | Low Confidence / Stubbed Logic |
| :--- | :---: | :---: | :---: | :---: |
| **1. LLM & AI Providers** | 6 | 4 (`gemini`, `openai`, `anthropic`, `ollama`) | 2 (`codex` auth bridge, `agy` CLI subprocess) | 0 |
| **2. Git Providers & VCS** | 5 | 4 (`github`, `gitlab`, `bitbucket`, `gitea`) | 1 (`CloneFreeGitClient` local worktree race) | 0 |
| **3. MCP Architecture** | 2 | 0 | 2 (`SimpleMcpClient`, `daa_mcp_server.py`) | 0 |
| **4. Message Queues & DBs** | 5 | 3 (`postgres`, `sqlite`, `sync` inline) | 1 (`rabbitmq` queue name mismatch) | 1 (`redis` / `MockSession` stub) |
| **5. Logging & Monitoring** | 6 | 6 (`cloudwatch`, `gcp`, `datadog`, `prometheus`, `sentry`, `webhook`) | 0 | 0 |
| **6. Ticketing & Tracking** | 3 | 2 (`jira`, `github_issues`) | 0 | 1 (`local` URL mock `DAA://INC-...`) |
| **7. Runtime & Containers** | 3 | 2 (`docker.sock` execution, `auth.json`) | 1 (`agy` / `.gemini` host coupling) | 0 |
| **8. Security & Auth** | 2 | 1 (`allowed_ip` / role check) | 1 (`handle_request_with_retry` hardcoded login) | 0 |
| **TOTALS** | **32 (27 unique)** | **22** | **8** | **2** |

---

## Detailed Integration Audit Matrix

### Category 1: LLM & AI Providers

#### 1. Google Gemini (`RateLimitedGemini` / `ChatGoogleGenerativeAI`)
- **Integration Name:** Google Gemini (Official API Integration)
- **Purpose:** Primary/default Large Language Model provider (`agent_executor`) for autonomous incident triage, root cause diagnosis, and code diff generation (`LLM_PROVIDER="gemini"`).
- **Files Involved:**
  - `app/python-agent/agent_src/llm_config.py:107-164` (`RateLimitedGemini` class definition & initialization)
  - `docker-compose.yml:81` (`GEMINI_API_KEY` injection)
- **Configuration Required:**
  - `LLM_PROVIDER="gemini"` (or `"google"`)
  - `GEMINI_API_KEY` (or `GOOGLE_API_KEY`)
  - `LLM_MODEL` (default: `"gemini-1.5-pro"`)
  - `GEMINI_MAX_RETRIES` (default: `5`)
  - `GEMINI_INITIAL_BACKOFF` (default: `2.0` seconds)
- **Can it be tested without external infrastructure/credentials?** **No.** Requires a valid Google Cloud/Gemini API key and outbound HTTPS connectivity to `generativelanguage.googleapis.com`.
- **Confidence Level:** **High**.
- **Why (Auditor Rationale):** The implementation wraps LangChain's `ChatGoogleGenerativeAI` in a custom `RateLimitedGemini` proxy class that explicitly catches `ResourceExhausted` exceptions (`429 Too Many Requests`) and applies exponential backoff up to `GEMINI_MAX_RETRIES` before failing.
- **Known Problems / Limitations:** During severe API rate-limiting, `RateLimitedGemini` sleeps synchronously on the calling thread (`time.sleep(backoff)`). If retries reach high backoff values (`2s -> 4s -> 8s -> 16s -> 32s`), the blocking sleep delays RabbitMQ message acknowledgments (`basic_ack`), potentially causing RabbitMQ broker connection closures (`ConnectionClosedByBroker`) due to missed heartbeat frames on synchronous consumers.
- **Missing Pieces / Stubbed Logic:** Fully implemented.

#### 2. Google Antigravity CLI Subprocess Driver (`AgyChatModel`)
- **Integration Name:** Google Antigravity CLI (`agy`) Subprocess Bridge
- **Purpose:** Invokes a local Google Antigravity CLI binary (`agy`) via system subprocess to generate LLM responses (`LLM_PROVIDER="agy"`), allowing agents to run inside containers without exposing raw API keys by leveraging host-level OAuth login state.
- **Files Involved:**
  - `app/python-agent/agent_src/llm_config.py:225-290` (`AgyChatModel` class & `_generate` method)
  - `docker-compose.yml:82-83` (`/home/rutvej/.local/bin/agy:/usr/local/bin/agy:ro` and `/home/rutvej/.gemini:/root/.gemini:ro`)
- **Configuration Required:**
  - `LLM_PROVIDER="agy"`
  - Host binary mounted at `/usr/local/bin/agy`
  - Host authentication state mounted at `/root/.gemini`
- **Can it be tested without external infrastructure/credentials?** **Yes**, provided the host machine running Docker has the `agy` CLI installed and authenticated (`~/.gemini`). If run without internet access, the CLI itself handles offline/cache behavior.
- **Confidence Level:** **Medium**.
- **Why (Auditor Rationale):** `AgyChatModel` inherits from `BaseChatModel` and successfully executes `subprocess.run(["agy", "-p", prompt], capture_output=True, text=True, check=True)` to retrieve output.
- **Known Problems / Limitations:**
  1. **Concatenated Text Prompting:** `_generate` flattens the entire chat message history (`SystemMessage`, `HumanMessage`, `AIMessage`) into a single plaintext string (`Prompt: {m.content}\nAnswer: {m.content}`).
  2. **OS Argument Length Exceeded:** The concatenated prompt string is passed directly as a command-line argument (`-p <prompt>`). If the chat history or stack trace exceeds Linux `MAX_ARG_STRLEN` (~128KB), `subprocess.run` fails with `OSError: [Errno 7] Argument list too long`.
  3. **No Streaming or Tool-Call Schemas:** Does not support LangChain `bind_tools` structured outputs or token streaming.
- **Missing Pieces / Stubbed Logic:** Function calling and tool schemas (`tool_calls`) are completely unsupported in this wrapper; tool requests degrade to raw text generation.

#### 3. OpenAI & OpenAI-Compatible REST Endpoints (`ChatOpenAI`)
- **Integration Name:** OpenAI / Custom OpenAI-Compatible API (`ChatOpenAI`)
- **Purpose:** Direct integration with OpenAI (`gpt-4o`, `gpt-4`) or any OpenAI-compatible server (e.g., Azure OpenAI, vLLM, LocalAI) when `LLM_PROVIDER="openai"`.
- **Files Involved:**
  - `app/python-agent/agent_src/llm_config.py:73-88`
- **Configuration Required:**
  - `LLM_PROVIDER="openai"`
  - `OPENAI_API_KEY`
  - `LLM_MODEL` (default: `"gpt-4o"`)
  - Optional: `OPENAI_API_BASE` (or `OPENAI_BASE_URL`) for custom endpoint targeting
- **Can it be tested without external infrastructure/credentials?** **No** (if connecting to official `api.openai.com`). **Yes** (if `OPENAI_API_BASE` is pointed to a local mock or Ollama instance).
- **Confidence Level:** **High**.
- **Why (Auditor Rationale):** Standard, clean usage of `langchain_openai.ChatOpenAI` initialized with explicit timeout (`timeout=60`).
- **Known Problems / Limitations:** Lacks the custom exponential backoff wrapper seen in `RateLimitedGemini`; rate limits or 5xx server errors surface immediately as exceptions to the agent safety wrapper.
- **Missing Pieces / Stubbed Logic:** Fully implemented.

#### 4. Anthropic (`ChatAnthropic`)
- **Integration Name:** Anthropic Claude API (`ChatAnthropic`)
- **Purpose:** Direct integration with Anthropic Claude models (`claude-3-5-sonnet-20241022`, `claude-3-opus`) when `LLM_PROVIDER="anthropic"`.
- **Files Involved:**
  - `app/python-agent/agent_src/llm_config.py:90-104`
- **Configuration Required:**
  - `LLM_PROVIDER="anthropic"`
  - `ANTHROPIC_API_KEY`
  - `LLM_MODEL` (default: `"claude-3-5-sonnet-20241022"`)
- **Can it be tested without external infrastructure/credentials?** **No.** Requires a valid Anthropic API key and connection to `api.anthropic.com`.
- **Confidence Level:** **High**.
- **Why (Auditor Rationale):** Correctly delegates to `langchain_anthropic.ChatAnthropic(model_name=model, anthropic_api_key=api_key)`.
- **Known Problems / Limitations:** If `langchain-anthropic` python package is uninstalled, `get_llm()` throws `ImportError` at runtime.
- **Missing Pieces / Stubbed Logic:** Fully implemented.

#### 5. Ollama / Local Open-Source LLMs (`ChatOllama`)
- **Integration Name:** Ollama Local LLM Inference (`ChatOllama`)
- **Purpose:** Enables fully local, on-premise AI inference (`llama3`, `mistral`, `codellama`, `deepseek-coder`) over HTTP when `LLM_PROVIDER="ollama"`.
- **Files Involved:**
  - `app/python-agent/agent_src/llm_config.py:166-179`
- **Configuration Required:**
  - `LLM_PROVIDER="ollama"`
  - `OLLAMA_BASE_URL` (default: `"http://host.docker.internal:11434"`)
  - `LLM_MODEL` (default: `"llama3"`)
- **Can it be tested without external infrastructure/credentials?** **Yes.** Runs entirely locally without cloud credentials or internet connectivity.
- **Confidence Level:** **High**.
- **Why (Auditor Rationale):** Uses `langchain_community.chat_models.ChatOllama` with configurable base URL and temperature.
- **Known Problems / Limitations:** The default `http://host.docker.internal:11434` requires Docker extra-hosts (`host.docker.internal:host-gateway` in `docker-compose.yml:95`). Local open-source models (e.g. `llama3:8b`) often fail to adhere strictly to complex LangChain multi-tool calling JSON schemas compared to GPT-4o or Gemini 1.5 Pro.
- **Missing Pieces / Stubbed Logic:** Fully implemented.

#### 6. Codex / ChatGPT Subscription Token Bridge (`CodexChatModel`)
- **Integration Name:** Codex / ChatGPT Subscription JWT Bridge (`CodexChatModel`)
- **Purpose:** Allows DAA to reuse a developer's existing ChatGPT/Codex subscription authentication token stored in `auth.json` (`/app/auth.json`) without consuming paid OpenAI API credits when `LLM_PROVIDER="codex"`.
- **Files Involved:**
  - `app/python-agent/agent_src/llm_config.py:29-71` (`CodexChatModel` & `_load_api_key`)
  - `docker-compose.yml:86` (`${CODEX_AUTH_JSON_PATH:-/home/rutvej/snap/codex/34/auth.json}:/app/auth.json:ro`)
- **Configuration Required:**
  - `LLM_PROVIDER="codex"`
  - Mounted `/app/auth.json` file containing either `OPENAI_API_KEY` or `"tokens": {"access_token": "..."}`
  - Optional: `OPENAI_API_BASE` (`https://api.openai.com/v1`)
- **Can it be tested without external infrastructure/credentials?** **Yes**, if a local `auth.json` containing a valid token is present on disk.
- **Confidence Level:** **Medium**.
- **Why (Auditor Rationale):** `_load_api_key` parses `/app/auth.json` and extracts `access_token` or `OPENAI_API_KEY`, initializing a raw `openai.OpenAI(api_key=api_key, base_url=api_base)` client.
- **Known Problems / Limitations:**
  1. **Token Expiry & User-Agent Filtering:** Internal ChatGPT `access_token` JWTs expire frequently. Furthermore, undocumented OpenAI API endpoints may reject standard `OpenAI-Python` User-Agent headers if not authenticated via official OAuth endpoints.
  2. **No Tool/Function Calling Support:** Like `AgyChatModel`, `CodexChatModel._generate` strips structured messages (`AIMessage`, `SystemMessage`) to plain text (`msg.content`) and invokes `self.client.chat.completions.create(model=..., messages=formatted_messages)`. It does not support LangChain tool schemas (`bind_tools`).
- **Missing Pieces / Stubbed Logic:** Tool/function calling is stripped; falls back to text-only completion.

---

### Category 2: Git Providers & VCS

#### 1. GitHub REST API (`GitHubProvider` & `create_pr_on_provider`)
- **Integration Name:** GitHub REST API v3 Integration
- **Purpose:** Provides stateless file reading (`get_file_content`), atomic multi-file commit authoring via Git Trees (`create_branch_with_changes`), Pull Request creation (`create_pull_request`), and PR diff reading (`get_pull_request_details`) across `git_api_providers.py` (Agent), `git_provider.py` (Dashboard PR Reader), and `fixes.py` (Backend Fix Approver).
- **Files Involved:**
  - `app/python-agent/agent_src/tools/git_api_providers.py:133-289` (`GitHubProvider`)
  - `app/backend-api/src/routers/git_provider.py:38-76` (`fetch_github_pr`)
  - `app/backend-api/src/routers/fixes.py:100-142` (`create_pr_on_provider` GitHub branch)
- **Configuration Required:**
  - `GITHUB_TOKEN` (or `repo_token` in `ProjectConnection`)
  - `DAA_REPO_URL` (or `GITHUB_REPO` in format `owner/repo`)
- **Can it be tested without external infrastructure/credentials?** **No.** Requires valid GitHub Personal Access Token (`repo` scope) and HTTPS access to `api.github.com`.
- **Confidence Level:** **High**.
- **Why (Auditor Rationale):** `create_branch_with_changes` correctly uses the GitHub Git Data API (`POST /git/blobs`, `POST /git/trees`, `POST /git/commits`, `PATCH /git/refs/heads/...`) to construct multi-file commits atomically without requiring a local `git clone`.
- **Known Problems / Limitations:**
  1. **Branch Protection & Signed Commits:** Because commits are constructed via REST API, they are signed by GitHub's web flow (or unsigned depending on token type). If repository branch protection rules enforce strict GPG/SSH commit signing or required status checks before PR opening, the tree update or PR creation fails with `403 Forbidden` or `422 Unprocessable Entity`.
  2. **Hardcoded Base Branch Fallback (`fixes.py:133-140`):** When creating a PR via `fixes.py`, it first attempts `base="master"`. If that returns `422/404`, it falls back (`res_fallback`) to `base="main"`. If the repository default branch is named `develop` or `trunk`, both attempts fail without querying `GET /repos/{owner}/{repo}` for the actual `default_branch`.
- **Missing Pieces / Stubbed Logic:** Fully implemented.

#### 2. GitLab SaaS & Self-Hosted API (`GitLabProvider` & `create_pr_on_provider`)
- **Integration Name:** GitLab REST API v4 Integration
- **Purpose:** Stateless file reading (`get_file_content`), atomic multi-action commits (`create_branch_with_changes`), Merge Request creation (`create_pull_request`), and MR reading for GitLab SaaS (`gitlab.com`) and self-hosted instances.
- **Files Involved:**
  - `app/python-agent/agent_src/tools/git_api_providers.py:292-497` (`GitLabProvider`)
  - `app/backend-api/src/routers/git_provider.py:79-114` (`fetch_gitlab_mr`)
  - `app/backend-api/src/routers/fixes.py:144-189` (`create_pr_on_provider` GitLab branch)
- **Configuration Required:**
  - `GITLAB_PRIVATE_TOKEN` (or `GITLAB_TOKEN` / `repo_token`)
  - `GITLAB_HOST` (or `GITLAB_URL`, default: `"gitlab.com"` or `"gitlab"`)
  - `DAA_REPO_URL` (or `user/repo` path)
- **Can it be tested without external infrastructure/credentials?** **No** for `gitlab.com`; **Yes** if targeted at a local Docker-hosted GitLab container (`GITLAB_HOST=gitlab:80`).
- **Confidence Level:** **High**.
- **Why (Auditor Rationale):** `create_branch_with_changes` utilizes GitLab's multi-file commit endpoint (`POST /api/v4/projects/{id}/repository/commits`) with `actions: [{"action": "update"/"create", "file_path": path, "content": content}]`.
- **Known Problems / Limitations:**
  - **Nested Subgroup Path Encoding Bug:** In both `GitLabProvider.__init__` (`git_api_providers.py:302`) and `fixes.py:154`, the project ID is derived by URL-encoding `f"{self.user}/{self.repo}"` (`urllib.parse.quote_plus(f"{gl_user}/{app_name}")`). If a GitLab project lives inside a nested subgroup hierarchy (`group/subgroup/team/app_name`), splitting on user/repo or assuming `gl_user/app_name` results in an invalid project ID, causing all API calls to fail with `404 Project Not Found`.
- **Missing Pieces / Stubbed Logic:** Fully implemented.

#### 3. Bitbucket Cloud API (`BitbucketProvider`)
- **Integration Name:** Bitbucket Cloud REST API v2.0 Integration
- **Purpose:** Stateless file reading (`get_file_content`), commit authoring via form-data upload (`create_branch_with_changes`), and PR creation (`create_pull_request`) for Bitbucket Cloud (`api.bitbucket.org`).
- **Files Involved:**
  - `app/python-agent/agent_src/tools/git_api_providers.py:499-693` (`BitbucketProvider`)
- **Configuration Required:**
  - `BITBUCKET_USERNAME`
  - `BITBUCKET_APP_PASSWORD`
  - `DAA_REPO_URL` (or `workspace/repo_slug`)
- **Can it be tested without external infrastructure/credentials?** **No.** Requires Bitbucket Cloud app credentials and connectivity to `api.bitbucket.org`.
- **Confidence Level:** **High**.
- **Why (Auditor Rationale):** Correctly posts multi-part form data to `/2.0/repositories/{workspace}/{repo_slug}/src` (`files = {p: c for p, c in changes.items()}`) to create commits and branches.
- **Known Problems / Limitations:** Bitbucket's `/src` endpoint requires submitting raw file bodies via `multipart/form-data`. If `changes` contains large binaries or hundreds of files, `requests.post` memory overhead and network payload size can trigger timeout or `413 Payload Too Large` from Bitbucket edge proxies.
- **Missing Pieces / Stubbed Logic:** Fully implemented.

#### 4. Self-Hosted Gitea API (`GiteaProvider`)
- **Integration Name:** Gitea REST API v1 Integration
- **Purpose:** Stateless file reading (`get_file_content`), branch authoring (`create_branch_with_changes`), and Pull Request creation (`create_pull_request`) against self-hosted Gitea instances (`api/v1/repos/...`).
- **Files Involved:**
  - `app/python-agent/agent_src/tools/git_api_providers.py:695-950` (`GiteaProvider`)
  - `app/backend-api/src/routers/fixes.py:106-140` (Gitea PR creation sharing GitHub URL structure)
- **Configuration Required:**
  - `GITEA_TOKEN`
  - `GITEA_URL` (or `DAA_REPO_URL`)
- **Can it be tested without external infrastructure/credentials?** **No** for real remote servers; **Yes** when tested against a local Gitea container (`GITEA_URL=http://gitea:3000`).
- **Confidence Level:** **High**.
- **Why (Auditor Rationale):** Handles Gitea API operations cleanly, utilizing tree/blob creation when available.
- **Known Problems / Limitations:**
  - **Non-Atomic Sequential File Commits:** In `create_branch_with_changes` (`git_api_providers.py:808-888`), the provider first creates the branch (`POST /api/v1/repos/{owner}/{repo}/branches`), and then iterates over `changes.items()`, sending individual `PUT` or `POST` requests to `/api/v1/repos/{owner}/{repo}/contents/{file_path}` for *each individual file*. Because older versions of Gitea lack a multi-file commit endpoint, modifying 10 files results in **10 separate sequential commits** on the branch rather than 1 atomic commit.
- **Missing Pieces / Stubbed Logic:** Fully implemented.

#### 5. Local / Hybrid Clone-Free Git Client (`CloneFreeGitClient` & `git_tool.py`)
- **Integration Name:** Hybrid Git Client (`CloneFreeGitClient` & `git_tool.py`)
- **Purpose:** Abstraction layer enabling SRE agent tools (`read_file_content`, `create_branch`, `commit_changes`, `push_changes`, `open_pull_request`) to operate transparently across both local subprocess Git checkouts (`DAA_GIT_MODE="local"`) and API-driven stateless operations (`DAA_GIT_MODE="api"` via `CloneFreeGitClient`).
- **Files Involved:**
  - `app/python-agent/agent_src/tools/git_tool.py:10-230`
  - `app/python-agent/agent_src/tools/clonefree_client.py:1-120`
- **Configuration Required:**
  - `DAA_GIT_MODE="local"` or `"api"`
  - `DAA_REPO_URL`
  - `/usr/bin/git` binary (if `local`) or API tokens (`GITHUB_TOKEN`, `GITLAB_PRIVATE_TOKEN` if `api`)
- **Can it be tested without external infrastructure/credentials?** **Yes.** When `DAA_GIT_MODE="local"`, tools can run against local file-based Git repositories (`file:///path/to/repo.git`) without external APIs.
- **Confidence Level:** **High**.
- **Why (Auditor Rationale):** `git_tool.py` checks `DAA_GIT_MODE == "api"` and delegates directly to `CloneFreeGitClient`, otherwise executes `subprocess.run(["git", ...], cwd=temp_dir)`.
- **Known Problems / Limitations:**
  - **Shared `/tmp/{app_name}` Race Condition (Non-Worktree Mode):** In `git_tool.py:150` (`clone_repo`), when running in `local` mode outside of the DAA 3.0 worktree orchestrator (`PostflightOrchestrator`), `temp_dir` is hardcoded to `/tmp/{app_name}` (`temp_dir = f"/tmp/{app_name}"`). If multiple parallel background jobs run for the same application simultaneously, they will race, overwrite, and corrupt each other's `.git` index in `/tmp/{app_name}`! (Note: DAA 3.0 orchestrator (`orchestrator.py:350-420`) mitigates this by creating isolated worktrees under `/tmp/daa/worktrees/{incident_id}`, but direct tool calls by agents or fallback mode remain vulnerable).
- **Missing Pieces / Stubbed Logic:** Fully implemented.

---

### Category 3: MCP (Model Context Protocol) Architecture

#### 1. DAA MCP Subprocess Client (`SimpleMcpClient` & `load_mcp_tools`)
- **Integration Name:** DAA MCP JSON-RPC Client (`SimpleMcpClient`)
- **Purpose:** Dynamically discovers (`tools/list`), wraps (`make_wrapper`), and executes (`tools/call`) external Model Context Protocol (MCP) server tools over stdio (`stdin`/`stdout` subprocess pipes) configured via `DAA_MCP_SERVERS` JSON environment variable.
- **Files Involved:**
  - `app/python-agent/agent_src/main.py:147-255` (`SimpleMcpClient`, `send_request`, & `load_mcp_tools`)
- **Configuration Required:**
  - `DAA_MCP_SERVERS` JSON string (e.g., `{"sqlite": {"command": "uvx", "args": ["mcp-server-sqlite", "--db-path", "/test.db"]}}`)
- **Can it be tested without external infrastructure/credentials?** **Yes**, works with local stdio server binaries (`python3 daa_mcp_server.py`) without cloud credentials.
- **Confidence Level:** **Medium**.
- **Why (Auditor Rationale):** Spawns child processes via `subprocess.Popen([command] + args, stdin=PIPE, stdout=PIPE, text=True)` and successfully exchanges JSON-RPC 2.0 messages (`{"jsonrpc": "2.0", "method": ..., "id": ...}`).
- **Known Problems / Limitations:**
  1. **Protocol Specification Violation (`initialize` Handshake Omitted):** Official MCP 2024-11-05 Specification requires every client to send an `initialize` request and receive a `capabilities` response before sending `notifications/initialized` or calling `tools/list`. `SimpleMcpClient.start()` (`main.py:155-163`) immediately sends `client.send_request("tools/list", id=1)` upon spawning the process! Standard strict MCP servers (such as official Node `@modelcontextprotocol/sdk` servers) will reject this request with error `-32002 (Server not initialized)`.
  2. **Framing & Transport Mismatch:** `send_request` reads/writes pure newline-delimited JSON (`self.proc.stdin.write(json.dumps(req) + "\n")` and `self.proc.stdout.readline()`). Standard stdio MCP servers use HTTP-style header framing (`Content-Length: <len>\r\n\r\n<json>`). `json.loads(line)` will crash with `JSONDecodeError` upon reading `Content-Length: 123`.
  3. **Ephemeral Process Spawning per Tool Call (`make_wrapper` lines 220-235):** Every time an agent calls a loaded MCP tool, `make_wrapper` spawns a **brand new `SimpleMcpClient` subprocess**, calls `tools/call`, and immediately closes the process (`wrapper_client.close()`). Any state, caching, or connection pooling maintained inside the MCP server is wiped between tool calls.
- **Missing Pieces / Stubbed Logic:** Does not support MCP server notifications (`notifications/*`), SSE transport, prompt discovery (`prompts/list`), or resource reading (`resources/read`).

#### 2. DAA SRE MCP Server (`daa_mcp_server.py`)
- **Integration Name:** DAA SRE MCP Server (`daa-sre-mcp-server` v2.0.0)
- **Purpose:** Exposes DAA internal SQLite/Postgres database queries (`get_fixes_awaiting_approval`, `get_incident_postmortem`, `get_active_incidents`, `get_fix_by_fingerprint`, `list_registered_apps`) and REST actions (`approve_remediation_fix`, `trigger_manual_incident`) over stdio JSON-RPC (`sys.stdin`/`sys.stdout`) for external MCP clients or Claude Desktop.
- **Files Involved:**
  - `app/daa_mcp_server.py:1-462`
  - `docker-compose.yml:111-120` (`mcp-server` container)
- **Configuration Required:**
  - `DATABASE_URL` (default: `sqlite:///test.db` or `postgresql://...`)
  - `DAA_BACKEND_API_URL` (default: `http://localhost:8000`)
  - Optional: `DAA_TOKEN` for REST API authorization header
- **Can it be tested without external infrastructure/credentials?** **Yes.** Uses local database connections (`get_db()`) and stdio pipes.
- **Confidence Level:** **Medium to High**.
- **Why (Auditor Rationale):** Implements `main()` (`daa_mcp_server.py:445-461`) reading stdio lines, parsing JSON, dispatching to `handle_request()`, and returning JSON-RPC `2.0` responses.
- **Known Problems / Limitations:**
  1. **Transport Framing Incompatibility:** Like `SimpleMcpClient`, `main()` reads `sys.stdin` line-by-line (`for line in sys.stdin: ... json.loads(line)`) and writes `json.dumps(resp) + "\n"`. It does not support `Content-Length:` headers, making it incompatible with standard third-party MCP clients unless bridged by a framing adapter.
  2. **Unparameterized / Driver-Dependent SQL Queries:** While `get_incident_postmortem` correctly uses `ph = _ph(conn)` (`cursor.execute(f"SELECT ... WHERE id = {ph}", (fix_id,))`), other queries (`get_active_incidents` lines 146-150, `get_fixes_awaiting_approval` lines 59-63) execute direct SQL strings without parameter binding or driver abstraction.
  3. **Optional `psycopg2` Dependency:** If `DATABASE_URL` starts with `postgresql://`, `get_db()` (`daa_mcp_server.py:27-33`) tries `import psycopg2`. If `psycopg2` is not installed in the execution environment, `get_db()` catches the exception, logs error to `stderr`, and returns `None`, causing all tool calls to return `Could not connect to database`.
- **Missing Pieces / Stubbed Logic:** `capabilities` return empty `{}` for resources/prompts; `initialize` method returns a static capabilities object.

---

### Category 4: Message Queues & Databases

#### 1. RabbitMQ Asynchronous Job Broker (`pika`)
- **Integration Name:** RabbitMQ Message Queue (`pika` Consumer & Publisher)
- **Purpose:** Decouples incident/telemetry ingestion (`backend-api`) from heavy autonomous SRE AI investigations (`python-agent`). Implements durable exchanges (`fix_jobs_dlx`) and dead-letter queues (`fix_jobs_dlq` with 30-minute message TTL) for failed tasks.
- **Files Involved:**
  - `app/python-agent/agent_src/main.py:518-580` (`main` consumer loop)
  - `app/backend-api/src/routers/ingest.py:265-278` (`pika` publisher in `ingest.py`)
  - `app/backend-api/src/routers/logs.py:250-286` (`pika` publisher & DLX declare in `logs.py`)
  - `app/backend-api/src/routers/telemetry.py:192-198` (`pika` publisher in `telemetry.py`)
  - `docker-compose.yml:36-47` (`rabbitmq` service)
- **Configuration Required:**
  - `RABBITMQ_HOST` (default: `"rabbitmq"` or `"localhost"`)
  - `RABBITMQ_QUEUE` (default: `"fix_jobs"`)
  - `DAA_QUEUE_MODE="rabbitmq"`
- **Can it be tested without external infrastructure/credentials?** **No** when in `rabbitmq` mode (requires running RabbitMQ broker container on port `5672`). **Yes** when `DAA_QUEUE_MODE="sync"`.
- **Confidence Level:** **Medium**.
- **Why (Auditor Rationale):** Consumer (`basic_consume` + `basic_ack`/`basic_nack`) and Publisher (`basic_publish`) logic properly set `durable=True` and configure dead-letter arguments (`x-dead-letter-exchange`).
- **Known Problems / Limitations:**
  1. **CRITICAL QUEUE NAME MISMATCH BUG:** In `python-agent/agent_src/main.py:33`, the consumer queue is dynamic: `RABBITMQ_QUEUE = os.environ.get("RABBITMQ_QUEUE", "fix_jobs")`. However, in `backend-api/src/routers/ingest.py:270` (`channel.queue_declare(queue="fix_jobs", ...)`), `logs.py:267/284` (`channel.queue_declare(queue="fix_jobs", ...)` despite defining `RABBITMQ_QUEUE` on line 23!), and `telemetry.py:192`, the publishing queue is **hardcoded to `"fix_jobs"`**. If a DevOps engineer sets `RABBITMQ_QUEUE="prod_incident_jobs"` in `.env`, the Python agent will consume from `prod_incident_jobs`, but the backend API will continue publishing to `fix_jobs`. All incidents will sit unprocessed in the wrong queue forever!
  2. **Synchronous Blocking Consumer Heartbeat Timeout:** `channel.basic_consume` executes `callback` (`process_job`) synchronously on the main thread. When an SRE investigation involves multiple LLM turns (`RateLimitedGemini` exponential backoff) or `run_tests` (`pytest` via Docker) lasting >60-120 seconds, the main thread is blocked. `pika.BlockingConnection` is unable to send/receive RabbitMQ heartbeat pings during this window, causing the broker to forcibly sever the TCP socket (`ConnectionClosedByBroker: (320, 'CONNECTION_FORCED - broker forced connection closure')`).
- **Missing Pieces / Stubbed Logic:** Fully implemented.

#### 2. Synchronous Inline Queue Fallback (`DAA_QUEUE_MODE="sync"`)
- **Integration Name:** Synchronous In-Process Job Dispatcher (`sync` mode)
- **Purpose:** Bypasses RabbitMQ completely when `DAA_QUEUE_MODE="sync"` by dynamically adding `agent_src` to `sys.path` inside `backend-api`, importing `process_job`, and executing the SRE investigation inline via FastAPI `BackgroundTasks`.
- **Files Involved:**
  - `app/backend-api/src/routers/ingest.py:248-264` (`if queue_mode == "sync": ... background_tasks.add_task(process_job, job)`)
- **Configuration Required:**
  - `DAA_QUEUE_MODE="sync"`
  - Shared Python environment where `backend-api` can access `../../../python-agent/agent_src`
- **Can it be tested without external infrastructure/credentials?** **Yes.** Allows completely serverless/single-container deployment without RabbitMQ container dependencies.
- **Confidence Level:** **High**.
- **Why (Auditor Rationale):** Clean fallback mechanism (`from agent_src.main import process_job; background_tasks.add_task(...)`) enabling zero-infrastructure testing and execution.
- **Known Problems / Limitations:** Runs `process_job` inside FastAPI's async event loop / background thread pool. If multiple incidents arrive concurrently, intensive LLM network operations and Docker `run_tests` subprocesses will saturate the API server's worker pool, increasing API request latency or causing thread starvation.
- **Missing Pieces / Stubbed Logic:** Fully implemented.

#### 3. PostgreSQL Production Database (`SQLAlchemy` / `psycopg2`)
- **Integration Name:** PostgreSQL Relational Database (`SQLAlchemy` Engine)
- **Purpose:** Enterprise production storage (`DAA_DB_PROVIDER="postgres"`) for applications, logs, incidents, fixes, project connections, alerts, users, and sliding-window escalation policies (`EscalationPolicy`).
- **Files Involved:**
  - `app/backend-api/src/database.py:167-172` (`engine = create_engine(DATABASE_URL, pool_size=20, max_overflow=40, pool_timeout=60)`)
  - `app/python-agent/agent_src/tools/log_query_tool.py:16-33`
  - `app/daa_mcp_server.py:26-34`
  - `docker-compose.yml:13-24` (`db` container)
- **Configuration Required:**
  - `DAA_DB_PROVIDER="postgres"` (or `internal-postgres` / `external-postgres`)
  - `DATABASE_URL` (e.g. `postgresql://daa:daa_pass@postgres:5432/daa_db`)
- **Can it be tested without external infrastructure/credentials?** **No** for real Postgres (requires running Postgres server). **Yes** via SQLite fallback (`DAA_DB_PROVIDER="sqlite"`).
- **Confidence Level:** **High**.
- **Why (Auditor Rationale):** Comprehensive ORM schema (`database.py:176-303`) with automated migrations (`run_db_migrations` lines 332-369) adding schema columns (`allowed_ip`, `token`, `active_lock`) and seeding synthetic admin accounts (`users` table ON CONFLICT DO NOTHING lines 374-387).
- **Known Problems / Limitations:** `backend-api/src/database.py:170` configures `pool_size=20, max_overflow=40`. In horizontally autoscaled deployments without a connection pooler like PgBouncer, each instance of `backend-api` and `python-agent` opens up to 60 connections, which will quickly exhaust default Postgres `max_connections` (typically 100).
- **Missing Pieces / Stubbed Logic:** Fully implemented.

#### 4. SQLite Local Database & Cloud Run WAL Guard (`sqlite:///./daa.db`)
- **Integration Name:** SQLite Database & Cloud Run FUSE Guard
- **Purpose:** Lightweight zero-config database engine for local development and single-node testing (`DAA_DB_PROVIDER="sqlite"`).
- **Files Involved:**
  - `app/backend-api/src/database.py:140-165`
  - `app/python-agent/agent_src/tools/log_query_tool.py:27-33`
- **Configuration Required:**
  - `DAA_DB_PROVIDER="sqlite"`
  - `DATABASE_URL` (default: `sqlite:///./daa.db` or `sqlite:///./test.db`)
- **Can it be tested without external infrastructure/credentials?** **Yes.** Operates purely on the local file system.
- **Confidence Level:** **High**.
- **Why (Auditor Rationale):** Uses `check_same_thread=False` and `timeout=30.0` to handle threaded access.
- **Known Problems / Limitations:** For local execution, `@event.listens_for(engine, "connect")` automatically sets `PRAGMA journal_mode=WAL` (`database.py:160-164`). However, when running on Google Cloud Run (`if "K_SERVICE" in os.environ:` line 141 and line 158), WAL mode is explicitly disabled with a warning (`database.py:144-150`). This is because Cloud Run bucket-mounted storage (GCS FUSE) does not support POSIX advisory locking or memory-mapped (`mmap`) files, which would otherwise result in `OperationalError: database is locked` or data corruption.
- **Missing Pieces / Stubbed Logic:** Fully implemented.

#### 5. Redis / Mock Database Provider (`MockSession` / `DAA_DB_PROVIDER="internal-redis" | "external-redis" | "none"`)
- **Integration Name:** Redis / Mock Database Provider (`MockSession`)
- **Purpose:** Intended to provide Redis or stateless in-memory operation modes (`DAA_DB_PROVIDER="internal-redis"`, `"external-redis"`, or `"none"`).
- **Files Involved:**
  - `app/backend-api/src/database.py:54-139` (`MockQuery` & `MockSession`)
  - `app/backend-api/src/database.py:137-139` (`if DAA_DB_PROVIDER in ("none", "internal-redis", "external-redis"): engine = None; SessionLocal = MockSession`)
  - `app/python-agent/agent_src/tools/log_query_tool.py:23-25`
- **Configuration Required:**
  - `DAA_DB_PROVIDER="internal-redis"` or `"external-redis"` or `"none"`
- **Can it be tested without external infrastructure/credentials?** **Yes**, operates entirely in memory without external connections.
- **Confidence Level:** **Low (for Redis) / High (as a Mock)**.
- **Why (Auditor Rationale):** Inspection of `database.py:137-139` reveals that when `DAA_DB_PROVIDER` is set to `"internal-redis"` or `"external-redis"`, **the application does not connect to Redis at all!** Instead, it assigns `engine = None` and `SessionLocal = MockSession`.
- **Known Problems / Limitations:** `MockSession` (`database.py:87-135`) is a dummy class where `.query()` returns a `MockQuery` (`.first()` -> `None`, `.all()` -> `[]`, `.count()` -> `0`), and all transactions (`.add()`, `.commit()`, `.rollback()`) execute `pass`. Any feature relying on persistent state (deduplication, sliding-window escalation policies, rate limits) will silently act as if the database is permanently empty.
- **Missing Pieces / Stubbed Logic:** **100% Stubbed Logic for Redis.** There is zero actual Redis client code (`redis-py` or `aioredis`) implemented in the codebase. `"internal-redis"` and `"external-redis"` are simply aliases for `MockSession`.

---

### Category 5: Logging & Monitoring

#### 1. AWS CloudWatch Logs (`AWSCloudWatchConnector`)
- **Integration Name:** AWS CloudWatch Logs API (`AWSCloudWatchConnector`)
- **Purpose:** Automatically queries AWS CloudWatch (`filter_log_events`) for up to `limit` historical log lines around the incident timestamp (`-15m` to `+1m`) when local database logs are missing (`log_query_tool.py:106-116`).
- **Files Involved:**
  - `app/python-agent/agent_src/log_connectors.py:55-132`
- **Configuration Required:**
  - `AWS_ACCESS_KEY_ID`
  - `AWS_SECRET_ACCESS_KEY`
  - Optional: `AWS_REGION` or `AWS_DEFAULT_REGION` (default: `"us-east-1"`)
- **Can it be tested without external infrastructure/credentials?** **No.** Requires AWS IAM credentials with `logs:DescribeLogGroups` and `logs:FilterLogEvents` permissions.
- **Confidence Level:** **High**.
- **Why (Auditor Rationale):** Uses `boto3.client("logs", region_name=...)` with clean error handling and fallback parsing.
- **Known Problems / Limitations:**
  1. **Optional Dependency Fallback (`lines 73-78`):** If `boto3` is uninstalled (`ImportError`), `fetch_logs` logs a warning and returns `None` cleanly.
  2. **Prefix-Only Log Group Resolution (`lines 99-112`):** Calls `client.describe_log_groups(logGroupNamePrefix=app_name)` and selects the first matching group (`groups[0]["logGroupName"]`). If logs are stored in a hierarchical structure like `/aws/lambda/prod-checkout-service` or `/k8s/cluster/checkout-service`, searching for `checkout-service` as a prefix returns `[]`, causing the query to fall back to `logGroupName=app_name` and fail with `ResourceNotFoundException` or return no logs.
- **Missing Pieces / Stubbed Logic:** Fully implemented.

#### 2. GCP Cloud Logging (`GCPCloudLoggingConnector`)
- **Integration Name:** Google Cloud Logging Client & REST API (`GCPCloudLoggingConnector`)
- **Purpose:** Fetches log entries around the incident window (`-15m` to `+1m`) via the `google.cloud.logging` Python SDK (`list_entries`), with an automatic fallback to the raw GCP Logging REST API v2 (`POST https://logging.googleapis.com/v2/entries:list`) when the SDK is missing or fails.
- **Files Involved:**
  - `app/python-agent/agent_src/log_connectors.py:134-274`
- **Configuration Required:**
  - `GOOGLE_APPLICATION_CREDENTIALS` (JSON service account path) OR
  - `GCP_PROJECT_ID` / `GOOGLE_CLOUD_PROJECT` (plus `GCP_ACCESS_TOKEN` for REST fallback)
- **Can it be tested without external infrastructure/credentials?** **No.** Requires valid GCP IAM credentials (`roles/logging.viewer`) and access to `logging.googleapis.com`.
- **Confidence Level:** **High**.
- **Why (Auditor Rationale):** Exceptionally robust dual-mode implementation (`lines 166-202` for SDK, `lines 205-273` for REST API with `google.auth` token refresh).
- **Known Problems / Limitations:** The filter string (`log_connectors.py:164`) is constructed as:  
  `f'resource.type="k8s_container" OR resource.type="gce_instance" OR logName:"{app_name}" AND timestamp >= "{start_time_iso}" AND timestamp <= "{end_time_iso}"'`  
  Because `AND` has higher precedence than `OR` in GCP filter syntax, the query evaluates as `(k8s_container) OR (gce_instance) OR (logName:"app_name" AND timestamp >= ... AND timestamp <= ...)`. Consequently, it will fetch **all historical `k8s_container` and `gce_instance` logs regardless of application name or timestamp**, potentially returning massive volumes of irrelevant log data or exhausting the `page_size=limit` quota with logs from other microservices!
- **Missing Pieces / Stubbed Logic:** Fully implemented.

#### 3. Datadog Logs API (`DatadogConnector`)
- **Integration Name:** Datadog Logs Search API (`DatadogConnector`)
- **Purpose:** Queries Datadog Logs API v2 (`POST https://api.{site}/api/v2/logs/events/search`) for log events (`service:{app_name} OR host:{app_name} OR {app_name}`) around the incident time window (`-15m` to `+1m`).
- **Files Involved:**
  - `app/python-agent/agent_src/log_connectors.py:276-338`
- **Configuration Required:**
  - `DD_API_KEY` (or `DATADOG_API_KEY`)
  - `DD_APP_KEY` (or `DATADOG_APP_KEY`)
  - Optional: `DD_SITE` (default: `"datadoghq.com"`)
- **Can it be tested without external infrastructure/credentials?** **No.** Requires Datadog API/Application keys and outbound HTTPS access to `api.datadoghq.com` (or `DD_SITE`).
- **Confidence Level:** **High**.
- **Why (Auditor Rationale):** Correctly formats headers (`DD-API-KEY`, `DD-APPLICATION-KEY`) and POST payload (`filter.query`, `filter.from`, `filter.to`, `page.limit`).
- **Known Problems / Limitations:** Fetches a single page of results (`limit` up to 500). Does not inspect or iterate over `page.cursor` if more than `limit` events exist in the 16-minute window.
- **Missing Pieces / Stubbed Logic:** Fully implemented.

#### 4. Prometheus Alertmanager Webhook Ingest (`POST /ingest/prometheus`)
- **Integration Name:** Prometheus Alertmanager Webhook Endpoint
- **Purpose:** Ingests Alertmanager webhook JSON (`POST /ingest/prometheus`), filters for firing alerts (`status == "firing"`), maps Prometheus labels (`service`/`job`/`app` to `app_name`, `alertname` to `exception_type`) and annotations (`description`/`summary` to `stack_trace`), and dispatches SRE investigations (`dispatch_investigation`).
- **Files Involved:**
  - `app/backend-api/src/routers/ingest.py:285-322`
- **Configuration Required:**
  - Optional: `DAA_API_KEY` (if `DAA_AUTH_ENABLED=true`, passed via `X-API-Key` or `Authorization: Bearer` header)
- **Can it be tested without external infrastructure/credentials?** **Yes.** Can be tested locally by sending synthetic Alertmanager JSON via HTTP POST.
- **Confidence Level:** **High**.
- **Why (Auditor Rationale):** Clean asynchronous route (`await verify_webhook_auth(request)` followed by iteration over `payload.get("alerts", [])`).
- **Known Problems / Limitations:** Explicitly bypasses database threshold checks (`DAA_POLICY_ENABLED`) on the assumption that Alertmanager already applied threshold alerting rules (`ingest.py:109-110`). If Alertmanager sends frequent repeat notifications (`repeat_interval`), deduplication (`occurrence_count`) catches existing active incidents, but does not re-evaluate `cooldown_minutes` if the previous incident was recently marked `resolved`.
- **Missing Pieces / Stubbed Logic:** Fully implemented.

#### 5. Sentry Webhook Ingest (`POST /ingest/sentry`)
- **Integration Name:** Sentry Webhook Endpoint
- **Purpose:** Ingests Sentry issue creation webhooks (`POST /ingest/sentry`), verifies HMAC signature (`verify_sentry_signature`), extracts issue metadata (`project.slug` -> `app_name`, `metadata.type`/`title` -> `exception_type`, `metadata.filename`/`culprit` -> `error_file`), and triggers investigation.
- **Files Involved:**
  - `app/backend-api/src/routers/ingest.py:324-361`
  - `app/backend-api/src/routers/ingest.py:77-97` (`verify_sentry_signature`)
- **Configuration Required:**
  - `SENTRY_WEBHOOK_SECRET` (for header `X-Sentry-Signature` HMAC SHA-256 verification) OR
  - `DAA_API_KEY` (fallback if secret not set)
- **Can it be tested without external infrastructure/credentials?** **Yes.** Can be tested locally with signed synthetic Sentry JSON payloads.
- **Confidence Level:** **High**.
- **Why (Auditor Rationale):** Uses `hmac.compare_digest(expected, signature)` to prevent timing attacks when validating Sentry webhook signatures.
- **Known Problems / Limitations:** Strictly checks `if payload.get("action") != "created": return {"status": "ignored"}` (`lines 333-334`). If a previously resolved Sentry issue regresses or re-triggers (`action == "unresolved"` or `action == "triggered"`), the webhook is ignored, preventing autonomous triage of regressions!
- **Missing Pieces / Stubbed Logic:** Fully implemented.

#### 6. Outbound Notification Webhook (`send_outbound_webhook`)
- **Integration Name:** Outbound Status Webhook Dispatcher
- **Purpose:** Sends JSON webhook notifications (`POST DAA_OUTBOUND_WEBHOOK_URL`) signed with `HMAC-SHA256` (`X-DAA-Signature`) when investigations complete or status updates occur (`event="daa.investigation.completed"`).
- **Files Involved:**
  - `app/backend-api/src/notifications/webhook.py:13-47`
- **Configuration Required:**
  - `DAA_OUTBOUND_WEBHOOK_URL`
  - Optional: `DAA_OUTBOUND_WEBHOOK_SECRET`
- **Can it be tested without external infrastructure/credentials?** **Yes.** Can be pointed at any local or external HTTP receiver (e.g., `http://localhost:9000/webhook`).
- **Confidence Level:** **High**.
- **Why (Auditor Rationale):** Uses `httpx.AsyncClient().post(url, headers=headers, content=data, timeout=10.0)` with proper HMAC calculation.
- **Known Problems / Limitations:** Fire-and-forget execution with `timeout=10.0` and no retry logic or dead-letter queue. If the receiving webhook server responds with `500 Internal Server Error` or experiences a brief network blip, the exception is caught and logged (`webhook.py:45-46`), but the notification event is permanently lost.
- **Missing Pieces / Stubbed Logic:** Fully implemented.

---

### Category 6: Ticketing & Issue Tracking

#### 1. Jira Cloud REST API (`_create_jira_ticket`)
- **Integration Name:** Jira Cloud REST API v3 Ticket Creator (`_create_jira_ticket`)
- **Purpose:** Automatically creates a Jira bug ticket (`POST {jira_url}/rest/api/3/issue`) formatted in Atlassian Document Format (ADF v1) when automated code remediation cannot be verified with high confidence or test suites fail repeatedly (`create_incident_ticket`).
- **Files Involved:**
  - `app/python-agent/agent_src/tools/ticket_tool.py:21-72`
- **Configuration Required:**
  - `JIRA_URL` (e.g. `https://company.atlassian.net`)
  - `JIRA_TOKEN` (Jira Cloud API Token)
  - `JIRA_EMAIL` (User email associated with token)
  - `JIRA_PROJECT_KEY` (e.g. `"ENG"` or `"SRE"`)
- **Can it be tested without external infrastructure/credentials?** **No.** Requires valid Atlassian Cloud credentials and access to `JIRA_URL`.
- **Confidence Level:** **High**.
- **Why (Auditor Rationale):** Correctly constructs ADF v1 payload (`"type": "doc", "version": 1, "content": ...`) with HTTP Basic Auth (`auth=(jira_email, jira_token)`).
- **Known Problems / Limitations:**
  1. **Hardcoded Issue Type & Priority (`lines 51-52`):** Submits `"issuetype": {"name": "Bug"}` and `"priority": {"name": priority_map.get(...)("High")}`. If the target Jira project (`JIRA_PROJECT_KEY`) uses custom issue schemes without an issue type literally named `Bug` (e.g., uses `Incident` or `Defect`), or custom priority names (`P1 - Critical`), Jira REST API v3 rejects the creation request with `HTTP 400 Bad Request`.
  2. **Hardcoded Labels (`line 53`):** Submits `"labels": ["daa-autonomous", "postmortem"]`. If field permissions on the Create Issue screen restrict label modifications, the API call fails.
- **Missing Pieces / Stubbed Logic:** Fully implemented.

#### 2. GitHub Issues API (`_create_github_issue`)
- **Integration Name:** GitHub Issues API Ticket Creator (`_create_github_issue`)
- **Purpose:** Serves as the secondary ticketing fallback (`ticket_tool.py:134-136`) when Jira credentials are unconfigured or Jira API calls fail. Posts a new issue (`POST https://api.github.com/repos/{github_repo}/issues`) with title `[DAA Incident] {title}`, markdown body, and severity labels (`critical`, `bug`, `daa-autonomous`).
- **Files Involved:**
  - `app/python-agent/agent_src/tools/ticket_tool.py:74-110`
- **Configuration Required:**
  - `GITHUB_TOKEN`
  - `GITHUB_REPO` (`owner/repo`)
- **Can it be tested without external infrastructure/credentials?** **No.** Requires GitHub token with `issues`/`repo` write permissions.
- **Confidence Level:** **High**.
- **Why (Auditor Rationale):** Clean REST call to `/repos/{github_repo}/issues` handling `201 Created` responses.
- **Known Problems / Limitations:** Truncates description at `65536` characters (`description[:65536]`). If repository settings strictly reject issues containing non-existent labels (`critical` or `daa-autonomous`), the API call returns `422 Unprocessable Entity`.
- **Missing Pieces / Stubbed Logic:** Fully implemented.

#### 3. Local Ticketing Fallback (`DAA://INC-...`)
- **Integration Name:** Local Synthetic Ticket Generator (`DAA://INC-...`)
- **Purpose:** Acts as the tertiary failsafe (`ticket_tool.py:138-158`) when neither Jira nor GitHub Issues is configured or when both remote API calls fail (`not ticket_url`). Returns a deterministic ticket ID (`INC-YYYYMMDD-XXXXXX`) and URL (`DAA://INC-...`) alongside a structured text summary so SRE agent workflows always receive a valid ticket identifier without crashing.
- **Files Involved:**
  - `app/python-agent/agent_src/tools/ticket_tool.py:138-158`
- **Configuration Required:** None (automatic fallback).
- **Can it be tested without external infrastructure/credentials?** **Yes**, 100% local inside memory.
- **Confidence Level:** **High (as a Fallback Mock)**.
- **Why (Auditor Rationale):** Guarantees task completion even in completely offline or unconfigured environments.
- **Known Problems / Limitations:** The generated URI (`DAA://INC-20260714-ABC123`) is purely synthetic and cannot be navigated to or tracked outside of DAA execution logs.
- **Missing Pieces / Stubbed Logic:** **Explicit Mock Fallback Logic.** Generates the message: `Local (configure JIRA_URL+JIRA_TOKEN or GITHUB_TOKEN+GITHUB_REPO to enable real ticketing)`.

---

### Category 7: Runtime & Container Execution

#### 1. Host Docker Daemon Socket Bind-Mount (`/var/run/docker.sock` & `run_tests`)
- **Integration Name:** Host Docker Daemon Bridge (`/var/run/docker.sock` & `run_tests`)
- **Purpose:** Enables the `python-agent` container (`run_tests` tool) to spin up ephemeral language runner containers (`python:3.10-slim`, `node:18-slim`, `golang:1.20`, `maven:3.8-openjdk-17-slim`, `ruby:3.1-slim`) on the **host machine's Docker daemon** to execute verification test suites (`pytest -v`, `npm test`, `go test`) inside cloned repositories (`docker run --rm -v {repo_path}:/workspace -w /workspace {runner_image} {test_command}`).
- **Files Involved:**
  - `app/python-agent/agent_src/tools/execution_tool.py:33-100` (`run_tests` tool execution)
  - `docker-compose.yml:84` (`- /var/run/docker.sock:/var/run/docker.sock`)
  - `docker-compose.yml:85` (`- /tmp/daa:/tmp/daa`)
- **Configuration Required:**
  - Host Docker daemon running and socket accessible at `/var/run/docker.sock`
  - `DAA_GIT_MODE="local"` and `DAA_DB_PROVIDER != "none"` (otherwise automatically bypassed with `Test execution bypassed: DAA SRE is running in Serverless mode`)
- **Can it be tested without external infrastructure/credentials?** **Yes**, executes locally against the host machine's Docker engine.
- **Confidence Level:** **High**.
- **Why (Auditor Rationale):** Correctly invokes `subprocess.run(cmd, shell=True, ...)` to launch ephemeral containers over the mounted Docker socket.
- **Known Problems / Limitations:**
  - **Docker-in-Docker Socket Volume Mount Path Trap:** Because `docker run` is sent over the host socket (`docker.sock`), `-v {repo_path}:/workspace` commands Docker to mount `{repo_path}` from the **host filesystem**, NOT from inside the `python-agent` container! When running via the DAA 3.0 orchestrator (`PostflightOrchestrator`), code is cloned into `/tmp/daa/worktrees/...`. Because `docker-compose.yml:85` bind-mounts `/tmp/daa:/tmp/daa` 1:1 between host and container, `-v /tmp/daa/worktrees/...:/workspace` resolves correctly on the host! However, when running in fallback local mode (`git_tool.py:150`), `temp_dir` is `/tmp/{app_name}` (inside the container's private `/tmp`). When `run_tests` calls `docker run -v /tmp/{app_name}:/workspace`, the host Docker daemon attempts to mount the *host's* `/tmp/{app_name}` (which either does not exist or contains unrelated host files), causing `pytest` or `npm test` to immediately fail with `directory not found` or empty workspace errors!
- **Missing Pieces / Stubbed Logic:** Fully implemented.

#### 2. Codex Authentication State Volume (`/app/auth.json`)
- **Integration Name:** Codex / Snap Auth State Bind-Mount (`/app/auth.json`)
- **Purpose:** Injects the host developer's local ChatGPT/Codex authentication JSON file (`auth.json`) read-only into the `python-agent` container at `/app/auth.json` so `CodexChatModel` can read `tokens.access_token` or `OPENAI_API_KEY`.
- **Files Involved:**
  - `app/python-agent/agent_src/llm_config.py:34-51` (`_load_api_key`)
  - `docker-compose.yml:86` (`${CODEX_AUTH_JSON_PATH:-/home/rutvej/snap/codex/34/auth.json}:/app/auth.json:ro`)
- **Configuration Required:**
  - `CODEX_AUTH_JSON_PATH` environment variable OR default path `/home/rutvej/snap/codex/34/auth.json` existing on host.
- **Can it be tested without external infrastructure/credentials?** **Yes**, if `auth.json` is present on host disk.
- **Confidence Level:** **High**.
- **Why (Auditor Rationale):** Standard read-only bind-mount consumed cleanly by `llm_config.py`.
- **Known Problems / Limitations:** Highly host-and-user specific default path (`/home/rutvej/snap/codex/34/...`). If deployed on another developer's machine or CI/CD runner where Snap/Codex is not installed at that exact path, Docker Compose will fail to start the container or create a blank directory at `/app/auth.json` unless `CODEX_AUTH_JSON_PATH` is overridden in `.env`.
- **Missing Pieces / Stubbed Logic:** Fully implemented.

#### 3. Antigravity CLI & Host State Mounts (`/usr/local/bin/agy` & `/root/.gemini`)
- **Integration Name:** Antigravity CLI & OAuth State Bind-Mounts
- **Purpose:** Mounts the host machine's `agy` executable (`~/.local/bin/agy`) and user authentication folder (`~/.gemini`) read-only into the `python-agent` container (`/usr/local/bin/agy` and `/root/.gemini`) so `AgyChatModel` can execute `subprocess.run(["agy", ...])` seamlessly without manual container login.
- **Files Involved:**
  - `app/python-agent/agent_src/llm_config.py:225-290`
  - `docker-compose.yml:82-83` (`/home/rutvej/.local/bin/agy:/usr/local/bin/agy:ro` and `/home/rutvej/.gemini:/root/.gemini:ro`)
- **Configuration Required:**
  - Host paths `/home/rutvej/.local/bin/agy` and `/home/rutvej/.gemini` existing.
- **Can it be tested without external infrastructure/credentials?** **Yes**, if host paths exist.
- **Confidence Level:** **High**.
- **Why (Auditor Rationale):** Direct binary and config injection via Docker bind mounts.
- **Known Problems / Limitations:** Hardcoded absolute user paths (`/home/rutvej/...`). Will prevent container startup on any other machine unless `.env` variable overrides or relative paths (`${HOME}/.gemini`) are introduced.
- **Missing Pieces / Stubbed Logic:** Fully implemented.

---

### Category 8: Authentication & Authorization Security

#### 1. DAA API Token & Dynamic Auto-Login Retry (`handle_request_with_retry`)
- **Integration Name:** Inter-Service Dynamic Auto-Authentication (`handle_request_with_retry`)
- **Purpose:** Intercepts outgoing HTTP calls from `python-agent` tools (`alert_tool`, `change_tracker_tool`, `code_nav_tool`, `search_tool`, etc.) to `backend-api`. If `res.status_code == 401 Unauthorized` (e.g. `DAA_TOKEN` expired or unconfigured), `handle_request_with_retry` automatically POSTs to `{backend_url}/auth/login` using hardcoded fallback credentials (`{"username": "testuser", "password": "testpassword"}`) to acquire a fresh JWT access token (`os.environ["DAA_TOKEN"] = new_token`), and retries the original request (`auth_helper.py:20-41`).
- **Files Involved:**
  - `app/python-agent/agent_src/tools/auth_helper.py:7-43`
  - `app/backend-api/src/routers/auth.py:46-61` (`login_user`)
- **Configuration Required:**
  - `DAA_TOKEN` (initial optional token)
  - `DAA_BACKEND_API_URL` (default: `http://backend-api:80`)
  - `DAA_AUTH_ENABLED` (boolean, default: `true` for SQL/Postgres modes)
- **Can it be tested without external infrastructure/credentials?** **Yes.** Completely internal inter-container communication.
- **Confidence Level:** **High when `DAA_AUTH_ENABLED=false` / Medium when `DAA_AUTH_ENABLED=true`**.
- **Why (Auditor Rationale):** When `DAA_AUTH_ENABLED=false`, `/auth/login` (`auth.py:48-49`) instantly returns `{"token": "dummy_token"}`, and `get_current_user` (`auth.py:69-70`) returns a synthetic admin user (`{"username": "admin", "id": "admin-id", "role": "admin"}`), ensuring 100% reliable execution.
- **Known Problems / Limitations:**
  - **Hardcoded Fallback Login Trap (`auth_helper.py:26`):** When `DAA_AUTH_ENABLED=true`, `/auth/login` queries the database `users` table (`pwd_context.verify(user.password, db_user.passwordHash)` on lines 50-52). Because `handle_request_with_retry` hardcodes `{"username": "testuser", "password": "testpassword"}`, unless a user named `testuser` with password `testpassword` has been explicitly seeded or registered via `/auth/register` in the active database, dynamic re-authentication will reject with `401 Incorrect username or password`, leaving the agent permanently locked out of all backend API tools!
- **Missing Pieces / Stubbed Logic:** When `DAA_AUTH_ENABLED=false`, auth checks and token signing are stubbed with dummy tokens (`dummy_token`, `admin-id`).

#### 2. Application Role & IP Whitelist Guard (`get_current_user` & `submit_log`)
- **Integration Name:** Application JWT Role & Subnet IP Whitelist Guard
- **Purpose:** Enforces strict cryptographic and network access boundaries on application-role JWT tokens (`role == "application"`). When an application submits telemetry (`POST /logs/`), `get_current_user` (`auth.py:77-112`) verifies that `token.sub` matches `log.app_name` (`logs.py:58-62`), and that the caller's IP address (`x-forwarded-for` or direct socket IP) matches the application's registered `allowed_ip` subnet (`ipaddress.ip_network` exact or CIDR match, bypassing check if loopback `127.0.0.1`/`::1`).
- **Files Involved:**
  - `app/backend-api/src/routers/auth.py:66-128` (`get_current_user`)
  - `app/backend-api/src/routers/logs.py:57-64` (`submit_log` role verification)
- **Configuration Required:**
  - `DAA_AUTH_ENABLED=true`
  - Database row in `applications` table with valid `allowed_ip` (e.g., `10.0.1.0/24` or `192.168.1.50`)
- **Can it be tested without external infrastructure/credentials?** **Yes.** Entirely self-contained in `backend-api`.
- **Confidence Level:** **High**.
- **Why (Auditor Rationale):** Uses standard `ipaddress.ip_network` and `ipaddress.ip_address` parsing with clear loopback exception handling (`auth.py:99-106`).
- **Known Problems / Limitations:**
  - **Spoofable `X-Forwarded-For` Header (`auth.py:92-94`):** Extrapolates client IP via `client_ip = request.headers.get("x-forwarded-for").split(",")[0].strip()`. If `backend-api` is exposed directly or deployed behind a load balancer that does not strip/overwrite incoming `X-Forwarded-For` headers from external requests, an attacker can arbitrarily spoof `X-Forwarded-For: 10.0.1.50` to bypass `allowed_ip` CIDR restrictions completely!
- **Missing Pieces / Stubbed Logic:** Fully implemented.

---

## Key Findings & Critical Integration Action Items

Based on code-verified discoveries, the following 5 integration action items should be prioritized before production rollout:

1. **Fix RabbitMQ Consumer/Publisher Queue Name Mismatch (`ingest.py:270` & `logs.py:267/284` vs `main.py:33`):**  
   Update `backend-api/src/routers/ingest.py`, `logs.py`, and `telemetry.py` to use `os.environ.get("RABBITMQ_QUEUE", "fix_jobs")` when declaring and publishing to RabbitMQ queues, matching `python-agent/agent_src/main.py:33`. Currently, overriding `RABBITMQ_QUEUE` breaks communication between backend and agent.

2. **Mitigate Socket Bind-Mount Path Trap in Local Docker Execution (`execution_tool.py:76` & `git_tool.py:150`):**  
   When running `run_tests` (`docker run -v {repo_path}:/workspace`) over the mounted host socket (`/var/run/docker.sock`), `{repo_path}` must be accessible at that exact path on the host. Ensure `DAA_GIT_MODE="local"` checkouts in `git_tool.py:150` clone inside `/tmp/daa/...` (`- /tmp/daa:/tmp/daa` bind mount) rather than `/tmp/{app_name}`, preventing host directory mount failures during testing.

3. **Align `SimpleMcpClient` with Official MCP Handshake Spec (`main.py:155-163`):**  
   Update `SimpleMcpClient.start()` to send `initialize` and receive `capabilities` before issuing `tools/list` (`id=1`), and wrap stdio communication in `Content-Length:` HTTP-style framing to ensure interoperability with standard third-party MCP SDK servers (`@modelcontextprotocol/sdk`).

4. **Eliminate Hardcoded User Paths in `docker-compose.yml` (`lines 82, 83, 86`):**  
   Replace `/home/rutvej/.local/bin/agy:/usr/local/bin/agy:ro`, `/home/rutvej/.gemini:/root/.gemini:ro`, and `/home/rutvej/snap/codex/34/auth.json` with parameterized environment variables (`${HOST_AGY_PATH:-/usr/local/bin/agy}`, `${HOST_GEMINI_DIR:-~/.gemini}`) to prevent Docker startup failures across different developer or CI machines.

5. **Fix GCP Cloud Logging Filter Operator Precedence (`log_connectors.py:164`):**  
   Add explicit parentheses around `OR` clauses in `GCPCloudLoggingConnector`:  
   `gcp_filter = f'(resource.type="k8s_container" OR resource.type="gce_instance" OR logName:"{app_name}") AND timestamp >= "{start_time_iso}" AND timestamp <= "{end_time_iso}"'`  
   Without parentheses, `AND` takes precedence over `OR`, causing the query to fetch all historical `k8s_container` logs cluster-wide without time bounds.

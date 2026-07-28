/**
 * DAA Documentation RAG Engine
 * Implements BM25 retrieval over pre-chunked DAA documentation.
 * No dependencies, no model download — pure JS, works on GitHub Pages.
 *
 * Usage:
 *   const context = retrieveContext("how does deduplication work?", 3);
 *   // Returns top-3 relevant doc chunks as a single string for the LLM prompt.
 */

// ─── Document Chunks ─────────────────────────────────────────────────────────
// Each chunk is a short, focused excerpt from the DAA documentation.

const DAA_CHUNKS = [
  {
    id: "overview-1",
    title: "What is DAA?",
    text: `DAA (Debugging Autonomous Agent) is an autonomous SRE platform. When your app breaks at 3am, DAA investigates the root cause and opens a pull request — while you sleep. It catches errors, uses an LLM agent to investigate logs, traces, and source code, and automatically opens a Pull Request with a code fix. DAA is self-hosted and private by design.`
  },
  {
    id: "overview-2",
    title: "How DAA Works — Step by Step",
    text: `Error fires in your app → DAA SDK catches it and sends to DAA (one line of code) → SHA-256 deduplication checks if it is the same error (if yes, suppressed silently; if new pattern, agent wakes up) → AI Agent investigates across 4 dimensions: Git commits (what changed recently?), App logs (what is the stack trace?), Traces (which request triggered it?), Source code (AST navigation to the exact line) → Opens a Pull Request with a code fix, root-cause explanation, and postmortem summary → You wake up, review the PR, and merge.`
  },
  {
    id: "overview-3",
    title: "What Makes DAA Different from Traditional Alerting",
    text: `Traditional alerting fires every time an error happens and just tells you "Error occurred", requiring manual investigation and paging you at 3am every time. DAA fires only once per unique error pattern, tells you the root cause and provides a code fix, so you only review a PR. With DAA there are no repeated 3am pages — only genuinely new problems wake the agent.`
  },
  {
    id: "features-1",
    title: "DAA Core Features",
    text: `Zero alert fatigue: SHA-256 fingerprint dedup plus sliding-window cooldowns. 4-dimension investigation: Git history, Logs, Traces, and AST code navigation. Agent safety: Hard 8-tool-call budget cap — no runaway LLM costs. Any LLM: Gemini, GPT-4o, Claude, Vertex, Ollama (air-gapped). Human-in-the-Loop (HITL): Approve AI fixes before the PR lands. Any git forge: GitHub, GitLab, Gitea, Bitbucket. MCP compatible: Use DAA as a tool inside Claude Desktop or Cursor.`
  },
  {
    id: "security-1",
    title: "Security, Privacy and Code Safety",
    text: `DAA is self-hosted and private by design. It runs in your own environment (via Docker) and uses the API keys you provide. Credentials are stored via environment variables only — never mounted as files into containers. CORS is restricted to an explicit allowlist. Webhook endpoints verify DAA_API_KEY and HMAC-SHA256. DAA has no central server that receives your code or data. Any code context is sent directly from your self-hosted DAA instance to the LLM provider you configure (Google Gemini, OpenAI, or a local Ollama instance).`
  },
  {
    id: "security-2",
    title: "Code Privacy — What Data DAA Accesses",
    text: `DAA only analyzes the specific context around a triggered error: the stack trace, related Git commits, and the specific lines of code in the AST. It does NOT scan or upload your entire codebase. The SRE Agent is strictly prohibited from pulling code from arbitrary URLs — it can only fetch data from secondary repositories that are explicitly pre-registered in the DAA database (SSRF protection). Code context is sent from your self-hosted instance to your LLM provider, never to any DAA central server.`
  },
  {
    id: "security-3",
    title: "Offline / Air-Gapped Operation",
    text: `Yes, you can configure DAA to use local LLMs (like Ollama) so no data ever leaves your network. DAA is model-agnostic and supports Gemini, GPT-4o, Claude, Vertex AI, and fully offline local models via Ollama. This means you can run DAA in a completely air-gapped environment with zero external network calls.`
  },
  {
    id: "deployment-1",
    title: "Deployment Modes Overview",
    text: `DAA supports three deployment modes. Single Docker container: best for trying it out or small teams, run with docker run -p 8000:8080 --env-file .env daa:latest. Docker Compose: best for self-hosted persistent deployments with Postgres and RabbitMQ, use daa redeploy. Serverless: best for Cloud Run or AWS Fargate with zero-ops, set DAA_DB_PROVIDER=none and DAA_GIT_MODE=api. Full deployment guide is in DEPLOYMENT.md.`
  },
  {
    id: "deployment-2",
    title: "Quickstart — Serverless Mode (1 Command)",
    text: `The easiest way to run DAA is as a stateless webhook receiver. Requirements: Docker, a free Gemini API key, and a GitHub Personal Access Token. Command: docker run -p 8000:8080 -e LLM_PROVIDER=google -e GEMINI_API_KEY="your_key" -e LLM_MODEL="gemini-2.5-flash" -e DAA_DB_PROVIDER=none -e DAA_GIT_TOKEN="github_pat_..." -e GIT_HOST="https://github.com" -e GIT_ORG="your-username" rutvej1/daa-standalone:latest. Then trigger a test: curl -X POST http://localhost:8000/ingest/prometheus -d '{"status":"firing","alerts":[{"labels":{"alertname":"TestCrash"}}]}'`
  },
  {
    id: "deployment-3",
    title: "Full-Stack Enterprise Deployment (Docker Compose)",
    text: `For full-stack mode with Postgres and RabbitMQ, use these environment variables: DAA_DB_PROVIDER=postgres (enables persistent storage), DAA_QUEUE_MODE=rabbitmq (enables distributed task processing), DAA_GIT_MODE=local (clones the repository locally for faster operations and deep AST analysis). Docker Compose services needed: daa-api, postgres (postgres:15-alpine), rabbitmq (rabbitmq:3-management-alpine). DATABASE_URL=postgresql://user:pass@postgres:5432/daa, CELERY_BROKER_URL=amqp://user:pass@rabbitmq:5672/`
  },
  {
    id: "deployment-4",
    title: "Serverless Deployment (Cloud Run / Fargate)",
    text: `For stateless serverless environments: DAA_DB_PROVIDER=none (disables persistence, allows scale to zero), DAA_GIT_MODE=api (interacts with Git purely via API, no local disk clone needed), DAA_QUEUE_MODE=sync, DAA_AUTH_ENABLED=false, DAA_POLICY_ENABLED=false. When running in this mode, DAA processes incidents instantly in memory with no external infrastructure (no Postgres or RabbitMQ required).`
  },
  {
    id: "integration-1",
    title: "Integration Option 1 — Webhooks (Recommended for Serverless)",
    text: `You do NOT need to use the DAA SDK or change your app code. Point your existing alerting tools (Sentry, Datadog, Prometheus, CloudWatch) to DAA webhook endpoints. Endpoints: POST /ingest/prometheus (standard Prometheus Alertmanager webhook format), POST /ingest/sentry (with HMAC-SHA256 signature header). Run DAA with DAA_AUTH_ENABLED=false and secure it behind your own API Gateway, AWS IAM, or Cloudflare Tunnel. Rely on your existing aggregator to group errors.`
  },
  {
    id: "integration-2",
    title: "Integration Option 2 — DAA SDK (Recommended for Full-Stack)",
    text: `If you don't have centralized logging, use the DAA SDK. Requires deploying DAA with DAA_AUTH_ENABLED=true (usually via Docker Compose). Register your app to get a DAA_TOKEN. Install with: pip install daa-sdk. Usage: from daa_sdk import DAAClient; daa = DAAClient()  # reads DAA_TOKEN from env; daa.report_exception(exception, app_name="my-service"). SDK also supports Node.js, Go, Java, Ruby, and .NET (community maintained).`
  },
  {
    id: "architecture-1",
    title: "High-Level Architecture Flow",
    text: `1. Client app sends an error log to the Backend API. 2. Backend API stores the log, runs deduplication, and if threshold is breached queues a job in RabbitMQ. 3. Python Agent (LangChain ReAct) consumes the job, inspects code across 4 dimensions, and produces a fix. 4. Python Agent updates fix status in the Backend API. 5. Admin Panel provides a web UI to view logs, fixes, and approve PRs. Services: backend-api (FastAPI, auth, log ingestion, fix tracking), python-agent (LLM-driven analysis, merge request creation), admin-panel (React dashboard), daa-sdk (client SDK), daa CLI.`
  },
  {
    id: "architecture-2",
    title: "3-Phase Orchestration Pipeline (DAA 3.0)",
    text: `DAA 3.0 uses a three-phase pipeline. Phase 1 Pre-Flight: Fingerprint dedup, repo cache pull, git worktree creation at /tmp/daa/<incident_id>, log hydration from 4 dimensions (traceback, 500 lines of app logs, metrics snapshot, last 10 git commits), and context packaging. Phase 2 Agent Core: LangChain ReAct loop with planning step (agent must output hypothesis and evidence_needed before running tools), hard 8-call budget cap, read-only investigation, then WRITE_DIFF or WRITE_ESCALATION. Phase 3 Post-Flight: Parse patch, apply diff, create branch fix/<fingerprint[:12]>, open Pull Request idempotently, generate postmortem Markdown, update Incident record, clean up worktrees.`
  },
  {
    id: "architecture-3",
    title: "Agent Safety — Budget Cap and Circuit Breaker",
    text: `Safety Layer 1 (Planning Step): The agent is forbidden from running tools until it outputs a JSON plan with hypothesis, evidence_needed, and will_not_check fields. Safety Layer 2 (Hard Cap): Tool calls are limited to 8 per run. A budget warning is injected at 5 calls. Exceeding 8 calls throws CapExceededException, aborting the agent. Circuit Breaker: If run_tests fails twice on a fix attempt, or the exception matches structural issues (NotImplementedError, complex race conditions), the agent stops writing files and creates a Jira incident ticket instead.`
  },
  {
    id: "dedup-1",
    title: "Deduplication and Alert Fatigue Prevention",
    text: `DAA prevents alert storms using fingerprint-based deduplication. Fingerprint Hash: SHA-256(app_name + exception_type + log_content[:200])[:16]. Database Check: Queries active incidents with status in investigating, pr_open, ticket_created, cooldown. If matched, increments incident counter and suppresses the agent silently. Stateless Remote Check: If running without a database, queries the remote Git server for a branch named fix/<fingerprint[:12]>. If the branch exists, the incident is assumed to be in-flight and execution is skipped. Sliding window default: 120 seconds, threshold: 15 errors. Immediate keywords (always escalate): FATAL, OOMKill, PANIC, DatabaseDeadlock.`
  },
  {
    id: "escalation-1",
    title: "Escalation Policies — How the Agent Gets Triggered",
    text: `Escalation policies define when to wake up the agent. Each policy is per-application and configures: rule_type (error_rate_threshold or severity_immediate), condition_value (number of errors), window_seconds (sliding window, default 120s), cooldown_minutes (prevents agent double-firing), severity_keywords (JSON array of immediate trigger words like FATAL). Configure via API: POST /applications/{id}/escalation-policies. CLI: daa policy --app <app-name> --threshold <count> --window <seconds>. Telemetry flow: log ingested → check immediate keywords → count errors in window → if threshold breached, create Incident and escalate to Agent.`
  },
  {
    id: "cli-1",
    title: "DAA CLI Reference — Core Commands",
    text: `daa init: Guided setup wizard — configures LLM key, git token, and deployment mode. daa register: Register a new target application (daa register --name <app-name> --repo <git-url> --language <language>). daa policy: Set escalation threshold (daa policy --app <app-name> --threshold <count> --window <seconds>). daa test: Send a synthetic error to trigger the triage agent (daa test --app <app-name> --error "<error message>"). daa status: Health check all containers. daa logs: View or stream real-time agent reasoning logs (daa logs --follow). daa redeploy: Rebuild and restart all containers. daa config set-model: Switch LLM provider or model without restarting. daa version: Prints CLI version (v3.0.0).`
  },
  {
    id: "cli-2",
    title: "DAA CLI — MCP Commands",
    text: `DAA supports the Model Context Protocol (MCP), allowing you to use DAA as an autonomous agent tool inside Claude Desktop, Cursor, or other MCP-compatible environments. daa mcp list: Lists all configured MCP servers. daa mcp add: Adds a new MCP server. daa mcp remove: Removes an MCP server by ID. You can use DAA as a tool inside Claude Desktop or Cursor through the MCP interface.`
  },
  {
    id: "api-1",
    title: "API Contract — Submit Log and Ingest Endpoints",
    text: `Submit Log: POST /logs/ with Authorization: Bearer <JWT_TOKEN>. Payload: {content, app_name, exception_type, trace_id, correlation_id, metadata_json}. Response if escalated: {logId, status: "Escalated to Agent", incidentId, fingerprint}. Response if below threshold: {logId, status: "Logged (Threshold not reached)", error_count, threshold, window_seconds}. Ingest Prometheus: POST /ingest/prometheus (standard Alertmanager format). Ingest Sentry: POST /ingest/sentry with X-Sentry-Signature HMAC header. Authentication: JWT Bearer token. If DAA_AUTH_ENABLED=false (serverless mode), authentication is bypassed.`
  },
  {
    id: "api-2",
    title: "API Contract — Fixes, Applications, and Configuration",
    text: `Query Fix by Fingerprint: GET /fixes/fingerprint/{fingerprint} → returns {status, pr_url, fix_id}. Approve Fix: POST /fixes/{id}/approve. Register Application: POST /applications/ with {name, language, repository_url} → returns {id, name, token, created_at}. The token is your DAA_TOKEN for SDK authentication. Configure Escalation Policy: POST /applications/{id}/escalation-policies. Observability APIs (internal, used by agent): GET /apps/{app_name}/logs, GET /apps/{app_name}/metrics, GET /apps/{app_name}/recent-changes.`
  },
  {
    id: "datamodel-1",
    title: "Data Model — Incidents and Fixes",
    text: `Incident fields: id (UUID), fingerprint (SHA-256 hash), app_name, status (investigating, pr_open, ticket_created, cooldown, resolved, human_required), occurrence_count, first_seen_at, last_seen_at, cooldown_until, agent_attempts, root_cause_summary, confidence_score (percent), pr_url, ticket_url (Jira), postmortem_md (full Markdown report). Fix fields: id, logId (source log), timestamp, generatedFix (unified git patch/diff), postmortem, isApproved (boolean, approved by SRE in UI), status (Pending, Applied, Failed), pull_request_url.`
  },
  {
    id: "datamodel-2",
    title: "Data Model — Applications, Users, and Escalation Policies",
    text: `Application fields: id, name (unique), description, language, repository_url, team_owner, token (API auth key for SDK). User fields: id, username (unique), passwordHash, role (User, Administrator, application). Escalation Policy fields: application_id, rule_type, condition_value, window_seconds, severity_keywords (JSON string), cooldown_minutes, is_active. Project Connections (Git/Jira): app_name, repo_provider (github/gitlab/gitea), repo_url, repo_token, jira_url, jira_token, jira_project_key.`
  },
  {
    id: "hitl-1",
    title: "Human-in-the-Loop (HITL) Mode",
    text: `DAA supports a Human-in-the-Loop mode controlled by the DAA_HITL_MODE environment variable. When DAA_HITL_MODE=true: After the agent generates a fix, it does NOT automatically push to a PR. Instead, it surfaces the fix in the React Admin Panel dashboard. An SRE reviews the AI-generated Root Cause Postmortem and code diff, then clicks Approve and Merge. When DAA_HITL_MODE=false: The agent automatically pushes the fix branch and opens a Pull Request directly without human approval. The PR URL is returned in the logs.`
  },
  {
    id: "llm-1",
    title: "Supported LLM Providers",
    text: `DAA is model-agnostic. Supported providers: LLM_PROVIDER=google with GEMINI_API_KEY (recommended: gemini-2.5-flash). LLM_PROVIDER=openai with OPENAI_API_KEY (GPT-4o). LLM_PROVIDER=anthropic with ANTHROPIC_API_KEY (Claude). LLM_PROVIDER=vertex for Google Vertex AI. LLM_PROVIDER=ollama for fully local air-gapped models (no internet required). Switch the model without restarting using: daa config set-model. The agent uses LangChain ReAct under the hood, so any LangChain-compatible provider can be configured.`
  },
  {
    id: "production-1",
    title: "Production Readiness and Known Gaps",
    text: `DAA v2.0 is an excellent Proof of Concept and internal SRE utility. Current gaps before exposing to external tenants: (1) ReAct text parsing should be replaced with native LLM function calling for 100% schema validation. (2) Agent executor should run in an ephemeral sandboxed environment (AWS Fargate, gVisor, Firecracker) not inside the agent container. (3) Authentication needs project-level OAuth (narrow GitHub/GitLab App permissions) not broad PATs. (4) High-throughput log ingestion should use Apache Kafka or RabbitMQ Streams instead of database polling. Overall readiness: Low-to-Medium for production SaaS.`
  },
  {
    id: "roadmap-1",
    title: "Roadmap and Known Gaps",
    text: `Completed: GET /dashboard endpoint (admin panel expects it). Auth enforcement alignment across log endpoints. Pending: Update log status when python-agent updates fix status. Consolidate environment variable usage across services. Improve observability (structured logging, distributed tracing, metrics). Add pagination and filtering UX to admin panel (search UI is present but not wired to backend). Future: Native LLM function calling to replace regex ReAct parsing. Sandboxed agent execution environments. Fine-grained RBAC and project-level OAuth tokens.`
  },
  {
    id: "quickstart-1",
    title: "Full Quickstart — Docker Compose Setup",
    text: `Prerequisites: Docker, Docker Compose, a Google Gemini API key. Steps: (1) cp .env.example .env and fill in required values (GitLab password, Gemini key, Postgres password). (2) docker-compose up -d. (3) Open http://localhost:8082 and create a project named test-app in GitLab. (4) Push test-app code to GitLab. (5) Create a GitLab personal access token with api scope and set GITLAB_PRIVATE_TOKEN in .env. (6) Register a backend user and get a JWT token via POST /auth/register and POST /auth/login. (7) Set DAA_TOKEN in .env. (8) Send a dummy log to verify ingestion. Admin panel: http://localhost:5003.`
  },
  {
    id: "quickstart-2",
    title: "Verification and Demo Workflow",
    text: `Step 1: git clone https://github.com/rutvej/DAA.git && ./install.sh && daa init. Step 2: Choose Profile A (Single container: docker build -t daa-standalone && docker run -p 8080:8080) or Profile B (Compose: docker compose up -d). Step 3: daa status or curl GET /health. Step 4: daa register --name demo-service --repo <git-url> --language python. Step 5: daa policy --app demo-service --threshold 1 --window 60. Step 6: daa test --app demo-service --message "AttributeError: ...". Step 7: daa logs --follow to watch agent reasoning. Step 8: Review and approve fix in admin panel at http://localhost:5003.`
  }
];

// ─── BM25 Implementation ──────────────────────────────────────────────────────

const BM25_K1 = 1.5;
const BM25_B  = 0.75;

function tokenize(text) {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .split(/\s+/)
    .filter(t => t.length > 1);
}

// Pre-compute token frequencies for all chunks
const _index = (() => {
  const n = DAA_CHUNKS.length;
  const tf = [];
  const df = {};
  let totalLen = 0;

  for (const chunk of DAA_CHUNKS) {
    const tokens = tokenize(chunk.title + ' ' + chunk.text);
    totalLen += tokens.length;
    const freq = {};
    for (const t of tokens) {
      freq[t] = (freq[t] || 0) + 1;
    }
    tf.push({ freq, len: tokens.length });
    for (const t of Object.keys(freq)) {
      df[t] = (df[t] || 0) + 1;
    }
  }

  const avgdl = totalLen / n;
  return { n, tf, df, avgdl };
})();

/**
 * Score a single document against a query using BM25.
 */
function bm25Score(docIdx, queryTokens) {
  const { n, tf, df, avgdl } = _index;
  const { freq, len } = tf[docIdx];
  let score = 0;

  for (const qt of queryTokens) {
    if (!freq[qt]) continue;
    const idf = Math.log((n - (df[qt] || 0) + 0.5) / ((df[qt] || 0) + 0.5) + 1);
    const tfNorm = (freq[qt] * (BM25_K1 + 1)) /
      (freq[qt] + BM25_K1 * (1 - BM25_B + BM25_B * len / avgdl));
    score += idf * tfNorm;
  }

  return score;
}

/**
 * Retrieve the top-K most relevant documentation chunks for a query.
 * Returns a formatted string ready to inject into a system prompt.
 *
 * @param {string} query - The user's question.
 * @param {number} topK  - Number of chunks to retrieve (default: 4).
 * @returns {string}     - Concatenated relevant documentation.
 */
function retrieveContext(query, topK = 4) {
  const queryTokens = tokenize(query);

  const scores = DAA_CHUNKS.map((chunk, i) => ({
    chunk,
    score: bm25Score(i, queryTokens)
  }));

  scores.sort((a, b) => b.score - a.score);

  const top = scores.slice(0, topK).filter(s => s.score > 0);

  if (top.length === 0) {
    // Fallback: return a summary chunk
    return DAA_CHUNKS.slice(0, 3).map(c => `### ${c.title}\n${c.text}`).join('\n\n');
  }

  return top.map(s => `### ${s.chunk.title}\n${s.chunk.text}`).join('\n\n');
}

# DAA Serverless-Safe LLM & Git Circuit Breaker Resilience Architecture (`v1.0`)

> **Status:** ACTIVE — Implemented in `[P1-RES-1]` (`v3.0`)  
> **Date:** 2026-07-16  
> **Target Modules:** `app/python-agent/agent_src/tools/git_api_providers.py`, `app/python-agent/agent_src/llm_config.py`, `app/python-agent/agent_src/main.py`

---

## 1. Architectural Motivation & Problem Statement

In autonomous AI self-healing and code remediation pipelines, external API dependencies—specifically LLM providers (Google Gemini, OpenAI, Anthropic, Ollama) and Git host REST APIs (GitHub, GitLab, Bitbucket, Gitea)—are subject to transient network failures, rate-limiting (`429 Too Many Requests`, `403 Secondary Rate Limit`), and gateway errors (`500 Internal Server Error`, `502 Bad Gateway`).

### The Old Failure Mode (`DAA 2.0`)
Previously, if a network request to an LLM provider or Git server failed mid-investigation (`main.py:850-854`):
1. An unhandled exception `e` was thrown inside the `AgentExecutor` loop.
2. `main.py` caught `e`, logged it via `report_daa_internal_error(e, "agent_core")`, and raised `e` up the stack.
3. The serverless container (e.g. GCP Cloud Run or AWS Fargate) crashed or exited the worker thread.
4. **All investigation telemetry, thought steps, and read-only diagnostic findings completed prior to the crash were permanently lost**, leaving the incident ticket in a zombie `investigating` status.

---

## 2. The Solution: Exponential Backoff + Serverless Fallback Circuit Breaker

To guarantee zero data loss and eliminate zombie tasks across both stateful cluster (`postgres + rabbitmq`) and serverless (`stateless + cloud run`) deployments, DAA `v3.0` implements a two-tier resilience architecture:

```
                      ┌──────────────────────────────────────┐
                      │    Incoming Incident Job (job.id)    │
                      └───────────────────┬──────────────────┘
                                          │
                                          ▼
                      ┌──────────────────────────────────────┐
                      │        run_preflight (Phase 1)       │
                      │  - Compute Fingerprint               │
                      │  - Check Git remote fix/{fingerprint}│
                      └───────────────────┬──────────────────┘
                                          │
                  ┌───────────────────────┴───────────────────────┐
                  ▼ (Fix found on remote)                         ▼ (No fix found)
     ┌───────────────────────────┐                   ┌───────────────────────────┐
     │ preflight["skip"] = True  │                   │      run_agent (Phase 2)  │
     │ - Log "Fix already open"  │                   │ - Tenacity Exponential    │
     │ - Complete without LLM    │                   │   Backoff (@retry 3x)     │
     └───────────────────────────┘                   └─────────────┬─────────────┘
                                                                   │
                                                ┌──────────────────┴──────────────────┐
                                                ▼ (Success)                           ▼ (Retries Exhausted)
                                   ┌───────────────────────────┐         ┌───────────────────────────┐
                                   │  PostflightOrchestrator   │         │  LLM Circuit Breaker      │
                                   │  - Apply Diff             │         │  Fallback Intercept       │
                                   │  - Push Branch / PR       │         │  - Extract Memory Logs    │
                                   └───────────────────────────┘         │  - Push Draft Fallback PR │
                                                                         └───────────────────────────┘
```

---

## 3. Tier 1: Tenacity Exponential Backoff (`llm_config.py` & `git_api_providers.py`)

Every network boundary is wrapped with `tenacity` decorators enforcing structured exponential backoff and jitter before raising exceptions:

### 3.1 Git REST API Boundary (`BaseGitProvider._request`)
All `CloneFreeGitClient` HTTP operations (`get_file_content`, `list_files`, `create_branch`, `write_file_content`, `create_pull_request`) inherit from `BaseGitProvider._request`. Wrapping this single method protects every provider uniformly:

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(requests.exceptions.RequestException),
    reraise=True,
)
def _request(self, method: str, path: str, **kwargs):
    # Executes HTTP request to GitHub, GitLab, Bitbucket, or Gitea
```

### 3.2 LLM Generation Boundary (`CodexChatModel`, `AgyChatModel`, `get_chat_completion`)
All model generation calls retry up to 3 times (`2s, 4s, 8s`) across HTTP and subprocess boundaries:

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((urllib.error.HTTPError, urllib.error.URLError, Exception)),
    reraise=True,
)
def _generate(self, messages, stop=None, run_manager=None, **kwargs):
    # ...
```

---

## 4. Tier 2: Serverless-Safe LLM Circuit Breaker & Partial Diagnosis Fallback (`main.py`)

When persistent API outages (e.g. 30+ minutes of provider downtime) exhaust Tier 1 retries, `process_job` (`main.py`) intercepts the fatal exception instead of raising:

### 4.1 In-Memory Telemetry Preservation (Cloud Run Safe)
Because serverless container storage is ephemeral (`/tmp`), `ExecutionLogCallbackHandler(job.log_id)` maintains the exact sequence of thought loops (`Thought -> Action -> Observation`) in memory (`callback_handler.logs`).

When `agent_executor.invoke()` fails, `main.py` extracts `callback_handler.logs` directly from RAM:

```python
partial_logs = callback_handler.logs if callback_handler.logs else ["No agent tool steps executed before failure."]
traces_formatted = "\n\n".join(partial_logs)
```

### 4.2 Deterministic Partial Diagnosis Postmortem Construction
Without invoking the LLM (`since the provider returned 500/429`), `main.py` constructs a formatted markdown report (`fallback_postmortem`) explaining that the circuit breaker tripped and attaching all diagnostic evidence collected up to the exact moment of failure.

### 4.3 Idempotent Git Branch & Draft PR Generation (`CloneFreeGitClient`)
The fallback payload is passed to `PostflightOrchestrator.run()`, which uses `CloneFreeGitClient` (over REST without local disk writes or `git` CLI binaries) to create or update branch `fix/{fingerprint[:12]}` (`status: escalated`, `reason: LLM Circuit Breaker Tripped`).

---

## 5. Idempotent Recovery & Zero Infinite Loops (`run_preflight`)

If the same incident re-triggers via cron schedule or log ingestion while the LLM is still down:

1. `run_preflight()` (`orchestrator.py:1150`) computes `fingerprint` and checks remote Git heads (`git ls-remote --heads ... refs/heads/fix/{fingerprint[:12]}`).
2. Because the first circuit breaker fallback already created `fix/{fingerprint[:12]}` (`fix_open`), `run_preflight` returns:
   ```python
   {
       "skip": True,
       "skip_reason": "Fix already exists: fix_open",
       "pr_url": pr_url
   }
   ```
3. `process_job()` (`main.py:664`) logs `[DAA 3.0] Skipping job... Duplicate incident. Existing fix: {pr_url}`, updates the ticket, and terminates immediately (`0` LLM tokens consumed).

This ensures **infinite retry loops are impossible**, while giving human developers a clean, audit-ready pull request with full investigation context on the very first failure.

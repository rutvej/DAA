# Python Agent Business Logic Specification

This document details the LLM integrations, output sanitization filters, planning validators, and post-flight remediation routines in the Python Agent.

## 1. LLM Models & Custom Chat wrappers

The agent initializes chat models via `get_llm()` in [llm_config.py](file:///home/rutvej/Desktop/DAA/app/python-agent/src/llm_config.py#L283-L336):

### A. Agy Chat Model (`AgyChatModel`)
Invokes the local command `agy --dangerously-skip-permissions --model <model> --print <prompt>`.
- **Fast Mode Cache**: If `DAA_AGENT_MODE=fast`, prompt inputs are hashed (SHA-256) and saved to `/tmp/daa_agy_cache/{hash}.txt`. Subsequent queries load this file to bypass CLI executions.

---

## 2. Safety Layers (`agent_safety.py`)

### Layer 1: Planning Step (`PlanningValidator`)
Pre-flight prepends structural requirements to the system prompt.
- **Enforcement**: The agent's very first response must contain a valid JSON block enclosing three keys: `"hypothesis"`, `"evidence_needed"`, and `"will_not_check"`.
- **Validation**: If the block is absent or keys are missing, the agent is blocked from calling any tools.

### Layer 2: Tool Ceilings (`HardCapCallbackHandler`)
Extends LangChain's `BaseCallbackHandler` to count tool runs:
- **Warning Threshold** (default: 5 calls): Sets a warning flag. The agent executor injects the string `[DAA BUDGET WARNING]` into the next model step to warn the LLM.
- **Budget Cap** (default: 8 calls): Immediately throws a `CapExceededException`. The `AgentSafetyWrapper` catches this and returns a fallback escalation result.

---

## 3. Post-Flight Patch & PR Pipeline

Managed by the `PostflightOrchestrator` after the agent generates its final response:

```mermaid
graph TD
    A[Parse Agent Output] --> B{Terminal Response Type?}
    B -->|WRITE_DIFF| C[Apply Unified Diff via patch]
    B -->|WRITE_ESCALATION| D[Escalate & Create JIRA board issue]
    C --> E[Checkout branch fix/fingerprint]
    E --> F[Commit and Push changes]
    F --> G[Open/Retrieve Pull Request]
    G --> H[Upload Markdown Postmortem]
```

### Git Actions
- **Local Git Mode**: Uses subprocess calls (`git checkout`, `git add`, `git commit`, `git push`) inside the `/tmp/daa/<incident_id>` worktree.
- **API Git Mode** (for stateless containers): Uses the `CloneFreeGitClient`. Files parsed from the diff are retrieved via GitLab API, patched in the virtual container worktree, pushed to a new branch, and committed via GitLab commits REST API.
- **Idempotency**: Before creating a Pull Request, the orchestrator queries the repository's open pulls list matching the head branch. If a PR exists, it retrieves the URL instead of opening a duplicate.

---

## 4. Secure Multi-Repository Context Access

To allow the SRE Agent to triage bugs that stem from shared libraries, dependencies, or upstream microservices:

1. **Authorization via Registration**: The SRE Agent is strictly prohibited from pulling code from arbitrary URLs injected dynamically in incoming error logs (guarding against Server-Side Request Forgery - SSRF). It can only fetch data from secondary repositories that are explicitly pre-registered in the DAA database.
2. **Work isolation (Primary Target)**: For any given incident log, the SRE Agent will only clone/worktree and execute code modifications on the target application's repository. Only this primary repository gets written to and verified via test execution on-disk.
3. **Read-Only Hybrid Access**: Any auxiliary repositories registered as dependencies are accessed in a read-only manner. Instead of being cloned to the SRE worker disk, their files are queried dynamically via Git REST APIs (GitHub/GitLab/Gitea) using `CloneFreeGitClient`, keeping the SRE worker workspace isolated and lightweight.

---

## 5. MCP Serverless Integration

The Python Agent connects to external tools using the Model Context Protocol (MCP) via `SimpleMcpClient`.
- **Current Capability**: The client currently uses **Stdio Transport**, spawning local binaries and communicating over standard input/output pipes.
- **Serverless Requirements (Cloud Run / Fargate)**: Stdio transport is incompatible with ephemeral, request-scoped serverless environments where custom external binaries cannot be reliably provisioned alongside the agent.
- **Path Forward**: To support Cloud Run and Fargate, the MCP client must be refactored to implement **SSE (Server-Sent Events) Transport** or HTTP, allowing the agent to connect to remote MCP servers deployed as independent microservices.

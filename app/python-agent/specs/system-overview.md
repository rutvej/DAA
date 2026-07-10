# Python Agent System Overview

This document details the software architecture, execution flow, and component design of the autonomous LangChain Python Agent.

## 1. Modular Architecture

The agent is located under `/home/rutvej/Desktop/DAA/app/python-agent/`.

```
app/python-agent/
├── src/
│   ├── main.py          # Queue consumer, LangChain agent core, and tool bindings
│   ├── orchestrator.py  # Pre-flight context assembly and Post-flight diff execution
│   ├── agent_safety.py  # Context Safety Layer (Planning & Hard cap)
│   ├── llm_config.py    # LLM wrappers (Google, OpenAI, Ollama, custom Codex/Agy)
│   ├── models.py        # Pydantic models (e.g., Job schema)
│   ├── log_connectors.py# Cloud logging drivers (AWS CloudWatch, GCP, Datadog)
│   └── tools/           # ReAct Agent tool definitions
│       ├── alert_tool.py
│       ├── change_tracker_tool.py
│       ├── code_nav_tool.py
│       ├── execution_tool.py
│       └── ...
```

---

## 2. Three-Phase Execution Pipeline

The execution sequence is managed by [process_job()](file:///home/rutvej/Desktop/DAA/app/python-agent/src/main.py#L528-L774):

### Phase 1: Pre-Flight
Managed by [run_preflight()](file:///home/rutvej/Desktop/DAA/app/python-agent/src/orchestrator.py#L855-L1028):
1. **Deduplication Check**: Queries database or git remotes for branch status.
2. **Worktree Creation**: Clones repository to `/var/daa/repo-cache/` and checks out a worktree at `/tmp/daa/<incident_id>`.
3. **Observability Hydration**: Connects to the backend and fetches application logs, system metrics, and Git history.
4. **Context Packaging**: Merges dimensions into a structured markdown system prompt.

### Phase 2: Agent Core (ReAct Loop)
1. **Planning Validation**: Front-loads investigation. Enforces that the agent publishes a JSON plan detailing hypotheses and targets before executing tools.
2. **ReAct Invocations**: The LLM queries read-only tools to inspect repository files, search variables, or view logs.
3. **Safety Monitoring**: Tool calls are counted. Warnings are injected if counts approach budget caps, and a hard ceiling of 8 calls triggers escalation.

### Phase 3: Post-Flight
Managed by [PostflightOrchestrator](file:///home/rutvej/Desktop/DAA/app/python-agent/src/orchestrator.py#L441-L822):
1. **Patch Extraction**: Parses the agent's output for unified diff content.
2. **Patch Application**: Applies changes to the worktree using the shell `patch` command.
3. **Git Sync**: Creates the branch, commits modifications, and pushes to remote.
4. **PR/MR Generation**: Idempotently creates a pull request on Gitea/GitHub/GitLab.
5. **Postmortem Logging**: Formats and uploads a postmortem markdown file.
6. **Worktree Cleanup**: Removes temporal worktree directory.

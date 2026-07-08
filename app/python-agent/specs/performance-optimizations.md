# DAA Python Agent — Performance Optimization Specs

> These specs target the three biggest token-burn and reliability problems in the python-agent.
> All changes are scoped to `app/python-agent/src/`.

---

## Spec 3 — `DAA_AGENT_MODE` Environment Variable

**File to edit:** `src/main.py`

### Problem
The 4-dimension workflow prompt is ~1,300 tokens and mandates a 6-step workflow even for trivial
one-line bugs. At 10 max iterations this costs ~80,000 tokens per job worst-case.

### Solution
Read `DAA_AGENT_MODE` from `.env` and switch prompt + iteration cap at startup.

| Mode | Prompt style | Max iterations | Est. tokens/job |
|------|-------------|----------------|-----------------|
| `full` *(default)* | 4-dimension workflow, strict ordering | 10 | ~80,000 |
| `fast` *(dev/debug)* | Minimal 5-step prompt | 5 | ~20,000 |

### Fast Mode Prompt (≈150 tokens)
```
You are a bug-fix agent. Clone repo, grep for the error, fix the file, open a PR.
If tests are unavailable (go: not found), skip them.
Max 5 tool calls. Output PR_URL.
```

### Implementation Notes
```python
# src/main.py — top of file, after env load
AGENT_MODE = os.getenv("DAA_AGENT_MODE", "full")  # "full" | "fast"

FAST_PROMPT = (
    "You are a bug-fix agent. Clone repo, grep for the error, fix the file, open a PR. "
    "If tests are unavailable (go: not found), skip them. "
    "Max 5 tool calls. Output PR_URL."
)

max_iterations = 5 if AGENT_MODE == "fast" else 10
system_prompt  = FAST_PROMPT if AGENT_MODE == "fast" else FULL_4D_PROMPT
```

### `.env` entry to add
```dotenv
# "full" = production 4-dimension workflow (default)
# "fast" = lean 5-step prompt for dev/debug (saves ~75% tokens)
DAA_AGENT_MODE=fast
```

---

## Spec 4 — Go Test Skip Rule

**File to edit:** `src/main.py` (system prompt, no code logic needed)

### Problem
`run_tests` returns exit code 127 (`go: not found`) inside the agent container.
The agent interprets this as a test failure, triggers the circuit breaker, and creates a Jira
ticket instead of a PR — wasting 2 full iterations and producing a wrong output.

### Solution
Add the following rule to **both** the `full` and `fast` system prompts:

```
RULE — Test tool inconclusive:
If `run_tests` returns exit code 127 or output contains "command not found",
treat the result as INCONCLUSIVE (not a failure).
Proceed directly to `create_pull_request`.
Do NOT trigger the circuit breaker.
```

### Why this matters
- Exit 127 = binary not in PATH, not a test failure.
- The circuit breaker should only fire on a non-zero exit where the binary *ran*.
- This rule prevents `payment-worker` from getting a Jira ticket instead of a PR.

---

## Spec 5 — `agy` Response Cache (Dev Mode)

**File to edit:** `src/llm_config.py`  
**Class:** `AgyChatModel._generate()`

### Problem
Re-running the same job after an agent code change re-spends all tokens on the identical
early steps (clone, grep, read file). Only the later steps change.

### Solution
When `DAA_AGENT_MODE=fast`, hash each prompt string and cache the `agy` response to disk.

```
Cache location: /tmp/daa_agy_cache/<sha256[:16]>.txt
```

### Pseudocode
```python
import hashlib, os, pathlib

CACHE_DIR = pathlib.Path("/tmp/daa_agy_cache")

def _generate(self, messages, ...):
    if os.getenv("DAA_AGENT_MODE") == "fast":
        prompt_text = serialize_messages(messages)          # existing helper
        cache_key   = hashlib.sha256(prompt_text.encode()).hexdigest()[:16]
        cache_file  = CACHE_DIR / f"{cache_key}.txt"

        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        if cache_file.exists():
            cached = cache_file.read_text()
            return build_llm_result(cached)                # wrap in LangChain AIMessage

    # --- normal agy call ---
    result = self._call_agy(messages, ...)

    if os.getenv("DAA_AGENT_MODE") == "fast":
        cache_file.write_text(extract_text(result))

    return result
```

### Effect
Repeated runs after a fix to a later step only re-spend tokens from the changed step onward.
Early steps (clone, grep, read) are served from disk at 0 token cost.

### Cache invalidation
Delete `/tmp/daa_agy_cache/` manually to bust the cache:
```bash
rm -rf /tmp/daa_agy_cache
```

---

## Spec 7 — Install Go in python-agent Dockerfile

**File to edit:** `app/python-agent/Dockerfile`

### Problem
The agent container has no `go` binary. `run_tests ./...` exits 127, which:
1. Triggers the Go test skip rule (Spec 4) — a workaround, not a fix.
2. Means the agent cannot verify that its Go fixes actually compile.

### Solution
Add Go installation to the Dockerfile so the agent can run `go build` / `go test`:

```dockerfile
# Add after the existing apt-get line (or create one)
RUN apt-get update && \
    apt-get install -y golang-go && \
    rm -rf /var/lib/apt/lists/*
```

### Trade-offs
| | Without Go | With Go |
|--|-----------|---------|
| Image size | smaller | +~500 MB |
| Test reliability | exit 127 workaround | actual compile/test |
| PR trustworthiness | agent guesses fix works | agent verifies fix compiles |

> **Recommendation:** Use the Dockerfile fix for staging/production runs.
> Use the prompt rule (Spec 4) as a fallback for local dev where image rebuild is slow.

---

## Open Bugs Related to These Specs

| Bug | Root cause | Fixed by |
|-----|-----------|---------|
| Agent analyzes `payment-worker` SSL error instead of Redis OOM | Old RabbitMQ messages survive queue purge when agent nacks | Spec 1 in `daa-e2e-demo` (inject directly, skip load test) |
| `go: not found` triggers circuit breaker | Go not in agent PATH | Spec 4 (prompt rule) + Spec 7 (Dockerfile) |
| Re-running burns all tokens from step 1 | No caching in `AgyChatModel` | Spec 5 (agy cache) |

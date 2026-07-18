# Reusable Starter Prompt Template for DAA Implementation Tasks

Whenever you start a new conversation to execute a task from **`INTERACTIVE_TODO_LIST.md`**, copy the prompt template below, fill in the `{{DYNAMIC_VALUES}}` (`{{TASK_ID}}`, `{{TASK_TITLE}}`, and `{{TARGET_FILES}}`), and paste it as your very first message to kick off the task session!

---

## 📋 Copy & Paste Starter Prompt

```markdown
You are my Staff Software Architect and Principal Security Engineer working on the DAA repository (`/home/rutvej/Desktop/DAA`) on branch `audit/comprehensive-10-phase-review`.

Our overall engineering roadmap is tracked in `IMPLEMENTATION_ROADMAP.md`, and our step-by-step checkable to-do list is tracked in `INTERACTIVE_TODO_LIST.md` at the repository root.

Your objective for this conversation is strictly limited to **Task {{TASK_ID}}: {{TASK_TITLE}}**.
Target Files: `{{TARGET_FILES}}`

### Critical Operating & Tool Rules:
1. Treat implementation code (`.py`, `.js`, `docker-compose.yml`, `main.tf`) as the sole source of truth.
2. ALWAYS use specific tools (`view_file`, `replace_file_content`, `grep_search`). NEVER run `cat`, `sed`, or `grep` inside a bash command.

### Workflow Steps for This Session:
1. **Inspect & Discuss:** First, read `INTERACTIVE_TODO_LIST.md` for `{{TASK_ID}}` and use `view_file` to inspect `{{TARGET_FILES}}`. Output a brief summary showing me the exact lines of code you plan to modify and *Why It Is Needed*. Ask for my confirmation before editing code.
2. **Execute:** Once I give approval, use `replace_file_content` (or `multi_replace_file_content`) to apply the exact drop-in code fixes.
3. **Verify & Check Off:** Verify that the file syntax and logic are correct. Then, update `INTERACTIVE_TODO_LIST.md` by changing `[ ]` to `[x]` for `{{TASK_ID}}`.
4. **Commit & Push:** Stage and commit the clean changes (`git add -A && git commit -m "fix(sec): complete {{TASK_ID}} — {{TASK_TITLE}}" && git push origin audit/comprehensive-10-phase-review`) and summarize the completion.

Please begin right now by carrying out **Step 1 (Inspect & Discuss)** for Task {{TASK_ID}}.
```

---

## 💡 Quick Reference: First 5 Tasks to Copy into Template

### Task 1 (`[P0-SEC-1]`)
- **`{{TASK_ID}}`**: `[P0-SEC-1]`
- **`{{TASK_TITLE}}`**: `Remove Host Developer Credentials & CLI Binary Volume Mounts`
- **`{{TARGET_FILES}}`**: `docker-compose.yml` (Lines 80–84)

### Task 2 (`[P0-SEC-2]`)
- **`{{TASK_ID}}`**: `[P0-SEC-2]`
- **`{{TASK_TITLE}}`**: `Restrict Overly Permissive LAN CORS Subnet Regex & Dynamic Origin Injection`
- **`{{TARGET_FILES}}`**: `app/backend-api/src/main.py` (Lines 64–67, 93–116)

### Task 3 (`[P0-SEC-3]`)
- **`{{TASK_ID}}`**: `[P0-SEC-3]`
- **`{{TASK_TITLE}}`**: `Eliminate Synthetic admin-id Privilege Escalation Bypasses`
- **`{{TARGET_FILES}}`**: `app/backend-api/src/routers/auth.py` (Lines 69–70), `app/backend-api/src/routers/telemetry.py` (Lines 46–61), `app/backend-api/src/routers/ingest.py` (Line 53)

### Task 4 (`[P0-SEC-4]`)
- **`{{TASK_ID}}`**: `[P0-SEC-4]`
- **`{{TASK_TITLE}}`**: `Replace shell=True Command Injection Vulnerabilities with Safe Tokenized Arrays`
- **`{{TARGET_FILES}}`**: `app/python-agent/agent_src/tools/execution_tool.py` (Lines 76–84), `daa` CLI

### Task 5 (`[P0-OPS-1]`)
- **`{{TASK_ID}}`**: `[P0-OPS-1]`
- **`{{TASK_TITLE}}`**: `Fix Cloud Run K_SERVICE Fatal Startup Crash & SQLite WAL Lock Corruption`
- **`{{TARGET_FILES}}`**: `terraform/main.tf` (Lines 61–74), `app/backend-api/src/database.py` (Lines 140–166), `app/backend-api/src/main.py` (Lines 44–50)

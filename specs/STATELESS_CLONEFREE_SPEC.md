# DAA Stateless & Clone-Free Architecture — Pluggable Cloud-Native to Data-Centre Blueprint

> **Status:** DRAFT — v0.1  
> **Date:** 2026-07-09  
> **Goal:** Support both the lightweight serverless/cloud-native deploy (zero-database, clone-free, HTTP-only) and the traditional high-scale enterprise data centre deployment (Postgres, RabbitMQ, local file-system caching) within a single unified codebase.

---

## 1. Core Architectural Pillars

To satisfy both serverless (Cloud Run, AWS Fargate, Vercel) and enterprise bare-metal requirements, DAA defines three operational dimensions that can be independently toggled:

```
                  ┌─────────────────────────────────────────┐
                  │          DAA CORE RUNTIME CONFIG        │
                  └─────────────────────────────────────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         ▼                             ▼                             ▼
 ┌──────────────┐              ┌──────────────┐              ┌──────────────┐
 │  STATE MODE  │              │   GIT MODE   │              │ QUEUE MODE   │
 └──────┬───────┘              └──────┬───────┘              └──────┬───────┘
        ├─ stateless (none)           ├─ api (clone-free)           ├─ sync (inline/asyncio)
        ├─ sqlite (local file)        └─ local (worktree clone)     └─ rabbitmq (distributed)
        └─ postgres (enterprise)
```

By configuration alone, a user can deploy DAA in any pattern:

1. **Stateless Serverless (Cloud Native)**: `STATE_MODE=none`, `GIT_MODE=api`, `QUEUE_MODE=sync`. Runs on Cloud Run without a database, without cloning repositories, with inline/background-task job handling.
2. **Stateless Stateful-Edge**: `STATE_MODE=sqlite`, `GIT_MODE=api`, `QUEUE_MODE=sync`. Local persistent DB file, API-based Git access.
3. **Full Data Centre (High Scale)**: `STATE_MODE=postgres`, `GIT_MODE=local`, `QUEUE_MODE=rabbitmq`. The standard DAA 3.0 distributed cluster setup.

---

## 2. Clone-Free Git Operations via Provider REST APIs

In serverless execution environments, file system write access is either constrained or expensive (consuming RAM for memory-backed `/tmp`). Furthermore, cloning large corporate codebases takes too much time and bandwidth on short-lived function invocations.

When `DAA_GIT_MODE=api` is set, DAA performs all code reads, file modifications, and commits directly using the Git Data REST APIs of GitHub or GitLab, bypassing local git clone operations completely.

### 2.1 File System Read/Write Simulation

Instead of using `os.path` and standard files, the agent's file system tools wrap the GitHub/GitLab contents API.

```python
# daa_minimal/git/clonefree_client.py
import base64
import httpx
from typing import Optional

class CloneFreeGitClient:
    """Manages file reading and writing directly via Git API without cloning."""
    
    def __init__(self, provider: str, repo_url: str, token: str):
        self.provider = provider  # "github" or "gitlab"
        self.token = token
        self.repo_url = repo_url
        self.headers = self._get_auth_headers()
        self.api_base = self._get_api_base()
        
    def get_file_content(self, path: str, ref: str = "main") -> Optional[str]:
        """Fetch file content directly via API."""
        if self.provider == "github":
            # GET /repos/{owner}/{repo}/contents/{path}?ref={ref}
            url = f"{self.api_base}/contents/{path}"
            resp = httpx.get(url, headers=self.headers, params={"ref": ref})
            if resp.status_code == 200:
                data = resp.json()
                # Content is base64 encoded
                return base64.b64decode(data["content"]).decode("utf-8")
        elif self.provider == "gitlab":
            # GET /projects/{id}/repository/files/{file_path}/raw?ref={ref}
            encoded_path = httpx.utils.quote(path, safe="")
            url = f"{self.api_base}/repository/files/{encoded_path}/raw"
            resp = httpx.get(url, headers=self.headers, params={"ref": ref})
            if resp.status_code == 200:
                return resp.text
        return None
```

### 2.2 Atomic Multi-file Commits (GitHub Git Data API)

To apply the proposed fix code without cloning, DAA uses the Git database transaction flow on GitHub:

```
Get current ref head sha ──▶ Create blob for modified file ──▶ Create tree referencing old tree + new blob ──▶ Create commit referencing parent commit & new tree ──▶ Update branch reference
```

```python
# daa_minimal/git/clonefree_client.py (continued)

    async def commit_changes(self, branch_name: str, parent_branch: str, file_path: str, content: str, commit_message: str):
        """Create a commit on a new branch with modified file content using GitHub Git Data API."""
        # 1. Get reference of base branch (e.g. refs/heads/main)
        base_ref = httpx.get(f"{self.api_base}/git/ref/heads/{parent_branch}", headers=self.headers).json()
        base_sha = base_ref["object"]["sha"]
        
        # 2. Get parent commit to fetch the base tree SHA
        parent_commit = httpx.get(f"{self.api_base}/git/commits/{base_sha}", headers=self.headers).json()
        base_tree_sha = parent_commit["tree"]["sha"]
        
        # 3. Create blob for new/modified file content
        blob_resp = httpx.post(f"{self.api_base}/git/blobs", headers=self.headers, json={
            "content": content,
            "encoding": "utf-8"
        }).json()
        new_blob_sha = blob_resp["sha"]
        
        # 4. Create new tree listing containing the new blob
        tree_resp = httpx.post(f"{self.api_base}/git/trees", headers=self.headers, json={
            "base_tree": base_tree_sha,
            "tree": [{
                "path": file_path,
                "mode": "100644",
                "type": "blob",
                "sha": new_blob_sha
            }]
        }).json()
        new_tree_sha = tree_resp["sha"]
        
        # 5. Create the Commit object
        commit_resp = httpx.post(f"{self.api_base}/git/commits", headers=self.headers, json={
            "message": commit_message,
            "tree": new_tree_sha,
            "parents": [base_sha]
        }).json()
        new_commit_sha = commit_resp["sha"]
        
        # 6. Create the new branch pointing to the new commit
        ref_payload = {
            "ref": f"refs/heads/{branch_name}",
            "sha": new_commit_sha
        }
        httpx.post(f"{self.api_base}/git/refs", headers=self.headers, json=ref_payload)
```

On **GitLab**, this is simplified into a single Commits API call:

```python
    async def commit_changes_gitlab(self, branch_name: str, parent_branch: str, file_path: str, content: str, commit_message: str):
        # POST /projects/{id}/repository/commits
        payload = {
            "branch": branch_name,
            "start_branch": parent_branch,
            "commit_message": commit_message,
            "actions": [{
                "action": "update", # or "create"
                "file_path": file_path,
                "content": content
            }]
        }
        httpx.post(f"{self.api_base}/repository/commits", headers=self.headers, json=payload)
```

---

## 3. Outbound Notification Webhooks

To let users integrate DAA easily with custom internal APIs, ticketing systems, or Slack apps without needing to read a database, DAA broadcasts job results to an outbound webhook.

### 3.1 Webhook Payload Format

When a diagnostic investigation ends (regardless of status), DAA fires a POST request:

```json
{
  "event": "daa.investigation.completed",
  "timestamp": "2026-07-09T18:50:00Z",
  "job_id": "90b8f05e-8594-4d8e-9081-6fca92f1abcb",
  "fingerprint": "8d3e91a27ccb",
  "app_name": "payment-service",
  "status": "fixed",                  // "fixed", "escalated", "duplicate"
  "pr_url": "https://github.com/myorg/payment-service/pull/42",
  "exception_type": "NullPointerException",
  "error_file": "src/main/java/com/example/Handler.java",
  "line_number": 42,
  "elapsed_seconds": 182,
  "postmortem": "# Root Cause...\n\nNull pointer error fixed by adding checks..."
}
```

### 3.2 Security: HMAC Webhook Signature

To allow the receiving server to verify that the webhook payload came from their DAA instance:
1. The user defines a secret token `DAA_OUTBOUND_WEBHOOK_SECRET`.
2. DAA computes the HMAC-SHA256 signature of the payload and sends it in the `X-DAA-Signature` header.

```python
# daa_minimal/notifications/webhook.py
import hmac
import hashlib
import json
import httpx

async def send_outbound_webhook(payload: dict, url: str, secret: str = None):
    data = json.dumps(payload)
    headers = {"Content-Type": "application/json"}
    
    if secret:
        signature = hmac.new(
            secret.encode("utf-8"),
            data.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        headers["X-DAA-Signature"] = signature
        
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, headers=headers, content=data, timeout=5.0)
    except Exception as e:
        print(f"Failed to dispatch outbound webhook: {e}")
```

---

## 4. Pluggable Configuration Model

Here is how the system parameters map to env configurations for each deployment paradigm:

| Mode | `DAA_STATE_MODE` | `DAA_GIT_MODE` | `DAA_QUEUE_MODE` | Runtime Requirement |
|---|---|---|---|---|
| **Serverless (Stateless)** | `none` | `api` | `sync` | No database, no local disk, zero queue servers. |
| **Edge Persistent** | `sqlite` | `api` | `sync` | One local SQLite file (mounted volume). |
| **Enterprise Scaled** | `postgres` | `local` | `rabbitmq` | Full Postgres cluster + RabbitMQ + Git workspaces. |

### Environment Configuration Example

```bash
# ── CORE PARADIGM SWITCHES ──
DAA_STATE_MODE=none            # none, sqlite, postgres
DAA_GIT_MODE=api               # api, local
DAA_QUEUE_MODE=sync            # sync, rabbitmq

# ── GIT API AUTH ──
GITHUB_TOKEN=ghp_xxx           # Used for Clone-Free Git operations
GITLAB_PRIVATE_TOKEN=glpat-xxx

# ── OUTBOUND WEBHOOK ──
DAA_OUTBOUND_WEBHOOK_URL=https://my-internal-dashboard.corp/api/daa-receiver
DAA_OUTBOUND_WEBHOOK_SECRET=my-super-secret-hmac-key
```

---

## 5. Security & Verification Analysis

### 5.1 Clone-Free Mode Advantages
* **Minimal Attack Surface**: The container does not store SSH keys or clone whole directories onto disk. If a container is compromised, the attacker has no local code cache to exfiltrate.
* **Strict Path Permissions**: Git API calls can be restricted to specific directories via OAuth scopes, preventing LLM agents from reading code outside the targeted workspace path.

### 5.2 Serverless Considerations
* Since Cloud Run auto-terminates long idle connections, Webhook payloads should return `status: accepted` instantly, while the actual `commit` and `pr` commands run on an asynchronous worker task in the background of the same runtime.

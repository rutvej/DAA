# DAA Serverless Policy — Handling Escalation Without Persistent Storage

> **Status:** DRAFT — v0.1  
> **Date:** 2026-07-09  
> **Problem:** Escalation policies (error rate thresholds, sliding windows, cooldowns) currently depend on Postgres. How do they work in a stateless Cloud Run / Fargate container with no database?

---

## 1. What Policies Need From Storage

Looking at the current policy evaluation in `backend-api/src/routers/logs.py`:

```python
# Current policy evaluation requires:
# 1. POLICY CONFIG  — threshold, window_seconds, severity_keywords, cooldown_minutes
# 2. ERROR COUNTER  — count of errors in sliding window (query across Log table)
# 3. COOLDOWN STATE — is this fingerprint in cooldown? (query Incident table)
# 4. DEDUP STATE    — is there an active incident for this fingerprint? (query Incident table)
```

These break into two categories:

| Data type | Nature | Changes how often? |
|---|---|---|
| Policy config (threshold, window, keywords) | **Configuration** | Rarely — set once per app |
| Error counter (sliding window count) | **Runtime state** | Every incoming error |
| Cooldown state (fingerprint → expiry time) | **Runtime state** | Every investigation |
| Dedup state (active incidents) | **Runtime state** | Every investigation |

**Key insight:** Policy config is *configuration*, not *data*. Runtime state is *ephemeral counters*, not *records*.

---

## 2. Solution: Split Config from State

### 2.1 Policy Config → Policy-as-Code (YAML / env var)

Policies are configuration. They belong in code, not in a database.

**Option A: YAML config file** (mounted or baked into image)

```yaml
# daa-policy.yaml
apps:
  my-service:
    repo_url: https://github.com/owner/my-service.git
    language: python
    policies:
      - rule_type: error_rate_threshold
        threshold: 5              # trigger after 5 errors
        window_seconds: 120       # within 2 minutes
        cooldown_minutes: 30
      - rule_type: severity_immediate
        keywords: ["FATAL", "OOMKill", "PANIC", "DatabaseDeadlock"]

  payment-api:
    repo_url: https://github.com/owner/payment-api.git
    language: java
    policies:
      - rule_type: error_rate_threshold
        threshold: 3
        window_seconds: 60
        cooldown_minutes: 60
      - rule_type: severity_immediate
        keywords: ["FATAL", "OutOfMemoryError"]
```

**Option B: Environment variables** (for single-app deployments)

```bash
DAA_APP_NAME=my-service
DAA_REPO_URL=https://github.com/owner/my-service.git
DAA_THRESHOLD=5
DAA_WINDOW_SECONDS=120
DAA_COOLDOWN_MINUTES=30
DAA_SEVERITY_KEYWORDS=FATAL,OOMKill,PANIC
```

**Option C: Webhook payload includes policy** (zero config)

The alerting system (Prometheus, Sentry, etc.) already knows severity.
The webhook payload itself carries enough context:

```json
{
  "app_name": "my-service",
  "repo_url": "https://github.com/owner/my-service.git",
  "severity": "FATAL",
  "exception_type": "OOMKill",
  "stack_trace": "..."
}
```

If severity is FATAL/CRITICAL → investigate immediately, no threshold needed.
If severity is WARNING/ERROR → the alerting system already applied its own threshold before calling DAA.

**This means: for the minimal edition, the upstream alerting tool IS the policy engine.**

### 2.2 Runtime State → Three Options

| Option | Persistence | Cost | Complexity | Best for |
|---|---|---|---|---|
| **A) In-memory counters** | None (lost on restart) | Free | Trivial | Single instance, dev/demo |
| **B) Upstash Redis** | Serverless Redis | ~$0 (free tier: 10K cmd/day) | Low | Production Cloud Run / Fargate |
| **C) No counters at all** | None | Free | Zero | When upstream alerting handles thresholds |

---

## 3. Option A: In-Memory Counters (Zero Dependencies)

Perfect for single-instance deployments. Uses Python's built-in data structures.

```python
import time
from collections import defaultdict
from threading import Lock

class InMemoryPolicyEngine:
    """Sliding window error counter + cooldown tracker. No external deps."""
    
    def __init__(self):
        self._lock = Lock()
        # app_name → list of timestamps
        self._error_timestamps: dict[str, list[float]] = defaultdict(list)
        # fingerprint → cooldown_expiry_timestamp
        self._cooldowns: dict[str, float] = {}
    
    def record_error(self, app_name: str) -> int:
        """Record an error and return the current count in the sliding window."""
        now = time.time()
        with self._lock:
            self._error_timestamps[app_name].append(now)
            return self._count_in_window(app_name, window_sec=120)
    
    def _count_in_window(self, app_name: str, window_sec: int) -> int:
        """Count errors within the sliding window, pruning old entries."""
        cutoff = time.time() - window_sec
        timestamps = self._error_timestamps[app_name]
        # Prune old entries
        self._error_timestamps[app_name] = [t for t in timestamps if t > cutoff]
        return len(self._error_timestamps[app_name])
    
    def is_in_cooldown(self, fingerprint: str) -> bool:
        """Check if a fingerprint is in cooldown."""
        with self._lock:
            expiry = self._cooldowns.get(fingerprint)
            if expiry and time.time() < expiry:
                return True
            # Clean up expired
            if expiry:
                del self._cooldowns[fingerprint]
            return False
    
    def set_cooldown(self, fingerprint: str, cooldown_minutes: int = 30):
        """Set cooldown for a fingerprint."""
        with self._lock:
            self._cooldowns[fingerprint] = time.time() + (cooldown_minutes * 60)
```

**Limitations:**
- Lost on container restart (acceptable — Cloud Run restarts are rare during active use)
- Not shared across instances (acceptable — Cloud Run routes same client to same instance)
- Memory grows with error volume (mitigated by sliding window pruning)

---

## 4. Option B: Upstash Redis (Production Serverless)

For production deployments where state must survive restarts and span multiple instances.

**Why Upstash specifically:**
- **HTTP API** — works from Cloud Run without VPC setup (unlike Memorystore/ElastiCache)
- **Pay-per-request** — free tier covers 10,000 commands/day (plenty for error counting)
- **Scales to zero** — no cost when DAA is idle
- **Global replication** — optional, for multi-region deployments
- **No connection management** — HTTP, not TCP. No connection pool needed in serverless.

### 4.1 Setup

```bash
# One env var is all you need
UPSTASH_REDIS_URL=https://xxx.upstash.io
UPSTASH_REDIS_TOKEN=AxxxxYYY
```

### 4.2 Implementation

```python
import httpx
import time

class UpstashPolicyEngine:
    """Serverless Redis-backed policy engine using Upstash REST API."""
    
    def __init__(self, url: str, token: str):
        self.url = url
        self.headers = {"Authorization": f"Bearer {token}"}
    
    def _cmd(self, *args) -> dict:
        """Execute a Redis command via Upstash HTTP API."""
        resp = httpx.post(
            self.url,
            headers=self.headers,
            json=list(args),
            timeout=5.0
        )
        return resp.json()
    
    def record_error(self, app_name: str, window_sec: int = 120) -> int:
        """Record error timestamp and return count in sliding window."""
        key = f"daa:errors:{app_name}"
        now = time.time()
        cutoff = now - window_sec
        
        # Pipeline: add timestamp, remove old entries, count remaining, set TTL
        pipeline = [
            ["ZADD", key, str(now), f"{now}"],
            ["ZREMRANGEBYSCORE", key, "0", str(cutoff)],
            ["ZCARD", key],
            ["EXPIRE", key, str(window_sec * 2)]  # auto-cleanup
        ]
        
        resp = httpx.post(
            f"{self.url}/pipeline",
            headers=self.headers,
            json=pipeline,
            timeout=5.0
        )
        results = resp.json()
        return int(results[2]["result"])  # ZCARD result
    
    def is_in_cooldown(self, fingerprint: str) -> bool:
        """Check if fingerprint is in cooldown (key exists in Redis)."""
        result = self._cmd("EXISTS", f"daa:cooldown:{fingerprint}")
        return result.get("result", 0) == 1
    
    def set_cooldown(self, fingerprint: str, cooldown_minutes: int = 30):
        """Set cooldown with auto-expiry."""
        self._cmd("SET", f"daa:cooldown:{fingerprint}", "1", "EX", str(cooldown_minutes * 60))
    
    def check_dedup(self, fingerprint: str) -> bool:
        """Check if fingerprint is being actively processed."""
        result = self._cmd("EXISTS", f"daa:active:{fingerprint}")
        return result.get("result", 0) == 1
    
    def mark_active(self, fingerprint: str, ttl_seconds: int = 600):
        """Mark fingerprint as actively being investigated (10 min TTL)."""
        self._cmd("SET", f"daa:active:{fingerprint}", "1", "EX", str(ttl_seconds))
```

### 4.3 Redis key layout

```
daa:errors:{app_name}        → Sorted Set (timestamps, for sliding window count)
daa:cooldown:{fingerprint}   → String "1" with TTL (auto-expires after cooldown)
daa:active:{fingerprint}     → String "1" with TTL (auto-expires after 10 min)
```

All keys have TTLs → **Redis self-cleans. Zero maintenance.**

---

## 5. Option C: No Counters — Let Upstream Handle It (Recommended Default)

This is the most elegant approach for the minimal edition:

> **If you're using Prometheus/Sentry/Datadog/CloudWatch to trigger DAA via webhook, those systems already evaluated the threshold before calling you.**

The flow becomes:

```
Prometheus Alertmanager:
  - rule: error_rate > 5 for 2m  ← THEY handle the threshold
  - action: POST to DAA webhook  ← DAA only gets called when threshold is breached

DAA receives webhook:
  - Compute fingerprint
  - Check git dedup (does fix branch exist?)
  - If new → investigate
  - If exists → skip
```

**The upstream alerting tool IS the policy engine.** DAA doesn't need its own error counting.

### What DAA minimal still needs:

| Concern | Solution |
|---|---|
| **Dedup** (don't process same bug twice) | Git branch check (already in MINIMAL_DOCKER_SPEC) |
| **Cooldown** (don't re-process too soon) | In-memory dict with TTL (Option A) or Upstash (Option B) |
| **Threshold** (when to trigger) | **Handled by upstream alerting system** |
| **Severity routing** (FATAL → immediate) | **Handled by upstream alerting system** |

---

## 6. Unified Policy Engine Interface

The code should support all three options via a single interface:

```python
import os

class PolicyEngine:
    """Factory that returns the right policy engine based on config."""
    
    @staticmethod
    def create():
        upstash_url = os.environ.get("UPSTASH_REDIS_URL")
        upstash_token = os.environ.get("UPSTASH_REDIS_TOKEN")
        
        if upstash_url and upstash_token:
            return UpstashPolicyEngine(upstash_url, upstash_token)
        else:
            return InMemoryPolicyEngine()
```

Usage in the webhook handler:

```python
policy_engine = PolicyEngine.create()

@app.post("/webhook")
async def webhook(payload: WebhookPayload):
    fingerprint = compute_fingerprint(payload)
    
    # 1. Dedup check (git-based)
    if check_git_dedup(payload.repo_url, fingerprint):
        return {"status": "duplicate", "fingerprint": fingerprint}
    
    # 2. Cooldown check
    if policy_engine.is_in_cooldown(fingerprint):
        return {"status": "cooldown", "fingerprint": fingerprint}
    
    # 3. No threshold check needed — upstream already applied it
    #    (or use policy_engine.record_error() if running without upstream alerting)
    
    # 4. Investigate
    policy_engine.mark_active(fingerprint)
    result = await run_investigation(payload)
    policy_engine.set_cooldown(fingerprint)
    
    return result
```

---

## 7. Decision Matrix

| Deployment | Policy config | Runtime state | Recommended |
|---|---|---|---|
| **Cloud Run + Prometheus/Sentry** | Not needed (upstream handles it) | In-memory (Option A) | ✅ Simplest |
| **Cloud Run, high traffic** | YAML config file | Upstash Redis (Option B) | ✅ Production |
| **Fargate + custom SDK** | YAML or env vars | Upstash Redis (Option B) | ✅ Production |
| **Local Docker, dev/demo** | Env vars | In-memory (Option A) | ✅ Simplest |
| **Self-hosted, single server** | YAML config file | In-memory (Option A) | ✅ Good enough |

---

## 8. Environment Variables Summary

```bash
# ── Policy Config (optional — only if not using upstream alerting) ──
DAA_POLICY_FILE=/app/daa-policy.yaml    # Path to policy YAML
# OR per-app env vars:
DAA_THRESHOLD=5
DAA_WINDOW_SECONDS=120
DAA_COOLDOWN_MINUTES=30
DAA_SEVERITY_KEYWORDS=FATAL,OOMKill,PANIC

# ── Runtime State Backend (optional — defaults to in-memory) ──
UPSTASH_REDIS_URL=https://xxx.upstash.io
UPSTASH_REDIS_TOKEN=AxxxxYYY
```

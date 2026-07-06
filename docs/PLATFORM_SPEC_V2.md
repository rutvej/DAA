# DAA v2.0 — Autonomous SRE Incident Diagnosis Platform

## Complete Technical Specification

**Version:** 2.0  
**Date:** July 2026  
**Status:** Approved — Implemented  
**Authors:** DAA Core Team

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement & Market Validation (July 2026)](#2-problem-statement--market-validation-july-2026)
3. [Competitive Landscape & DAA's Differentiation](#3-competitive-landscape--daas-differentiation)
4. [Platform Vision: From Error-to-PR → Autonomous SRE](#4-platform-vision-from-error-to-pr--autonomous-sre)
5. [Core Architecture](#5-core-architecture)
6. [The Escalation Engine (No Alert Fatigue)](#6-the-escalation-engine-no-alert-fatigue)
7. [The 4-Dimension SRE Investigation Orchestration](#7-the-4-dimension-sre-investigation-orchestration)
8. [Surgical Code Retrieval (5-Tier Architecture)](#8-surgical-code-retrieval-5-tier-architecture)
9. [Anti-Recursion & Deduplication Mechanisms](#9-anti-recursion--deduplication-mechanisms)
10. [Failure Mode & Effects Analysis (FMEA)](#10-failure-mode--effects-analysis-fmea)
11. [Intelligent Output Matrix (PR vs. Ticket vs. Postmortem)](#11-intelligent-output-matrix-pr-vs-ticket-vs-postmortem)
12. [Multi-Model & Local LLM Support](#12-multi-model--local-llm-support)
13. [Multi-Language SDK Ecosystem](#13-multi-language-sdk-ecosystem)
14. [Cloud Logging & Observability Integration](#14-cloud-logging--observability-integration)
15. [Infrastructure & Deployment (Terraform)](#15-infrastructure--deployment-terraform)
16. [Database Schema & Models](#16-database-schema--models)
17. [API Surface](#17-api-surface)
18. [Agent Tool Registry](#18-agent-tool-registry)
19. [Security, Guardrails & Trust](#19-security-guardrails--trust)
20. [Implementation Roadmap](#20-implementation-roadmap)

---

## 1. Executive Summary

**DAA (Developer Agentic Assistant)** is an open-source, self-hosted **Autonomous SRE Incident Diagnosis Platform** that replaces the first 30–60 minutes of manual firefighting when production systems break.

Unlike traditional observability tools (Datadog, Sentry, PagerDuty) that dump raw alerts on engineers, DAA autonomously:

1. **Correlates logs across distributed microservices** (Python, Go, Node.js, Java, Ruby, .NET) using OpenTelemetry trace IDs and time-window analysis.
2. **Investigates across 4 dimensions** — recent code changes, infrastructure health, correlated logs, and diagnostic verification — exactly like a senior SRE would.
3. **Produces actionable output** — either a hotfix Pull Request (with verified tests), a Jira/GitHub Incident Ticket with a structured Postmortem report, or a script rerun recommendation.

DAA only activates on **escalation-worthy incidents** (user-defined thresholds), not on every transient error. It includes circuit breakers, deduplication fingerprinting, and confidence-gated guardrails to prevent infinite loops, hallucinated fixes, and alert fatigue.

---

## 2. Problem Statement & Market Validation (July 2026)

### 2.1 The Problem Is Real and Unsolved

In modern distributed architectures (Kubernetes, microservices, event-driven meshes), production incidents are **multi-service cascade failures**. When a Python API returns HTTP 500, the root cause might be:

- A Redis connection timeout in a Go worker (2 services upstream)
- A RabbitMQ queue deadlock caused by a recent deployment
- An environment variable misconfiguration after a Terraform apply
- A race condition in a background job triggered by a schema migration

**No single tool in 2026 connects all of these dots autonomously.**

### 2.2 What Exists Today (July 2026 Landscape)

| Category | Tools | What They Do | What They DON'T Do |
| :--- | :--- | :--- | :--- |
| **Observability** | Datadog, Grafana, New Relic, Splunk | Collect metrics, logs, traces. Display dashboards. | Don't investigate. Don't explain WHY. Don't correlate across services. Don't produce fixes. |
| **Alert Management** | PagerDuty, Opsgenie, incident.io | Route alerts to on-call engineers. Escalate. Track SLAs. | Don't investigate the alert. Don't read code. Don't produce PRs or postmortems. |
| **AI SRE Agents (Commercial)** | Resolve AI, Vibe OnCall, Shoreline | Resolve AI: Multi-agent investigation. Shoreline: Fleet-wide runbook automation. | Resolve AI: Complex setup, closed-source, expensive. Shoreline: Only executes known runbooks, no code-level reasoning. PagerDuty Copilot: Mostly documentation assistance, limited autonomous investigation. |
| **AI SRE Agents (Open Source)** | OpenSRE, Aurora (Arvo AI), IncidentFox | Investigation-phase assistants. Query cloud infra. Correlate alerts. | **None produce code PRs.** None have built-in SDK ecosystems. None handle the full lifecycle (investigate → fix code → verify tests → open PR). High operational overhead. No escalation thresholds. |

### 2.3 The Gap Nobody Is Filling

The critical gap in 2026 is that **no open-source tool provides the complete closed-loop**:

```
Escalation Trigger → Multi-Service Log Correlation → 4-Dimension Investigation 
→ Surgical Code Navigation → Verified Code Fix OR Structured Postmortem 
→ PR / Jira Ticket → Deduplication & Cooldown
```

**Specifically:**

1. **OpenSRE/Aurora/IncidentFox** stop at investigation. They produce an RCA report but never touch the code, never open a PR, never run tests. An engineer must still manually read the report, find the file, write the fix, run tests, and push.
2. **Resolve AI** comes closest but is closed-source, expensive, and does not produce code PRs.
3. **No open-source tool** has built-in multi-language SDKs for instrumenting applications, escalation threshold policies, or circuit breakers to prevent infinite agent loops.

**DAA fills this gap as an open-source, self-hosted, end-to-end platform.**

---

## 3. Competitive Landscape & DAA's Differentiation

### 3.1 Feature Matrix (DAA vs. Market)

| Feature | DAA v2.0 | OpenSRE | Aurora | IncidentFox | Resolve AI | PagerDuty |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Open Source | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Self-Hosted / Local LLMs | ✅ (Ollama) | ✅ | ✅ | Partial | ❌ | ❌ |
| Multi-Language SDK | ✅ (6 langs) | ❌ | ❌ | ❌ | ❌ | ❌ |
| Escalation Thresholds | ✅ | ❌ | ❌ | Partial | Partial | ✅ |
| Cross-Service Log Correlation | ✅ (Trace ID + Time Window) | Partial | Partial | ✅ | ✅ | ❌ |
| Code-Level Bug Fix (PR) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Test Verification Before PR | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Postmortem Generation | ✅ | Partial | ✅ | ✅ | ✅ | Partial |
| Jira/GitHub Ticket Creation | ✅ | ❌ | Partial | Partial | ✅ | ✅ |
| Anti-Recursion / Dedup | ✅ | ❌ | ❌ | ❌ | Partial | ❌ |
| Circuit Breaker (Agent) | ✅ | ❌ | ❌ | ❌ | Partial | ❌ |
| Terraform Deployment | ✅ | ❌ | ✅ | ❌ | N/A | N/A |

### 3.2 DAA's Unique Value Proposition

> **DAA is the only open-source platform that goes from alert escalation to verified code fix (or structured postmortem with Jira ticket) in a single autonomous pipeline, with built-in anti-recursion guardrails.**

---

## 4. Platform Vision: From Error-to-PR → Autonomous SRE

### 4.1 Current State (DAA v1.0)

```
SDK captures exception → Backend ingests log → RabbitMQ → Python Agent 
→ Agent reads code, writes fix → Opens GitHub PR
```

**Limitations of v1.0:**
- Triggered on EVERY error (alert fatigue)
- Looks at a single error payload in isolation (no cross-service correlation)
- No deduplication (same bug = infinite duplicate PRs)
- LLM reads entire files (token explosion, hallucination)
- Only outputs PRs (no Postmortems, no Tickets for infra issues)

### 4.2 Target State (DAA v2.0)

```
Escalation Policy breached → IncidentEscalationEvent → RabbitMQ 
→ SRE Agent (4-Dimension Investigation) → Surgical Code Retrieval 
→ Confidence-Gated Output (PR / Ticket / Postmortem) → Dedup & Cooldown
```

---

## 5. Core Architecture

### 5.1 System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        APPLICATION LAYER                            │
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │Python App│  │ Go Worker │  │ Node API │  │ Java Svc │  ...      │
│  │ (SDK)    │  │ (SDK)    │  │ (SDK)    │  │ (SDK)    │           │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘           │
│       │              │              │              │                │
│       └──────────────┴──────┬───────┴──────────────┘                │
│                             │ HTTP POST /api/logs                   │
│                             ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                   FASTAPI BACKEND                            │   │
│  │                                                              │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐   │   │
│  │  │Log Ingestion│  │  Escalation  │  │   Fingerprint &   │   │   │
│  │  │  & Storage  │  │    Engine    │  │   Deduplication    │   │   │
│  │  └──────┬──────┘  └──────┬───────┘  └────────┬──────────┘   │   │
│  │         │                │                    │              │   │
│  │         ▼                ▼                    ▼              │   │
│  │  ┌──────────┐    ┌──────────────┐    ┌───────────────┐      │   │
│  │  │PostgreSQL│    │ Redis Counter│    │ Incident State│      │   │
│  │  │  (Logs,  │    │  (Sliding    │    │   Machine     │      │   │
│  │  │  Fixes,  │    │   Window)    │    │ (Open/Cool/   │      │   │
│  │  │ Alerts)  │    │              │    │  Closed)      │      │   │
│  │  └──────────┘    └──────────────┘    └───────────────┘      │   │
│  │                                                              │   │
│  │  Only if threshold breached AND no active dedup match:       │   │
│  │         │                                                    │   │
│  │         ▼                                                    │   │
│  │  ┌──────────────┐                                            │   │
│  │  │   RabbitMQ   │── IncidentEscalationEvent ──┐              │   │
│  │  │   (Queue)    │                             │              │   │
│  │  └──────────────┘                             │              │   │
│  └───────────────────────────────────────────────┼──────────────┘   │
│                                                  │                  │
│                                                  ▼                  │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              PYTHON SRE REACT AGENT                          │   │
│  │                                                              │   │
│  │  ┌────────────────────────────────────────────────────────┐  │   │
│  │  │              TOOL REGISTRY                             │  │   │
│  │  │                                                        │  │   │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  │  │   │
│  │  │  │ view_file    │  │ query_corr   │  │ check_recent│  │  │   │
│  │  │  │ _slice       │  │ _logs        │  │ _changes    │  │  │   │
│  │  │  └──────────────┘  └──────────────┘  └─────────────┘  │  │   │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  │  │   │
│  │  │  │ grep_search  │  │ check_infra  │  │ read_repo   │  │  │   │
│  │  │  │ /find_symbol │  │ _alerts      │  │ _map        │  │  │   │
│  │  │  └──────────────┘  └──────────────┘  └─────────────┘  │  │   │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  │  │   │
│  │  │  │ run_tests    │  │ run_diag     │  │ git_tool    │  │  │   │
│  │  │  │              │  │ _script      │  │ (PR/MR)     │  │  │   │
│  │  │  └──────────────┘  └──────────────┘  └─────────────┘  │  │   │
│  │  │  ┌──────────────┐  ┌──────────────┐                   │  │   │
│  │  │  │ create_jira  │  │ semantic     │                   │  │   │
│  │  │  │ _ticket      │  │ _search      │                   │  │   │
│  │  │  └──────────────┘  └──────────────┘                   │  │   │
│  │  └────────────────────────────────────────────────────────┘  │   │
│  │                                                              │   │
│  │  Budget: max 8 tool calls, 300s hard timeout                 │   │
│  │  Confidence Gate: <85% on concurrency bugs → NO code PR      │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    ADMIN PANEL (React)                        │   │
│  │  • Incident Timeline    • Postmortem Viewer (1-click DL)     │   │
│  │  • Escalation Config    • Application Registry               │   │
│  │  • Agent Replay Logs    • Project Connections                 │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 Technology Stack

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| Backend API | Python / FastAPI | Log ingestion, escalation engine, REST API |
| Agent | Python / LangChain ReAct | Autonomous SRE investigation & remediation |
| Message Broker | RabbitMQ | Async job dispatch (log → agent) |
| Database | PostgreSQL | Persistent storage for logs, fixes, incidents, connections |
| Cache / Counters | Redis | Sliding-window error rate counters for escalation |
| Admin Panel | React.js | Dashboard for incident management |
| SDKs | Python, Node.js, Go, Java, Ruby, .NET | Client-side error capture & telemetry |
| Deployment | Terraform + Docker Compose | Cloud Run / ECS / ACA deployment |

---

## 6. The Escalation Engine (No Alert Fatigue)

### 6.1 Problem

Launching an LLM investigation on every transient HTTP 500 error is:
- **Expensive** ($0.05–$2.00 per investigation)
- **Noisy** (most 500s are transient retries, timeouts, or client errors)
- **Dangerous** (flooding the agent creates queue backlog and delayed response to real incidents)

### 6.2 Solution: Application-Level Escalation Policies

When users register an application in DAA, they define an **Escalation Policy**:

```json
{
  "application_id": "payment-service",
  "escalation_rules": [
    {
      "rule_type": "error_rate_threshold",
      "condition": "error_count >= 15 within 120 seconds",
      "description": "Trigger if 15+ errors in a 2-minute window"
    },
    {
      "rule_type": "error_rate_spike",
      "condition": "error_rate increase >= 300% vs previous 10-minute baseline",
      "description": "Trigger if error rate triples suddenly"
    },
    {
      "rule_type": "severity_immediate",
      "condition": "severity IN ('FATAL', 'OOMKill', 'DatabaseDeadlock', 'PANIC')",
      "description": "Immediately trigger on critical severity keywords"
    },
    {
      "rule_type": "external_webhook",
      "source": "prometheus_alertmanager | pagerduty | datadog",
      "description": "Trigger when an external monitoring system fires an alert"
    }
  ],
  "cooldown_minutes": 30,
  "max_concurrent_investigations": 2
}
```

### 6.3 Sliding Window Implementation (Redis)

```
┌────────────────────────────────────────────────────────────┐
│                   ESCALATION ENGINE FLOW                    │
│                                                            │
│  Incoming Log ──► Redis INCR (key: app:payment:errors)     │
│                   with TTL = window_seconds                │
│                          │                                 │
│                          ▼                                 │
│                   Current Count >= Threshold?              │
│                      │              │                      │
│                     YES             NO                     │
│                      │              │                      │
│                      ▼              ▼                      │
│              Check Dedup DB     Silently store log.        │
│              (Fingerprint?)     No agent triggered.        │
│                   │                                        │
│               No Match?                                    │
│                   │                                        │
│                   ▼                                        │
│          Push IncidentEscalationEvent to RabbitMQ          │
│          (contains: all logs in window, alert context)     │
└────────────────────────────────────────────────────────────┘
```

### 6.4 Database Model: `Application` and `EscalationPolicy`

```python
class Application(Base):
    __tablename__ = "applications"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    name = Column(String, nullable=False, unique=True)      # e.g., "payment-service"
    description = Column(String)                              # e.g., "Handles Stripe charges"
    language = Column(String)                                 # e.g., "python", "go"
    repository_url = Column(String)                           # e.g., "https://github.com/..."
    spec_file_path = Column(String)                           # path to OpenAPI/architecture spec
    team_owner = Column(String)                               # e.g., "payments-team"
    created_at = Column(DateTime, default=datetime.utcnow)
    
    escalation_policies = relationship("EscalationPolicy", back_populates="application")

class EscalationPolicy(Base):
    __tablename__ = "escalation_policies"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    application_id = Column(String, ForeignKey("applications.id"))
    rule_type = Column(String)           # "error_rate_threshold" | "severity_immediate" | "external_webhook" | "error_rate_spike"
    condition_value = Column(Integer)     # e.g., 15 (error count threshold)
    window_seconds = Column(Integer)      # e.g., 120 (2-minute window)
    severity_keywords = Column(JSON)      # e.g., ["FATAL", "OOMKill", "PANIC"]
    cooldown_minutes = Column(Integer, default=30)
    is_active = Column(Boolean, default=True)
    
    application = relationship("Application", back_populates="escalation_policies")
```

---

## 7. The 4-Dimension SRE Investigation Orchestration

### 7.1 How a Human SRE Investigates (The Gold Standard)

When a senior SRE wakes up at 3:00 AM for a P1 outage, they do NOT just read logs. They execute a systematic investigation across **4 dimensions**:

1. **What just changed?** → Check recent git commits, deployments, config changes, version bumps
2. **What is system health?** → Check CPU, memory, pod restarts, DB connection pools, queue depths
3. **What do logs say?** → Correlate logs from all related services in a synchronized time window
4. **Can we reproduce it?** → Rerun a failing script, hit a health check endpoint, run test suites

### 7.2 Agent Orchestration: The ReAct SRE Loop

The Python ReAct agent follows this explicit investigation workflow via its system prompt:

```
SYSTEM PROMPT (SRE Agent):

You are an autonomous SRE investigator. When you receive an 
IncidentEscalationEvent, follow this EXACT investigation protocol:

STEP 1 — CHANGE HORIZON: Call `check_recent_changes` to inspect:
  - Git commits/PRs merged in the last 24 hours for the affected service
  - CI/CD deployment history and Terraform/Helm diffs
  - Dependency version changes (Redis, DB, libraries)

STEP 2 — INFRASTRUCTURE HORIZON: Call `check_infra_alerts` to inspect:
  - Active cloud alerts (CPU spike, OOM, disk full, pod crash loops)
  - Database connection pool utilization
  - Queue depth / consumer lag on RabbitMQ / Kafka

STEP 3 — CORRELATED LOG HORIZON: Call `query_correlated_logs` to fetch:
  - All logs from ALL registered services within ±5 minutes of the incident
  - Filter by trace_id / correlation_id if available (OpenTelemetry)
  - Identify the cascade: which service failed FIRST?

STEP 4 — DIAGNOSTIC HORIZON: Call `run_diagnostic` to verify:
  - Execute health check scripts defined in the application spec
  - Run test suites (pytest, npm test, go test) if a code fix is proposed
  - Attempt to reproduce the failure in a sandboxed environment

STEP 5 — SYNTHESIZE & ACT:
  - Combine all 4 dimensions into a root cause hypothesis
  - Calculate confidence score (0-100)
  - If confidence >= 85% AND root cause is a code bug:
      → Write the fix, run tests, open a PR
  - If confidence < 85% OR root cause is infra/config/version:
      → Generate Postmortem report, open Jira/GitHub Ticket
  - NEVER attempt to fix race conditions, deadlocks, or concurrency 
    bugs with code PRs. Always escalate those to human review.

BUDGET: Max 8 tool calls. Hard timeout: 300 seconds.
If you cannot determine root cause within budget, escalate to human.
```

### 7.3 Investigation Dimension Details

#### Dimension 1: Change Horizon — `check_recent_changes`

| Data Source | What We Query | Why It Matters |
| :--- | :--- | :--- |
| GitHub / GitLab API | PRs merged in last 24h for affected repo | 80% of outages are caused by recent code changes |
| CI/CD Webhooks | Recent deployment timestamps | Correlate "deployed at 14:32" with "errors started at 14:35" |
| Terraform / Helm Diff | Infrastructure config changes | Catch "someone changed the Redis instance type" |
| Package Manager Diffs | `requirements.txt` / `go.mod` / `package.json` | Catch "Redis client library upgraded from v4 to v5" |

#### Dimension 2: Infrastructure Horizon — `check_infra_alerts`

| Signal | Source | Example Finding |
| :--- | :--- | :--- |
| CPU / Memory Saturation | Cloud Monitoring / Prometheus | "Go Worker pods at 98% memory — likely OOM imminent" |
| Pod Restart Count | Kubernetes API / Cloud Run Logs | "payment-service restarted 12 times in 5 minutes" |
| DB Connection Pool | Application metrics / Cloud SQL | "PostgreSQL max_connections reached (100/100)" |
| Queue Depth / Consumer Lag | RabbitMQ Management / Kafka | "payment_queue depth: 45,000 messages (normal: 50)" |

#### Dimension 3: Correlated Log Horizon — `query_correlated_logs`

**Strategy: Trace-ID first, Time-Window fallback.**

```
IF trace_id / correlation_id is present in the error payload:
    → Query logs WHERE trace_id = X across ALL services
    → Result: Exact 20-50 log lines for that single failing transaction

ELSE (no distributed tracing):
    → Query logs WHERE timestamp BETWEEN (error_time - 5min) AND (error_time + 5min)
      AND application_id IN (affected_service + its known dependencies)
    → Apply LLM summarization to compress >1000 lines into key events
```

#### Dimension 4: Diagnostic Horizon — `run_diagnostic`

| Scenario | Diagnostic Action | Expected Outcome |
| :--- | :--- | :--- |
| Failing test suite | Run `pytest -x` on cloned repo | Identify which test fails and why |
| Stuck background job | Rerun the specific job/script in sandbox | Check if it's a transient lock or persistent bug |
| Suspected config issue | Execute health check endpoint `GET /healthz` | Verify if the service can connect to its dependencies |
| Version mismatch | Run `redis-cli INFO server` or equivalent | Check actual vs. expected version |

---

## 8. Surgical Code Retrieval (5-Tier Architecture)

### 8.1 The Problem

In an enterprise repository with 100,000+ lines of code:
- **Token Limits:** Feeding the entire codebase exceeds context limits (128k–1M tokens)
- **Cost Explosion:** Reading all code costs $0.50–$2.00 per investigation
- **"Lost in the Middle" Effect:** LLMs lose reasoning accuracy when surrounded by irrelevant code
- **Hallucination Risk:** More irrelevant context = higher chance of hallucinated fixes

### 8.2 Solution: The LLM Never Reads Entire Files

Instead of reading full files or the entire repository, the agent navigates the codebase through **5 progressive tiers of precision**:

```
Tier 1: Stack-Trace Localization
  └─ Error says "file.py:142" → Read ONLY lines 120-160 (~300 tokens)

Tier 2: Symbol & AST Navigation  
  └─ Line 142 calls validate_account() → grep_search("def validate_account") 
     → Found at models/account.py:45 → Read ONLY lines 40-70

Tier 3: Repository Map (Skeletonization)
  └─ Need architectural context? Read compressed repo skeleton
     100,000 lines → 2,000-line skeleton (~6,000 tokens)
     Contains: file paths, class names, function signatures, docstrings ONLY

Tier 4: Semantic Code RAG (Vector / BM25 Search)
  └─ Conceptual lookup: "where is the redis timeout configured?"
     → Vector search returns top 3 relevant function chunks

Tier 5: Recent Git Diff Priority
  └─ 80% of bugs are in recently changed code
     → Read ONLY the diff of commits merged in last 24h
```

### 8.3 Token Budget Comparison

| Approach | Tokens Per Investigation | Cost (Gemini 2.5 Flash) | Accuracy |
| :--- | :--- | :--- | :--- |
| Naive: Read entire repo | 100,000–500,000 | $0.50–$2.00 | Low (lost-in-middle) |
| **DAA Surgical: 5-Tier** | **2,000–8,000** | **$0.01–$0.05** | **High (focused context)** |

### 8.4 Tier Details

#### Tier 1: Stack-Trace Slice Viewer (`view_file_slice`)

Every exception payload contains file paths, function names, and line numbers:
```
Traceback (most recent call last):
  File "src/services/payment.py", line 142, in process_charge
    result = validate_account(user_id)
  File "src/models/account.py", line 45, in validate_account
    return db.query(Account).filter_by(id=uid).one()
```

The agent calls:
```python
view_file_slice(file="src/services/payment.py", start=125, end=160)
```
→ Returns ~35 lines, ~300 tokens. The agent sees the exact bug context.

#### Tier 2: Symbol Navigation (`grep_search` / `find_symbol`)

If line 142 calls a function the agent hasn't seen:
```python
grep_search(query="def validate_account", search_path="src/")
# → Result: src/models/account.py:L45
view_file_slice(file="src/models/account.py", start=40, end=70)
```
The agent navigates by **symbols** (functions, classes, methods) — never by scrolling.

#### Tier 3: Repository Map (`read_repomap`)

When the agent needs architectural context (e.g., "which service calls which?"), it reads a pre-generated skeleton:

```python
# Example Repomap output (compressed from 100k-line repo):
# src/services/
#   payment.py
#     class PaymentService:
#       def process_charge(self, user_id: str, amount: float) -> dict
#       def refund_charge(self, charge_id: str) -> bool
#   notification.py
#     class NotificationService:
#       def send_email(self, to: str, template: str, context: dict) -> None
# src/models/
#   account.py
#     class Account(Base):
#       id: str
#       balance: float
#     def validate_account(uid: str) -> Account
```

The entire architecture is visible in ~6,000 tokens without any implementation details.

#### Tier 4: Semantic Code Search (`semantic_search`)

For conceptual lookups where the agent doesn't know the file or function name:
```python
semantic_search(query="redis connection timeout retry configuration")
# → Returns: src/config/redis.py:get_redis_client() (similarity: 0.92)
#            src/workers/base.py:retry_with_backoff() (similarity: 0.87)
```

Powered by offline BM25 or vector embedding index of function-level code chunks.

#### Tier 5: Recent Git Diff Priority (`check_recent_changes`)

Before searching the entire codebase, check what recently changed:
```bash
git log --oneline --since="24 hours ago" --stat
# → 3 files changed: src/services/payment.py, src/config/redis.py, docker-compose.yml
```

The agent reads only the diffs of these 3 files, since they are the most likely culprits.

---

## 9. Anti-Recursion & Deduplication Mechanisms

### 9.1 The Recursion Trap

Without safeguards, the following catastrophic loop occurs:

```
Bug in production → Agent wakes up → Opens PR #42 for the fix
→ Bug still in production (PR not merged yet!)
→ 2 minutes later: same bug → Agent wakes up AGAIN → Opens PR #43 (duplicate!)
→ Repeat forever: PR #44, #45, #46...
```

### 9.2 Four Anti-Recursion Mechanisms

#### Mechanism 1: Incident Fingerprinting & Deduplication

Every incoming error is hashed into a unique fingerprint:

```python
import hashlib

def generate_fingerprint(log_entry: dict) -> str:
    """
    Generate a unique fingerprint for an error by hashing:
    - Service name (which app)
    - Exception type (what kind of error)
    - Top non-library stack frame (where in user code)
    """
    raw = f"{log_entry['application_id']}:" \
          f"{log_entry['exception_type']}:" \
          f"{get_top_user_frame(log_entry['stack_trace'])}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
```

Before launching the agent, the backend checks:
```
IF fingerprint exists in active_incidents WHERE status IN ('investigating', 'pr_open', 'cooldown'):
    → SUPPRESS agent launch
    → Increment occurrence_count on existing incident
    → Add comment to existing PR/Ticket: "Recurred 18 times since investigation started"
ELSE:
    → Create new incident record
    → Launch SRE agent
```

#### Mechanism 2: "Awaiting Deployment" Cooldown Window

When the agent successfully opens a PR or creates a Jira Ticket:

```
Incident Status: 'investigating' → 'remediation_pending'
Cooldown Timer: 60 minutes (or until CI/CD deployment webhook received)

During cooldown:
  - All matching fingerprints are SUPPRESSED
  - Occurrence counter keeps incrementing
  - Optional: webhook from GitHub Actions on merge/deploy → end cooldown early
```

#### Mechanism 3: Circuit Breaker (Max Retries)

```
IF agent fails to produce a fix that passes run_tests after 2 attempts:
    → Circuit breaker TRIPS
    → Incident status: 'human_required'
    → Agent generates an Architectural Gap Report instead
    → Opens a Jira Story (not bug) tagged: "Requires Human Engineering Epic"
    → No further agent attempts for this fingerprint until manually reset

IF error type indicates a FEATURE GAP (e.g., NotImplementedError, HTTP 501):
    → Circuit breaker trips IMMEDIATELY on first attempt
    → Agent never tries to write code for missing features
```

#### Mechanism 4: ReAct Loop Budget & Hard Timeout

```
Agent Execution Constraints:
  - max_iterations: 8 tool calls (prevents infinite reasoning loops)
  - hard_timeout: 300 seconds (prevents hung agent processes)
  - max_tokens_per_investigation: 32,000 (prevents cost explosion)

IF budget exhausted:
    → Agent aborts gracefully
    → Writes partial findings to incident record
    → Escalates to human PagerDuty/Slack notification
```

### 9.3 Incident State Machine

```
                    ┌───────────┐
                    │  new_log  │
                    └─────┬─────┘
                          │
                    ┌─────▼─────┐     Threshold NOT met
                    │ evaluating├─────────────────────► (silently stored)
                    └─────┬─────┘
                          │ Threshold MET + No dedup match
                    ┌─────▼──────────┐
                    │ investigating  │
                    └─────┬──────────┘
                          │
               ┌──────────┼──────────┐
               │          │          │
        ┌──────▼───┐ ┌────▼────┐ ┌──▼──────────┐
        │ pr_open  │ │ ticket  │ │ human       │
        │          │ │ _created│ │ _required   │
        └──────┬───┘ └────┬────┘ └─────────────┘
               │          │         (circuit breaker)
        ┌──────▼──────────▼──┐
        │   cooldown         │
        │  (30-60 min TTL)   │
        └──────────┬─────────┘
                   │ TTL expires or deploy webhook
            ┌──────▼──────┐
            │   resolved  │
            └─────────────┘
```

---

## 10. Failure Mode & Effects Analysis (FMEA)

### 10.1 Comprehensive Failure Modes

| # | Failure Mode | Severity | Likelihood | Root Cause | Mitigation in DAA v2.0 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| F1 | **Context Explosion:** LLM receives 50k+ log lines in a 5-minute window from 20 services | Critical | High | Naive time-window querying without filtering | **OpenTelemetry Trace-ID filtering.** Query by trace_id first; fall back to time-window with LLM summarization (compress >1000 lines to key events before agent receives them). |
| F2 | **Infinite PR Loop:** Agent creates duplicate PRs for the same unmerged bug | Critical | High | No deduplication between incident occurrences | **SHA256 Fingerprinting + Dedup DB.** Check before launching agent. Cooldown window until PR merged/deployed. |
| F3 | **Hallucinated Fix:** LLM writes code that introduces new bugs or uses non-existent libraries | High | Medium | LLM confabulation on complex logic; hallucinated dependencies | **Mandatory `run_tests` verification.** Dependency freeze (agent cannot modify `requirements.txt` / `package.json` without human approval). Circuit breaker after 2 failed test attempts. |
| F4 | **Concurrency/Race Bug Misdiagnosis:** LLM attempts to fix a distributed race condition with a naive code patch | Critical | Medium | LLMs fundamentally struggle with stateful concurrent reasoning | **Confidence-gated guardrail.** If issue involves locks, transactions, or concurrency patterns → confidence < 85% → agent MUST NOT produce code PR. Only Postmortem + Ticket. |
| F5 | **Test Environment Mismatch:** `run_tests` passes locally but fix breaks production because tests lack cloud dependencies | High | High | Local test environment differs from production (missing S3, Redis, gRPC mocks) | **CI/CD Verification Mode.** Agent pushes draft branch → real CI/CD pipeline (GitHub Actions / GitLab CI) runs tests → agent waits for webhook result. Optional: Docker Compose / DevContainer sandboxing. |
| F6 | **Secret Leakage:** Agent copies API keys, passwords, or tokens from log files into PR descriptions or Jira tickets | Critical | Medium | Production logs contain sensitive data; LLM includes them verbatim | **Regex Secret Scrubber** on all log ingestion. Patterns: API keys, JWTs, passwords, connection strings, AWS credentials. Scrub BEFORE logs reach LLM context. |
| F7 | **Agent Stuck in Loop:** ReAct agent enters infinite tool-call cycle (e.g., repeatedly reading same file) | Medium | Low | LLM reasoning loop on ambiguous problems | **Hard budget: 8 tool calls, 300s timeout.** Graceful abort with partial findings escalated to human. |
| F8 | **Cloud Logging API Rate Limits:** Agent floods CloudWatch / GCP Logging / Azure Monitor with queries | Medium | Medium | Unthrottled cloud API calls during multi-service investigation | **Rate limiter on cloud logging tools.** Max 10 API calls per investigation. Cache recent query results in Redis (5-min TTL). |
| F9 | **Stale Repomap / Code Index:** Semantic search returns outdated function locations after recent refactor | Low | Medium | Index not updated after git push | **Webhook-triggered re-indexing.** On git push webhook → regenerate repomap and re-index code embeddings. Lazy refresh: if agent finds stale result → trigger re-index and retry. |
| F10 | **Multi-Tenant Data Leakage:** In shared deployments, Agent for Service A accidentally reads logs from Service B | Critical | Low | Insufficient access control on log queries | **Strict application_id scoping.** Every tool query is automatically scoped to the incident's application_id and its declared dependencies. Agent cannot query logs from unrelated applications. |

---

## 11. Intelligent Output Matrix (PR vs. Ticket vs. Postmortem)

### 11.1 Decision Tree

The agent does NOT always produce a PR. The output depends on the root cause:

```
Root Cause Analysis Complete
  │
  ├─ Is it a CODE BUG? (syntax error, logic error, unhandled exception, wrong return value)
  │   ├─ Confidence >= 85%?
  │   │   ├─ YES → Write fix → Run tests → Tests pass?
  │   │   │   ├─ YES → Open GitHub/GitLab PR (hotfix branch)
  │   │   │   └─ NO → Circuit breaker (attempt 2/2)
  │   │   │       ├─ Still fails → Escalate: Jira Ticket + Postmortem
  │   │   │       └─ Passes on retry → Open PR
  │   │   └─ NO → Generate Postmortem + Jira Ticket (hypothesis only)
  │   │
  │   └─ Is it a CONCURRENCY / RACE CONDITION / DEADLOCK?
  │       └─ ALWAYS → Postmortem + Jira Ticket (NEVER auto-fix)
  │
  ├─ Is it an INFRA / CONFIG issue? (Redis OOM, DB connection exhausted, env var missing)
  │   └─ Generate Postmortem → Jira Ticket with exact remediation commands
  │       (e.g., "helm rollback redis 1.4.2" or "set MAX_CONNECTIONS=200")
  │
  ├─ Is it a VERSION MISMATCH? (library upgrade broke API compatibility)
  │   └─ Generate Postmortem → Jira Ticket with rollback/pin recommendation
  │
  ├─ Is it a TRANSIENT FAILURE? (rate limit hit, temporary network partition, job lock)
  │   └─ Recommend script rerun / job retry → Jira Ticket (informational)
  │
  └─ Is it a FEATURE GAP? (NotImplementedError, missing endpoint, unbuilt feature)
      └─ Generate Architectural Gap Report → Jira Story (not bug)
          Tag: "Requires Human Engineering Epic"
```

### 11.2 Output Formats

#### Pull Request (Code Bug Fix)
```markdown
## 🔧 DAA Automated Hotfix: NullPointerException in PaymentService

**Incident ID:** INC-2026-07-05-001
**Root Cause:** `validate_account()` returns None when account is soft-deleted,
but `process_charge()` does not check for None before accessing `.balance`.

**Fix Applied:**
- Added null check in `src/services/payment.py:142`
- Added test case in `tests/test_payment.py`

**Verification:** ✅ All 47 tests pass (pytest exit code 0)
**Confidence:** 94%

**Correlated Evidence:**
- 23 occurrences of this error in the last 15 minutes
- No infrastructure alerts active
- No recent deployments (last deploy: 6 hours ago)
```

#### Jira / GitHub Issue Ticket (Infrastructure / Complex Issue)
```markdown
## 🚨 Incident Ticket: Redis Connection Pool Exhaustion

**Severity:** P1 — Production Impact
**Affected Services:** payment-service, notification-service
**Incident Window:** 2026-07-05 14:32 UTC – 14:47 UTC

**Root Cause Analysis:**
Redis connection pool maxed out at 50 connections after Go Worker 
started leaking connections due to missing `defer conn.Close()` in 
the retry handler (introduced in PR #387, merged 2 hours ago).

**Recommended Actions:**
1. Immediate: Restart Go Worker pods to clear leaked connections
2. Short-term: Rollback PR #387 or apply fix to `workers/retry.go:78`
3. Long-term: Add connection pool monitoring alert (threshold: 80%)

**Evidence Gathered:**
- Redis INFO: connected_clients=50/50 (saturated)
- Go Worker logs: 142 "connection refused" errors in 5 minutes
- Git: PR #387 modified `workers/retry.go` (merged at 12:30 UTC)
```

#### Postmortem Report (Always Generated)
```markdown
## 📋 Postmortem Report

**Incident ID:** INC-2026-07-05-001
**Duration:** 15 minutes (14:32 – 14:47 UTC)
**Impact:** Payment processing failed for ~340 transactions

### Timeline
- 12:30 UTC: PR #387 merged (Go Worker retry handler refactor)
- 14:30 UTC: Go Worker deployment completed
- 14:32 UTC: First Redis "connection refused" errors
- 14:35 UTC: DAA escalation threshold breached (15 errors / 2 min)
- 14:36 UTC: DAA SRE Agent investigation started
- 14:38 UTC: Root cause identified (connection leak in retry handler)
- 14:40 UTC: Jira Ticket created with rollback recommendation
- 14:47 UTC: Human engineer rolled back PR #387. Errors ceased.

### Root Cause
Missing `defer conn.Close()` in the Go Worker retry handler caused 
Redis connections to leak on each retry attempt.

### What Went Well
- DAA identified the root cause within 2 minutes of escalation
- Cross-service log correlation correctly traced the cascade

### Action Items
- [ ] Fix connection leak in Go Worker (owner: backend-team)
- [ ] Add Redis connection pool monitoring alert
- [ ] Add integration test for connection cleanup in retry paths
```

---

## 12. Multi-Model & Local LLM Support

### 12.1 Supported Providers

| Provider | Models | Use Case | Configuration |
| :--- | :--- | :--- | :--- |
| **Google Gemini** | gemini-2.5-flash, gemini-2.5-pro | Cloud-hosted, fast, cost-effective | `LLM_PROVIDER=google`, `LLM_API_KEY=...` |
| **OpenAI** | gpt-4o, gpt-4.1, o3-mini | Cloud-hosted, strong reasoning | `LLM_PROVIDER=openai`, `LLM_API_KEY=...` |
| **Anthropic** | claude-sonnet-4, claude-opus-4 | Cloud-hosted, excellent code reasoning | `LLM_PROVIDER=anthropic`, `LLM_API_KEY=...` |
| **Ollama (Local)** | llama3, mistral, codellama, qwen2.5-coder | Self-hosted, air-gapped, free | `LLM_PROVIDER=ollama`, `LLM_BASE_URL=http://localhost:11434/v1` |
| **vLLM (Local)** | Any HuggingFace model | High-throughput self-hosted inference | `LLM_PROVIDER=ollama`, `LLM_BASE_URL=http://vllm-server:8000/v1` |

### 12.2 Dynamic Initialization

```python
# app/python-agent/src/llm_config.py

def get_chat_model():
    provider = os.environ.get("LLM_PROVIDER", "google")
    model = os.environ.get("LLM_MODEL", "gemini-2.5-flash")
    
    if provider == "google":
        return ChatGoogleGenerativeAI(model=model, api_key=os.environ["LLM_API_KEY"])
    elif provider == "openai":
        return ChatOpenAI(model=model, api_key=os.environ["LLM_API_KEY"])
    elif provider == "anthropic":
        return ChatAnthropic(model=model, api_key=os.environ["LLM_API_KEY"])
    elif provider in ("ollama", "local"):
        return ChatOpenAI(
            model=model,
            base_url=os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1"),
            api_key="not-needed"
        )
```

---

## 13. Multi-Language SDK Ecosystem

### 13.1 Supported Languages

| Language | SDK Location | Status |
| :--- | :--- | :--- |
| Python | `app/daa-sdk/python-sdk/` | ✅ Implemented |
| Node.js / JavaScript | `app/daa-sdk/node-sdk/` | ✅ Implemented |
| Go | `app/daa-sdk/go-sdk/` | ✅ Implemented |
| Java | `app/daa-sdk/java-sdk/` | ✅ Implemented |
| Ruby | `app/daa-sdk/ruby-sdk/` | ✅ Implemented |
| .NET / C# | `app/daa-sdk/dotnet-sdk/` | ✅ Implemented |

### 13.2 SDK Payload Format (Standardized)

All SDKs send the following JSON payload to `POST /api/logs`:

```json
{
  "application_id": "payment-service",
  "level": "ERROR",
  "message": "NullPointerException in process_charge",
  "stack_trace": "File \"src/services/payment.py\", line 142...",
  "exception_type": "NullPointerException",
  "timestamp": "2026-07-05T14:32:15.123Z",
  "trace_id": "abc123def456",
  "correlation_id": "req-789",
  "environment": "production",
  "metadata": {
    "user_id": "usr_123",
    "endpoint": "POST /api/charge",
    "http_status": 500
  }
}
```

### 13.3 OpenTelemetry Integration (v2.0 Addition)

SDKs will automatically extract and forward:
- `trace_id` from OpenTelemetry context (if instrumented)
- `span_id` for precise transaction tracing
- `parent_span_id` for dependency chain reconstruction

---

## 14. Cloud Logging & Observability Integration

### 14.1 Supported Cloud Log Sources

| Provider | Integration Method | Logs Captured |
| :--- | :--- | :--- |
| **AWS CloudWatch** | CloudWatch Logs subscription filter → SNS → DAA webhook | Application logs, Lambda logs, ECS/EKS logs |
| **GCP Cloud Logging** | Log Router sink → Pub/Sub → DAA webhook | GKE logs, Cloud Run logs, Cloud Functions logs |
| **Azure Monitor** | Diagnostic settings → Event Hub → DAA webhook | AKS logs, App Service logs, Function App logs |
| **Prometheus Alertmanager** | Webhook receiver in DAA | Metric-based alerts (CPU, memory, error rate) |
| **PagerDuty** | Webhook integration | Incident escalation events |
| **Datadog** | Webhook integration | Monitor alerts and log-based alerts |

### 14.2 Cloud Logging Fetch (Agent-Initiated)

When trace-ID log correlation is insufficient, the agent can actively query cloud logging APIs:

```python
# Agent tool: fetch_cloud_logs
def fetch_cloud_logs(
    provider: str,          # "aws" | "gcp" | "azure"
    log_group: str,         # e.g., "/aws/ecs/payment-service"
    start_time: datetime,   # incident_time - 5 minutes
    end_time: datetime,     # incident_time + 5 minutes
    filter_pattern: str     # e.g., "ERROR" or trace_id
) -> list[LogEntry]:
    """
    Rate limited: max 10 API calls per investigation.
    Results cached in Redis with 5-minute TTL.
    """
```

---

## 15. Infrastructure & Deployment (Terraform)

### 15.1 Supported Deployment Targets

| Platform | Terraform Module | Services Deployed |
| :--- | :--- | :--- |
| **Google Cloud Run** | `terraform/gcp/` | Backend API, Python Agent, Cloud SQL, Memorystore (Redis) |
| **AWS ECS / Fargate** | `terraform/aws/` | Backend API, Python Agent, RDS, ElastiCache |
| **Azure Container Apps** | `terraform/azure/` | Backend API, Python Agent, Azure PostgreSQL, Azure Cache |
| **Docker Compose (Local)** | `docker-compose.yml` | All services (dev/staging) |

### 15.2 One-Click Setup

```bash
# Interactive setup wizard
python setup_keys.py

# Prompts for:
# 1. LLM provider selection (Gemini / OpenAI / Ollama)
# 2. API key entry or local model pull (ollama pull llama3)
# 3. GitHub/GitLab token configuration
# 4. Jira API key and project configuration
# 5. Cloud logging credentials (optional)
# 6. Generate .env file
```

---

## 16. Database Schema & Models

### 16.1 Entity Relationship Diagram

```
┌──────────────────┐     ┌────────────────────┐     ┌──────────────────┐
│   Application    │────<│  EscalationPolicy  │     │      Alert       │
├──────────────────┤     ├────────────────────┤     ├──────────────────┤
│ id (PK)          │     │ id (PK)            │     │ id (PK)          │
│ name             │     │ application_id (FK)│     │ application_id   │
│ description      │     │ rule_type          │     │ alert_type       │
│ language         │     │ condition_value     │     │ severity         │
│ repository_url   │     │ window_seconds     │     │ message          │
│ spec_file_path   │     │ severity_keywords  │     │ source           │
│ team_owner       │     │ cooldown_minutes   │     │ is_active        │
│ created_at       │     │ is_active          │     │ created_at       │
└────────┬─────────┘     └────────────────────┘     │ resolved_at      │
         │                                          └──────────────────┘
         │
    ┌────┴───────────┐     ┌──────────────────┐     ┌──────────────────┐
    │    LogEntry     │────<│    Incident      │────<│      Fix         │
    ├────────────────┤     ├──────────────────┤     ├──────────────────┤
    │ id (PK)        │     │ id (PK)          │     │ id (PK)          │
    │ application_id │     │ fingerprint      │     │ incident_id (FK) │
    │ level          │     │ application_id   │     │ fix_type         │
    │ message        │     │ status           │     │ pr_url           │
    │ stack_trace    │     │ occurrence_count  │     │ ticket_url       │
    │ exception_type │     │ first_seen_at    │     │ postmortem_md    │
    │ trace_id       │     │ last_seen_at     │     │ confidence_score │
    │ correlation_id │     │ cooldown_until   │     │ agent_log        │
    │ timestamp      │     │ agent_attempts   │     │ created_at       │
    │ metadata (JSON)│     │ root_cause_summary│    └──────────────────┘
    └────────────────┘     │ created_at       │
                           └──────────────────┘

    ┌──────────────────┐
    │ProjectConnection │
    ├──────────────────┤
    │ id (PK)          │
    │ application_id   │
    │ provider         │   ("github" | "gitlab" | "jira")
    │ base_url         │
    │ token_encrypted  │
    │ repo_owner       │
    │ repo_name        │
    │ jira_project_key │
    │ created_at       │
    └──────────────────┘
```

---

## 17. API Surface

### 17.1 Core Endpoints

| Method | Endpoint | Purpose |
| :--- | :--- | :--- |
| `POST` | `/api/logs` | Ingest error logs from SDKs / cloud webhooks |
| `GET` | `/api/logs` | List all ingested logs (with filters) |
| `GET` | `/api/logs/correlated` | Query correlated logs across services (trace_id / time window) |
| `POST` | `/api/applications` | Register a new application |
| `GET` | `/api/applications` | List registered applications |
| `PUT` | `/api/applications/{id}` | Update application settings |
| `POST` | `/api/applications/{id}/escalation-policies` | Create escalation policy |
| `GET` | `/api/applications/{id}/escalation-policies` | List escalation policies |
| `POST` | `/api/alerts` | Ingest infrastructure alerts |
| `GET` | `/api/alerts/active` | Get active alerts (for agent correlation) |
| `POST` | `/api/incidents` | Create incident (usually system-triggered) |
| `GET` | `/api/incidents` | List incidents (with status filter) |
| `GET` | `/api/incidents/{id}` | Get incident details + postmortem |
| `PATCH` | `/api/incidents/{id}` | Update incident status (cooldown, resolved) |
| `POST` | `/api/projects` | Register project connection (GitHub/GitLab/Jira) |
| `GET` | `/api/projects` | List project connections |
| `GET` | `/api/fixes` | List generated fixes |
| `GET` | `/api/fixes/{id}` | Get fix details + postmortem download |
| `POST` | `/api/webhooks/github` | Receive GitHub deployment/merge webhooks |
| `POST` | `/api/webhooks/pagerduty` | Receive PagerDuty escalation webhooks |
| `POST` | `/api/webhooks/cloudwatch` | Receive AWS CloudWatch log events |
| `POST` | `/api/webhooks/gcp-logging` | Receive GCP Cloud Logging events |

---

## 18. Agent Tool Registry

### 18.1 Complete Tool Inventory

| Tool Name | Category | Purpose | Token Cost |
| :--- | :--- | :--- | :--- |
| `view_file_slice` | Code Navigation | Read specific line range (±20 lines around error) | ~300 tokens |
| `grep_search` | Code Navigation | Find function/class definitions by name | ~200 tokens |
| `read_repomap` | Code Navigation | Read compressed repository skeleton | ~6,000 tokens |
| `semantic_search` | Code Navigation | Vector/BM25 conceptual code search | ~500 tokens |
| `check_recent_changes` | Change Horizon | Query recent git commits, PRs, deployments | ~1,000 tokens |
| `query_correlated_logs` | Log Horizon | Fetch cross-service logs by trace_id or time window | ~2,000 tokens |
| `check_infra_alerts` | Infra Horizon | Query active alerts, pod health, resource saturation | ~500 tokens |
| `fetch_cloud_logs` | Log Horizon | Query AWS CloudWatch / GCP Logging / Azure Monitor | ~1,500 tokens |
| `run_tests` | Diagnostic | Execute test suites (pytest, npm test, go test) | ~500 tokens |
| `run_diagnostic_script` | Diagnostic | Execute health checks or rerun failed scripts | ~300 tokens |
| `read_service_specs` | Context | Read OpenAPI specs or architecture docs | ~1,000 tokens |
| `write_file` | Remediation | Write code fix to cloned repository | ~200 tokens |
| `create_pr` | Remediation | Open GitHub PR / GitLab MR | ~100 tokens |
| `create_jira_ticket` | Remediation | Create Jira Issue with postmortem | ~100 tokens |
| `create_github_issue` | Remediation | Create GitHub Issue with postmortem | ~100 tokens |

### 18.2 Tool Execution Constraints

```yaml
agent_execution_budget:
  max_tool_calls: 8
  hard_timeout_seconds: 300
  max_tokens_per_investigation: 32000
  max_cloud_api_calls: 10
  
guardrails:
  concurrency_bug_confidence_threshold: 85   # Below this → no code PR
  max_fix_attempts_before_circuit_break: 2
  forbidden_file_modifications:
    - "requirements.txt"
    - "package.json"
    - "go.mod"
    - "pom.xml"
    - "Gemfile"
    - "*.csproj"
  secret_scrub_patterns:
    - "AKIA[0-9A-Z]{16}"          # AWS Access Key
    - "sk-[a-zA-Z0-9]{48}"        # OpenAI API Key
    - "ghp_[a-zA-Z0-9]{36}"       # GitHub PAT
    - "eyJ[a-zA-Z0-9_-]*\\.[a-zA-Z0-9_-]*\\.[a-zA-Z0-9_-]*"  # JWT
    - "password\\s*[:=]\\s*\\S+"   # Generic password patterns
```

---

## 19. Security, Guardrails & Trust

### 19.1 Secret Scrubbing Pipeline

All logs are scrubbed BEFORE reaching the LLM:

```
SDK → POST /api/logs → [Secret Scrubber] → [Log Storage] → [Agent Context]
                              │
                    Regex patterns match:
                    - AWS keys → "***AWS_KEY***"
                    - JWTs → "***JWT_TOKEN***"
                    - Passwords → "***REDACTED***"
                    - Connection strings → "***CONN_STRING***"
```

### 19.2 Dependency Freeze

The agent is prohibited from modifying dependency manifests (`requirements.txt`, `package.json`, `go.mod`, etc.) in automated PRs. If a fix requires a new dependency, the agent must:
1. Flag it in the PR description
2. Request human approval before the dependency is added

### 19.3 Application-Scoped Data Isolation

Every tool query is automatically scoped:
```python
# All queries include this filter:
WHERE application_id IN (
    incident.application_id,
    ...incident.application.declared_dependencies
)
```

The agent cannot access logs, code, or configurations of applications not related to the current incident.

### 19.4 Agent Replay & Audit Trail

Every agent investigation is fully logged:
- Every tool call, its arguments, and its response
- The LLM's reasoning at each step
- Final decision rationale and confidence score
- Total token usage and cost

This replay log is stored in the `Fix.agent_log` field and visible in the Admin Panel for complete auditability.

---

## 20. Implementation Roadmap

### Phase 1: Foundation (Weeks 1–2)
- [ ] Implement `Application` and `EscalationPolicy` database models
- [ ] Build Redis sliding-window escalation engine
- [ ] Implement `Incident` model with fingerprinting and state machine
- [ ] Build deduplication check in log ingestion pipeline
- [ ] Add `POST /api/applications` and escalation policy endpoints

### Phase 2: Agent Upgrade (Weeks 3–4)
- [ ] Implement `view_file_slice` tool (replace full-file reading)
- [ ] Implement `grep_search` / `find_symbol` tool
- [ ] Build repomap generator (AST skeletonization via ctags/tree-sitter)
- [ ] Implement `read_repomap` tool
- [ ] Implement `query_correlated_logs` tool (trace_id + time-window)
- [ ] Implement `check_recent_changes` tool (GitHub/GitLab API)
- [ ] Upgrade agent system prompt to enforce 4-Dimension investigation protocol

### Phase 3: Guardrails & Output (Weeks 5–6)
- [ ] Implement confidence scoring in agent decision logic
- [ ] Build circuit breaker mechanism (max 2 attempts)
- [ ] Implement secret scrubbing regex pipeline on log ingestion
- [ ] Implement Jira ticket creation tool
- [ ] Implement GitHub Issue creation tool
- [ ] Add structured Postmortem report template generation
- [ ] Build cooldown timer with CI/CD deployment webhook integration

### Phase 4: Observability & Cloud (Weeks 7–8)
- [ ] Build webhook receivers for CloudWatch, GCP Logging, Azure Monitor
- [ ] Implement `fetch_cloud_logs` agent tool with rate limiting
- [ ] Add Prometheus Alertmanager webhook receiver
- [ ] Build PagerDuty webhook integration (inbound alerts + outbound escalation)
- [ ] Implement agent replay viewer in Admin Panel

### Phase 5: Polish & Production (Weeks 9–10)
- [ ] Semantic code search (BM25/vector embedding index)
- [ ] CI/CD verification mode (push draft branch → wait for CI webhook)
- [ ] Admin Panel: application registry UI, escalation policy editor
- [ ] Admin Panel: incident timeline and postmortem viewer
- [ ] Load testing and performance optimization
- [ ] Documentation and contributor guide

---

## Appendix A: Glossary

| Term | Definition |
| :--- | :--- |
| **Escalation Policy** | User-defined rules that determine when an error pattern becomes a "burning issue" worthy of agent investigation |
| **Fingerprint** | SHA256 hash of (service + exception type + top stack frame) used to deduplicate identical errors |
| **Cooldown** | Time window after a fix is proposed during which duplicate incidents are suppressed |
| **Circuit Breaker** | Safety mechanism that stops the agent from retrying after N failed fix attempts |
| **Repomap** | Compressed skeleton of a codebase (file paths + function signatures only, no implementation) |
| **Surgical Retrieval** | Strategy where the LLM reads only specific code slices instead of entire files |
| **ReAct Loop** | Reason + Act agent pattern where the LLM alternates between thinking and calling tools |
| **Trace ID** | OpenTelemetry distributed tracing identifier that links logs across services for one transaction |
| **Postmortem** | Structured incident report containing timeline, root cause, impact, and action items |

---

## Appendix B: Configuration Reference

```bash
# .env file — complete configuration

# === LLM Configuration ===
LLM_PROVIDER=google                    # google | openai | anthropic | ollama
LLM_MODEL=gemini-2.5-flash            # Model name
LLM_API_KEY=your-api-key-here         # API key (not needed for ollama)
LLM_BASE_URL=                         # Custom endpoint (for ollama/vLLM)

# === Database ===
DATABASE_URL=postgresql://user:pass@localhost:5432/daa

# === Message Broker ===
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# === Redis (Escalation Counters) ===
REDIS_URL=redis://localhost:6379/0

# === GitHub Integration ===
GITHUB_TOKEN=ghp_xxxxx
GITHUB_DEFAULT_OWNER=your-org
GITHUB_DEFAULT_REPO=your-repo

# === GitLab Integration ===
GITLAB_TOKEN=glpat-xxxxx
GITLAB_BASE_URL=https://gitlab.com

# === Jira Integration ===
JIRA_BASE_URL=https://your-org.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-jira-token
JIRA_PROJECT_KEY=PROJ

# === Cloud Logging (Optional) ===
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1
GCP_PROJECT_ID=
GCP_CREDENTIALS_JSON=
AZURE_LOG_ANALYTICS_WORKSPACE_ID=
AZURE_LOG_ANALYTICS_KEY=

# === Agent Constraints ===
AGENT_MAX_ITERATIONS=8
AGENT_HARD_TIMEOUT_SECONDS=300
AGENT_MAX_TOKENS=32000
AGENT_CONFIDENCE_THRESHOLD=85
AGENT_MAX_FIX_ATTEMPTS=2
AGENT_COOLDOWN_MINUTES=30
```

# DAA Deployment Combinations Matrix — Unified Serverless to Datacenter Blueprint

> **Status:** DRAFT — v0.1  
> **Date:** 2026-07-09  
> **Goal:** Map out every possible architectural configuration of DAA, demonstrating how it scales from a zero-database stateless Cloud Run setup to a massive bare-metal enterprise deployment.

---

## 1. The Operational Dimensions

DAA is governed by four configuration axes:

1. **Log/Alert Source**: How errors are received (DAA SDK vs. Prometheus/Sentry webhooks).
2. **Authentication & Identity**: How access is authorized (Cloud IAM, API Keys, or Custom User JWTs).
3. **Git Storage Paradigm**: How code is read and written (REST API-only vs. Local Workspace Clones).
4. **Queue Broker**: How jobs are buffered and scaled (Async Inline, Cloud MQ, or Dedicated Message Queue).

---

## 2. Configuration Combinations Matrix

The following table maps the 6 primary deployment profiles, ordering from the most lightweight serverless option to the heaviest enterprise datacenter setup.

| Profile | Log Source | Authentication | State/DB Mode | Git Mode | Queue Mode | Ideal Platforms |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Pure Serverless (Zero-Infra)** | Existing Alerting (Sentry/Prometheus) | Cloud IAM (GCP/AWS) | **None (No DB)** | `api` (Clone-free) | `sync` (Cloud Run concurrency) | Google Cloud Run, AWS Fargate |
| **2. Edge API-Key Webhook** | Existing Alerting (Sentry/Prometheus) | API Key Header | **None (No DB)** | `api` (Clone-free) | `sync` (Inline background) | Docker Run, Vercel, Fly.io |
| **3. Serverless SDK (Light-State)** | DAA Telemetry SDK | Cloud IAM (GCP/AWS) | **Upstash Redis** (Policy state only) | `api` (Clone-free) | `sync` (Inline background) | Cloud Run + Upstash |
| **4. Self-Hosted Edge (Single VM)** | DAA Telemetry SDK | API Key or Custom User Auth | **SQLite** (Persistent DB file) | `api` (Clone-free) | `sync` (Threaded worker) | Single VM, local Docker |
| **5. Hybrid Serverless Queue** | DAA Telemetry SDK | Cloud IAM | **Upstash Redis** | `api` or `local` | **Cloud MQ** (Pub/Sub or SQS) | AWS ECS/Fargate + SQS |
| **6. Enterprise Datacenter** | SDK + Alerts | Custom JWT Auth | **Postgres DB** | `local` (Workspace cache) | **RabbitMQ / Kafka** | Bare metal, Kubernetes, VPC |

---

## 3. Dimension Deep-Dives & Architectural Trade-offs

### 3.1 Log Source vs. Policy & Database Requirements

The error source directly dictates whether DAA needs a policy engine database:

*   **Existing Alerting System (Prometheus / Sentry / Datadog)**:
    *   *No local database needed.*
    *   The alerting system acts as the policy engine: it has already calculated error thresholds, sliding windows, and deduplication alerts before calling DAA.
    *   DAA only processes actual escalated incidents. Cooldowns can be tracked in memory or via simple branch name check lookups on the git remote (`git ls-remote`).
*   **DAA SDK**:
    *   *State database needed.*
    *   Because the SDK streams raw, unaggregated errors directly from the application runtime, DAA must perform deduplication, sliding window counts, and cooldown checks.
    *   This requires a state store: either **Upstash Redis** (for serverless environments) or **SQLite/Postgres** (for stateful servers).

---

### 3.2 Authentication & User Control vs. Database

*   **GCP IAM / AWS IAM (Cloud Native)**:
    *   *No database needed.*
    *   Access is managed entirely by the cloud provider (e.g., Cloud Run IAM policies, API Gateways, or AWS Cognito). DAA trusts the inbound identity header.
*   **API Key (Simple Webhook Auth)**:
    *   *No database needed.*
    *   A simple environment variable checks if `X-DAA-API-KEY` matches.
*   **Custom JWT Auth (Standard DAA)**:
    *   *Database required.*
    *   If you need individual user sign-ins, user management, and JWT generation, you must run a database (SQLite or Postgres) to store user credentials.

---

### 3.3 Git Operation Mode: REST API-Only vs. Local Cloning

Why not use the API-only mode everywhere to save disk space?

*   **REST API-Only (`api`)**:
    *   *Pros:* Zero local disk usage. Extremely fast startup. Ideal for serverless runtimes.
    *   *Cons:* Rate limits on GitHub/GitLab (e.g., 5,000 requests/hour limit). Cannot run tests locally. The LLM cannot perform a broad grep over the entire repo easily without calling the API multiple times.
*   **Local Cloning (`local`)**:
    *   *Pros:* No API rate limits for reading code. Fast local grep. Allows the agent to run unit tests and linters locally (`mvn test`, `npm test`) to verify the code fix actually works before opening the PR.
    *   *Cons:* High disk space. Heavy. Takes time to clone on cold-starts.

**Rule of Thumb:** Use `api` for quick, lightweight serverless deployments. Use `local` if you want DAA to validate fixes locally by running tests before pushing branches.

---

### 3.4 The Queue Spectrum

*   **Synchronous / Inline Queue (`sync`)**:
    *   FastAPI receives the webhook, immediately spawns an async task, and returns `status: accepted`.
    *   The request scaling is delegated to the hosting platform (e.g. Cloud Run auto-scaling).
*   **Cloud MQ (Serverless Queue)**:
    *   GCP Pub/Sub or AWS SQS buffers the error events and invokes DAA instances. Excellent for durability without running servers.
*   **Dedicated Queue (RabbitMQ / Kafka)**:
    *   Essential for large-scale enterprise deployments with dedicated worker pools. Guarantees message delivery and handles complex routing/dead-lettering.

---

## 4. Visualizing the Deployment Extremes

### Extreme A: Pure Stateless Cloud Run (Zero Infra)

```
┌──────────────────────────────────────────────────────────┐
│              Cloud Run (Zero Database)                   │
│                                                          │
│  Sentry Webhook ────▶ [FastAPI App] ──────▶ API Git      │
│  (Auth: Cloud IAM)     (Queue: Inline)       (GitHub/    │
│                        (Policy: None)        GitLab)     │
└──────────────────────────────────────────────────────────┘
```

### Extreme B: Enterprise Datacenter (Maximum Durability)

```
┌──────────────────────────────────────────────────────────┐
│                Enterprise Datacenter                     │
│                                                          │
│  SDK telemtry ──▶ [FastAPI API] ──▶ [Postgres]           │
│                         │                                │
│                         ▼                                │
│                   [RabbitMQ]                             │
│                         │                                │
│                         ▼                                │
│                   [Agent Workers] ──▶ Local Git Workspace│
└──────────────────────────────────────────────────────────┘
```

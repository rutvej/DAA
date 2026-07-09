# DAA Alert Integrations — Zero-SDK Adoption via Existing Observability Tools

> **Status:** DRAFT — v0.1  
> **Date:** 2026-07-09  
> **Insight:** Instead of asking users to install a DAA SDK, let them point their existing alerting tools (Prometheus, Sentry, Datadog, CloudWatch, PagerDuty, etc.) at DAA's webhook. Where they currently send alerts to Slack/email/PagerDuty, they add DAA as another webhook destination. **Zero code changes. Zero new dependencies.**

---

## 1. The Problem With SDKs

The current approach:
```
App code → import daa_sdk → daa_sdk.report(error) → DAA API
```

**Barriers to adoption:**
- User must modify application code
- User must install a new dependency (`pip install daa-sdk`, `npm install daa-sdk`)
- User must configure the SDK (API URL, token, app name)
- User must redeploy their application
- Every language needs a separate SDK (Go, Python, Node, Java, Ruby, .NET)

**The 2026 reality:** Every production app already has logging and alerting configured. Prometheus, Sentry, Datadog, CloudWatch — they're already catching the errors. They just send notifications to Slack/email instead of to an agent that can fix them.

---

## 2. The New Approach: DAA as a Webhook Receiver

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Your App   │────▶│  Existing Alerting│────▶│  DAA Webhook │
│  (no changes)│     │  (Prometheus,     │     │  POST /ingest│
│              │     │   Sentry, etc.)   │     │  /prometheus │
│              │     │                  │     │  /sentry     │
│              │     │  Where you'd     │     │  /datadog    │
│              │     │  send to Slack...│     │  /cloudwatch │
│              │     │  also send to DAA│     │              │
└─────────────┘     └──────────────────┘     └─────────────┘
```

**Zero code changes. Just add a webhook URL to your existing alerting config.**

---

## 3. Supported Integrations

### 3.1 Prometheus Alertmanager

**User's existing `alertmanager.yml`:**
```yaml
receivers:
  - name: 'slack-and-daa'
    slack_configs:
      - api_url: 'https://hooks.slack.com/xxx'     # existing
    webhook_configs:
      - url: 'https://your-daa.run.app/ingest/prometheus'  # ← add this line
        send_resolved: true
```

**DAA receives Alertmanager's standard JSON:**
```json
{
  "status": "firing",
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "HighErrorRate",
        "severity": "critical",
        "service": "payment-api",
        "namespace": "production"
      },
      "annotations": {
        "summary": "Error rate > 5% for payment-api",
        "description": "NullPointerException in PaymentHandler.java:42"
      },
      "startsAt": "2026-07-09T18:00:00Z",
      "generatorURL": "http://prometheus:9090/graph?g0.expr=..."
    }
  ]
}
```

**DAA adapter extracts:**
- `app_name` ← `labels.service`
- `exception_type` ← parsed from `annotations.description`
- `severity` ← `labels.severity`
- `repo_url` ← looked up from app config (YAML or env var)

---

### 3.2 Sentry (Webhooks)

**Sentry → Settings → Integrations → Webhooks:**
```
URL: https://your-daa.run.app/ingest/sentry
```

**Sentry sends:**
```json
{
  "action": "created",
  "data": {
    "issue": {
      "id": "12345",
      "title": "NullPointerException: Cannot read property 'id' of undefined",
      "culprit": "src/handlers/payment.js",
      "level": "error",
      "platform": "javascript",
      "project": {
        "slug": "payment-api",
        "name": "Payment API"
      },
      "metadata": {
        "type": "NullPointerException",
        "value": "Cannot read property 'id' of undefined",
        "filename": "src/handlers/payment.js"
      }
    }
  }
}
```

**DAA adapter extracts:**
- `app_name` ← `data.issue.project.slug`
- `exception_type` ← `data.issue.metadata.type`
- `error_file` ← `data.issue.metadata.filename`
- `stack_trace` ← `data.issue.title`

---

### 3.3 Datadog (Webhooks)

**Datadog → Monitors → Notification → @webhook-daa:**
```
URL: https://your-daa.run.app/ingest/datadog
```

**Datadog sends:**
```json
{
  "id": "12345",
  "title": "[Triggered] High error rate on payment-api",
  "body": "Error rate for payment-api exceeded threshold...",
  "tags": ["service:payment-api", "env:production"],
  "priority": "P1",
  "alert_type": "error",
  "event_type": "alert"
}
```

**DAA adapter extracts:**
- `app_name` ← parsed from `tags` (`service:payment-api`)
- `severity` ← `priority` or `alert_type`
- `description` ← `body`

---

### 3.4 Google Cloud Alerting (Cloud Monitoring)

**Cloud Monitoring → Alert Policy → Notification Channel → Webhook:**
```
URL: https://your-daa.run.app/ingest/gcp-alerting
```

**GCP sends:**
```json
{
  "incident": {
    "incident_id": "abc123",
    "resource_name": "payment-api",
    "state": "open",
    "summary": "Cloud Run service payment-api error rate above 5%",
    "condition_name": "High Error Rate",
    "url": "https://console.cloud.google.com/monitoring/..."
  }
}
```

---

### 3.5 AWS CloudWatch Alarms (via SNS → Lambda → DAA)

**CloudWatch → SNS Topic → Lambda function → DAA webhook**

Or simpler with **Amazon EventBridge:**
```
CloudWatch Alarm → EventBridge Rule → API Destination (DAA webhook)
```

---

### 3.6 PagerDuty (Webhooks V3)

**PagerDuty → Integrations → Generic Webhooks V3:**
```
URL: https://your-daa.run.app/ingest/pagerduty
```

---

### 3.7 Opsgenie

**Opsgenie → Settings → Integrations → Webhook:**
```
URL: https://your-daa.run.app/ingest/opsgenie
```

---

### 3.8 Grafana Alerting (Unified Alerting)

**Grafana → Alerting → Contact Points → Webhook:**
```
URL: https://your-daa.run.app/ingest/grafana
```

Grafana's webhook format is nearly identical to Alertmanager's — the same adapter handles both.

---

## 4. Universal Ingest Adapter Architecture

```python
# ingest/router.py

from fastapi import APIRouter, Request

router = APIRouter(prefix="/ingest")

@router.post("/prometheus")
async def ingest_prometheus(request: Request):
    payload = await request.json()
    jobs = PrometheusAdapter.parse(payload)
    for job in jobs:
        await enqueue_investigation(job)
    return {"status": "accepted", "jobs": len(jobs)}

@router.post("/sentry")
async def ingest_sentry(request: Request):
    payload = await request.json()
    job = SentryAdapter.parse(payload)
    if job:
        await enqueue_investigation(job)
    return {"status": "accepted"}

@router.post("/datadog")
async def ingest_datadog(request: Request):
    payload = await request.json()
    job = DatadogAdapter.parse(payload)
    if job:
        await enqueue_investigation(job)
    return {"status": "accepted"}

@router.post("/gcp-alerting")
async def ingest_gcp(request: Request):
    payload = await request.json()
    job = GCPAlertingAdapter.parse(payload)
    if job:
        await enqueue_investigation(job)
    return {"status": "accepted"}

@router.post("/generic")
async def ingest_generic(request: Request):
    """Catch-all for any webhook — attempts auto-detection of format."""
    payload = await request.json()
    job = GenericAdapter.auto_detect_and_parse(payload)
    if job:
        await enqueue_investigation(job)
    return {"status": "accepted"}
```

### Adapter Interface

```python
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class InvestigationJob:
    app_name: str
    repo_url: Optional[str]     # looked up from config if not in payload
    exception_type: str
    error_file: Optional[str]
    line_number: Optional[int]
    stack_trace: Optional[str]
    log_content: Optional[str]
    severity: str               # "info", "warning", "error", "critical", "fatal"
    source: str                 # "prometheus", "sentry", "datadog", etc.
    raw_payload: dict           # original payload for debugging

class PrometheusAdapter:
    @staticmethod
    def parse(payload: dict) -> List[InvestigationJob]:
        jobs = []
        for alert in payload.get("alerts", []):
            if alert.get("status") != "firing":
                continue
            labels = alert.get("labels", {})
            annotations = alert.get("annotations", {})
            
            jobs.append(InvestigationJob(
                app_name=labels.get("service") or labels.get("job") or labels.get("app", "unknown"),
                repo_url=None,  # looked up from config
                exception_type=labels.get("alertname", "Unknown"),
                error_file=None,
                line_number=None,
                stack_trace=annotations.get("description", ""),
                log_content=annotations.get("summary", ""),
                severity=labels.get("severity", "error"),
                source="prometheus",
                raw_payload=alert,
            ))
        return jobs

class SentryAdapter:
    @staticmethod
    def parse(payload: dict) -> Optional[InvestigationJob]:
        if payload.get("action") != "created":
            return None
        issue = payload.get("data", {}).get("issue", {})
        metadata = issue.get("metadata", {})
        
        return InvestigationJob(
            app_name=issue.get("project", {}).get("slug", "unknown"),
            repo_url=None,
            exception_type=metadata.get("type", issue.get("title", "Unknown")),
            error_file=metadata.get("filename"),
            line_number=None,
            stack_trace=issue.get("title", ""),
            log_content=str(issue.get("culprit", "")),
            severity=issue.get("level", "error"),
            source="sentry",
            raw_payload=payload,
        )
```

---

## 5. App-to-Repo Mapping

When alerts come from Prometheus/Sentry/Datadog, they include the **app name** but not the **repo URL**. DAA needs the repo URL to clone the code and create PRs.

### Solution: App registry config

```yaml
# daa-apps.yaml (or env vars)
apps:
  payment-api:
    repo_url: https://github.com/myorg/payment-api.git
    language: java
    
  user-service:
    repo_url: https://github.com/myorg/user-service.git
    language: python
    
  frontend:
    repo_url: https://github.com/myorg/frontend.git
    language: typescript
```

Or as a single env var:
```bash
DAA_APP_REGISTRY='{"payment-api":"https://github.com/myorg/payment-api.git","user-service":"https://github.com/myorg/user-service.git"}'
```

---

## 6. Adoption Comparison: SDK vs. Alert Integration

| Aspect | DAA SDK (current) | Alert Integration (new) |
|---|---|---|
| **Code changes** | Yes (import SDK, add calls) | **None** |
| **New dependency** | Yes (per language) | **None** |
| **Redeploy app** | Yes | **No** |
| **Setup time** | 30–60 min | **5 min** (add webhook URL) |
| **Error detail** | Full (stack trace, variables) | Varies by source |
| **Language support** | 6 SDKs to maintain | **Universal** (any language, any framework) |
| **Maintenance burden** | High (SDK per language) | **Low** (one adapter per alerting tool) |

---

## 7. Hybrid Approach: SDK + Alert Integrations

The SDK and alert integrations are not mutually exclusive:

```
                    ┌──────────────────┐
  SDK (detailed) ──▶│                  │
                    │   DAA Webhook    │──▶ Agent Investigation
  Prometheus ──────▶│   /ingest/*      │
                    │                  │
  Sentry ─────────▶│   Normalizes all │
                    │   to same format │
  Datadog ────────▶│                  │
                    └──────────────────┘
```

- **SDK path** provides richer context (exact stack trace, local variables, request context)
- **Alert path** provides zero-friction adoption (no code changes)
- Both feed into the same investigation pipeline

---

## 8. Quick Start Examples

### "I use Prometheus + Alertmanager"

```yaml
# Add to your alertmanager.yml receivers:
webhook_configs:
  - url: 'https://your-daa.run.app/ingest/prometheus'
    http_config:
      bearer_token: 'your-daa-api-key'
```
**Done. 2 lines. No code changes.**

### "I use Sentry"

```
Sentry Dashboard → Settings → Integrations → Internal Integration → Webhooks
URL: https://your-daa.run.app/ingest/sentry
Events: issue.created
```
**Done. 1 URL. No code changes.**

### "I use Datadog"

```
Datadog → Monitors → Edit Monitor → Notification
Add: @webhook-daa
Configure webhook URL: https://your-daa.run.app/ingest/datadog
```
**Done. 1 URL. No code changes.**

### "I use Google Cloud Monitoring"

```bash
gcloud alpha monitoring channels create \
  --display-name="DAA Agent" \
  --type=webhook_tokenauth \
  --channel-labels=url=https://your-daa.run.app/ingest/gcp-alerting
```
**Done. 1 command. No code changes.**

---

## 9. Implementation Plan

### Phase 1: Core adapters
1. `PrometheusAdapter` — highest priority (most common in self-hosted)
2. `SentryAdapter` — highest priority (most common in SaaS)
3. `GenericAdapter` — auto-detect format from any webhook

### Phase 2: Cloud-native adapters
4. `GCPAlertingAdapter` — for Cloud Run users
5. `DatadogAdapter` — popular in enterprise
6. `GrafanaAdapter` — shares format with Prometheus

### Phase 3: Incident management adapters
7. `PagerDutyAdapter`
8. `OpsgenieAdapter`

### New file structure in `minimal/`:
```
daa_minimal/
├── ingest/
│   ├── __init__.py
│   ├── router.py              # FastAPI routes for /ingest/*
│   ├── base.py                # InvestigationJob dataclass
│   ├── prometheus_adapter.py
│   ├── sentry_adapter.py
│   ├── datadog_adapter.py
│   ├── gcp_adapter.py
│   ├── grafana_adapter.py
│   ├── pagerduty_adapter.py
│   └── generic_adapter.py    # Auto-detect format
├── ...
```

---

## 10. The SDK Still Has Value

The SDK is **not deprecated** — it provides features that alert integrations can't:

| Feature | Alert Integration | SDK |
|---|---|---|
| Full stack trace with local variables | ❌ | ✅ |
| Request context (headers, body) | ❌ | ✅ |
| Custom metadata | ❌ | ✅ |
| Correlation IDs | ❌ | ✅ |
| Real-time streaming (not batched) | ❌ | ✅ |

**Recommendation:** Market alert integrations for **adoption** (zero friction), SDK for **power users** (richer context).

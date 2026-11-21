<div align="center">

# DAA GitHub Action

**Your app breaks. DAA investigates and opens a PR — right inside GitHub Actions.**

No hosting. No PAT tokens. No infrastructure.

[![GitHub Action](https://img.shields.io/badge/GitHub_Action-DAA-purple?logo=github-actions)](https://github.com/rutvej/DAA)

</div>

---

## ⚡ Quick Start (2 steps)

### Step 1: Add your LLM API key as a secret

Go to **Settings → Secrets and variables → Actions → New repository secret**

| Secret Name | Value |
|---|---|
| `GEMINI_API_KEY` | Your [Google AI Studio](https://aistudio.google.com/app/apikey) API key |

> 💡 Also supports `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` — just change `llm_provider`.

### Step 2: Add the workflow file

Create `.github/workflows/daa.yml` in your repo:

```yaml
name: DAA - Auto Debug
on:
  issues:
    types: [opened, labeled]
  workflow_dispatch:
    inputs:
      error_description:
        description: 'Paste the error/stack trace'
        required: true

permissions:
  contents: write
  pull-requests: write
  issues: write

jobs:
  investigate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: rutvej/DAA/action@main
        with:
          llm_provider: google
          llm_api_key: ${{ secrets.GEMINI_API_KEY }}
```

**That's it.** Open a bug issue with the label `daa` and watch DAA investigate.

---

## 🔌 All Trigger Types

### 1. Issues (Automatic)

When someone opens an issue labeled `daa`, DAA reads the issue body, investigates the error, and opens a fix PR.

```yaml
on:
  issues:
    types: [opened, labeled]
```

**Issue format:** Just describe the bug. If you include a stack trace in a code block, DAA will extract it automatically.

### 2. Manual Dispatch (Paste & Fix)

Go to **Actions → DAA → Run workflow** and paste a stack trace.

```yaml
on:
  workflow_dispatch:
    inputs:
      error_description:
        description: 'Paste the error/stack trace'
        required: true
```

### 3. External Webhooks (Sentry, PagerDuty, etc.)

Point your alerting tool at the GitHub API to trigger DAA via `repository_dispatch`:

```bash
curl -X POST "https://api.github.com/repos/OWNER/REPO/dispatches" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -d '{
    "event_type": "daa-alert",
    "client_payload": {
      "exception_type": "NullPointerException",
      "stack_trace": "at com.example.Service.process(Service.java:42)",
      "error_file": "src/main/java/Service.java"
    }
  }'
```

```yaml
on:
  repository_dispatch:
    types: [daa-alert]
```

### 4. Scheduled Scan

Periodically scan for open bug issues and auto-investigate:

```yaml
on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
```

---

## ⚙️ Configuration

| Input | Default | Description |
|---|---|---|
| `llm_provider` | `google` | LLM provider: `google`, `openai`, `anthropic` |
| `llm_api_key` | *required* | API key for the LLM provider (pass via `secrets.*`) |
| `llm_model` | auto | Model override (e.g. `gemini-2.5-flash`, `gpt-4o`) |
| `agent_mode` | `full` | `full` (4-dimension investigation) or `fast` (quick fix) |
| `max_tool_calls` | `8` | Safety cap on agent tool calls |
| `target_branch` | `main` | Base branch for fix PRs |
| `label_filter` | `daa` | Only trigger on issues with this label (empty = all) |
| `app_name` | repo name | Application name override |
| `error_description` | auto | Manual error/stack trace (for `workflow_dispatch`) |

### Outputs

| Output | Description |
|---|---|
| `pr_url` | URL of the created PR (if any) |
| `outcome` | `pr_created`, `escalated`, `skipped`, or `error` |
| `postmortem` | Path to the generated postmortem file |

---

## 🔒 Security

- **No PAT tokens needed** — uses the auto-injected `GITHUB_TOKEN` scoped to this repo only
- **Secrets never logged** — LLM API keys are passed via GitHub encrypted secrets
- **Ephemeral compute** — each run uses a fresh, disposable GitHub runner
- **Agent safety cap** — hard limit on tool calls prevents runaway LLM costs
- **No data leaves your control** — code context goes directly to your configured LLM provider

---

## 💰 Cost

| Resource | Free Tier |
|---|---|
| GitHub Actions | 2,000 minutes/month (public repos: unlimited) |
| LLM API | Depends on provider (Gemini free tier: 1500 req/day) |

A typical DAA investigation uses **~3 minutes** of runner time and **~5-8 LLM calls**.

---

## How It Works

```
Bug issue opened (or manual dispatch, or external webhook)
        ↓
GitHub Action runner starts (ephemeral, free)
        ↓
DAA agent investigates across 4 dimensions:
   • Git commits  → what changed recently?
   • App logs     → what's the stack trace?
   • Traces       → which request triggered it?
   • Source code  → AST navigation to the exact line
        ↓
Agent creates a branch, applies fix, opens PR
        ↓
DAA comments back on the issue with results
        ↓
You review the PR and merge.
```

---

## Comparison with Self-Hosted DAA

| | Self-Hosted (Docker) | GitHub Action |
|---|---|---|
| **Steps to start** | 5+ | 2 |
| **Hosting needed** | Yes | No |
| **PAT token** | Required | Not needed |
| **Cost** | Your server | Free |
| **Best for** | Production monitoring, Sentry/PagerDuty integration | Open source projects, small teams, quick fixes |

> The GitHub Action is a **zero-friction on-ramp**. For production monitoring with real-time alerting, see the [full DAA deployment guide](../DEPLOYMENT.md).

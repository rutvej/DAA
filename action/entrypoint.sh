#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# DAA GitHub Action — Entrypoint
# Extracts error context from the GitHub event, configures the agent, and runs.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

echo "🔍 DAA GitHub Action — Debugging Autonomous Agent"
echo "═══════════════════════════════════════════════════"

# ── 1. Map Action Inputs to Agent Environment Variables ────────────────────
# GitHub Actions passes inputs as INPUT_<NAME> environment variables (uppercase).
export LLM_PROVIDER="${INPUT_LLM_PROVIDER:-google}"
export LLM_API_KEY="${INPUT_LLM_API_KEY:-}"
export LLM_MODEL="${INPUT_LLM_MODEL:-}"
export DAA_AGENT_MODE="${INPUT_AGENT_MODE:-full}"
export DAA_MAX_TOOL_CALLS="${INPUT_MAX_TOOL_CALLS:-8}"
export DAA_TOOL_CALL_WARNING_AT="$(( ${INPUT_MAX_TOOL_CALLS:-8} - 3 ))"
export DAA_TARGET_BRANCH="${INPUT_TARGET_BRANCH:-main}"
export DAA_LABEL_FILTER="${INPUT_LABEL_FILTER:-daa}"

# Map provider-specific key names so the agent's llm_config.py can find them
case "$LLM_PROVIDER" in
  google)
    export GEMINI_API_KEY="$LLM_API_KEY"
    export GOOGLE_API_KEY="$LLM_API_KEY"
    ;;
  openai)  export OPENAI_API_KEY="$LLM_API_KEY" ;;
  anthropic) export ANTHROPIC_API_KEY="$LLM_API_KEY" ;;
esac

# ── 2. Configure Git to use GITHUB_TOKEN ───────────────────────────────────
# GITHUB_TOKEN is auto-injected by GitHub Actions. No PAT needed.
if [ -n "${GITHUB_TOKEN:-}" ]; then
  git config --global url."https://x-access-token:${GITHUB_TOKEN}@github.com/".insteadOf "https://github.com/"
  export DAA_GIT_TOKEN="${GITHUB_TOKEN}"
  export GITHUB_TOKEN="${GITHUB_TOKEN}"
  echo "✅ Git authentication configured via GITHUB_TOKEN"
else
  echo "⚠️  No GITHUB_TOKEN found. PR creation will fail."
fi

# ── 3. Derive repo info from GITHUB_REPOSITORY ────────────────────────────
export GIT_HOST="${GIT_HOST:-https://github.com}"
export GIT_ORG="${GIT_ORG:-${GITHUB_REPOSITORY_OWNER:-$(echo $GITHUB_REPOSITORY | cut -d/ -f1)}}"
export DAA_REPO_URL="${GIT_HOST}/${GITHUB_REPOSITORY}.git"

# App name: use input override or default to repo name
if [ -n "${INPUT_APP_NAME:-}" ]; then
  export DAA_APP_NAME="${INPUT_APP_NAME}"
else
  export DAA_APP_NAME="$(echo $GITHUB_REPOSITORY | cut -d/ -f2)"
fi

# ── 4. Stateless mode overrides ───────────────────────────────────────────
export DAA_MODE=action
export DAA_DB_PROVIDER=none
export DAA_QUEUE_MODE=sync
export DAA_GIT_MODE=api
export DAA_AUTH_ENABLED=false
export DAA_TRIGGER_SOURCE="github-action"

echo "📋 Config: provider=$LLM_PROVIDER | mode=$DAA_AGENT_MODE | repo=$GITHUB_REPOSITORY | app=$DAA_APP_NAME"
echo "═══════════════════════════════════════════════════"

# ── 5. Run the DAA Action Runner ──────────────────────────────────────────
exec python -u /app/action_runner.py

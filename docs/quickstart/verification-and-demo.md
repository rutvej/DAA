# Verification and Demo Workflow

This guide demonstrates a fully self-contained verification workflow using the `daa test` synthetic error generator, eliminating the need for external dummy repositories.

## Step 1: Install & Initialize
```bash
git clone https://github.com/rutvej/DAA.git
cd DAA
./install.sh
source ~/.bashrc # Ensure daa CLI is on PATH

# Run the interactive setup wizard
daa init
```
*Note: During `daa init`, select **Google Gemini** (or your preferred LLM) and choose your target deployment profile.*

## Step 2: Deploy Services (Choose Profile A or B)
### Profile A: Single-Container Standalone (Stateless Serverless / Edge)
```bash
docker build -t daa-standalone:latest .
docker run -d --name daa -p 8080:8080 --env-file .env daa-standalone:latest
export DAA_BACKEND_API_URL="http://localhost:8080"
```

### Profile B: Distributed Full-Stack Cluster (Docker Compose)
```bash
docker compose up -d --build
export DAA_BACKEND_API_URL="http://localhost:8000"
```

## Step 3: Verify Platform Health
```bash
curl -X GET "${DAA_BACKEND_API_URL}/health"
# Expected Output: {"status": "ok"}

# Or using the CLI:
daa status
```

## Step 4: Register a Target Application
Register a real repository you own (or a local bare git repo):
```bash
daa register --name demo-service \
  --repo https://github.com/your-org/demo-service.git \
  --language python
```

## Step 5: Configure Escalation Thresholds
Set a policy so that any single error triggers immediate agent escalation:
```bash
daa policy --app demo-service --threshold 1 --window 60
```

## Step 6: Send Synthetic Telemetry & Trigger AI Triage
Use `daa test` to simulate an unhandled exception occurring in production:
```bash
daa test --app demo-service --message "AttributeError: 'RedisCache' object has no attribute 'connec'. Did you mean 'connect'?"
```

## Step 7: Monitor Real-Time Agent Reasoning
Watch the agent consume the job, check Git commits, locate the exact file/line, verify tests, and formulate the fix:
```bash
daa logs --follow
```

## Step 8: Review & Approve in Admin Panel (or Auto-PR)
- If `DAA_HITL_MODE=true` (Human-In-The-Loop):
  1. Open the React Dashboard: `http://localhost:5003` (for Compose) or `http://localhost:8080/admin` (baked-in).
  2. Click on the generated Incident.
  3. Review the AI-generated Root Cause Postmortem and code diff.
  4. Click **Approve & Merge**.
- If `DAA_HITL_MODE=false`:  
  The agent automatically pushes the fix branch and returns the live Pull Request URL in the logs.

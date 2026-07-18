# DAA Deployment Guide

## Single Container (Quickest)

```bash
# Build and run everything in one container (SQLite, no external deps)
docker build -t daa:latest .
docker run -d --name daa -p 8000:8080 --env-file .env daa:latest
```

Open **http://localhost:8000/admin** for the admin panel.

---

## Docker Compose (Recommended for Self-Hosted)

```bash
daa init          # Configure LLM + git credentials
daa redeploy      # Starts: backend-api, python-agent, postgres, rabbitmq, admin-panel
daa status        # Verify all containers are healthy
```

Services:
- `http://localhost:8000` — Backend API + `/admin` panel
- `http://localhost:5003` — Dedicated React admin panel
- `http://localhost:15672` — RabbitMQ management UI (guest/guest)

---

## Serverless (Cloud Run / AWS Fargate)

Set these environment variables in your serverless config:

```bash
DAA_DB_PROVIDER=none        # No database — stateless mode
DAA_GIT_MODE=api            # Use REST API instead of git clone
DAA_QUEUE_MODE=sync         # No RabbitMQ — inline processing
DAA_AUTH_ENABLED=false      # Use IAM proxy auth instead
```

Then deploy the single Docker image. See `daa init` → choose "Stateless / Serverless" for guided setup.

---

## Environment Variables Reference

See [`.env.example`](./.env.example) for the full list with descriptions.

Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | *required* | JWT signing key — set to a random string |
| `LLM_PROVIDER` | `google` | `google` / `openai` / `anthropic` / `vertex` / `ollama` |
| `GEMINI_API_KEY` | — | API key for your LLM provider |
| `DAA_DB_PROVIDER` | `sqlite` | `none` / `sqlite` / `postgres` |
| `DAA_AUTH_ENABLED` | `false` | Enable JWT login portal |
| `GITHUB_TOKEN` | — | For opening pull requests |
| `DAA_API_KEY` | — | Protects webhook ingest endpoints |

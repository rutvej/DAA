# DAA Platform

DAA is a multi-service platform that ingests error logs, routes them to an LLM-powered Python agent, and tracks fix status through a backend API and admin panel UI. The repo includes a Python SDK and a test app to generate sample errors.

## Services
- `app/backend-api`: FastAPI service for auth, log ingestion, fix status, and health.
- `app/python-agent`: RabbitMQ consumer that analyzes logs and opens merge requests.
- `app/admin-panel`: React admin UI for viewing logs and fixes.
- `app/daa-sdk`: Python SDK for sending logs to the backend API.
- `app/test-app`: Flask app that triggers errors for testing.
- Infrastructure: PostgreSQL, RabbitMQ, and GitLab (local) via Docker Compose.

## Architecture
See `docs/architecture.md` for an overview and pointers to detailed specs under `app/*/specs`.

## Quickstart
1. Copy environment template:
   ```bash
   cp .env.example .env
   ```
2. Fill in values in `.env` (see configuration section below).
3. Start services:
   ```bash
   docker-compose up -d
   ```
4. Open the admin panel at `http://localhost:5003`.
5. Register and log in using the Admin Panel UI.

For detailed steps (including GitLab setup), see `docs/quickstart.md`.

## Configuration
Key variables required in `.env`:
- `SECRET_KEY`: JWT signing key for the backend API.
- `POSTGRES_PASSWORD`: Password for the Postgres service.
- `GITLAB_ROOT_PASSWORD`: Password used for local GitLab root.
- `GITLAB_PRIVATE_TOKEN`: GitLab access token used by the agent.
- `GEMINI_API_KEY`: API key for Google Gemini.
- `DAA_TOKEN`: Backend JWT token used by the SDK/test app.
- `REPO_NAME`: Repo name used by the SDK/test app (default `test-app`).

See `.env.example` for the full list.

## Tests
Backend API:
```bash
DATABASE_URL=sqlite:///./test.db RABBITMQ_HOST=localhost PYTHONPATH=app/backend-api/src pytest app/backend-api/tests/
```

Python agent:
```bash
python3 -m unittest discover app/python-agent/tests
```

Admin panel:
```bash
cd app/admin-panel
npm test -- --watchAll=false
```

## Known Gaps
These are documented areas that are incomplete or inconsistent today:
- Admin panel calls `/dashboard`, but backend has no `GET /dashboard` route.
- Log list endpoints are unauthenticated while log submission is authenticated.
- Python agent updates fix status but does not update the log status.
- Environment variable usage differs across services (see `docs/roadmap.md`).

## Documentation
- `docs/architecture.md`
- `docs/quickstart.md`
- `docs/roadmap.md`

## License
MIT. See `LICENSE`.

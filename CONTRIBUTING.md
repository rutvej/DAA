# Contributing

Thanks for your interest in contributing. This repo is a multi-service platform.
Please read the steps below before submitting a PR.

## Development Setup
1. Clone the repo and create a branch.
2. Copy `.env.example` to `.env` and fill in required values.
3. Use Docker Compose for local services:
   ```bash
   docker-compose up -d
   ```

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

## Linting
We use `ruff` for Python linting.
```bash
ruff check app/backend-api app/python-agent
```

## Pull Request Guidelines
- Keep PRs focused and scoped.
- Include tests for new behavior when applicable.
- Update documentation if user-facing behavior changes.
- Ensure CI passes before requesting review.

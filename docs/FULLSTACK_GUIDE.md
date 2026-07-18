# Full-Stack Enterprise Deployment Guide

This guide covers how to deploy DAA in a high-concurrency, distributed environment using Docker Compose.

## Architecture & Configuration

For full-stack mode (Postgres + RabbitMQ), use the following settings:

- `DAA_DB_PROVIDER=postgres`: Enables persistent storage using PostgreSQL.
- `DAA_QUEUE_MODE=rabbitmq`: Enables distributed task processing.
- `DAA_GIT_MODE=local`: Clones the repository locally for faster operations and deep AST analysis.

### Docker Compose Snippet

The `docker-compose.yml` should align with the connection strings required by these configurations:

```yaml
version: '3.8'
services:
  daa-api:
    image: rutvej1/daa-standalone:latest
    environment:
      - DAA_DB_PROVIDER=postgres
      - DAA_QUEUE_MODE=rabbitmq
      - DAA_GIT_MODE=local
      - DATABASE_URL=postgresql://user:pass@postgres:5432/daa
      - CELERY_BROKER_URL=amqp://user:pass@rabbitmq:5672/
    depends_on:
      - postgres
      - rabbitmq

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=daa

  rabbitmq:
    image: rabbitmq:3-management-alpine
```

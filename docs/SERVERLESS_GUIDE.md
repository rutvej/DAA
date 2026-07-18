# Serverless Deployment Guide

This guide covers how to deploy DAA in a stateless, serverless environment such as Google Cloud Run or AWS Fargate.

## Environment Variables

For stateless mode, you MUST use the following configuration:

- `DAA_DB_PROVIDER=none`: Disables database persistence, allowing the container to scale to zero.
- `DAA_GIT_MODE=api`: Interacts with Git purely via the API, avoiding the need for a local clone on a persistent disk.

### Example Run Command

```bash
docker run -d --name daa \
  -p 8000:8080 \
  -e LLM_PROVIDER=google \
  -e GEMINI_API_KEY=your_api_key \
  -e DAA_DB_PROVIDER=none \
  -e DAA_GIT_MODE=api \
  -e DAA_QUEUE_MODE=sync \
  -e DAA_AUTH_ENABLED=false \
  -e DAA_POLICY_ENABLED=false \
  rutvej1/daa-standalone:latest
```

When running in this mode, DAA processes incidents instantly in memory and does not require any external infrastructure like PostgreSQL or RabbitMQ.

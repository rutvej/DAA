FROM python:3.11-slim

LABEL maintainer="rutvej"
LABEL description="DAA - Debugging Autonomous Agent (GitHub Action)"

# System dependencies — git for repo operations, patch for diff application
RUN apt-get update && apt-get install -y --no-install-recommends \
      git \
      patch \
      curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only what the agent needs — no FastAPI, no RabbitMQ, no admin panel
COPY action/requirements-action.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent source code and common utilities
COPY app/python-agent/agent_src/ /app/agent_src/
COPY app/common/ /app/common/

# Copy the action entrypoint and runner
COPY action/entrypoint.sh /app/entrypoint.sh
COPY action/action_runner.py /app/action_runner.py
RUN chmod +x /app/entrypoint.sh

# Runtime environment — stateless action mode
ENV PYTHONPATH="/app" \
    DAA_MODE=action \
    DAA_DB_PROVIDER=none \
    DAA_QUEUE_MODE=sync \
    DAA_GIT_MODE=api \
    DAA_AUTH_ENABLED=false

ENTRYPOINT ["/app/entrypoint.sh"]

FROM python:3.11-slim

# Install system dependencies, git, postgres, redis, and golang
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    postgresql \
    postgresql-contrib \
    redis-server \
    golang-go \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and scripts
COPY . .

# Setup default environment variables
ENV DAA_DB_PROVIDER=sqlite
ENV PORT=8080

EXPOSE 8080

RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]

#!/bin/bash
set -e

echo "=== DAA Pluggable Single-Image Supervisor ==="

# Set PYTHONPATH to include both backend-api and python-agent
export PYTHONPATH="/app/app/backend-api:/app/app/python-agent:$PYTHONPATH"

# ── 1. Handle Internal Postgres ──
if [ "$DAA_DB_PROVIDER" = "internal-postgres" ]; then
    echo "Initializing and starting internal Postgres server..."
    DB_DATA="/var/lib/postgresql/data"
    
    # Check if DB directory is initialized, if not initialize it
    if [ ! -d "$DB_DATA/base" ]; then
        chown -R postgres:postgres /var/lib/postgresql
        INITDB_PATH=$(ls /usr/lib/postgresql/*/bin/initdb | head -n 1)
        su - postgres -c "$INITDB_PATH -D $DB_DATA"
    fi
    
    # Start Postgres daemon
    PG_CTL_PATH=$(ls /usr/lib/postgresql/*/bin/pg_ctl | head -n 1)
    su - postgres -c "$PG_CTL_PATH -D $DB_DATA -l /tmp/postgres.log start"
    
    # Wait for database availability
    echo "Waiting for Postgres to start..."
    until su - postgres -c "pg_isready" >/dev/null 2>&1; do
        sleep 1
    done
    echo "Postgres started successfully."
    
    # Configure DAA default database user & table
    su - postgres -c "psql -c \"CREATE USER daa WITH PASSWORD 'daa_pass';\" || true"
    su - postgres -c "psql -c \"CREATE DATABASE daa_db OWNER daa;\" || true"
    export DATABASE_URL="postgresql://daa:daa_pass@localhost:5432/daa_db"
fi

# ── 2. Handle Internal Redis ──
if [ "$DAA_DB_PROVIDER" = "internal-redis" ]; then
    echo "Starting internal Redis server..."
    redis-server --daemonize yes
    export REDIS_URL="redis://localhost:6379/0"
fi

# ── 3. Start DAA FastAPI Server & Worker ──
PORT="${PORT:-8080}"
echo "Starting DAA API on port $PORT..."

if [ "$DAA_QUEUE_MODE" = "sync" ]; then
    # In serverless/sync mode, running the API server is enough (worker runs inline via BackgroundTasks)
    exec uvicorn app.backend-api.src.main:app --host 0.0.0.0 --port "$PORT"
else
    # In distributed mode, run API and Agent worker as concurrent background processes
    echo "Starting DAA Agent Worker..."
    python -m src.main &
    exec uvicorn app.backend-api.src.main:app --host 0.0.0.0 --port "$PORT"
fi

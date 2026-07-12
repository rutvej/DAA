FROM python:3.11-alpine

# ── System dependencies ───────────────────────────────────────────────────────
# Build-time compilers (gcc, musl-dev) are needed for bcrypt/psycopg2 but can
# be removed after pip install via the --virtual trick to keep the layer small.
RUN apk add --no-cache \
      git \
      curl \
      bash \
      docker-cli \
      patch \
      postgresql-client \
    && apk add --no-cache --virtual .build-deps \
      gcc \
      musl-dev \
      libffi-dev \
      openssl-dev

WORKDIR /app

# ── Python dependencies ───────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && apk del .build-deps

# ── Source code ───────────────────────────────────────────────────────────────
# .dockerignore strips: node_modules, .venv, .git, *.db, admin-panel source,
# SDK language dirs, terraform, docs, tests — see .dockerignore for full list.
COPY . .

# ── Runtime environment ───────────────────────────────────────────────────────
ENV DAA_DB_PROVIDER=sqlite \
    DAA_SERVE_PANEL=true \
    PORT=8080

EXPOSE 8080

RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]

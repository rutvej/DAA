#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           DAA Run-Matrix Tutorial — Interactive Step-by-Step Demo           ║
║                                                                              ║
║  This tutorial walks you through every combination in the run matrix.        ║
║  At each major step the script pauses and waits for your ENTER key press.   ║
║  After a PR is raised you will be given direct clickable links to inspect   ║
║  the result in the Gitea UI and the DAA admin panel.                        ║
╚══════════════════════════════════════════════════════════════════════════════╝

  Usage:
    python tutorial_matrix.py            # run all 6 combinations
    python tutorial_matrix.py 0 2        # run only combo 0 and 2 (0-based)
    python tutorial_matrix.py --list     # print all combos and exit

  Environment variables (override defaults):
    DAA_IMAGE    - Docker image to use   (default: rutvej1/daa-standalone:latest)
    DEMO_PATH    - Path to daa-e2e-demo  (default: auto-detected)
"""

import os
import subprocess
import sys
import time

import requests

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS — tweak these if your setup differs
# ─────────────────────────────────────────────────────────────────────────────

# Absolute path to THIS file's parent directory (daa-e2e-demo)
DEMO_PATH = os.path.dirname(os.path.abspath(__file__))

# DAA docker image pulled from Docker Hub (NO local build required)
DAA_IMAGE = os.environ.get("DAA_IMAGE", "rutvej1/daa-standalone:latest")

# DAA API endpoint — standalone container exposes 8080 mapped to host:8000
DAA_URL = "http://localhost:8000"

# Demo infra Postgres (lives in daa-e2e-demo docker-compose.yml)
# Format: postgresql://<user>:<password>@<host>/<db>
# "postgres" resolves inside the Docker network that the daa-standalone
# container joins (daa-e2e-demo_default).
DEMO_POSTGRES_URL = "postgresql://payflow:payflow_secret@postgres/payflow"

# Gitea (lightweight self-hosted Git server)
GITEA_URL = "http://localhost:3000"
GITEA_USER = "daa-admin"
GITEA_PASS = "DaaDemo123!"

# ─────────────────────────────────────────────────────────────────────────────
# THE COMBINATION MATRIX
# Each dict describes ONE test scenario.  Fields explained inline.
# ─────────────────────────────────────────────────────────────────────────────
COMBINATIONS = [
    # ── 1. True Serverless ──────────────────────────────────────────────────
    # No DB, no queue — the simplest possible DAA deployment.
    # DAA processes a single pre-qualified Prometheus webhook and raises a PR.
    {
        "staging": "Image",  # run as a single Docker container (not compose)
        "db": "none",  # no persistent database → MockSession in memory
        "queue": "sync",  # no RabbitMQ; fix jobs run inline / synchronously
        "git": "api",  # clone/push via Git HTTP API (not local filesystem)
        "auth": "false",  # JWT auth disabled → no Bearer token required
        "policy": "false",  # escalation-policy engine disabled
        "_label": "True Serverless (stateless webhook ingest)",
    },
    # ── 2a. Serverless + Postgres + Auth ────────────────────────────────────
    {
        "staging": "Image",
        "db": "postgres",  # PostgreSQL for incident/fix persistence
        "queue": "sync",  # still synchronous — no RabbitMQ container needed
        "git": "api",
        "auth": "true",  # JWT auth ON → every SDK call needs a Bearer token
        "policy": "true",  # escalation policy enforced → human must approve fix
        "_label": "Serverless + Postgres + Auth + Policy",
    },
    # ── 2b. Serverless + Postgres, no Auth ──────────────────────────────────
    {
        "staging": "Image",
        "db": "postgres",
        "queue": "sync",
        "git": "api",
        "auth": "false",  # auth OFF — open endpoints for easy local dev/demo
        "policy": "false",
        "_label": "Serverless + Postgres (no auth)",
    },
    # ── 3. Async Serverless (RabbitMQ) ──────────────────────────────────────
    {
        "staging": "Image",
        "db": "postgres",
        "queue": "rabbitmq",  # fix jobs pushed to RabbitMQ queue for async processing
        "git": "api",
        "auth": "true",
        "policy": "true",
        "_label": "Async Serverless (Postgres + RabbitMQ + Auth + Policy)",
    },
    # ── 4a. Full Docker-Compose stack + Auth ────────────────────────────────
    {
        "staging": "Compose",  # multi-container compose (backend-api + python-agent)
        "db": "postgres",
        "queue": "rabbitmq",
        "git": "local",  # git clone to local filesystem volume (not HTTP API)
        "auth": "true",
        "policy": "true",
        "_label": "Fullstack Compose (auth + policy)",
    },
    # ── 4b. Full Docker-Compose stack, no Auth ──────────────────────────────
    {
        "staging": "Compose",
        "db": "postgres",
        "queue": "rabbitmq",
        "git": "local",
        "auth": "false",
        "policy": "false",
        "_label": "Fullstack Compose (no auth)",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# TERMINAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"
DIM = "\033[2m"


def c(color, text):
    return f"{color}{text}{RESET}"


def banner(text, color=CYAN):
    width = 74
    print()
    print(c(color, "╔" + "═" * width + "╗"))
    for line in text.strip().splitlines():
        padded = line.center(width)
        print(c(color, "║") + padded + c(color, "║"))
    print(c(color, "╚" + "═" * width + "╝"))
    print()


def section(title):
    print()
    print(c(CYAN, f"┌─── {title} " + "─" * max(0, 68 - len(title)) + "┐"))


def explain(text):
    """Print a ℹ️  explanation block in yellow."""
    print()
    for line in text.strip().splitlines():
        print(c(YELLOW, "  ℹ  ") + line)
    print()


def step(num, title):
    print()
    print(c(BOLD, c(BLUE, f"  ▶  Step {num}: {title}")))


def ok(msg):
    print(c(GREEN, f"  ✓  {msg}"))


def warn(msg):
    print(c(YELLOW, f"  ⚠  {msg}"))


def fail(msg):
    print(c(RED, f"  ✗  {msg}"))


def info(msg):
    print(c(DIM, f"     {msg}"))


def wait_for_user(prompt="Press ENTER to continue..."):
    """Block until the user presses ENTER — core tutorial mechanic."""
    print()
    try:
        input(c(MAGENTA, f"  ⏸   {prompt} "))
    except KeyboardInterrupt:
        print("\n  Interrupted by user.  Exiting tutorial.")
        sys.exit(0)
    print()


# ─────────────────────────────────────────────────────────────────────────────
# SUBPROCESS HELPERS
# ─────────────────────────────────────────────────────────────────────────────


def run(cmd, cwd=None, check=True):
    """Print and execute a shell command."""
    print(c(DIM, f"     $ {cmd}"))
    subprocess.run(cmd, shell=True, cwd=cwd, check=check)


def run_capture(cmd, cwd=None):
    """Run a command and return (returncode, stdout, stderr)."""
    res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr


# ─────────────────────────────────────────────────────────────────────────────
# WAIT HELPERS
# ─────────────────────────────────────────────────────────────────────────────


def wait_for_http(url, label, retries=30, interval=3):
    print(c(DIM, f"     [waiting] {label} @ {url} ..."), flush=True)
    for attempt in range(retries):
        try:
            if requests.get(url, timeout=2).status_code == 200:
                ok(f"{label} ready")
                return True
        except Exception:
            pass
        time.sleep(interval)
        if attempt % 5 == 4:
            info(f"  Still waiting … ({(attempt + 1) * interval}s elapsed)")
    warn(f"{label} not ready after {retries * interval}s — continuing anyway")
    return False


def wait_for_postgres(cwd, user):
    info(f"Waiting for Postgres (user={user}) …")
    for _ in range(30):
        r = subprocess.run(
            f"docker-compose exec -T postgres pg_isready -U {user}",
            shell=True,
            cwd=cwd,
            capture_output=True,
        )
        if r.returncode == 0:
            ok("Postgres ready")
            return True
        time.sleep(2)
    warn("Postgres not ready — continuing anyway")
    return False


# ─────────────────────────────────────────────────────────────────────────────
# GITEA SEEDING
# ─────────────────────────────────────────────────────────────────────────────


def seed_gitea() -> str:
    """
    Create Gitea admin, generate scoped token, create repos, push source code.
    Returns the raw token string.
    """
    import shutil
    import tempfile
    import uuid

    section("Seeding Gitea")
    info("Creating admin user (ignored if already exists) …")
    subprocess.run(
        f"docker-compose exec -T --user git gitea gitea admin user create "
        f"--admin --username {GITEA_USER} --password '{GITEA_PASS}' --email admin@payflow.dev",
        shell=True,
        cwd=DEMO_PATH,
        capture_output=True,
    )

    token_name = f"daa-token-{uuid.uuid4().hex[:8]}"
    gitea_token = ""

    info("Requesting scoped API token (write:repository + write:issue) …")
    try:
        r = requests.post(
            f"{GITEA_URL}/api/v1/users/{GITEA_USER}/tokens",
            auth=(GITEA_USER, GITEA_PASS),
            json={
                "name": token_name,
                "scopes": ["write:repository", "write:issue", "read:user"],
            },
            timeout=10,
        )
        if r.status_code == 201:
            gitea_token = r.json().get("sha1", "")
            ok(f"Scoped token created: {gitea_token[:6]}…")
        else:
            warn(f"REST token API → {r.status_code}")
    except Exception as e:
        warn(f"REST token API error: {e}")

    if not gitea_token:
        info("Falling back to CLI token generation …")
        res = subprocess.run(
            f"docker-compose exec -T --user git gitea gitea admin user generate-access-token "
            f"-u {GITEA_USER} -t {token_name}-cli --raw",
            shell=True,
            cwd=DEMO_PATH,
            capture_output=True,
            text=True,
        )
        gitea_token = res.stdout.strip().split("\n")[-1].strip()
        ok(f"CLI token: {gitea_token[:6]}…")

    for repo in ["payment-api", "payment-worker"]:
        r = requests.post(
            f"{GITEA_URL}/api/v1/user/repos",
            auth=(GITEA_USER, GITEA_PASS),
            json={"name": repo, "auto_init": False, "default_branch": "main"},
        )
        if r.status_code in (201, 409):
            ok(f"Gitea repo '{repo}' ready")
        else:
            warn(f"Repo '{repo}' → {r.status_code}")

    for repo in ["payment-api", "payment-worker"]:
        src_dir = os.path.join(DEMO_PATH, repo)
        if not os.path.isdir(src_dir):
            warn(f"Source dir {src_dir} not found, skipping push")
            continue
        with tempfile.TemporaryDirectory() as tmpdir:
            shutil.copytree(
                src_dir,
                tmpdir,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(".git"),
            )
            push_url = f"http://{GITEA_USER}:{GITEA_PASS}@localhost:3000/{GITEA_USER}/{repo}.git"
            push_cmd = (
                f"git -C {tmpdir} init -b main && "
                f"git -C {tmpdir} add . && "
                f"git -C {tmpdir} -c user.email=demo@payflow.dev "
                f"-c user.name='DAA Demo' commit -m 'Initial commit' && "
                f"git -C {tmpdir} push --force {push_url} main"
            )
            result = subprocess.run(
                push_cmd, shell=True, capture_output=True, text=True
            )
            if result.returncode == 0:
                ok(f"Source code pushed → {repo}")
            else:
                warn(f"Push to '{repo}' failed:\n{result.stderr[-400:]}")

    return gitea_token


# ─────────────────────────────────────────────────────────────────────────────
# STATE RESET (clean slate between combos)
# ─────────────────────────────────────────────────────────────────────────────

_state = {"gitea_token": ""}


def reset_state():
    section("Resetting State")
    info("Tearing down all containers and volumes for a clean slate …")
    run("docker run --rm -v /tmp:/tmp alpine rm -rf /tmp/daa", check=False)
    run("docker run --rm -v /var/daa:/var/daa alpine rm -rf /var/daa/*", check=False)
    run("docker-compose down -v", cwd=DEMO_PATH, check=False)
    run("docker rm -f daa-standalone", check=False)

    info("Starting infrastructure (Gitea, Redis, Postgres, RabbitMQ) …")
    run("docker-compose up -d gitea redis postgres rabbitmq", cwd=DEMO_PATH)

    wait_for_http(
        "http://localhost:3000/api/v1/version", "Gitea", retries=30, interval=3
    )
    wait_for_postgres(DEMO_PATH, "payflow")

    _state["gitea_token"] = seed_gitea()

    info("Starting demo applications (payment-api, payment-worker) …")
    run("docker-compose up -d payment-api payment-worker", cwd=DEMO_PATH)
    wait_for_http("http://localhost:8001/health", "payment-api", retries=20, interval=3)
    ok("Reset complete — infrastructure is ready")


# ─────────────────────────────────────────────────────────────────────────────
# AUTH HELPERS
# ─────────────────────────────────────────────────────────────────────────────


def register_admin():
    try:
        requests.post(
            f"{DAA_URL}/auth/register",
            json={"username": "testuser", "password": "testpassword"},
            timeout=5,
        )
    except Exception:
        pass


def login():
    try:
        res = requests.post(
            f"{DAA_URL}/auth/login",
            json={"username": "testuser", "password": "testpassword"},
            timeout=5,
        )
        if res.status_code == 200:
            return res.json().get("token")
    except Exception:
        pass
    return None


def provision_app_token(app_name: str) -> str:
    try:
        requests.post(
            f"{DAA_URL}/auth/register",
            json={
                "username": app_name,
                "password": f"{app_name}-secret",
                "role": "application",
            },
            timeout=5,
        )
    except Exception:
        pass
    try:
        res = requests.post(
            f"{DAA_URL}/auth/login",
            json={"username": app_name, "password": f"{app_name}-secret"},
            timeout=5,
        )
        if res.status_code == 200:
            return res.json().get("token", "")
    except Exception:
        pass
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# TUTORIAL COMBO RUNNER
# ─────────────────────────────────────────────────────────────────────────────


def run_combo_tutorial(combo_idx: int, combo: dict, total: int):
    """
    Walk through one combination of the matrix with per-step explanations
    and user-controlled pauses.
    """
    label = combo.get("_label", str(combo))
    staging = combo["staging"]
    db = combo["db"]
    queue = combo["queue"]
    git_mode = combo["git"]
    auth = combo["auth"]
    policy = combo["policy"]

    # ── COMBO HEADER ─────────────────────────────────────────────────────────
    banner(
        f"COMBO {combo_idx + 1} / {total}\n"
        f"{label}\n"
        f"\n"
        f"staging={staging}  db={db}  queue={queue}  git={git_mode}  auth={auth}  policy={policy}",
        color=MAGENTA,
    )

    explain(
        f"What this combo tests:\n"
        f"  • staging={staging!r}\n"
        f"      'Image'   → DAA runs as ONE standalone Docker container (pulled from Hub).\n"
        f"                  The image already contains both the FastAPI backend and the\n"
        f"                  Python SRE agent. Nothing is built locally.\n"
        f"      'Compose' → DAA is split into two services: backend-api + python-agent,\n"
        f"                  orchestrated by docker-compose.  Requires the DAA source tree.\n"
        f"\n"
        f"  • db={db!r}\n"
        f"      'none'    → DAA uses an in-memory MockSession.  Incidents are not\n"
        f"                  persisted across restarts.  Perfect for stateless webhooks.\n"
        f"      'postgres' → Full PostgreSQL persistence. Incidents, fixes, and policy\n"
        f"                   records survive container restarts.\n"
        f"\n"
        f"  • queue={queue!r}\n"
        f"      'sync'    → Fix jobs run immediately inside the request cycle (no broker).\n"
        f"      'rabbitmq'→ Fix jobs are pushed to a RabbitMQ queue and consumed\n"
        f"                   asynchronously by a worker. Required for Compose mode.\n"
        f"\n"
        f"  • git={git_mode!r}\n"
        f"      'api'     → Agent interacts with Git purely via the Gitea REST/HTTP API.\n"
        f"                   No local checkout needed.  Works inside any container.\n"
        f"      'local'   → Agent clones the repo to a volume on the host (/var/daa).\n"
        f"                   Faster for large repos but requires volume mounts.\n"
        f"\n"
        f"  • auth={auth!r}\n"
        f"      'false'   → JWT authentication is disabled.  All /logs/ and /incidents/\n"
        f"                   endpoints are open — great for quick demo without token mgmt.\n"
        f"      'true'    → JWT auth enforced.  The payment-api / payment-worker SDKs\n"
        f"                   must present a Bearer token with every request.\n"
        f"\n"
        f"  • policy={policy!r}\n"
        f"      'false'   → Auto-remediation: DAA approves & pushes the fix automatically.\n"
        f"      'true'    → Human-in-the-loop: DAA proposes a fix then waits for an\n"
        f"                   explicit /fixes/<id>/approve call before pushing the PR."
    )

    wait_for_user("Understood the combo? Press ENTER to begin RESET →")

    # ── STEP 1: RESET ────────────────────────────────────────────────────────
    step(1, "Reset all state (clean slate)")
    explain(
        "We tear down every container and Docker volume so each combo starts fresh.\n"
        "This prevents cross-contamination between test runs (stale tokens, old\n"
        "incident records, leftover branches in Gitea, etc.).\n"
        "\n"
        "What gets destroyed:\n"
        "  /tmp/daa          — agent's temporary clone workspace (root-owned)\n"
        "  /var/daa/*        — persistent agent workspace volume\n"
        "  daa-e2e-demo_*    — all demo infra volumes (pgdata, gitea_data)\n"
        "  daa-standalone    — the DAA container from the previous run\n"
        "\n"
        "After the wipe, infra is brought up fresh and Gitea is re-seeded with\n"
        "the admin user, a scoped token, and the payment-api / payment-worker repos."
    )
    wait_for_user("Press ENTER to execute reset →")
    reset_state()
    wait_for_user("Reset done ✓  Press ENTER to proceed to environment setup →")

    # ── STEP 2: PULL IMAGE ───────────────────────────────────────────────────
    if staging == "Image":
        step(2, "Pull the DAA standalone image from Docker Hub")
        explain(
            f"Image: {DAA_IMAGE}\n"
            f"\n"
            f"Instead of building DAA from source we pull the pre-built image.\n"
            f"This image bundles:\n"
            f"  • FastAPI backend   (uvicorn on port 8080)\n"
            f"  • Python SRE agent  (LangChain-based, reads env vars for LLM/Git config)\n"
            f"  • All Python deps   (no pip install needed at runtime)\n"
            f"\n"
            f"The container will be connected to the demo Docker network so it can\n"
            f"reach the postgres, rabbitmq, and gitea services by their service names."
        )
        wait_for_user("Press ENTER to run 'docker pull' →")
        run(f"docker pull {DAA_IMAGE}")
        ok(f"Image {DAA_IMAGE} is local and ready")
        wait_for_user("Image pulled ✓  Press ENTER to configure the environment →")

    # ── STEP 3: BUILD .env ───────────────────────────────────────────────────
    step(3, "Build the DAA .env configuration")

    git_token = _state["gitea_token"] or os.environ.get("DAA_GIT_TOKEN", "")
    git_repo_url = f"http://192.168.1.41:3000/{GITEA_USER}/payment-api.git"

    if staging == "Image":
        db_url = DEMO_POSTGRES_URL if db == "postgres" else ""
        network = "daa-e2e-demo_default"
        backend_api_url = "http://localhost:8080"
    else:
        # Compose mode: DAA brings up its own internal Postgres
        db_url = "postgresql://youruser:demo_postgres_password@postgres/yourdb"
        network = "daa_default"
        backend_api_url = "http://backend-api:80"

    env_content = (
        f"LLM_PROVIDER=google\n"
        f"LLM_MODEL=gemini-3.1-flash-lite\n"
        f"GEMINI_API_KEY=your_gemini_api_key_here\n"
        f"DAA_DB_PROVIDER={db}\n"
        f"DAA_QUEUE_MODE={queue}\n"
        f"DAA_GIT_MODE={git_mode}\n"
        f"DAA_AUTH_ENABLED={auth}\n"
        f"DAA_POLICY_ENABLED={policy}\n"
        f"SECRET_KEY=demo_secret_key\n"
        f"DATABASE_URL={db_url}\n"
        f"RABBITMQ_HOST=rabbitmq\n"
        f"DAA_BACKEND_API_URL={backend_api_url}\n"
        f"DAA_GIT_TOKEN={git_token}\n"
        f"GIT_REPO_URL={git_repo_url}\n"
        f"GIT_HOST=http://host.docker.internal:3000\n"
        f"GIT_ORG={GITEA_USER}\n"
    )

    explain(
        "Each environment variable and WHY it is set:\n"
        "\n"
        f"  LLM_PROVIDER=mock\n"
        f"      Switch between 'mock' (deterministic dummy LLM — zero cost, instant),\n"
        f"      'gemini', 'openai', or 'anthropic'.  'mock' is used here so the test\n"
        f"      always produces a predictable fix without spending API quota.\n"
        f"\n"
        f"  LLM_MODEL=gemini-2.5-flash\n"
        f"      Which model variant to use when LLM_PROVIDER is 'gemini'.  Has no\n"
        f"      effect in mock mode, but is kept for consistency with production.\n"
        f"\n"
        f"  GEMINI_API_KEY=...\n"
        f"      Credentials for the Gemini API.  The mock provider ignores this,\n"
        f"      but a real key is required if you switch to LLM_PROVIDER=gemini.\n"
        f"\n"
        f"  DAA_DB_PROVIDER={db}\n"
        f"      Controls which database adapter DAA uses:\n"
        f"        'none'     → in-memory MockSession (no persistence)\n"
        f"        'postgres' → SQLAlchemy + asyncpg against DATABASE_URL\n"
        f"\n"
        f"  DAA_QUEUE_MODE={queue}\n"
        f"      How fix jobs are dispatched:\n"
        f"        'sync'    → run_fix() called inline in the same process/thread\n"
        f"        'rabbitmq'→ job pushed to RABBITMQ_HOST, picked up by worker loop\n"
        f"\n"
        f"  DAA_GIT_MODE={git_mode}\n"
        f"      How the agent reads & writes to Git:\n"
        f"        'api'   → purely via Gitea/GitHub REST API (no git binary needed)\n"
        f"        'local' → git clone to /var/daa, then file edits + git push\n"
        f"\n"
        f"  DAA_AUTH_ENABLED={auth}\n"
        f"      true  → FastAPI middleware validates JWT on every protected endpoint.\n"
        f"              Applications must POST /auth/login to get a token first.\n"
        f"      false → middleware is bypassed; all requests succeed without a token.\n"
        f"\n"
        f"  DAA_POLICY_ENABLED={policy}\n"
        f"      true  → DAA moves incident to 'awaiting_approval' after proposing fix.\n"
        f"              Human SRE calls POST /fixes/<id>/approve to proceed.\n"
        f"      false → DAA auto-approves and pushes the PR without human intervention.\n"
        f"\n"
        f"  SECRET_KEY=demo_secret_key\n"
        f"      JWT signing secret.  Rotate this in production!\n"
        f"\n"
        f"  DATABASE_URL={db_url or '(empty — db=none)'}\n"
        f"      Full SQLAlchemy connection string.  Empty when DAA_DB_PROVIDER=none.\n"
        f"      The 'postgres' hostname resolves inside the Docker network.\n"
        f"\n"
        f"  RABBITMQ_HOST=rabbitmq\n"
        f"      Hostname of the RabbitMQ broker inside the Docker network.\n"
        f"      Only used when DAA_QUEUE_MODE=rabbitmq.\n"
        f"\n"
        f"  DAA_BACKEND_API_URL={backend_api_url}\n"
        f"      The agent calls this URL to POST status updates (fix_proposed,\n"
        f"      pr_open, etc.) back to the FastAPI backend.\n"
        f"      Image mode → localhost:8080 (same container, loopback).\n"
        f"      Compose mode → http://backend-api:80 (separate service).\n"
        f"\n"
        f"  DAA_GIT_TOKEN={git_token[:6]}… (truncated)\n"
        f"      Gitea personal-access token generated by seed_gitea().\n"
        f"      Scopes: write:repository + write:issue (needed to push branches + open PRs).\n"
        f"\n"
        f"  GIT_REPO_URL={git_repo_url}\n"
        f"      Template URL for the app's Git repo.  ingest.py substitutes app_name\n"
        f"      as the final path segment to derive the per-app repo URL dynamically.\n"
        f"      host.docker.internal resolves to the Docker host — allowing the\n"
        f"      container to reach Gitea running on the host's port 3000.\n"
        f"\n"
        f"  GIT_HOST=http://host.docker.internal:3000\n"
        f"  GIT_ORG={GITEA_USER}\n"
        f"      Decomposed form of the Gitea base URL and organisation name.\n"
        f"      Used to construct {{GIT_HOST}}/{{GIT_ORG}}/{{app_name}}.git\n"
        f"      for apps that aren't pre-registered in the DB (stateless mode)."
    )

    wait_for_user("Press ENTER to write the .env file and launch DAA →")

    env_path = os.path.join(DEMO_PATH, ".daa_tutorial.env")
    with open(env_path, "w") as f:
        f.write(env_content)
    ok(f".env written to {env_path}")
    print(c(DIM, env_content))

    # ── STEP 4: START DAA ────────────────────────────────────────────────────
    step(4, f"Start DAA ({staging} mode)")

    if staging == "Image":
        explain(
            f"We start the pre-pulled image '{DAA_IMAGE}' as a named container.\n"
            f"\n"
            f"  --name daa-standalone\n"
            f"      Gives the container a predictable name so we can reference it\n"
            f"      in 'docker logs', 'docker rm', and 'docker exec' later.\n"
            f"\n"
            f"  --network {network}\n"
            f"      Attach to the demo infra network.  This lets the DAA container\n"
            f"      resolve 'postgres', 'rabbitmq', 'gitea' by service name — the\n"
            f"      same hostnames used in DATABASE_URL and RABBITMQ_HOST.\n"
            f"\n"
            f"  --add-host host.docker.internal:host-gateway\n"
            f"      Injects a /etc/hosts entry mapping 'host.docker.internal' to\n"
            f"      the Docker host IP (172.17.0.1 on Linux, or host.docker.internal\n"
            f"      on Mac/Windows).  Required so Gitea HTTP API calls from inside\n"
            f"      the container can reach Gitea on localhost:3000 of the host.\n"
            f"\n"
            f"  --env-file {env_path}\n"
            f"      Inject all the environment variables we just built.\n"
            f"\n"
            f"  -p 8000:8080\n"
            f"      Map host port 8000 → container port 8080 (where uvicorn listens).\n"
            f"      All tutorial API calls use http://localhost:8000."
        )
        wait_for_user("Press ENTER to start the daa-standalone container →")
        run(
            f"docker run -d --name daa-standalone"
            f" --network {network}"
            f" --add-host host.docker.internal:host-gateway"
            f" --env-file {env_path}"
            f" -p 8000:8080"
            f" {DAA_IMAGE}"
        )
    else:
        explain(
            "Compose mode: we bring up two DAA services from the DAA source directory.\n"
            "  backend-api   — FastAPI service that exposes the REST API on port 80.\n"
            "  python-agent  — Long-running worker that polls for pending fix jobs.\n"
            "\n"
            "Both services share the same .env file and an internal Docker network\n"
            "so they can communicate via service-name DNS.\n"
            "\n"
            "NOTE: Compose mode requires the DAA source tree at ~/Desktop/DAA.\n"
            "      The docker-compose.yml in that directory defines both services."
        )
        daa_path = os.path.expanduser("~/Desktop/DAA")
        wait_for_user(
            "Press ENTER to run docker-compose up for backend-api + python-agent →"
        )
        import shutil

        shutil.copy(env_path, os.path.join(daa_path, ".env"))
        ok(f".env copied to {daa_path}/.env")
        run("docker-compose up -d --build backend-api python-agent", cwd=daa_path)

    wait_for_http(f"{DAA_URL}/health", "DAA API", retries=30, interval=3)
    ok("DAA API is up and responding")
    wait_for_user("DAA is running ✓  Press ENTER to begin the incident test →")

    # ── STEP 5: RUN TEST ─────────────────────────────────────────────────────
    step(5, "Execute the end-to-end incident test")
    headers = {}

    if auth == "true":
        explain(
            "auth=true means every API call needs a JWT Bearer token.\n"
            "\n"
            "  1. We POST /auth/register to create the 'testuser' admin account.\n"
            "  2. We POST /auth/login to receive a signed JWT.\n"
            "  3. We provision separate application tokens for payment-api and\n"
            "     payment-worker so their SDK calls to POST /logs/ are authorised.\n"
            "  4. We restart the demo containers with DAA_TOKEN injected so the\n"
            "     SDKs present the correct token automatically."
        )
        wait_for_user("Press ENTER to set up auth tokens →")

        register_admin()
        token = login()
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        api_token = provision_app_token("payment-api")
        worker_token = provision_app_token("payment-worker")
        if api_token:
            ok(f"payment-api token: {api_token[:6]}…")
            subprocess.run(
                f"DAA_TOKEN_PAYMENT_API={api_token} DAA_TOKEN_PAYMENT_WORKER={worker_token} "
                "docker-compose up -d --no-deps payment-api payment-worker",
                shell=True,
                cwd=DEMO_PATH,
                capture_output=True,
            )
            time.sleep(3)
            ok("Demo containers restarted with fresh DAA tokens")

        wait_for_user(
            "Auth tokens provisioned ✓  Press ENTER to trigger the incident →"
        )

    pr_url = None
    success = False

    if db == "none":
        # ── Stateless path ────────────────────────────────────────────────────
        explain(
            "db=none (Stateless Mode):\n"
            "\n"
            "In stateless mode the SDK path (payment-api → POST /logs/) is not used\n"
            "because MockSession never persists anything — no deduplication, no policy\n"
            "engine.  Instead we fire a single, pre-qualified Prometheus alert directly\n"
            "at the /ingest/prometheus endpoint.\n"
            "\n"
            "The alert payload mimics what Alertmanager would send after a threshold\n"
            "is breached externally.  DAA receives it, generates a fix, and pushes a\n"
            "PR — all without touching a database."
        )
        wait_for_user("Press ENTER to POST the Prometheus alert →")

        alert_payload = {
            "version": "4",
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "HighErrorRate",
                        "service": "payment-api",
                        "severity": "critical",
                    },
                    "annotations": {
                        "summary": "payment-api error rate exceeded threshold",
                        "description": "RedisConnectionError: max connections exceeded\n  at checkout() line 42",
                    },
                }
            ],
        }
        try:
            res = requests.post(
                f"{DAA_URL}/ingest/prometheus",
                json=alert_payload,
                headers=headers,
                timeout=10,
            )
            if res.status_code != 200:
                fail(f"Ingest rejected: {res.status_code}  {res.text}")
            else:
                ok(f"Alert accepted: {res.json()}")
        except Exception as e:
            fail(f"Ingest request failed: {e}")

        explain(
            "The alert has been ingested.  DAA is now:\n"
            "  1. Parsing the alert labels to identify the service ('payment-api').\n"
            "  2. Constructing the repo URL from GIT_HOST / GIT_ORG / service-name.\n"
            "  3. Fetching source files via the Gitea API.\n"
            "  4. Asking the LLM (mock) to propose a code fix.\n"
            "  5. Creating a branch + PR in Gitea.\n"
            "\n"
            "We will now poll Gitea every 3 seconds for up to 60 s waiting for the PR."
        )
        wait_for_user("Press ENTER to start polling for the PR →")

        for attempt in range(20):
            time.sleep(3)
            try:
                prs = requests.get(
                    f"{GITEA_URL}/api/v1/repos/{GITEA_USER}/payment-api/pulls",
                    params={"state": "open"},
                    auth=(GITEA_USER, GITEA_PASS),
                    timeout=5,
                ).json()
                if prs:
                    pr_url = prs[0].get("html_url", "")
                    ok(f"PR created: {pr_url}")
                    success = True
                    break
            except Exception:
                pass
            info(f"  Attempt {attempt + 1}/20 — no PR yet …")

        if not success:
            fail("No PR appeared within 60 s.")

    else:
        # ── DB-backed path ────────────────────────────────────────────────────
        explain(
            "DB-backed mode:\n"
            "\n"
            "We trigger the incident the same way a real Redis OOM failure would:\n"
            "  1. load_test.sh sends hundreds of concurrent HTTP requests to\n"
            "     payment-api, saturating Redis's 50 MB limit.\n"
            "  2. payment-api's SDK intercepts each RedisConnectionError and POSTs\n"
            "     an error log to DAA's /logs/ endpoint.\n"
            "  3. DAA's policy engine counts errors in a sliding window.  When the\n"
            "     threshold is exceeded an incident is created and a fix job queued.\n"
            "  4. The SRE agent analyses the error, writes a patch, and (if policy=true)\n"
            "     waits for human approval before pushing the branch + PR.\n"
            "\n"
            "We will poll GET /incidents every 3 s to watch the status progress:\n"
            "  detecting → investigating → fix_proposed/awaiting_approval → pr_open"
        )
        wait_for_user("Press ENTER to run load_test.sh →")
        run("./load_test.sh", cwd=DEMO_PATH, check=False)

        ok("Load test complete — monitoring for incident resolution …")
        for poll_idx in range(45):
            try:
                res = requests.get(f"{DAA_URL}/incidents", headers=headers, timeout=5)
                incidents = res.json() if res.ok else []
                if incidents:
                    incident_id = incidents[0]["id"]
                    status = incidents[0]["status"]
                    print(
                        c(
                            DIM,
                            f"     [{poll_idx * 3}s] Incident {incident_id[:8]} → '{status}'",
                        )
                    )

                    if policy == "true" and status in (
                        "fix_proposed",
                        "awaiting_approval",
                    ):
                        fix_id = incidents[0].get("fix_id")
                        if not fix_id:
                            by_log = requests.get(
                                f"{DAA_URL}/fixes/by-log/{incident_id}",
                                headers=headers,
                                timeout=5,
                            )
                            if by_log.ok:
                                fix_id = by_log.json().get("id")
                        if fix_id:
                            explain(
                                f"policy=true — fix {fix_id[:8]} is awaiting_approval.\n"
                                f"The DAA policy engine paused here to wait for a human SRE.\n"
                                f"We are now acting as that human and calling POST /fixes/<id>/approve."
                            )
                            wait_for_user("Press ENTER to APPROVE the fix →")
                            requests.post(
                                f"{DAA_URL}/fixes/{fix_id}/approve",
                                headers=headers,
                                timeout=5,
                            )
                            ok(
                                f"Fix {fix_id[:8]} approved — agent will now push the PR"
                            )
                            time.sleep(2)

                    if status in ("resolved", "completed", "pr_open"):
                        ok(f"Incident reached terminal state: '{status}'")
                        success = True
                        # Fetch the PR URL from Gitea
                        try:
                            prs = requests.get(
                                f"{GITEA_URL}/api/v1/repos/{GITEA_USER}/payment-api/pulls",
                                params={"state": "open"},
                                auth=(GITEA_USER, GITEA_PASS),
                                timeout=5,
                            ).json()
                            if prs:
                                pr_url = prs[0].get("html_url", "")
                        except Exception:
                            pass
                        break
            except Exception:
                pass
            time.sleep(3)

        if not success:
            fail("Timeout: incident did not reach terminal state within 135 s.")

    # ── STEP 6: RESULTS + LINKS ──────────────────────────────────────────────
    step(6, "Results & Admin Panel Links")

    if success:
        print()
        print(c(GREEN, "  ══════════════════════════════════════════════════"))
        print(c(GREEN, f"  ✓  PASS  —  {label}"))
        print(c(GREEN, "  ══════════════════════════════════════════════════"))
        print()

        if pr_url:
            explain(
                f"A Pull Request was successfully raised by the DAA SRE agent!\n"
                f"\n"
                f"  PR URL (Gitea):  {pr_url}\n"
                f"\n"
                f"Open the link above in your browser to review the auto-generated\n"
                f"code patch.  You can diff the changes, add comments, or merge it\n"
                f"just like any human-authored PR."
            )
            print(c(CYAN, f"  🔗  PR:           {pr_url}"))

        if staging == "Image":
            print(c(CYAN, "  🔗  DAA Internal Admin Panel (FastAPI Swagger UI):"))
            print(c(BOLD, "         http://localhost:8000/docs"))
            print()
            explain(
                "The internal admin panel for Image mode is the FastAPI Swagger UI.\n"
                "\n"
                "  http://localhost:8000/docs\n"
                "\n"
                "From here you can:\n"
                "  • GET  /incidents          — list all detected incidents\n"
                "  • GET  /incidents/<id>     — full incident detail (logs, fix_id, status)\n"
                "  • GET  /fixes/<id>         — view the proposed patch and diff\n"
                "  • POST /fixes/<id>/approve — manually approve a pending fix\n"
                "  • GET  /health             — liveness check\n"
                "  • GET  /metrics            — Prometheus metrics\n"
                "\n"
                "All endpoints are documented with example request/response bodies.\n"
                "If auth=true, click 'Authorize' and paste your Bearer token."
            )
        else:
            # Compose mode has a separate frontend admin panel
            compose_admin = "http://localhost:3001"
            print(c(CYAN, "  🔗  DAA Frontend Admin Panel (Compose mode):"))
            print(c(BOLD, f"         {compose_admin}"))
            print()
            explain(
                "In Compose mode DAA also spins up a React/Next.js frontend dashboard.\n"
                "\n"
                f"  {compose_admin}\n"
                "\n"
                "The dashboard shows:\n"
                "  • Live incident feed with severity badges\n"
                "  • Fix proposals with diff viewer\n"
                "  • One-click 'Approve' / 'Reject' buttons for policy-gated fixes\n"
                "  • Metrics graphs (error rate, mean-time-to-fix, PR merge rate)\n"
                "  • Configuration panel (LLM provider, DB, queue, Git settings)\n"
                "\n"
                "The Swagger UI is still available at http://localhost:8000/docs\n"
                "for raw API access alongside the frontend."
            )
            print(
                c(CYAN, "  🔗  DAA Swagger UI (raw API):  http://localhost:8000/docs")
            )

        print(c(CYAN, f"  🔗  Gitea UI:      http://localhost:3000/{GITEA_USER}"))
        print(c(CYAN, "  🔗  RabbitMQ UI:   http://localhost:15673  (guest/guest)"))
        print()

    else:
        print()
        print(c(RED, "  ══════════════════════════════════════════════════"))
        print(c(RED, f"  ✗  FAIL  —  {label}"))
        print(c(RED, "  ══════════════════════════════════════════════════"))
        print()
        explain(
            "The combo did not reach a terminal state.  Dumping container logs\n"
            "to help diagnose the failure …"
        )
        _dump_logs(staging)

    wait_for_user("Inspect the results, then press ENTER to tear down and continue →")

    # ── STEP 7: TEARDOWN ─────────────────────────────────────────────────────
    step(7, "Teardown")
    if staging == "Image":
        run("docker rm -f daa-standalone", check=False)
    else:
        daa_path = os.path.expanduser("~/Desktop/DAA")
        run("docker-compose down -v", cwd=daa_path, check=False)

    ok("DAA containers removed.  Infra left running for the next combo.")
    wait_for_user("Teardown done.  Press ENTER to move to the next combo →")

    return success


def _dump_logs(staging):
    """Print last 80 lines of relevant container logs."""
    sep = "─" * 60
    print(c(DIM, sep))
    if staging == "Image":
        rc, out, err = run_capture("docker logs --tail 80 daa-standalone")
        print(c(DIM, out or "(no stdout)"))
        if err:
            print(c(DIM, err))
    else:
        daa_path = os.path.expanduser("~/Desktop/DAA")
        for svc in ["backend-api", "python-agent"]:
            rc, out, err = run_capture(
                f"docker-compose logs --no-color --tail 60 {svc}", cwd=daa_path
            )
            print(c(DIM, f"--- {svc} ---"))
            print(c(DIM, out or "(no stdout)"))
    print(c(DIM, sep))


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────


def main():
    banner(
        "DAA  —  Run Matrix Interactive Tutorial\n"
        "\n"
        f"Image: {DAA_IMAGE}\n"
        f"Combos: {len(COMBINATIONS)}\n"
        "\n"
        "This tutorial will walk you through every combination in the\n"
        "run matrix.  At each step you will see a detailed explanation\n"
        "of what is happening and WHY each variable is set the way it is.\n"
        "\n"
        "After a PR is raised you will be given direct links to:\n"
        "  • The PR in Gitea (review the auto-generated code patch)\n"
        "  • The DAA admin panel (inspect incidents, fixes, metrics)\n"
        "\n"
        "Press ENTER at each pause to proceed.",
        color=CYAN,
    )

    if "--list" in sys.argv:
        print(c(BOLD, "Available combinations:"))
        for i, c_ in enumerate(COMBINATIONS):
            print(f"  [{i}]  {c_.get('_label', str(c_))}")
        sys.exit(0)

    # Parse optional combo indices from CLI
    indices = []
    for arg in sys.argv[1:]:
        try:
            indices.append(int(arg))
        except ValueError:
            pass

    if indices:
        selected = [(i, COMBINATIONS[i]) for i in indices]
        print(c(YELLOW, f"  Running selected combos: {indices}"))
    else:
        selected = list(enumerate(COMBINATIONS))
        print(c(YELLOW, f"  Running full matrix ({len(selected)} combos)"))

    wait_for_user("Press ENTER to start the tutorial →")

    results = []
    for run_num, (orig_idx, combo) in enumerate(selected):
        ok_flag = run_combo_tutorial(run_num, combo, len(selected))
        results.append((combo, ok_flag))

        # Rolling summary after every combo
        print()
        print(c(BOLD, f"  ── Rolling Summary ({run_num + 1}/{len(selected)}) ──"))
        for c_, passed in results:
            status = c(GREEN, "✓ PASS") if passed else c(RED, "✗ FAIL")
            tag = (
                f"staging={c_['staging']:7}  db={c_['db']:8}  "
                f"queue={c_['queue']:8}  auth={c_['auth']:5}  policy={c_['policy']}"
            )
            print(f"    {status}  {tag}")
        print()

    # Final summary
    banner("MATRIX RESULTS", color=GREEN if all(p for _, p in results) else RED)
    for combo, ok_flag in results:
        status = c(GREEN, "✓ PASS") if ok_flag else c(RED, "✗ FAIL")
        tag = (
            f"staging={combo['staging']:7}  db={combo['db']:8}  "
            f"queue={combo['queue']:8}  auth={combo['auth']:5}  policy={combo['policy']}"
        )
        print(f"    {status}  {tag}")

    all_pass = all(p for _, p in results)
    print()
    print(
        c(
            GREEN if all_pass else RED,
            "  Overall: ALL PASS ✓" if all_pass else "  Overall: SOME FAILURES ✗",
        )
    )
    print()
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()

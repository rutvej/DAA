import hashlib
import hmac
import json
import logging
import os
import subprocess
import sys
import uuid
from datetime import datetime
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..database import (
    get_db,
    Log as DBLog,
    Incident,
    ProjectConnection,
    DAA_DB_PROVIDER,
    DAA_AUTH_ENABLED,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ingest")

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def resolve_jsonpath(data: dict, path: str):
    """Resolves standard dotted JSONPaths (e.g. $.event.service -> data['event']['service'])"""
    if not path or not isinstance(data, dict):
        return None
    if path.startswith("$"):
        path = path[1:]
    parts = [p for p in path.split(".") if p]
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


async def verify_webhook_auth(request: Request):
    """Verifies DAA_API_KEY if configured in environment."""
    if not DAA_AUTH_ENABLED:
        return
    daa_api_key = os.environ.get("DAA_API_KEY")
    if daa_api_key:
        api_key_header = request.headers.get("X-API-Key")
        auth_header = request.headers.get("Authorization")

        valid = False
        if api_key_header == daa_api_key:
            valid = True
        elif auth_header:
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ", 1)[1]
                if token == daa_api_key:
                    valid = True
            elif auth_header == daa_api_key:
                valid = True

        if not valid:
            raise HTTPException(
                status_code=401, detail="Unauthorized: Invalid DAA_API_KEY"
            )


async def verify_sentry_signature(request: Request):
    """Verifies X-Sentry-Signature if SENTRY_WEBHOOK_SECRET is configured."""
    if not DAA_AUTH_ENABLED:
        return
    sentry_secret = os.environ.get("SENTRY_WEBHOOK_SECRET")
    if sentry_secret:
        signature = request.headers.get("X-Sentry-Signature")
        if not signature:
            raise HTTPException(status_code=401, detail="Missing Sentry signature")

        body = await request.body()
        expected = hmac.new(
            sentry_secret.encode("utf-8"), body, hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            raise HTTPException(status_code=401, detail="Invalid Sentry signature")
    else:
        # Fallback to standard DAA_API_KEY
        await verify_webhook_auth(request)


async def dispatch_investigation(
    app_name: str,
    exception_type: str,
    stack_trace: str,
    severity: str,
    db: Session,
    background_tasks: BackgroundTasks,
    error_file: str = None,
):
    """Computes fingerprint, runs deduplication check, records database state, and dispatches the job."""
    # [Item 1] Explicit note: Webhook/log-app-sourced errors (Sentry, Prometheus, generic log ingestion)
    # have no policy check; they escalate immediately on ingestion (upstream system already thresholded it).

    # 1. Compute fingerprint
    top_frame = stack_trace[:200]
    raw_fp = f"{app_name}:{exception_type}:{top_frame}"
    fingerprint = hashlib.sha256(raw_fp.encode("utf-8")).hexdigest()[:16]

    # 2. Check Deduplication in Database
    active_incident = (
        db.query(Incident)
        .filter(
            Incident.fingerprint == fingerprint,
            Incident.status.in_(
                ["investigating", "pr_open", "ticket_created", "cooldown"]
            ),
        )
        .first()
    )

    if active_incident:
        active_incident.occurrence_count = (active_incident.occurrence_count or 1) + 1
        active_incident.last_seen_at = datetime.utcnow()
        db.commit()
        logger.info(
            f"Deduplication hit in DB: suppressing investigation for fingerprint {fingerprint}"
        )
        return

    # Check Git remote branches in stateless mode (since DB query returns None)
    repo_url = os.environ.get("DAA_REPO_URL")
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GITLAB_PRIVATE_TOKEN")

    if DAA_DB_PROVIDER != "none":
        proj = (
            db.query(ProjectConnection)
            .filter(ProjectConnection.app_name == app_name)
            .first()
        )
        if proj:
            repo_url = proj.repo_url
            token = proj.repo_token

    if repo_url:
        branch_name = f"fix/{fingerprint[:12]}"
        try:
            auth_url = repo_url
            if token:
                parsed = urlparse(repo_url)
                netloc = f"{token}@{parsed.hostname}"
                auth_url = parsed._replace(netloc=netloc).geturl()

            res = subprocess.run(
                ["git", "ls-remote", "--heads", auth_url, f"refs/heads/{branch_name}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.stdout.strip():
                logger.info(
                    f"Deduplication hit via Git remote: branch {branch_name} exists. Suppressing investigation."
                )
                return
        except Exception as e:
            logger.warning(f"Failed to check Git remote for deduplication: {e}")

    # 3. Create Log and Incident
    db_log = DBLog(
        id=str(uuid.uuid4()),
        app_name=app_name,
        content=stack_trace,
        status="Escalated to Agent",
        exception_type=exception_type,
        timestamp=datetime.utcnow(),
    )
    db.add(db_log)

    new_incident = Incident(
        id=str(uuid.uuid4()),
        fingerprint=fingerprint,
        app_name=app_name,
        status="investigating",
        occurrence_count=1,
        first_seen_at=datetime.utcnow(),
        last_seen_at=datetime.utcnow(),
    )
    db.add(new_incident)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        active_incident = (
            db.query(Incident)
            .filter(
                Incident.fingerprint == fingerprint,
                Incident.status.in_(
                    ["investigating", "pr_open", "ticket_created", "cooldown"]
                ),
            )
            .first()
        )
        if active_incident:
            active_incident.occurrence_count = (
                active_incident.occurrence_count or 1
            ) + 1
            active_incident.last_seen_at = datetime.utcnow()
            db.commit()
            logger.info(
                f"Deduplication hit via DB lock race: suppressing investigation for fingerprint {fingerprint}"
            )
            return
        else:
            raise

    # 4. Enqueue Job
    job_id = db_log.id
    job_data = {
        "id": str(job_id),
        "log_id": str(job_id),
        "incident_id": str(new_incident.id),
        "fingerprint": fingerprint,
        "app_name": db_log.app_name,
        "status": "pending",
        "created_at": db_log.timestamp.isoformat(),
        "updated_at": db_log.timestamp.isoformat(),
        "error_log": {
            "id": str(db_log.id),
            "app_name": db_log.app_name,
            "content": db_log.content,
            "stack_trace": stack_trace,
            "exception_type": exception_type,
            "timestamp": db_log.timestamp.isoformat(),
        },
    }
    if error_file:
        job_data["error_file"] = error_file
        job_data["error_log"]["error_file"] = error_file

    queue_mode = os.environ.get("DAA_QUEUE_MODE", "rabbitmq").lower()
    if queue_mode == "sync":
        agent_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../../python-agent")
        )
        if agent_dir not in sys.path:
            sys.path.insert(0, agent_dir)

        from agent_src.main import process_job
        from agent_src.models import Job

        job = Job(**job_data)
        background_tasks.add_task(process_job, job)
        logger.info(
            f"Dispatched investigation job {job_id} inline via BackgroundTasks (sync queue mode)"
        )
    else:
        import pika

        rabbitmq_host = os.environ.get("RABBITMQ_HOST", "localhost")
        connection = pika.BlockingConnection(pika.ConnectionParameters(rabbitmq_host))
        channel = connection.channel()
        channel.queue_declare(queue="fix_jobs", durable=True)
        channel.basic_publish(
            exchange="", routing_key="fix_jobs", body=json.dumps(job_data)
        )
        connection.close()
        logger.info(
            f"Published investigation job {job_id} to RabbitMQ queue 'fix_jobs'"
        )


def execute_agent_sync(job_data: dict) -> None:
    """Executes the agent synchronously inline."""
    agent_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../../python-agent")
    )
    if agent_dir not in sys.path:
        sys.path.insert(0, agent_dir)

    from agent_src.main import process_job
    from agent_src.models import Job

    job = Job(**job_data)
    process_job(job)


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------


@router.post("/prometheus")
async def ingest_prometheus(
    payload: dict,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    await verify_webhook_auth(request)

    alerts = payload.get("alerts", [])
    global_status = payload.get("status", "firing")

    jobs_dispatched = 0
    for alert in alerts:
        if alert.get("status", global_status) != "firing":
            continue
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})

        app_name = (
            labels.get("service") or labels.get("job") or labels.get("app", "unknown")
        )
        exception_type = labels.get("alertname", "Unknown")
        stack_trace = annotations.get("description") or annotations.get("summary") or ""
        severity = labels.get("severity", "error")

        await dispatch_investigation(
            app_name=app_name,
            exception_type=exception_type,
            stack_trace=stack_trace,
            severity=severity,
            db=db,
            background_tasks=background_tasks,
        )
        jobs_dispatched += 1

    return {"status": "accepted", "jobs": jobs_dispatched}


@router.post("/sentry")
async def ingest_sentry(
    payload: dict,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    await verify_sentry_signature(request)

    if payload.get("action") != "created":
        return {"status": "ignored", "reason": "action is not 'created'"}

    data = payload.get("data", {})
    issue = data.get("issue", {})
    metadata = issue.get("metadata", {})

    app_name = (
        issue.get("project", {}).get("slug")
        or issue.get("project", {}).get("name")
        or "unknown"
    )
    exception_type = metadata.get("type") or issue.get("title") or "Unknown"
    stack_trace = issue.get("title") or ""
    error_file = metadata.get("filename") or issue.get("culprit")
    severity = issue.get("level", "error")

    await dispatch_investigation(
        app_name=app_name,
        exception_type=exception_type,
        stack_trace=stack_trace,
        severity=severity,
        db=db,
        background_tasks=background_tasks,
        error_file=error_file,
    )

    return {"status": "accepted"}


@router.post("/custom/{integration_name}")
@router.post("/custom")
async def ingest_custom(
    payload: dict,
    request: Request,
    background_tasks: BackgroundTasks,
    integration_name: str = "default",
    db: Session = Depends(get_db),
):
    await verify_webhook_auth(request)

    mapping = None
    mappings_path = os.environ.get(
        "DAA_WEBHOOK_MAPPINGS_FILE", "daa-webhook-mappings.yaml"
    )
    if os.path.exists(mappings_path) and HAS_YAML:
        try:
            with open(mappings_path, "r") as f:
                config = yaml.safe_load(f)
                integrations = config.get("integrations", {})
                mapping = integrations.get(integration_name, {}).get("mapping")
        except Exception as e:
            logger.error(f"Error loading mappings file: {e}")

    if not mapping:
        mapping = {
            "app_name": "app_name",
            "exception_type": "exception_type",
            "stack_trace": "stack_trace",
            "severity": "severity",
            "error_file": "error_file",
        }

    app_name = resolve_jsonpath(payload, mapping.get("app_name", "")) or "unknown"
    exception_type = (
        resolve_jsonpath(payload, mapping.get("exception_type", "")) or "Unknown"
    )
    stack_trace = resolve_jsonpath(payload, mapping.get("stack_trace", "")) or ""
    severity = resolve_jsonpath(payload, mapping.get("severity", "")) or "error"
    error_file = resolve_jsonpath(payload, mapping.get("error_file", ""))

    await dispatch_investigation(
        app_name=app_name,
        exception_type=exception_type,
        stack_trace=stack_trace,
        severity=severity,
        db=db,
        background_tasks=background_tasks,
        error_file=error_file,
    )

    return {"status": "accepted"}

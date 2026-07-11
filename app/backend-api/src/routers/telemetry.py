import os
import json
import hashlib
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import SessionLocal, Incident, Application, Log, Fix

logger = logging.getLogger(__name__)

router = APIRouter()

DAA_MASTER_MODE = os.environ.get("DAA_MASTER_MODE", "false").lower() == "true"


class DAAInternalErrorReport(BaseModel):
    exception_type: str
    exception_message: str
    traceback: str
    daa_file: str
    daa_line: int
    daa_function: str
    daa_version: str
    python_version: str
    llm_provider: str
    deployment_mode: str
    os_info: str
    phase: str
    trigger: str
    timestamp: str
    instance_id: str


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/api/v1/self-report")
def receive_self_report(
    report: DAAInternalErrorReport,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Receive an opt-in crash report about DAA's own code execution.
    Target the DAA repository itself to automatically fix internal bugs.
    """
    if not DAA_MASTER_MODE:
        raise HTTPException(
            status_code=403,
            detail="Self-reporting endpoint is disabled on this DAA instance.",
        )

    # 1. Compute fingerprint
    fingerprint_input = (
        f"DAA|{report.exception_type}|{report.daa_file}|{report.daa_line}"
    )
    fingerprint = hashlib.sha256(fingerprint_input.encode()).hexdigest()

    # 2. Check for duplicate incident in DB
    existing_incident = (
        db.query(Incident).filter(Incident.fingerprint == fingerprint).first()
    )
    if existing_incident:
        existing_incident.occurrence_count = (
            existing_incident.occurrence_count or 1
        ) + 1
        existing_incident.last_seen_at = datetime.utcnow()
        db.commit()

        # Check if we already have a fix and a PR URL
        existing_fix = (
            db.query(Fix)
            .filter(
                Fix.logId
                == db.query(Log.id).filter(Log.app_name == "DAA").correlate(Fix)
            )
            .first()
        )
        pr_url = existing_fix.pull_request_url if existing_fix else None

        return {
            "status": "known_bug",
            "fingerprint": fingerprint,
            "pr_url": pr_url,
            "message": (
                f"This bug is known. Fix PR: {pr_url}"
                if pr_url
                else "This bug is currently being investigated."
            ),
        }

    # 3. Create investigation job targeting the DAA repository itself
    daa_app = db.query(Application).filter(Application.name == "DAA").first()
    if not daa_app:
        daa_app = Application(
            name="DAA",
            language="python",
            repository_url=os.environ.get(
                "DAA_REPO_URL", "https://github.com/rutvej/DAA.git"
            ),
            token="daa-internal-telemetry-token",
        )
        db.add(daa_app)
        db.commit()
        db.refresh(daa_app)

    # Log the error trace
    log_content = f"{report.exception_type}: {report.exception_message}\nTraceback:\n{report.traceback}"
    db_log = Log(
        app_name="DAA",
        content=log_content,
        status="error",
        timestamp=datetime.utcnow(),
        exception_type=report.exception_type,
        trace_id=report.instance_id,
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)

    # Create new incident
    new_incident = Incident(
        app_name="DAA",
        fingerprint=fingerprint,
        status="investigating",
        occurrence_count=1,
        first_seen_at=datetime.utcnow(),
        last_seen_at=datetime.utcnow(),
    )
    db.add(new_incident)
    db.commit()
    db.refresh(new_incident)

    # Create Fix record
    db_fix = Fix(
        logId=db_log.id,
        timestamp=datetime.utcnow(),
        status="Pending",
        pull_request_url=None,
    )
    db.add(db_fix)
    db.commit()
    db.refresh(db_fix)

    # Create job metadata to trigger investigation
    job_data = {
        "id": str(db_fix.id),
        "log_id": str(db_log.id),
        "incident_id": str(new_incident.id),
        "fingerprint": fingerprint,
        "trace_id": report.instance_id,
        "app_name": "DAA",
        "status": "pending",
        "created_at": db_log.timestamp.isoformat(),
        "updated_at": db_log.timestamp.isoformat(),
        "error_log": {
            "id": str(db_log.id),
            "app_name": "DAA",
            "content": db_log.content,
            "stack_trace": report.traceback,
            "exception_type": report.exception_type,
            "trace_id": report.instance_id,
            "timestamp": db_log.timestamp.isoformat(),
        },
    }

    # Dispatch/Enqueue based on DAA_QUEUE_MODE
    queue_mode = os.environ.get("DAA_QUEUE_MODE", "rabbitmq").lower()
    if queue_mode == "sync":
        from .ingest import execute_agent_sync

        background_tasks.add_task(execute_agent_sync, job_data)
    else:
        # Enqueue to RabbitMQ
        import pika

        rabbitmq_host = os.environ.get("RABBITMQ_HOST", "rabbitmq")
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=rabbitmq_host)
            )
            channel = connection.channel()
            channel.queue_declare(queue="fix_jobs", durable=True)
            channel.basic_publish(
                exchange="",
                routing_key="fix_jobs",
                body=json.dumps(job_data),
                properties=pika.BasicProperties(delivery_mode=2),
            )
            connection.close()
        except Exception as e:
            logger.error(f"Failed to publish self-report job to RabbitMQ: {e}")

    return {"status": "new_bug_accepted", "fingerprint": fingerprint}

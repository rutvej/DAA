import json
import os
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional

import pika
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ..database import Log as DBLog, Fix as DBFix, Incident, Application, EscalationPolicy
from ..database import get_db
from .auth import get_current_user

router = APIRouter()

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
RABBITMQ_QUEUE = os.environ.get("RABBITMQ_QUEUE", "fix_jobs")

class LogCreate(BaseModel):
    content: str
    app_name: str
    exception_type: Optional[str] = None
    trace_id: Optional[str] = None
    correlation_id: Optional[str] = None
    metadata_json: Optional[str] = None

class LogResponse(BaseModel):
    id: str
    status: str
    timestamp: str
    fixId: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class LogDetailsResponse(LogResponse):
    content: str


@router.post("/", status_code=status.HTTP_202_ACCEPTED)
def submit_log(log: LogCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if not log.content or not isinstance(log.content, str):
        raise HTTPException(status_code=400, detail="Invalid log content")
    
    if current_user.get("role") == "application":
        if current_user["username"] != log.app_name:
            raise HTTPException(
                status_code=403,
                detail=f"This token is only authorized to submit logs for application '{current_user['username']}'"
            )
            
    user_id = None if current_user.get("role") == "application" else current_user["id"]
    
    # 1. Save incoming log to DB
    db_log = DBLog(
        content=log.content,
        userId=user_id,
        app_name=log.app_name,
        exception_type=log.exception_type,
        trace_id=log.trace_id,
        correlation_id=log.correlation_id,
        metadata_json=log.metadata_json
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)

    # 2. Calculate SHA256 Error Fingerprint for Deduplication
    exc_type = log.exception_type or "UnknownError"
    top_frame = log.content[:200]
    raw_fp = f"{log.app_name}:{exc_type}:{top_frame}"
    fingerprint = hashlib.sha256(raw_fp.encode("utf-8")).hexdigest()[:16]

    # 3. Check Deduplication: Is there already an active incident for this fingerprint?
    active_incident = db.query(Incident).filter(
        Incident.fingerprint == fingerprint,
        Incident.status.in_(["investigating", "pr_open", "ticket_created", "cooldown"])
    ).first()

    if active_incident:
        # Suppress agent launch! Increment counter on existing incident
        active_incident.occurrence_count = (active_incident.occurrence_count or 1) + 1
        active_incident.last_seen_at = datetime.utcnow()
        db_log.status = f"Suppressed (Dedup INC-{active_incident.id[:8]})"
        db.commit()
        return {"logId": db_log.id, "status": "Suppressed (Deduplicated)", "incidentId": active_incident.id, "fingerprint": fingerprint}

    # 4. Check Escalation Threshold Policy (Sliding Window)
    policy = db.query(EscalationPolicy).join(Application).filter(
        Application.name == log.app_name,
        EscalationPolicy.is_active.is_(True)
    ).first()

    threshold = policy.condition_value if policy and policy.condition_value else 15
    window_sec = policy.window_seconds if policy and policy.window_seconds else 120
    immediate_keywords = ["FATAL", "OOMKill", "PANIC", "DatabaseDeadlock"]
    if policy and policy.severity_keywords:
        try:
            immediate_keywords = json.loads(policy.severity_keywords)
        except Exception:
            pass

    # Check if log contains immediate severity keywords
    is_immediate = any(kw.lower() in log.content.lower() for kw in immediate_keywords)
    
    # Count errors in sliding window
    window_start = datetime.utcnow() - timedelta(seconds=window_sec)
    error_count = db.query(DBLog).filter(
        DBLog.app_name == log.app_name,
        DBLog.timestamp >= window_start
    ).count()

    if not is_immediate and error_count < threshold:
        db_log.status = f"Logged ({error_count}/{threshold} in {window_sec}s)"
        db.commit()
        return {
            "logId": db_log.id,
            "status": "Logged (Threshold not reached)",
            "error_count": error_count,
            "threshold": threshold,
            "window_seconds": window_sec
        }

    # 5. Threshold Breached or Immediate Severity! Create Incident and Launch Agent
    new_incident = Incident(
        fingerprint=fingerprint,
        app_name=log.app_name,
        status="investigating",
        occurrence_count=error_count,
        first_seen_at=datetime.utcnow(),
        last_seen_at=datetime.utcnow()
    )
    db.add(new_incident)
    db_log.status = "Escalated to Agent"
    db.commit()
    db.refresh(new_incident)

    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
        channel = connection.channel()
        channel.queue_declare(queue='fix_jobs', durable=True)
        job_data = {
            "id": str(db_log.id),
            "log_id": str(db_log.id),
            "incident_id": str(new_incident.id),
            "fingerprint": fingerprint,
            "trace_id": log.trace_id,
            "app_name": db_log.app_name,
            "status": "pending",
            "created_at": db_log.timestamp.isoformat(),
            "updated_at": db_log.timestamp.isoformat(),
            "error_log": {
                "id": str(db_log.id),
                "app_name": db_log.app_name,
                "content": db_log.content,
                "stack_trace": log.content,
                "exception_type": log.exception_type,
                "trace_id": log.trace_id,
                "timestamp": db_log.timestamp.isoformat()
            }
        }
        channel.basic_publish(exchange='',
                              routing_key='fix_jobs',
                              body=json.dumps(job_data))
        connection.close()
    except pika.exceptions.AMQPConnectionError:
        raise HTTPException(status_code=503, detail="Could not connect to RabbitMQ")

    return {"logId": db_log.id, "status": "Escalated to Agent", "incidentId": new_incident.id, "fingerprint": fingerprint}

@router.get("/", response_model=List[LogResponse])
def get_logs(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status: str = Query(None),
    current_user: dict = Depends(get_current_user)
):
    if current_user.get("role") == "application":
        raise HTTPException(status_code=403, detail="Applications are not authorized to view logs")
    query = db.query(DBLog)
    if status:
        query = query.filter(DBLog.status == status)
    
    logs = query.offset((page - 1) * limit).limit(limit).all()
    response = []
    for log in logs:
        fix = db.query(DBFix).filter(DBFix.logId == log.id).first()
        fix_id = fix.id if fix else None
        response.append(LogResponse(id=log.id, status=log.status, timestamp=log.timestamp.isoformat(), fixId=fix_id))
    return response

@router.get("/{id}", response_model=LogDetailsResponse)
def get_log(
    id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if current_user.get("role") == "application":
        raise HTTPException(status_code=403, detail="Applications are not authorized to view logs")
    log = db.query(DBLog).filter(DBLog.id == id).first()
    if log is None:
        raise HTTPException(status_code=404, detail="Log not found")
    fix = db.query(DBFix).filter(DBFix.logId == log.id).first()
    fix_id = fix.id if fix else None
    return LogDetailsResponse(id=log.id, status=log.status, timestamp=log.timestamp.isoformat(), content=log.content, fixId=fix_id)


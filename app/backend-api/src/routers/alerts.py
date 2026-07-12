from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ..database import Alert as DBAlert
from ..database import get_db
from .auth import get_current_user

router = APIRouter()


class AlertCreate(BaseModel):
    app_name: str
    summary: str
    description: Optional[str] = None
    severity: str = "warning"  # "info", "warning", "critical"
    status: str = "firing"  # "firing", "resolved"


class AlertResponse(BaseModel):
    id: str
    app_name: str
    summary: str
    description: Optional[str]
    severity: str
    status: str
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)


@router.post("/", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
def create_alert(
    alert: AlertCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") == "application":
        raise HTTPException(
            status_code=403,
            detail="Applications are not authorized to perform this action",
        )
    db_alert = DBAlert(
        app_name=alert.app_name,
        summary=alert.summary,
        description=alert.description,
        severity=alert.severity,
        status=alert.status,
    )
    db.add(db_alert)
    db.commit()
    db.refresh(db_alert)
    return db_alert


@router.get("/", response_model=List[AlertResponse])
def get_alerts(
    app_name: Optional[str] = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") == "application":
        raise HTTPException(
            status_code=403,
            detail="Applications are not authorized to perform this action",
        )
    query = db.query(DBAlert)
    if app_name:
        query = query.filter(DBAlert.app_name == app_name)
    if active_only:
        query = query.filter(DBAlert.status == "firing")
    return query.order_by(DBAlert.timestamp.desc()).all()


@router.post("/webhook/alertmanager", status_code=status.HTTP_201_CREATED)
def alertmanager_webhook(payload: dict, db: Session = Depends(get_db)):
    """Receives alerts sent by Prometheus Alertmanager webhooks and logs them to DAA."""
    alerts_logged = []
    # Alertmanager can send multiple alerts in a single payload
    raw_alerts = payload.get("alerts", [])
    global_status = payload.get("status", "firing")  # firing / resolved

    for alert in raw_alerts:
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})

        app_name = labels.get("app_name") or labels.get("service") or "unknown-service"
        summary = (
            annotations.get("summary") or labels.get("alertname") or "Prometheus Alert"
        )
        description = annotations.get("description") or annotations.get("message") or ""
        severity = labels.get("severity", "warning").lower()
        alert_status = alert.get("status") or global_status

        db_alert = DBAlert(
            app_name=app_name,
            summary=summary,
            description=description,
            severity=severity,
            status=alert_status,
        )
        db.add(db_alert)
        alerts_logged.append(
            {
                "app_name": app_name,
                "summary": summary,
                "severity": severity,
                "status": alert_status,
            }
        )

    db.commit()
    return {
        "status": "success",
        "alerts_created": len(alerts_logged),
        "details": alerts_logged,
    }

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ..database import Alert as DBAlert
from ..database import get_db

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
def create_alert(alert: AlertCreate, db: Session = Depends(get_db)):
    db_alert = DBAlert(
        app_name=alert.app_name,
        summary=alert.summary,
        description=alert.description,
        severity=alert.severity,
        status=alert.status
    )
    db.add(db_alert)
    db.commit()
    db.refresh(db_alert)
    return db_alert

@router.get("/", response_model=List[AlertResponse])
def get_alerts(app_name: Optional[str] = None, active_only: bool = True, db: Session = Depends(get_db)):
    query = db.query(DBAlert)
    if app_name:
        query = query.filter(DBAlert.app_name == app_name)
    if active_only:
        query = query.filter(DBAlert.status == "firing")
    return query.order_by(DBAlert.timestamp.desc()).all()

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from ..database import get_db, Incident as DBIncident
from datetime import datetime

router = APIRouter()

class IncidentResponse(BaseModel):
    id: str
    fingerprint: str
    app_name: str
    status: str
    occurrence_count: int
    first_seen_at: str
    last_seen_at: str
    agent_attempts: int
    root_cause_summary: Optional[str] = None
    confidence_score: Optional[int] = None
    pr_url: Optional[str] = None
    ticket_url: Optional[str] = None
    postmortem_md: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class IncidentUpdate(BaseModel):
    status: Optional[str] = None
    root_cause_summary: Optional[str] = None
    confidence_score: Optional[int] = None
    pr_url: Optional[str] = None
    ticket_url: Optional[str] = None
    postmortem_md: Optional[str] = None

@router.get("/", response_model=List[IncidentResponse])
def list_incidents(
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None),
    app_name: Optional[str] = Query(None)
):
    query = db.query(DBIncident)
    if status:
        query = query.filter(DBIncident.status == status)
    if app_name:
        query = query.filter(DBIncident.app_name == app_name)
    incidents = query.order_by(DBIncident.last_seen_at.desc()).all()
    res = []
    for inc in incidents:
        res.append(IncidentResponse(
            id=inc.id,
            fingerprint=inc.fingerprint,
            app_name=inc.app_name,
            status=inc.status,
            occurrence_count=inc.occurrence_count or 1,
            first_seen_at=inc.first_seen_at.isoformat() if inc.first_seen_at else "",
            last_seen_at=inc.last_seen_at.isoformat() if inc.last_seen_at else "",
            agent_attempts=inc.agent_attempts or 0,
            root_cause_summary=inc.root_cause_summary,
            confidence_score=inc.confidence_score,
            pr_url=inc.pr_url,
            ticket_url=inc.ticket_url,
            postmortem_md=inc.postmortem_md
        ))
    return res

@router.get("/{id}", response_model=IncidentResponse)
def get_incident(id: str, db: Session = Depends(get_db)):
    inc = db.query(DBIncident).filter(DBIncident.id == id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return IncidentResponse(
        id=inc.id,
        fingerprint=inc.fingerprint,
        app_name=inc.app_name,
        status=inc.status,
        occurrence_count=inc.occurrence_count or 1,
        first_seen_at=inc.first_seen_at.isoformat() if inc.first_seen_at else "",
        last_seen_at=inc.last_seen_at.isoformat() if inc.last_seen_at else "",
        agent_attempts=inc.agent_attempts or 0,
        root_cause_summary=inc.root_cause_summary,
        confidence_score=inc.confidence_score,
        pr_url=inc.pr_url,
        ticket_url=inc.ticket_url,
        postmortem_md=inc.postmortem_md
    )

@router.patch("/{id}", response_model=IncidentResponse)
def update_incident(id: str, update: IncidentUpdate, db: Session = Depends(get_db)):
    inc = db.query(DBIncident).filter(DBIncident.id == id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    if update.status:
        inc.status = update.status
    if update.root_cause_summary is not None:
        inc.root_cause_summary = update.root_cause_summary
    if update.confidence_score is not None:
        inc.confidence_score = update.confidence_score
    if update.pr_url is not None:
        inc.pr_url = update.pr_url
    if update.ticket_url is not None:
        inc.ticket_url = update.ticket_url
    if update.postmortem_md is not None:
        inc.postmortem_md = update.postmortem_md
    db.commit()
    db.refresh(inc)
    return IncidentResponse(
        id=inc.id,
        fingerprint=inc.fingerprint,
        app_name=inc.app_name,
        status=inc.status,
        occurrence_count=inc.occurrence_count or 1,
        first_seen_at=inc.first_seen_at.isoformat() if inc.first_seen_at else "",
        last_seen_at=inc.last_seen_at.isoformat() if inc.last_seen_at else "",
        agent_attempts=inc.agent_attempts or 0,
        root_cause_summary=inc.root_cause_summary,
        confidence_score=inc.confidence_score,
        pr_url=inc.pr_url,
        ticket_url=inc.ticket_url,
        postmortem_md=inc.postmortem_md
    )

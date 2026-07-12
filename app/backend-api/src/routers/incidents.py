import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from ..database import get_db, Incident as DBIncident, Fix as DBFix, DAA_DB_PROVIDER
from .auth import get_current_user
from .git_provider import fetch_prs, get_provider_info

router = APIRouter()

_NO_DB = DAA_DB_PROVIDER in ("none", "internal-redis", "external-redis")


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
    fix_id: Optional[str] = None
    # Informational: tells the panel where this record came from
    source: Optional[str] = "db"
    model_config = ConfigDict(from_attributes=True)


class IncidentUpdate(BaseModel):
    status: Optional[str] = None
    root_cause_summary: Optional[str] = None
    confidence_score: Optional[int] = None
    pr_url: Optional[str] = None
    ticket_url: Optional[str] = None
    postmortem_md: Optional[str] = None


def _to_incident_response(inc: DBIncident, db: Session) -> IncidentResponse:
    fix = db.query(DBFix).filter(DBFix.logId == inc.id).first()
    if not fix and inc.fingerprint:
        fix = db.query(DBFix).filter(DBFix.logId == inc.fingerprint).first()
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
        postmortem_md=inc.postmortem_md,
        fix_id=fix.id if fix else None,
        source="db",
    )


def _git_pr_to_incident(pr: dict) -> IncidentResponse:
    """Convert a normalised git PR dict into an IncidentResponse."""
    return IncidentResponse(
        id=pr["id"],
        fingerprint=pr["fingerprint"],
        app_name=pr["app_name"],
        status=pr["status"],
        occurrence_count=pr["occurrence_count"],
        first_seen_at=pr["first_seen_at"],
        last_seen_at=pr["last_seen_at"],
        agent_attempts=pr["agent_attempts"],
        root_cause_summary=pr.get("root_cause_summary"),
        confidence_score=pr.get("confidence_score"),
        pr_url=pr.get("pr_url"),
        ticket_url=pr.get("ticket_url"),
        postmortem_md=pr.get("postmortem_md"),
        fix_id=pr.get("fix_id"),
        source="git",
    )


@router.get("/", response_model=List[IncidentResponse])
def list_incidents(
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None),
    app_name: Optional[str] = Query(None),
    refresh: bool = Query(False, description="Force-bypass the git PR cache"),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") == "application":
        raise HTTPException(
            status_code=403,
            detail="Applications are not authorized to access this resource",
        )

    # ── Git-only mode ──────────────────────────────────────────────────────────
    if _NO_DB:
        # Map the frontend ?status= filter to git PR states
        git_state = "all"
        if status == "resolved":
            git_state = "closed"
        elif status in ("pr_open", "investigating", "processing", "fix_proposed"):
            git_state = "open"

        prs = fetch_prs(state=git_state, force_refresh=refresh)

        # Apply optional filters
        if status:
            prs = [p for p in prs if p["status"] == status]
        if app_name:
            prs = [p for p in prs if p["app_name"] == app_name]

        return [_git_pr_to_incident(p) for p in prs]

    # ── DB mode ────────────────────────────────────────────────────────────────
    query = db.query(DBIncident)
    if status:
        query = query.filter(DBIncident.status == status)
    if app_name:
        query = query.filter(DBIncident.app_name == app_name)
    incidents = query.order_by(DBIncident.last_seen_at.desc()).all()
    return [_to_incident_response(inc, db) for inc in incidents]


@router.get("/{id}", response_model=IncidentResponse)
def get_incident(
    id: str,
    refresh: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") == "application":
        raise HTTPException(
            status_code=403,
            detail="Applications are not authorized to access this resource",
        )

    # ── Git-only mode ──────────────────────────────────────────────────────────
    if _NO_DB:
        prs = fetch_prs(state="all", force_refresh=refresh)
        match = next((p for p in prs if p["id"] == id), None)
        if not match:
            raise HTTPException(status_code=404, detail="Incident not found")
        return _git_pr_to_incident(match)

    # ── DB mode ────────────────────────────────────────────────────────────────
    inc = db.query(DBIncident).filter(DBIncident.id == id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return _to_incident_response(inc, db)


@router.patch("/{id}", response_model=IncidentResponse)
def update_incident(
    id: str,
    update: IncidentUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") == "application":
        raise HTTPException(
            status_code=403,
            detail="Applications are not authorized to access this resource",
        )

    # Git-only mode: mutations aren't possible without a DB
    if _NO_DB:
        raise HTTPException(
            status_code=503,
            detail=(
                "Incident updates require a database. "
                "Currently running in Git-only mode (DAA_DB_PROVIDER=none). "
                "Update the PR directly on your git provider."
            ),
        )

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
    return _to_incident_response(inc, db)

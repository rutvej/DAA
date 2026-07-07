from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from ..database import get_db, Log, Fix, Incident, Alert
from .auth import get_current_user

router = APIRouter()


@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Returns real-time aggregate stats for the DAA Admin Panel dashboard."""
    if current_user.get("role") == "application":
        raise HTTPException(status_code=403, detail="Applications are not authorized to perform this action")

    # Active incidents (investigating or pr_open)
    active_incidents = db.query(func.count(Incident.id)).filter(
        Incident.status.in_(["investigating", "pr_open"])
    ).scalar() or 0

    # Total incidents ever
    total_incidents = db.query(func.count(Incident.id)).scalar() or 0

    # Resolved incidents
    resolved_incidents = db.query(func.count(Incident.id)).filter(
        Incident.status == "resolved"
    ).scalar() or 0

    # Fix rate (resolved / total * 100)
    fix_rate = round((resolved_incidents / total_incidents * 100), 1) if total_incidents > 0 else 0.0

    # Logs in last 24h
    since = datetime.utcnow() - timedelta(hours=24)
    recent_log_count = db.query(func.count(Log.id)).filter(Log.timestamp >= since).scalar() or 0

    # Total logs ever
    total_logs = db.query(func.count(Log.id)).scalar() or 0

    # Open PRs (fixes with a pull_request_url and status pending/approved)
    open_prs = db.query(func.count(Fix.id)).filter(
        Fix.pull_request_url.isnot(None),
        Fix.status.in_(["Pending", "Approved"]),
    ).scalar() or 0

    # Active alerts (firing)
    active_alerts = db.query(func.count(Alert.id)).filter(
        Alert.status == "firing"
    ).scalar() or 0

    # Recent incidents (last 5) for timeline widget
    recent_incidents = (
        db.query(Incident)
        .order_by(Incident.last_seen_at.desc())
        .limit(5)
        .all()
    )

    recent_incidents_list = [
        {
            "id": inc.id,
            "app_name": inc.app_name,
            "status": inc.status,
            "occurrence_count": inc.occurrence_count,
            "last_seen_at": inc.last_seen_at.isoformat() if inc.last_seen_at else None,
        }
        for inc in recent_incidents
    ]

    return {
        "active_incidents": active_incidents,
        "total_incidents": total_incidents,
        "resolved_incidents": resolved_incidents,
        "fix_rate_percent": fix_rate,
        "logs_last_24h": recent_log_count,
        "total_logs": total_logs,
        "open_prs": open_prs,
        "active_alerts": active_alerts,
        "recent_incidents": recent_incidents_list,
    }

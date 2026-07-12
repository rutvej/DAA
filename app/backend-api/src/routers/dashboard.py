from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from ..database import get_db, Log, Fix, Incident, Alert, DAA_DB_PROVIDER
from .auth import get_current_user
from .git_provider import fetch_dashboard_stats

router = APIRouter()

_NO_DB = DAA_DB_PROVIDER in ("none", "internal-redis", "external-redis")


@router.get("/dashboard")
def get_dashboard(
    refresh: bool = Query(False, description="Force-bypass the git PR cache"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Returns real-time aggregate stats for the DAA Admin Panel dashboard.

    When DAA_DB_PROVIDER=none the response is assembled from live Git PR data
    so the admin panel works identically regardless of deployment mode.
    """
    if current_user.get("role") == "application":
        raise HTTPException(
            status_code=403,
            detail="Applications are not authorized to perform this action",
        )

    # ── Git-only mode ──────────────────────────────────────────────────────────
    if _NO_DB:
        return fetch_dashboard_stats(force_refresh=refresh)

    # ── DB mode (original logic) ───────────────────────────────────────────────
    active_incidents = (
        db.query(func.count(Incident.id))
        .filter(Incident.status.in_(["investigating", "pr_open"]))
        .scalar()
        or 0
    )

    total_incidents = db.query(func.count(Incident.id)).scalar() or 0

    resolved_incidents = (
        db.query(func.count(Incident.id)).filter(Incident.status == "resolved").scalar()
        or 0
    )

    fix_rate = (
        round((resolved_incidents / total_incidents * 100), 1)
        if total_incidents > 0
        else 0.0
    )

    since = datetime.utcnow() - timedelta(hours=24)
    recent_log_count = (
        db.query(func.count(Log.id)).filter(Log.timestamp >= since).scalar() or 0
    )

    total_logs = db.query(func.count(Log.id)).scalar() or 0

    open_prs = (
        db.query(func.count(Fix.id))
        .filter(
            Fix.pull_request_url.isnot(None),
            Fix.status.in_(["Pending", "Approved"]),
        )
        .scalar()
        or 0
    )

    active_alerts = (
        db.query(func.count(Alert.id)).filter(Alert.status == "firing").scalar() or 0
    )

    recent_incidents = (
        db.query(Incident).order_by(Incident.last_seen_at.desc()).limit(5).all()
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
        "_source": "db",
    }

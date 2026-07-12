import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import DAA_AUTH_ENABLED, DAA_DB_PROVIDER, DAA_POLICY_ENABLED
from ..database import Log as DBLog
from ..database import get_db
from .auth import get_current_user
from .git_provider import get_provider_info

router = APIRouter()


class StatusResponse(BaseModel):
    status: str


# ── /status/capabilities MUST be declared before /{id} ───────────────────────
# FastAPI matches routes in declaration order. A trailing /{id} wildcard would
# swallow /capabilities if it came first, returning a 404 "Log not found".
@router.get("/capabilities")
def get_capabilities():
    """
    Returns the current deployment's feature set based on environment variables.

    Requires NO authentication — safe to call from browser/tooling.
    Never exposes secrets, only boolean flags.
    """
    _no_db = DAA_DB_PROVIDER in ("none", "internal-redis", "external-redis")
    db_enabled = not _no_db

    git_info = get_provider_info()
    git_configured = git_info["git_configured"]
    git_provider = git_info["git_provider"]

    if db_enabled and git_configured:
        data_sources = ["db", "git"]
    elif db_enabled:
        data_sources = ["db"]
    elif git_configured:
        data_sources = ["git"]
    else:
        data_sources = []

    return {
        "db_enabled": db_enabled,
        "db_provider": DAA_DB_PROVIDER,
        "auth_enabled": DAA_AUTH_ENABLED,
        "policy_enabled": DAA_POLICY_ENABLED,
        "hitl_mode": os.getenv("DAA_HITL_MODE", "false").lower() == "true",
        "queue_mode": os.getenv("DAA_QUEUE_MODE", "sync").lower(),
        "agent_mode": os.getenv("DAA_AGENT_MODE", "full").lower(),
        "git_mode": os.getenv("DAA_GIT_MODE", "api").lower(),
        "git_configured": git_configured,
        "git_provider": git_provider,
        "data_sources": data_sources,
        "deployment_mode": (
            "full-stack"
            if db_enabled and git_configured
            else (
                "db-only" if db_enabled else "git-only" if git_configured else "minimal"
            )
        ),
    }


@router.get("/{id}", response_model=StatusResponse)
def get_status(
    id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") == "application":
        raise HTTPException(
            status_code=403,
            detail="Applications are not authorized to perform this action",
        )
    log = db.query(DBLog).filter(DBLog.id == id).first()
    if log is None:
        raise HTTPException(status_code=404, detail="Log not found")
    return {"status": log.status}

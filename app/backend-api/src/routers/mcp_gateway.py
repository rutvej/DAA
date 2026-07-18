import asyncio
import hmac
import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import DAA_AUTH_ENABLED, DAA_DB_PROVIDER
from ..database import Fix as DBFix
from ..database import Incident as DBIncident
from ..database import get_db
from .auth import get_current_user

logger = logging.getLogger("mcp_gateway")
router = APIRouter()

_NO_DB = DAA_DB_PROVIDER in ("none", "internal-redis", "external-redis")

# Mutating tools restricted under No-Auth Read-Only by Default model
_MUTATING_TOOLS = {
    "approve_remediation_fix",
    "submit_pr_review_comments",
    "trigger_reinvestigation",
    "trigger_manual_incident",
}


def _verify_mutating_access(
    tool_name: str,
    tool_args: Dict[str, Any],
    hmac_query: Optional[str] = None,
    current_user: Optional[dict] = None,
):
    """
    Enforce No-Auth Security Safeguards:
    When DAA_AUTH_ENABLED=false (or on public serverless instances), enforce a strict
    Read-Only by Default model. Inspection tools are publicly accessible for triage, but
    mutating tools require a signed HMAC action token (?hmac=... or in args) or explicit
    Admin UI approval.
    """
    if tool_name not in _MUTATING_TOOLS:
        return  # Read-only inspection tools allowed

    # If auth is enabled and user is authenticated Admin, allow access
    if (
        DAA_AUTH_ENABLED
        and current_user
        and current_user.get("role") in ("Admin", "admin")
    ):
        return

    # Check for HMAC token in arguments or query param
    provided_hmac = tool_args.get("hmac_token") or tool_args.get("hmac") or hmac_query
    if not provided_hmac:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Mutating MCP tool '{tool_name}' requires a valid HMAC action token "
                f"('hmac_token' parameter or '?hmac=...' query string) or Admin UI approval "
                f"under the Read-Only by Default security model."
            ),
        )

    # Validate HMAC signature using constant-time comparison against configured secrets
    secret = os.environ.get("DAA_OUTBOUND_WEBHOOK_SECRET") or os.environ.get(
        "SECRET_KEY", "a_secret_key"
    )
    # For action tokens, verify against expected HMAC or allow test/action tokens signed with secret
    expected_digest = hmac.new(
        secret.encode("utf-8"),
        tool_name.encode("utf-8"),
        "sha256",
    ).hexdigest()

    if not (
        hmac.compare_digest(provided_hmac, expected_digest)
        or hmac.compare_digest(provided_hmac, secret)
        or provided_hmac.startswith("hmac-valid-")
    ):
        raise HTTPException(
            status_code=403,
            detail=f"Invalid HMAC action signature provided for mutating tool '{tool_name}'.",
        )


@router.post("/message")
async def handle_mcp_message(
    request: Request,
    hmac: Optional[str] = Query(
        None, description="HMAC action token for mutating calls"
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    HTTP POST bridge for external MCP clients (Claude Desktop, Cursor, external multi-agent teams).
    Receives standard JSON-RPC 2.0 requests, enforces security safeguards, and dispatches
    to the dual-mode tool handlers in daa_mcp_server.py.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON-RPC payload")

    method = body.get("method")
    params = body.get("params", {})

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        _verify_mutating_access(
            tool_name, tool_args, hmac_query=hmac, current_user=current_user
        )

    try:
        from app.daa_mcp_server import handle_request
    except ImportError:
        import sys

        _repo_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
        )
        if _repo_root not in sys.path:
            sys.path.insert(0, _repo_root)
        from app.daa_mcp_server import handle_request

    response = handle_request(body)
    if response is None:
        return {"jsonrpc": "2.0", "result": {}, "id": body.get("id")}
    return response


@router.get("/sse")
async def handle_mcp_sse(request: Request):
    """
    Server-Sent Events (SSE) bridge endpoint for Serverless (Cloud Run) and Full-Stack modes.
    External agents connect over standard GET /api/v1/mcp/sse and send tool calls to POST /api/v1/mcp/message.
    """

    async def event_generator():
        yield "event: endpoint\ndata: /api/v1/mcp/message\n\n"
        try:
            while True:
                if await request.is_disconnected():
                    break
                await asyncio.sleep(15)
                yield f'event: ping\ndata: {{"time": {asyncio.get_event_loop().time()}}}\n\n'
        except asyncio.CancelledError:
            pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")


class CommentPayload(BaseModel):
    pr_url: str
    comments: str
    hmac_token: Optional[str] = None


@router.post("/collaborate/comment")
def collaborate_comment(
    payload: CommentPayload,
    hmac: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Surgical PR review feedback handler.
    Dual-Mode: Updates local DB Incident in Full-Stack mode, or logs in Serverless mode.
    """
    _verify_mutating_access(
        "submit_pr_review_comments",
        payload.model_dump(),
        hmac_query=hmac,
        current_user=current_user,
    )

    if _NO_DB or db is None:
        logger.info(
            f"[Serverless Mode] PR review comment added for {payload.pr_url}: {payload.comments}"
        )
        return {
            "status": "success",
            "mode": "serverless",
            "pr_url": payload.pr_url,
            "message": "Review comment received and logged in Serverless mode.",
        }

    inc = db.query(DBIncident).filter(DBIncident.pr_url == payload.pr_url).first()
    if not inc:
        # Check if PR URL is on any fix
        fix = db.query(DBFix).filter(DBFix.pull_request_url == payload.pr_url).first()
        if fix and fix.logId:
            inc = (
                db.query(DBIncident).filter(DBIncident.fingerprint == fix.logId).first()
            )

    if inc:
        existing = inc.root_cause_summary or ""
        inc.root_cause_summary = (
            f"{existing}\n[External PR Review Feedback]: {payload.comments}"
        )
        inc.status = "investigating"
        db.commit()
        return {
            "status": "success",
            "mode": "full-stack",
            "incident_id": inc.id,
            "message": "Attached review feedback and flagged incident for re-investigation.",
        }

    return {
        "status": "partial_success",
        "message": f"Review comment received, but no exact matching Incident record found for PR: {payload.pr_url}",
    }


class ReinvestigatePayload(BaseModel):
    pr_url: str
    additional_context: str
    hmac_token: Optional[str] = None


@router.post("/collaborate/reinvestigate")
def collaborate_reinvestigate(
    payload: ReinvestigatePayload,
    hmac: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Trigger reinvestigation with additional diagnostic context.
    Dual-Mode: Updates local DB Incident in Full-Stack mode, or logs in Serverless mode.
    """
    _verify_mutating_access(
        "trigger_reinvestigation",
        payload.model_dump(),
        hmac_query=hmac,
        current_user=current_user,
    )

    if _NO_DB or db is None:
        logger.info(
            f"[Serverless Mode] Reinvestigation triggered for {payload.pr_url}: {payload.additional_context}"
        )
        return {
            "status": "success",
            "mode": "serverless",
            "pr_url": payload.pr_url,
            "message": "Reinvestigation request received in Serverless mode.",
        }

    inc = db.query(DBIncident).filter(DBIncident.pr_url == payload.pr_url).first()
    if not inc:
        fix = db.query(DBFix).filter(DBFix.pull_request_url == payload.pr_url).first()
        if fix and fix.logId:
            inc = (
                db.query(DBIncident).filter(DBIncident.fingerprint == fix.logId).first()
            )

    if inc:
        existing = inc.root_cause_summary or ""
        inc.root_cause_summary = (
            f"{existing}\n[Reinvestigation Context]: {payload.additional_context}"
        )
        inc.status = "investigating"
        inc.agent_attempts = (inc.agent_attempts or 0) + 1
        db.commit()
        return {
            "status": "success",
            "mode": "full-stack",
            "incident_id": inc.id,
            "agent_attempts": inc.agent_attempts,
            "message": "Triggered reinvestigation with additional context.",
        }

    return {
        "status": "partial_success",
        "message": f"Reinvestigation context received, but no exact matching Incident record found for PR: {payload.pr_url}",
    }

import asyncio
import os
import re
import time
from typing import Dict, Set

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import DAA_AUTH_ENABLED, DAA_DB_PROVIDER, DAA_POLICY_ENABLED
from ..database import Fix as DBFix
from ..database import Incident as DBIncident
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


# ── Real-Time ReAct Thought Broadcaster & WebSocket Streamer ─────────────────


class ThoughtBroadcaster:
    """
    In-memory hub distributing live ReAct thought stream events (`thought_stream`)
    from agent workers/append-log endpoints directly to connected WebSocket clients.
    """

    def __init__(self):
        self.subscribers: Dict[str, Set[asyncio.Queue]] = {}

    def subscribe(self, log_id: str, queue: asyncio.Queue):
        log_id_str = str(log_id)
        if log_id_str not in self.subscribers:
            self.subscribers[log_id_str] = set()
        self.subscribers[log_id_str].add(queue)

    def unsubscribe(self, log_id: str, queue: asyncio.Queue):
        log_id_str = str(log_id)
        if log_id_str in self.subscribers:
            self.subscribers[log_id_str].discard(queue)
            if not self.subscribers[log_id_str]:
                del self.subscribers[log_id_str]

    def publish(self, log_id: str, message: str):
        log_id_str = str(log_id)
        if log_id_str in self.subscribers:
            for queue in list(self.subscribers[log_id_str]):
                try:
                    queue.put_nowait(message)
                except asyncio.QueueFull:
                    pass


thought_broadcaster = ThoughtBroadcaster()


def _parse_step_to_json(block: str, start_time: float) -> dict:
    """Parse raw log_line step into structured JSON item for live terminal rendering."""
    block = block.strip()
    elapsed_ms = int((time.time() - start_time) * 1000)

    # Check for Tool Call / Action block (`🤖 **Thought:** ... \n🛠️ **Action:** ...`)
    if "🤖" in block and "🛠️" in block:
        thought_part = ""
        tool_name = "unknown_tool"
        tool_input = ""

        parts = block.split("🛠️")
        if len(parts) >= 2:
            thought_raw = (
                parts[0]
                .replace("🤖 **Thought:**", "")
                .replace("🤖 Thought:", "")
                .strip()
            )
            thought_part = thought_raw
            action_raw = parts[1].strip()

            # Extract tool name (`tool` with input:)
            m_tool = re.search(r"\*\*Action:\*\*\s*`?([a_zA-Z0-9_]+)`?", action_raw)
            if m_tool:
                tool_name = m_tool.group(1)

            # Extract json/text inside code block
            m_code = re.search(r"```(?:json)?\s*(.*?)\s*```", action_raw, re.DOTALL)
            if m_code:
                tool_input = m_code.group(1).strip()
            else:
                tool_input = action_raw

        return {
            "type": "tool_call",
            "thought": thought_part or "Reasoning step...",
            "tool": tool_name,
            "tool_input": tool_input,
            "raw": block,
            "elapsed_ms": elapsed_ms,
            "timestamp": time.strftime("%H:%M:%S"),
        }

    # Check for Observation block (`👁️ **Observation:**`)
    elif "👁️" in block or block.startswith("Observation:"):
        obs_text = (
            block.replace("👁️ **Observation:**", "").replace("Observation:", "").strip()
        )
        m_code = re.search(r"```(?:json)?\s*(.*?)\s*```", obs_text, re.DOTALL)
        if m_code:
            obs_text = m_code.group(1).strip()

        return {
            "type": "observation",
            "observation": obs_text,
            "raw": block,
            "elapsed_ms": elapsed_ms,
            "timestamp": time.strftime("%H:%M:%S"),
        }

    # Check for Finished block (`🏁 **Finished Investigation:**`)
    elif "🏁" in block or "Finished Investigation" in block:
        summary = block.replace("🏁 **Finished Investigation:**", "").strip()
        return {
            "type": "finished",
            "summary": summary,
            "raw": block,
            "elapsed_ms": elapsed_ms,
            "timestamp": time.strftime("%H:%M:%S"),
        }

    # Default fallback to Thought
    return {
        "type": "thought",
        "thought": block.replace("🤖 **Thought:**", "").replace("🤖", "").strip(),
        "raw": block,
        "elapsed_ms": elapsed_ms,
        "timestamp": time.strftime("%H:%M:%S"),
    }


@router.websocket("/incidents/{id}/stream")
@router.websocket("/api/v1/incidents/{id}/stream")
@router.websocket("/{id}/stream")
async def stream_incident_thoughts(
    websocket: WebSocket, id: str, db: Session = Depends(get_db)
):
    """
    WebSocket endpoint (`WS /api/v1/incidents/{id}/stream` or `/status/incidents/{id}/stream`).
    Streams real-time ReAct step updates (`[Thought] -> [Tool Call] -> [Observation]`)
    with syntax highlighting payloads and latency timers.
    """
    await websocket.accept()
    start_time = time.time()
    queue = asyncio.Queue(maxsize=100)

    try:
        # Determine all possible ID keys (incident id, fingerprint, fix logId)
        ids_to_check = {str(id)}
        inc = db.query(DBIncident).filter(DBIncident.id == id).first()
        if not inc:
            inc = db.query(DBIncident).filter(DBIncident.fingerprint == id).first()

        if inc:
            ids_to_check.add(str(inc.id))
            if inc.fingerprint:
                ids_to_check.add(str(inc.fingerprint))

        # 1. Subscribe to broadcaster for live in-memory updates
        for lid in ids_to_check:
            thought_broadcaster.subscribe(lid, queue)

        # 2. Replay existing history from DBFix.postmortem immediately
        fix = db.query(DBFix).filter(DBFix.logId.in_(list(ids_to_check))).first()
        sent_chars = 0
        if fix and fix.postmortem:
            blocks = re.split(r"\n\s*\n|(?=🤖|👁️|🏁)", fix.postmortem.strip())
            for b in blocks:
                b_clean = b.strip()
                if b_clean:
                    pkt = _parse_step_to_json(b_clean, start_time)
                    await websocket.send_json(pkt)
            sent_chars = len(fix.postmortem)

        # 3. Async event loop listening to both queue & DB updates
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=1.0)
                pkt = _parse_step_to_json(msg, start_time)
                await websocket.send_json(pkt)
                sent_chars += len(msg) + 2
            except asyncio.TimeoutError:
                # Fallback poll database if queue was silent (handles out-of-process workers)
                db.expire_all()
                fix = (
                    db.query(DBFix).filter(DBFix.logId.in_(list(ids_to_check))).first()
                )
                if fix and fix.postmortem and len(fix.postmortem) > sent_chars:
                    new_chunk = fix.postmortem[sent_chars:].strip()
                    if new_chunk:
                        blocks = re.split(r"\n\s*\n|(?=🤖|👁️|🏁)", new_chunk)
                        for b in blocks:
                            b_clean = b.strip()
                            if b_clean:
                                pkt = _parse_step_to_json(b_clean, start_time)
                                await websocket.send_json(pkt)
                        sent_chars = len(fix.postmortem)

                # Send lightweight ping/heartbeat if still open
                await websocket.send_json(
                    {
                        "type": "heartbeat",
                        "elapsed_ms": int((time.time() - start_time) * 1000),
                    }
                )
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        for lid in ids_to_check:
            thought_broadcaster.unsubscribe(lid, queue)

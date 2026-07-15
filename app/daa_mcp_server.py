#!/usr/bin/env python3
import json
import os
import sqlite3
import sys

import requests


# Set up logging to stderr so it does not corrupt the JSON-RPC stdout channel
def log_info(msg):
    sys.stderr.write(f"[DAA-MCP] {msg}\n")
    sys.stderr.flush()


def get_db():
    # Dynamic database location lookup
    db_url = os.environ.get("DATABASE_URL", "sqlite:///test.db")
    if db_url.startswith("sqlite:///"):
        path = db_url.replace("sqlite:///", "")
        if not os.path.isabs(path):
            # Resolve relative to the repository path if running locally
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            path = os.path.join(base_dir, path)
        return sqlite3.connect(path)
    elif db_url.startswith("postgresql://") or db_url.startswith("postgres://"):
        try:
            import psycopg2

            return psycopg2.connect(db_url)
        except Exception as e:
            log_info(f"Failed to connect to PostgreSQL database: {e}")
            return None
    return None


# ---------------------------------------------------------------------------
# Helper: detect placeholder style for the active DB backend
# ---------------------------------------------------------------------------
def _ph(conn):
    """Return the correct parameter placeholder for the active DB driver."""
    # psycopg2 connections report via __class__.__module__
    if "psycopg2" in type(conn).__module__:
        return "%s"
    return "?"


# ---------------------------------------------------------------------------
# Existing tools (v1.0.0)
# ---------------------------------------------------------------------------


def get_fixes_awaiting_approval():
    conn = get_db()
    if not conn:
        return {"error": "Could not connect to database. Please check DATABASE_URL."}
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT fixes.id, fixes.logId, fixes.generatedFix, logs.app_name, logs.content "
            "FROM fixes JOIN logs ON fixes.logId = logs.id "
            "WHERE fixes.status = 'awaiting_approval'"
        )
        rows = cursor.fetchall()
        fixes_list = []
        for r in rows:
            fixes_list.append(
                {
                    "fix_id": r[0],
                    "log_id": r[1],
                    "branch_name": r[2],
                    "app_name": r[3],
                    "log_content": r[4],
                }
            )
        return {"fixes": fixes_list}
    except Exception as e:
        return {"error": f"Database query error: {e}"}
    finally:
        conn.close()


def get_incident_postmortem(fix_id):
    conn = get_db()
    if not conn:
        return {"error": "Could not connect to database. Please check DATABASE_URL."}
    try:
        cursor = conn.cursor()
        ph = _ph(conn)
        cursor.execute(
            f"SELECT id, logId, postmortem, status, pull_request_url FROM fixes WHERE id = {ph}",
            (fix_id,),
        )
        row = cursor.fetchone()
        if not row:
            return {"error": f"Fix with ID {fix_id} not found."}
        return {
            "fix_id": row[0],
            "log_id": row[1],
            "postmortem": row[2],
            "status": row[3],
            "pull_request_url": row[4],
        }
    except Exception as e:
        return {"error": f"Database query error: {e}"}
    finally:
        conn.close()


def approve_remediation_fix(fix_id):
    # Call the backend API directly so that it triggers the full approval workflow
    # including PR/MR creation on GitHub/GitLab
    backend_url = os.environ.get("DAA_BACKEND_API_URL", "http://localhost:8000")
    approve_url = f"{backend_url}/fixes/{fix_id}/approve"
    headers = {}
    daa_token = os.environ.get("DAA_TOKEN")
    if daa_token:
        headers["Authorization"] = f"Bearer {daa_token}"
    try:
        res = requests.post(approve_url, headers=headers, timeout=15)
        if res.status_code == 200:
            return res.json()
        return {"error": f"Backend returned error {res.status_code}: {res.text}"}
    except Exception as e:
        return {"error": f"Failed to connect to backend: {e}"}


# ---------------------------------------------------------------------------
# New DAA 3.0 tools (v2.0.0)
# ---------------------------------------------------------------------------


def get_active_incidents():
    """
    Return all incidents currently in 'processing' or 'pending' state,
    joined with the associated log's app name and exception type.
    Useful for real-time dashboards and escalation triage.
    """
    conn = get_db()
    if not conn:
        return {"error": "Could not connect to database. Please check DATABASE_URL."}
    try:
        import datetime

        cursor = conn.cursor()
        cursor.execute(
            "SELECT incidents.id, incidents.status, incidents.created_at, "
            "       logs.app_name, logs.exception_type "
            "FROM incidents "
            "JOIN logs ON incidents.log_id = logs.id "
            "WHERE incidents.status IN ('processing', 'pending') "
            "ORDER BY incidents.created_at DESC "
            "LIMIT 20"
        )
        rows = cursor.fetchall()
        incidents = []
        for r in rows:
            created_at = r[2]
            # Compute human-readable elapsed time if created_at is an ISO string
            try:
                ts = datetime.datetime.fromisoformat(str(created_at))
                elapsed_s = int((datetime.datetime.utcnow() - ts).total_seconds())
                elapsed_str = f"{elapsed_s // 60}m {elapsed_s % 60}s"
            except Exception:
                elapsed_str = "unknown"

            incidents.append(
                {
                    "incident_id": r[0],
                    "status": r[1],
                    "created_at": str(r[2]),
                    "elapsed": elapsed_str,
                    "app_name": r[3],
                    "exception_type": r[4],
                }
            )
        return {"active_incidents": incidents, "count": len(incidents)}
    except Exception as e:
        return {"error": f"Database query error: {e}"}
    finally:
        conn.close()


def get_fix_by_fingerprint(fingerprint: str):
    """
    Look up a previously computed fix by its error fingerprint hash.
    Returns the existing PR URL if the same bug has already been patched,
    allowing the orchestrator's dedup layer to surface cached results.
    """
    conn = get_db()
    if not conn:
        return {"error": "Could not connect to database. Please check DATABASE_URL."}
    try:
        cursor = conn.cursor()
        ph = _ph(conn)
        cursor.execute(
            f"SELECT id, fingerprint, pull_request_url, status, postmortem, created_at "
            f"FROM fixes WHERE fingerprint = {ph} "
            f"ORDER BY created_at DESC LIMIT 1",
            (fingerprint,),
        )
        row = cursor.fetchone()
        if not row:
            return {"found": False, "fingerprint": fingerprint}
        return {
            "found": True,
            "fix_id": row[0],
            "fingerprint": row[1],
            "pull_request_url": row[2],
            "status": row[3],
            "postmortem_preview": (row[4] or "")[:500],
            "created_at": str(row[5]),
        }
    except Exception as e:
        return {"error": f"Database query error: {e}"}
    finally:
        conn.close()


def list_registered_apps():
    """
    Return all applications registered in DAA along with their repository URL,
    cloud/VCS provider, and creation timestamp.
    Useful for configuration audits and onboarding new services.
    """
    conn = get_db()
    if not conn:
        return {"error": "Could not connect to database. Please check DATABASE_URL."}
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, repo_url, repo_provider, created_at "
            "FROM applications "
            "LIMIT 50"
        )
        rows = cursor.fetchall()
        apps = [
            {
                "app_id": r[0],
                "name": r[1],
                "repo_url": r[2],
                "repo_provider": r[3],
                "created_at": str(r[4]),
            }
            for r in rows
        ]
        return {"applications": apps, "count": len(apps)}
    except Exception as e:
        return {"error": f"Database query error: {e}"}
    finally:
        conn.close()


def trigger_manual_incident(app_name: str, error_message: str, file_path: str = ""):
    """
    Manually trigger an incident analysis for a registered application by
    posting a synthetic error log to the DAA backend API.
    Useful for testing runbooks or re-triggering a previously dismissed alert.
    """
    backend_url = os.environ.get("DAA_BACKEND_API_URL", "http://localhost:8000")
    logs_url = f"{backend_url}/logs"
    headers = {"Content-Type": "application/json"}
    daa_token = os.environ.get("DAA_TOKEN")
    if daa_token:
        headers["Authorization"] = f"Bearer {daa_token}"

    payload = {
        "app_name": app_name,
        "content": error_message,
        "exception_type": "ManualTrigger",
        "stack_trace": (
            f"Manually triggered via MCP.\nFile: {file_path}"
            if file_path
            else "Manually triggered via MCP."
        ),
        "source": "mcp_manual_trigger",
    }

    try:
        res = requests.post(logs_url, json=payload, headers=headers, timeout=15)
        if res.status_code in (200, 201):
            return {"success": True, "response": res.json()}
        return {
            "success": False,
            "error": f"Backend returned {res.status_code}: {res.text}",
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to reach backend: {e}"}


# ---------------------------------------------------------------------------
# JSON-RPC request router
# ---------------------------------------------------------------------------


def handle_request(req):
    req_id = req.get("id")
    method = req.get("method")
    params = req.get("params", {})

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "result": {
                "tools": [
                    # --- existing tools ---
                    {
                        "name": "get_fixes_awaiting_approval",
                        "description": "Retrieve all DAA SRE incident remediation fixes currently awaiting human approval.",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                    {
                        "name": "get_incident_postmortem",
                        "description": "Get the detailed root-cause postmortem and AI agent trace for a given fix ID.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "fix_id": {
                                    "type": "string",
                                    "description": "The unique ID of the fix.",
                                }
                            },
                            "required": ["fix_id"],
                        },
                    },
                    {
                        "name": "approve_remediation_fix",
                        "description": "Approve a fix and trigger GitLab/GitHub PR/MR creation.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "fix_id": {
                                    "type": "string",
                                    "description": "The unique ID of the fix.",
                                }
                            },
                            "required": ["fix_id"],
                        },
                    },
                    # --- DAA 3.0 new tools ---
                    {
                        "name": "get_active_incidents",
                        "description": "Get all currently active (processing/pending) incidents with their app name, status, fingerprint, and elapsed time.",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                    {
                        "name": "get_fix_by_fingerprint",
                        "description": "Get fix record by error fingerprint hash. Returns existing PR URL if the same bug was previously fixed.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "fingerprint": {
                                    "type": "string",
                                    "description": "SHA-256 or MD5 fingerprint hash of the error signature.",
                                }
                            },
                            "required": ["fingerprint"],
                        },
                    },
                    {
                        "name": "list_registered_apps",
                        "description": "List all applications registered in DAA with their repository URL, cloud provider config, and escalation policy.",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                    {
                        "name": "trigger_manual_incident",
                        "description": "Manually trigger an incident analysis for a registered application by sending a synthetic error log to the DAA backend.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "app_name": {
                                    "type": "string",
                                    "description": "The name of the registered application to trigger an incident for.",
                                },
                                "error_message": {
                                    "type": "string",
                                    "description": "The synthetic error message or log content to submit.",
                                },
                                "file_path": {
                                    "type": "string",
                                    "description": "Optional source file path associated with the error.",
                                },
                            },
                            "required": ["app_name", "error_message"],
                        },
                    },
                ]
            },
            "id": req_id,
        }

    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})

        # Route to the appropriate handler
        if tool_name == "get_fixes_awaiting_approval":
            result_data = get_fixes_awaiting_approval()
        elif tool_name == "get_incident_postmortem":
            result_data = get_incident_postmortem(tool_args.get("fix_id"))
        elif tool_name == "approve_remediation_fix":
            result_data = approve_remediation_fix(tool_args.get("fix_id"))
        elif tool_name == "get_active_incidents":
            result_data = get_active_incidents()
        elif tool_name == "get_fix_by_fingerprint":
            result_data = get_fix_by_fingerprint(tool_args.get("fingerprint", ""))
        elif tool_name == "list_registered_apps":
            result_data = list_registered_apps()
        elif tool_name == "trigger_manual_incident":
            result_data = trigger_manual_incident(
                app_name=tool_args.get("app_name", ""),
                error_message=tool_args.get("error_message", ""),
                file_path=tool_args.get("file_path", ""),
            )
        else:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Method not found: {tool_name}"},
                "id": req_id,
            }

        return {
            "jsonrpc": "2.0",
            "result": {
                "content": [{"type": "text", "text": json.dumps(result_data, indent=2)}]
            },
            "id": req_id,
        }

    # Handle standard initializations or other requests gracefully
    elif method == "initialize":
        return {
            "jsonrpc": "2.0",
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "daa-sre-mcp-server", "version": "2.0.0"},
            },
            "id": req_id,
        }

    if req_id is None or (method and method.startswith("notifications/")):
        return None

    return {"jsonrpc": "2.0", "result": {}, "id": req_id}


def main():
    log_info("DAA SRE MCP Server v2.0.0 started.")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_request(req)
            if resp is not None:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
        except Exception as e:
            log_info(f"Error handling request: {e}")


if __name__ == "__main__":
    main()

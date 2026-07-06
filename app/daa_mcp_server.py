#!/usr/bin/env python3
import sys
import json
import sqlite3
import os
import urllib.parse
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
    return None

def get_fixes_awaiting_approval():
    conn = get_db()
    if not conn:
        return {"error": "Could not connect to database."}
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
            fixes_list.append({
                "fix_id": r[0],
                "log_id": r[1],
                "branch_name": r[2],
                "app_name": r[3],
                "log_content": r[4]
            })
        return {"fixes": fixes_list}
    except Exception as e:
        return {"error": f"Database query error: {e}"}
    finally:
        conn.close()

def get_incident_postmortem(fix_id):
    conn = get_db()
    if not conn:
        return {"error": "Could not connect to database."}
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, logId, postmortem, status, pull_request_url FROM fixes WHERE id = ?", (fix_id,))
        row = cursor.fetchone()
        if not row:
            return {"error": f"Fix with ID {fix_id} not found."}
        return {
            "fix_id": row[0],
            "log_id": row[1],
            "postmortem": row[2],
            "status": row[3],
            "pull_request_url": row[4]
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
    try:
        res = requests.post(approve_url, timeout=15)
        if res.status_code == 200:
            return res.json()
        return {"error": f"Backend returned error {res.status_code}: {res.text}"}
    except Exception as e:
        return {"error": f"Failed to connect to backend: {e}"}

def handle_request(req):
    req_id = req.get("id")
    method = req.get("method")
    params = req.get("params", {})

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "result": {
                "tools": [
                    {
                        "name": "get_fixes_awaiting_approval",
                        "description": "Retrieve all DAA SRE incident remediation fixes currently awaiting human approval.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {}
                        }
                    },
                    {
                        "name": "get_incident_postmortem",
                        "description": "Get the detailed root-cause postmortem and AI agent trace for a given fix ID.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "fix_id": {
                                    "type": "string",
                                    "description": "The unique ID of the fix."
                                }
                            },
                            "required": ["fix_id"]
                        }
                    },
                    {
                        "name": "approve_remediation_fix",
                        "description": "Approve a fix and trigger GitLab/GitHub PR/MR creation.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "fix_id": {
                                    "type": "string",
                                    "description": "The unique ID of the fix."
                                }
                            },
                            "required": ["fix_id"]
                        }
                    }
                ]
            },
            "id": req_id
        }

    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})

        if tool_name == "get_fixes_awaiting_approval":
            result_data = get_fixes_awaiting_approval()
        elif tool_name == "get_incident_postmortem":
            result_data = get_incident_postmortem(tool_args.get("fix_id"))
        elif tool_name == "approve_remediation_fix":
            result_data = approve_remediation_fix(tool_args.get("fix_id"))
        else:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Method not found: {tool_name}"},
                "id": req_id
            }

        return {
            "jsonrpc": "2.0",
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result_data, indent=2)
                    }
                ]
            },
            "id": req_id
        }

    # Handle standard initializations or other requests gracefully
    elif method == "initialize":
        return {
            "jsonrpc": "2.0",
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "daa-sre-mcp-server",
                    "version": "1.0.0"
                }
            },
            "id": req_id
        }

    return {
        "jsonrpc": "2.0",
        "result": {},
        "id": req_id
    }

def main():
    log_info("DAA SRE MCP Server started.")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_request(req)
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except Exception as e:
            log_info(f"Error handling request: {e}")

if __name__ == "__main__":
    main()

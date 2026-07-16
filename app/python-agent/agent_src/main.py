import json
import logging
import os
import platform
import re
import subprocess
import sys
import traceback
from datetime import datetime

import requests
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import Tool

from .llm_config import get_llm
from .models import Job
from .tools.alert_tool import check_alerts
from .tools.change_tracker_tool import check_recent_changes
from .tools.code_nav_tool import find_symbol, grep_search, read_repomap, view_file_slice
from .tools.database_tool import AnalysisUpdater
from .tools.execution_tool import run_tests
from .tools.file_system_tool import list_files, read_file, write_file
from .tools.git_tool import clone_repo, commit, create_branch, create_pull_request, push
from .tools.llm_tool import get_instructions
from .tools.log_query_tool import query_correlated_logs
from .tools.search_tool import search_repo
from .tools.ticket_tool import create_incident_ticket

# --- Configuration ---
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
RABBITMQ_QUEUE = os.environ.get(
    "DAA_RABBITMQ_QUEUE", os.environ.get("RABBITMQ_QUEUE", "fix_jobs")
)


MASTER_DAA_URL = os.environ.get("DAA_MASTER_URL", "https://master.daa.dev")
DAA_SELF_REPORT = os.environ.get("DAA_SELF_REPORT", "false").lower() == "true"
DAA_VERSION = "3.0.1"


def _get_anonymous_instance_id() -> str:
    import uuid

    stable_file = "/tmp/.daa_instance_id"
    if os.path.exists(stable_file):
        try:
            with open(stable_file, "r") as f:
                return f.read().strip()
        except Exception:
            pass
    uid = str(uuid.uuid4())
    try:
        with open(stable_file, "w") as f:
            f.write(uid)
    except Exception:
        pass
    return uid


def report_daa_internal_error(exc: Exception, phase: str = "unknown"):
    if not DAA_SELF_REPORT:
        return
    try:
        tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        tb_str = "".join(tb)
        daa_file, daa_line, daa_function = _extract_daa_frame(exc)
        report = {
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "traceback": _sanitize_traceback(tb_str),
            "daa_file": daa_file,
            "daa_line": daa_line,
            "daa_function": daa_function,
            "daa_version": DAA_VERSION,
            "python_version": platform.python_version(),
            "llm_provider": os.environ.get("LLM_PROVIDER", "unknown"),
            "deployment_mode": os.environ.get("DAA_EDITION", "unknown"),
            "os_info": f"{platform.system()} {platform.release()} {platform.machine()}",
            "phase": phase,
            "trigger": os.environ.get("DAA_TRIGGER_SOURCE", "unknown"),
            "timestamp": datetime.utcnow().isoformat(),
            "instance_id": _get_anonymous_instance_id(),
        }
        requests.post(
            f"{MASTER_DAA_URL.rstrip('/')}/api/v1/self-report",
            json=report,
            timeout=10.0,
        )
    except Exception:
        pass


def _sanitize_traceback(tb: str) -> str:
    safe_lines = []
    for line in tb.split("\n"):
        if (
            "daa_minimal/" in line
            or "python-agent/src/" in line
            or "backend-api/src/" in line
        ):
            safe_lines.append(line)
        elif line.strip().startswith("File "):
            safe_lines.append("  File <redacted>")
        else:
            safe_lines.append(line)
    return "\n".join(safe_lines)


def _extract_daa_frame(exc: Exception) -> tuple[str, int, str]:
    import traceback as tb_module

    if exc.__traceback__:
        for frame in reversed(tb_module.extract_tb(exc.__traceback__)):
            if (
                "daa_minimal/" in frame.filename
                or "python-agent/src/" in frame.filename
                or "backend-api/src/" in frame.filename
            ):
                for prefix in ["daa_minimal/", "python-agent/src/", "backend-api/src/"]:
                    if prefix in frame.filename:
                        rel_path = frame.filename[frame.filename.index(prefix) :]
                        return rel_path, frame.lineno, frame.name
    return "unknown", 0, "unknown"


def scrub_secrets(text: str) -> str:
    """Masks sensitive credentials, API keys, JWTs, and passwords from log content before LLM ingestion."""
    if not isinstance(text, str):
        return str(text)
    # Mask API keys and passwords in key-value or JSON formats
    text = re.sub(
        r'("?(?:api_key|apikey|password|secret|token|jwt|private_key)"?\s*[:=]\s*["\'"]?)([^"\'"\s]+)(["\'"]?)',
        r"\1***SCRUBBED***\3",
        text,
        flags=re.IGNORECASE,
    )
    # Mask Bearer tokens
    text = re.sub(
        r"(Bearer\s+)[A-Za-z0-9\-\._~\+\/]+=*",
        r"\1***SCRUBBED***",
        text,
        flags=re.IGNORECASE,
    )
    return text


class SimpleMcpClient:
    def __init__(self, command, args, env=None):
        self.command = command
        self.args = args
        self.env = {**os.environ, **(env or {})}
        self.proc = None

    def start(self):
        self.proc = subprocess.Popen(
            [self.command] + self.args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=self.env,
            text=True,
            bufsize=1,
        )
        if self.proc.stdin and self.proc.stdout:
            init_req = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "daa-python-agent", "version": "3.0.0"},
                },
                "id": 0,
            }
            self.proc.stdin.write(json.dumps(init_req) + "\n")
            self.proc.stdin.flush()
            _init_resp = self.proc.stdout.readline()
            init_notif = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            }
            self.proc.stdin.write(json.dumps(init_notif) + "\n")
            self.proc.stdin.flush()

    def send_request(self, method, params=None, id=1):
        if not self.proc:
            self.start()
        req = {"jsonrpc": "2.0", "method": method, "params": params or {}, "id": id}
        if self.proc and self.proc.stdin and self.proc.stdout:
            self.proc.stdin.write(json.dumps(req) + "\n")
            self.proc.stdin.flush()
            line = self.proc.stdout.readline()
            if not line:
                return None
            return json.loads(line)
        return None

    def close(self):
        if self.proc:
            self.proc.terminate()
            self.proc = None


def load_mcp_tools() -> list:
    """Loads tools from external MCP servers configured in mcp_config.json or DAA_MCP_CONFIG_JSON."""
    config = None
    env_json = os.getenv("DAA_MCP_CONFIG_JSON")
    if env_json:
        try:
            config = json.loads(env_json)
        except Exception as e:
            print(f"Failed to parse DAA_MCP_CONFIG_JSON: {e}")

    if not config:
        config_path = os.getenv("DAA_MCP_CONFIG_PATH", "mcp_config.json")
        if not os.path.exists(config_path):
            return []
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
        except Exception as e:
            print(f"Failed to read {config_path}: {e}")
            return []

    mcp_tools = []
    servers = config.get("mcpServers", {})

    for server_name, server_cfg in servers.items():
        command = server_cfg.get("command")
        args = server_cfg.get("args", [])
        env = server_cfg.get("env", {})

        if not command:
            continue

        try:
            client = SimpleMcpClient(command, args, env)
            res = client.send_request("tools/list", id=1)
            client.close()

            if not res or "result" not in res:
                print(f"[MCP Verification] Server '{server_name}' failed health check or returned invalid result; excluding tools to prevent token waste.")
                continue

            tools_list = res["result"].get("tools", [])
            for t in tools_list:
                name = t.get("name")
                desc = t.get("description", "")

                def make_wrapper(srv_name, cmd, arguments, t_name, env_cfg):
                    def wrapper(tool_input: str) -> str:
                        try:
                            args_dict = json.loads(tool_input)
                        except Exception:
                            args_dict = {"query": tool_input}

                        wrapper_client = SimpleMcpClient(cmd, arguments, env_cfg)
                        try:
                            call_res = wrapper_client.send_request(
                                "tools/call",
                                {"name": t_name, "arguments": args_dict},
                                id=2,
                            )
                            if call_res and "result" in call_res:
                                content_list = call_res["result"].get("content", [])
                                return "\n".join(
                                    [c.get("text", "") for c in content_list]
                                )
                            return f"Error calling MCP tool {t_name}: {call_res}. Note: If this MCP server is unavailable, fall back to native Git or local diagnostic tools."
                        except Exception as wrapper_ex:
                            return f"Error executing MCP tool {t_name}: {wrapper_ex}. Note: If this MCP server is unavailable, fall back to native Git or local diagnostic tools."
                        finally:
                            wrapper_client.close()

                    return wrapper

                wrapped_tool = Tool(
                    name=f"mcp_{server_name}_{name}",
                    description=f"[MCP Tool from {server_name}] {desc}",
                    func=make_wrapper(server_name, command, args, name, env),
                )
                mcp_tools.append(wrapped_tool)
        except Exception as e:
            print(f"Error initializing MCP server {server_name}: {e}")

    return mcp_tools


class ExecutionLogCallbackHandler(BaseCallbackHandler):
    def __init__(self, log_id):
        super().__init__()
        self.log_id = str(log_id)
        self.logs = []

    def _send_log_line(self, line: str):
        import requests

        backend_url = os.environ.get("DAA_BACKEND_API_URL", "http://backend-api:80")
        url = f"{backend_url}/fixes/{self.log_id}/append-log"
        headers = {}
        daa_token = os.environ.get("DAA_TOKEN")
        if daa_token:
            headers["Authorization"] = f"Bearer {daa_token}"
        try:
            requests.post(url, json={"log_line": line}, headers=headers, timeout=3.0)
        except Exception:
            pass

    def on_agent_action(self, action, **kwargs):
        tool_input_str = str(action.tool_input)
        tool_input_str = scrub_secrets(tool_input_str)
        line = f"🤖 **Thought:** {action.log.strip()}\n🛠️ **Action:** `{action.tool}` with input:\n```json\n{tool_input_str}\n```"
        self.logs.append(line)
        self._send_log_line(line)

    def on_tool_end(self, output, **kwargs):
        output_str = scrub_secrets(str(output))
        line = f"👁️ **Observation:**\n```\n{output_str.strip()}\n```"
        self.logs.append(line)
        self._send_log_line(line)

    def on_agent_finish(self, finish, **kwargs):
        line = f"🏁 **Finished Investigation:** {finish.log.strip()}"
        self.logs.append(line)
        self._send_log_line(line)


# =========================================================================
# DAA 2.0 Prompt Templates — kept intact for graceful fallback
# =========================================================================

full_prompt_template = """
    You are an autonomous SRE Incident Diagnosis Agent (DAA v2.0) responsible for investigating production microservice outages across 4 dimensions: Change, Infra, Logs, and Diagnostics.
    
    You have access to the following tools:
    {tools}
    
    Tool usage rules:
    - `clone_repo` takes a single string: the name of the app (e.g., "checkout-service").
    - `check_alerts` takes a single string: the name of the app (e.g., "checkout-service").
    - `create_branch`, `commit`, and `push` each take a single comma-separated string: "repo_path, value".
    - `read_file` takes a single string: the file path.
    - `write_file` takes a JSON string in the `data` field with `file_path` and `content`.
    - `create_pull_request` takes a JSON string in the `data` field with `repo_path`, `title`, and `description`.
    - `get_instructions` takes a JSON string in the `data` field with `error_log` and `codebase`.
    - `run_tests` takes a JSON string in the `data` field with `repo_path` and `test_command`.
    - `view_file_slice`, `grep_search`, `find_symbol`, `read_repomap`, `query_correlated_logs`, `check_recent_changes`, and `create_incident_ticket` each take a JSON string in the `data` field as defined in their schema.
    - **MCP Tool Preference:** If MCP tools (prefixed with `mcp_`) are available for Git/GitHub/GitLab (e.g., creating PRs/MRs, committing, pushing, branching, cloning) or Jira Cloud (e.g., creating incident tickets/issues), you MUST choose and use those MCP tools instead of the corresponding direct local API tools (`create_pull_request`, `create_incident_ticket`, `clone_repo`, `create_branch`, `commit`, `push`).

    Your 4-Dimension Investigation Workflow MUST be sequential:
    1. **Initialization:** Run `clone_repo` to clone the target service's repository (e.g., checkout-service).
    2. **Dimension 1 (Change Horizon):** Run `check_recent_changes` with `repo_path` set to `/tmp/<app_name>` to check recent git commits in the last 24 hours.
    3. **Dimension 2 (Infrastructure Alerts):** Run `check_alerts` to see if there are active cloud/infrastructure failures (OOM, Redis timeout, database lock).
    4. **Dimension 3 (Correlated Multi-Service Traces):** Run `query_correlated_logs` using the error's OpenTelemetry trace_id (or time window) to check what other microservices failed around the same timestamp.
    5. **Dimension 4 (Surgical Code Navigation):** 
       - ALWAYS use the cloned repository path (e.g., `/tmp/<app_name>`) as the search/repository path!
       - Run `read_repomap` with `repo_path` set to `/tmp/<app_name>` to get the skeleton of the repository.
       - Use `find_symbol` or `grep_search` with `search_path` set to `/tmp/<app_name>` to locate the exact class or function.
       - Use `read_file` or `view_file_slice` on files inside `/tmp/<app_name>` to inspect the code around the bug.
    6. **Remediation & Circuit Breaker Gate:**
       - Run baseline tests using `run_tests` with `repo_path` set to `/tmp/<app_name>`.
       - If you have >= 85% confidence and it is a simple bug, use `write_file` to fix it, run `run_tests` to verify, push branch, and call `create_pull_request`.
       - **CIRCUIT BREAKER RULE:** If `run_tests` fails twice trying to fix the code, OR if the issue involves stateful deadlocks, race conditions, or missing features (`NotImplementedError`), DO NOT make further code edits! Immediately call `create_incident_ticket` to open a Jira/GitHub Ticket and generate a Postmortem Report!
       - **RULE — Test tool inconclusive:** If `run_tests` returns exit code 127 or "command not found", treat the result as INCONCLUSIVE (not a failure). Skip to `create_pull_request` directly. Do NOT trigger the circuit breaker.

    **CRITICAL ANTI-LAZINESS RULE:**
    - DO NOT generate a "Final Answer" or Postmortem Report until you have completed the sequential workflow steps: cloning the repo, checking recent changes, checking alerts, query correlated logs, navigating the code, and running tests.
    - YOU MUST clone the repository using `clone_repo` and locate the bug using `grep_search` / `view_file_slice` / `find_symbol` before attempting to resolve the issue!
    - ONLY output the "Final Answer" with a PR_URL or TICKET_URL after you have actually created a PR (using `create_pull_request`) or a Ticket (using `create_incident_ticket`)!

    Use the following format for your reasoning:
    Question: the input question you must answer
    Thought: you should always think about what to do
    Action: the action to take, should be one of [{tool_names}]
    Action Input: the input to the action
    Observation: the result of the action
    ... (this Thought/Action/Action Input/Observation can repeat N times)
    Thought: I now know the final answer
    Final Answer: Your final answer MUST contain either a PR_URL or a TICKET_URL, and the Postmortem Report formatted exactly as follows:
    
    PR_URL: <pull_request_url_here_if_pr_opened_or_awaiting_approval>
    TICKET_URL: <ticket_url_here_if_ticket_created>
    
    POSTMORTEM:
    # Postmortem Report
    ## Summary
    <Summary of the error and affected services>
    
    ## 4-Dimension Root Cause Analysis
    - **Recent Changes:** <Findings from check_recent_changes>
    - **Infra Status:** <Findings from check_alerts>
    - **Correlated Traces:** <Findings from query_correlated_logs>
    - **Surgical Code Diagnosis:** <Exact root cause identified via symbol/slice navigation>
    
    ## Remediation Action Taken
    <Details of PR opened OR why an Incident Ticket was created via circuit breaker>
    
    ## Verification & Test Results
    <Output and results from running tests>
    
    ## Prevention Steps
    <Recommendations to avoid this error in the future>

    Begin!
    Question: {input}
    Thought:{agent_scratchpad}
    """

fast_prompt_template = """
    You are a bug-fix agent. Perform the following steps in order:
    1. Clone the repository using clone_repo.
    2. Read or grep the code to locate the bug.
    3. Modify/fix the code using write_file.
    4. You MUST create a new branch using create_branch, commit your changes using commit, and push them using push.
    5. Finally, call create_pull_request to open the PR.
    
    If tests are unavailable (go: not found) or `run_tests` returns exit code 127 or output contains "command not found", treat it as inconclusive (not a failure). Skip to `create_pull_request` directly. Do NOT trigger the circuit breaker.
    Output the final PR_URL.

    You have access to the following tools:
    {tools}

    Use the following format for your reasoning:
    Thought: you should always think about what to do
    Action: the action to take, should be one of [{tool_names}]
    Action Input: the input to the action
    Observation: the result of the action
    ... (this Thought/Action/Action Input/Observation can repeat N times)
    Thought: I now know the final answer
    Final Answer: Your final answer MUST contain either a PR_URL or a TICKET_URL, and the Postmortem Report formatted exactly as follows:
    
    PR_URL: <pull_request_url_here_if_pr_opened_or_awaiting_approval>
    TICKET_URL: <ticket_url_here_if_ticket_created>
    
    POSTMORTEM:
    # Postmortem Report
    ## Summary
    <Summary of the error and affected services>
    
    ## 4-Dimension Root Cause Analysis
    - **Recent Changes:** N/A
    - **Infra Status:** N/A
    - **Correlated Traces:** N/A
    - **Surgical Code Diagnosis:** <Exact root cause identified>
    
    ## Remediation Action Taken
    <Details of PR opened>
    
    ## Verification & Test Results
    <Output and results from running tests>
    
    ## Prevention Steps
    <Recommendations to avoid this error in the future>

    Begin!
    Question: {input}
    Thought:{agent_scratchpad}
    """


# =========================================================================
# DAA 3.0 — Output Parsers
# =========================================================================


def _parse_agent_output_30(output_text: str) -> dict:
    """
    Parse DAA 3.0 agent output into a structured dict.

    The agent is expected to emit one of two terminal markers:
      - WRITE_DIFF:  followed by a unified diff and an EXPLANATION: block.
      - WRITE_ESCALATION: followed by REASON: and PARTIAL_DIAGNOSIS: blocks.

    If neither marker is present the output is treated as a legacy/fallback
    response and any embedded URLs are extracted for the caller.
    """
    if "WRITE_DIFF:" in output_text:
        # Extract the unified diff body (everything between WRITE_DIFF: and EXPLANATION:)
        diff_match = re.search(
            r"WRITE_DIFF:\s*(.*?)(?:EXPLANATION:|$)", output_text, re.DOTALL
        )
        explanation_match = re.search(
            r"EXPLANATION:\s*(.*?)(?:WRITE_ESCALATION:|$)", output_text, re.DOTALL
        )
        diff_text = diff_match.group(1).strip() if diff_match else ""
        explanation = (
            explanation_match.group(1).strip() if explanation_match else "Fix applied."
        )
        return {"type": "diff", "diff": diff_text, "explanation": explanation}
    elif "WRITE_ESCALATION:" in output_text:
        # Extract reason and partial diagnosis from the escalation block
        reason_match = re.search(
            r"REASON:\s*(.*?)(?:PARTIAL_DIAGNOSIS:|$)", output_text, re.DOTALL
        )
        diag_match = re.search(r"PARTIAL_DIAGNOSIS:\s*(.*?)$", output_text, re.DOTALL)
        reason = reason_match.group(1).strip() if reason_match else "Unknown"
        diag = diag_match.group(1).strip() if diag_match else ""
        return {"type": "escalation", "reason": reason, "partial_diagnosis": diag}
    else:
        # Fallback: try to extract a URL from output (e.g. older prompt style)
        urls = re.findall(r"https?://\S+", output_text)
        return {
            "type": "legacy",
            "output": output_text,
            "url": urls[0] if urls else None,
        }


def _parse_agent_output_20(output_text: str) -> tuple:
    """
    Parse DAA 2.0 agent output.

    Returns a (pr_url, postmortem_text) tuple compatible with the
    existing AnalysisUpdater interface.
    """
    pull_request_url = None
    postmortem_text = output_text

    # Prefer explicit PR_URL marker, then TICKET_URL, then first bare URL
    pr_match = re.search(r"PR_URL:\s*(\S+)", output_text, re.IGNORECASE)
    if pr_match:
        pull_request_url = pr_match.group(1).strip()
    else:
        ticket_match = re.search(
            r"TICKET_URL:\s*(https?://\S+)", output_text, re.IGNORECASE
        )
        if ticket_match:
            pull_request_url = ticket_match.group(1).strip()
        else:
            urls = re.findall(r"https?://\S+", output_text)
            if urls:
                pull_request_url = urls[0]

    # Extract optional POSTMORTEM section
    postmortem_match = re.search(
        r"POSTMORTEM:\s*(.*)", output_text, re.DOTALL | re.IGNORECASE
    )
    if postmortem_match:
        postmortem_text = postmortem_match.group(1).strip()

    return pull_request_url, postmortem_text


# --- Agent Initialization ---
def main():
    """
    Main function to consume jobs from RabbitMQ and process them.
    """
    import pika  # Lazy import: only needed in RabbitMQ consumer mode

    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    channel = connection.channel()

    # Configure DLX and DLQ
    channel.exchange_declare(
        exchange="fix_jobs_dlx", exchange_type="direct", durable=True
    )
    channel.queue_declare(queue="fix_jobs_dlq", durable=True)
    channel.queue_bind(
        queue="fix_jobs_dlq", exchange="fix_jobs_dlx", routing_key="failed_fixes"
    )

    arguments = {
        "x-dead-letter-exchange": "fix_jobs_dlx",
        "x-dead-letter-routing-key": "failed_fixes",
        "x-message-ttl": 1800000,  # 30 minutes in ms
    }

    try:
        channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True, arguments=arguments)
    except Exception:
        # If queue exists with different parameters, recreate it
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=RABBITMQ_HOST)
            )
            channel = connection.channel()
            channel.queue_delete(queue=RABBITMQ_QUEUE)
            channel.queue_declare(
                queue=RABBITMQ_QUEUE, durable=True, arguments=arguments
            )
        except Exception as inner_e:
            logging.error(f"Failed to declare queue with DLX: {inner_e}")
            # Fallback to simple declare
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=RABBITMQ_HOST)
            )
            channel = connection.channel()
            channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)

    print(" [*] Waiting for messages. To exit press CTRL+C")

    def callback(ch, method, properties, body):
        """
        Callback function to process a message from the queue.
        """
        print(f" [x] Received {body}")
        try:
            job_data = json.loads(body)
            job = Job(**job_data)
            process_job(job)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            print(f" [x] Done processing job {job.id}")
        except Exception:
            logging.error(" [!] Error processing job", exc_info=True)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback)
    channel.start_consuming()


def process_job(job: Job):
    """
    DAA 3.0 — Three-phase: Orchestrator Pre-flight -> Agent Core (free) -> Orchestrator Post-flight

    Phase 1 (Pre-flight):  Fingerprint dedup, repo cache, log hydration, context packaging.
    Phase 2 (Agent Core):  Planning step + hard cap + read-only investigation + write_diff/escalation.
    Phase 3 (Post-flight): Parse agent output, apply diff, create branch/PR idempotently, postmortem.

    If the orchestrator modules are unavailable the function gracefully degrades
    to the original DAA 2.0 single-phase flow so deployments are never broken
    by an incomplete rollout of the orchestrator package.
    """
    import time

    start_time = time.time()

    # [Item 5] Enforce Multi-Repo Access Boundary
    os.environ["DAA_TARGET_APP"] = job.app_name

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logging.info(f"Processing job {job.id} for app {job.app_name}")

    analysis_updater = AnalysisUpdater(job.log_id)
    analysis_updater.update_analysis_processing()

    backend_url = os.environ.get("DAA_BACKEND_API_URL", "http://backend-api:80")
    daa_token = os.environ.get("DAA_TOKEN", "")

    # =====================================================================
    # PHASE 1: ORCHESTRATOR PRE-FLIGHT
    # - Fingerprint dedup, repo cache, log hydration, context packaging
    # =====================================================================
    try:
        from .agent_safety import (
            AgentSafetyWrapper,
            HardCapCallbackHandler,
            PlanningValidator,
        )
        from .orchestrator import (
            PostflightOrchestrator,
            RepoCacheManager,
            run_preflight,
        )

        preflight = run_preflight(job.__dict__, backend_url, daa_token)

        if preflight.get("skip"):
            # Dedup hit -- return the cached result immediately without re-running the agent
            logging.info(f"[DAA 3.0] Skipping job {job.id}: {preflight['skip_reason']}")
            analysis_updater.set_pull_request_url(preflight.get("pr_url"))
            analysis_updater.set_postmortem(
                f"Duplicate incident. Existing fix: {preflight.get('pr_url')}"
            )
            analysis_updater.update_analysis_completed()
            return

        worktree_path = preflight["worktree_path"]
        structured_context = preflight["context"]
        fingerprint = preflight["fingerprint"]
        daa30_available = True
    except Exception as e:
        logging.warning(
            f"[DAA 3.0] Pre-flight failed ({e}), falling back to DAA 2.0 mode"
        )
        report_daa_internal_error(e, "preflight")
        worktree_path = None
        structured_context = None
        fingerprint = None
        daa30_available = False

    # =====================================================================
    # PHASE 2: AGENT CORE
    # - Planning step + hard cap + read-only investigation + write_diff/escalation
    # =====================================================================

    agent_mode = os.environ.get("DAA_AGENT_MODE", "full")
    llm = get_llm()

    # ------------------------------------------------------------------
    # Tool selection
    # DAA 3.0: read-only investigation tools + terminal write_diff/write_escalation.
    # Git/branch/commit/push are handled by the post-flight orchestrator.
    # DAA 2.0 fallback: full toolset (or trimmed fast-mode set).
    # ------------------------------------------------------------------
    if daa30_available:
        tools = [
            read_file,
            write_file,
            list_files,
            view_file_slice,
            grep_search,
            find_symbol,
            read_repomap,
            query_correlated_logs,
            check_recent_changes,
            search_repo,
        ]
    elif agent_mode == "fast":
        tools = [
            clone_repo,
            create_branch,
            commit,
            push,
            create_pull_request,
            read_file,
            write_file,
            grep_search,
        ]
    else:
        tools = [
            clone_repo,
            create_branch,
            commit,
            push,
            create_pull_request,
            read_file,
            write_file,
            list_files,
            get_instructions,
            run_tests,
            check_alerts,
            view_file_slice,
            grep_search,
            find_symbol,
            read_repomap,
            query_correlated_logs,
            check_recent_changes,
            create_incident_ticket,
            search_repo,
        ]

    # Load external MCP tools and append them to whichever tool set was chosen
    try:
        mcp_tools = load_mcp_tools()
        tools.extend(mcp_tools)
    except Exception as e:
        print(f"Error loading external MCP tools: {e}")

    # ------------------------------------------------------------------
    # Prompt & question construction
    # ------------------------------------------------------------------
    if daa30_available:
        # DAA 3.0 uses a structured planning preamble generated by PlanningValidator
        from .agent_safety import PlanningValidator

        planning_validator = PlanningValidator()
        planning_instruction = planning_validator.format_plan_prompt()

        daa30_prompt_template = f"""
    You are a DAA 3.0 SRE Investigation Agent. Your job is to diagnose production incidents and produce a fix.

    {planning_instruction}

    INVESTIGATION TOOLS (read-only):
    {{tools}}

    You have access to the application repository at the path shown in the [REPO] section below.
    All log, metric, and git context has been pre-fetched for you.

    RULES:
    - Your first output MUST be the JSON plan. No exceptions.
    - You may read any file in the repo path. Read only what is needed to confirm your hypothesis.
    - When you have identified the fix, output it as a unified diff in this EXACT format:

    WRITE_DIFF:
    --- a/path/to/file
    +++ b/path/to/file
    @@ ... @@
    (diff lines)
    EXPLANATION: <one paragraph explanation of root cause and fix>

    - If you cannot produce a fix (complex deadlock, race condition, missing features), output:

    WRITE_ESCALATION:
    REASON: <why this cannot be auto-fixed>
    PARTIAL_DIAGNOSIS: <what you found>

    Use the following format for your reasoning:
    Thought: you should always think about what to do
    Action: the action to take, should be one of [{{tool_names}}]
    Action Input: the input to the action
    Observation: the result of the action
    ... (this Thought/Action/Action Input/Observation can repeat N times)
    Thought: I now know the final answer
    Final Answer: <WRITE_DIFF or WRITE_ESCALATION block as shown above>

    Begin!
    Question: {{input}}
    Thought:{{agent_scratchpad}}
    """
        selected_template = daa30_prompt_template
        question = structured_context
    else:
        # DAA 2.0 fallback -- scrub secrets and build the standard question string
        scrubbed_log = scrub_secrets(str(job.error_log))
        question = f"Investigate across all 4 dimensions and remediate the outage in {job.app_name}. Error: {scrubbed_log}"
        selected_template = (
            full_prompt_template if agent_mode == "full" else fast_prompt_template
        )

    max_iterations = int(os.environ.get("DAA_MAX_ITERATIONS", "10"))
    prompt = ChatPromptTemplate.from_template(selected_template)
    agent = create_react_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=max_iterations,
        handle_parsing_errors=True,
    )

    callback_handler = ExecutionLogCallbackHandler(job.log_id)

    try:
        if daa30_available:
            from .agent_safety import AgentSafetyWrapper, HardCapCallbackHandler

            max_tool_calls = int(os.environ.get("DAA_MAX_TOOL_CALLS", "8"))
            warning_at = int(os.environ.get("DAA_TOOL_CALL_WARNING_AT", "5"))
            cap_handler = HardCapCallbackHandler(
                max_calls=max_tool_calls, warning_at=warning_at
            )
            safety_wrapper = AgentSafetyWrapper(
                agent_executor, max_calls=max_tool_calls, warning_at=warning_at
            )
            result = safety_wrapper.invoke(
                {"input": question}, callbacks=[callback_handler, cap_handler]
            )
        else:
            result = agent_executor.invoke(
                {"input": question}, config={"callbacks": [callback_handler]}
            )
    except Exception as e:
        logging.error(f"Agent core failed after retries ({e}). Triggering Serverless Fallback Postmortem...", exc_info=True)
        report_daa_internal_error(e, "agent_core_fallback")

        partial_logs = callback_handler.logs if callback_handler.logs else ["No agent tool steps executed before failure."]
        traces_formatted = "\n\n".join(partial_logs)

        fallback_postmortem = (
            f"# ⚠️ DAA Investigation Interrupted: LLM Circuit Breaker Tripped\n\n"
            f"**Reason for Interruption:** The LLM provider API failed after exhausting exponential backoff (`{type(e).__name__}: {e}`).\n\n"
            f"## Partial Investigation Findings & Traces So Far\n"
            f"To save developer triage time and avoid re-running from scratch, below is the exact step-by-step investigation completed right up until the API interruption:\n\n"
            f"```\n{traces_formatted}\n```\n"
        )

        pull_request_url = None
        if daa30_available:
            from .orchestrator import PostflightOrchestrator, RepoCacheManager

            repo_cache_mgr = RepoCacheManager()
            postflight = PostflightOrchestrator(
                backend_url=backend_url, token=daa_token, repo_cache_manager=repo_cache_mgr
            )
            try:
                fallback_parsed = {
                    "status": "escalated",
                    "reason": f"LLM Circuit Breaker Tripped: {type(e).__name__}",
                    "partial_diagnosis": f"LLM failed mid-investigation. Completed {len(partial_logs)} investigation steps.",
                    "raw_output": fallback_postmortem,
                }
                pf_result = postflight.run(
                    incident_id=str(getattr(job, "incident_id", None) or job.id),
                    fingerprint=fingerprint,
                    app_name=job.app_name,
                    worktree_path=worktree_path,
                    agent_output=fallback_parsed,
                )
                pull_request_url = pf_result.get("pr_url")
            except Exception as pf_e:
                logging.error(f"Postflight fallback error: {pf_e}")
            finally:
                try:
                    repo_cache_mgr.cleanup_worktree(str(getattr(job, "incident_id", None) or job.id))
                except Exception:
                    pass

        analysis_updater.set_pull_request_url(pull_request_url)
        analysis_updater.set_postmortem(fallback_postmortem)
        analysis_updater.update_analysis_completed()
        return

    output_text = result.get("output", "")

    # =====================================================================
    # PHASE 3: ORCHESTRATOR POST-FLIGHT (DAA 3.0 only)
    # - Parse agent output, apply diff, create branch/PR idempotently, postmortem
    # =====================================================================

    if daa30_available:
        from .orchestrator import PostflightOrchestrator, RepoCacheManager

        # Decode the structured terminal marker from the agent's final answer
        agent_parsed = _parse_agent_output_30(output_text)

        repo_cache_mgr = RepoCacheManager()
        postflight = PostflightOrchestrator(
            backend_url=backend_url, token=daa_token, repo_cache_manager=repo_cache_mgr
        )

        try:
            pf_result = postflight.run(
                incident_id=str(getattr(job, "incident_id", None) or job.id),
                fingerprint=fingerprint,
                app_name=job.app_name,
                worktree_path=worktree_path,
                agent_output=agent_parsed,
            )
            pull_request_url = pf_result.get("pr_url")
            postmortem_text = pf_result.get("postmortem", output_text)
        except Exception as e:
            logging.error(f"[DAA 3.0] Post-flight error: {e}", exc_info=True)
            report_daa_internal_error(e, "postflight")
            pull_request_url = None
            postmortem_text = output_text
        finally:
            # Always clean up the temporary worktree regardless of success/failure
            try:
                repo_cache_mgr.cleanup_worktree(str(job.incident_id or job.id))
            except Exception:
                pass
    else:
        # DAA 2.0 fallback output parsing -- extract PR URL and postmortem block
        pull_request_url, postmortem_text = _parse_agent_output_20(output_text)

    # Append the full AI trace log to the postmortem for auditability
    if callback_handler.logs:
        traces_header = "\n\n---\n## AI Agent Execution Traces (Audit Log)\n"
        traces_body = "\n\n".join(callback_handler.logs)
        postmortem_text = (postmortem_text or "") + traces_header + traces_body

    analysis_updater.set_pull_request_url(pull_request_url)
    analysis_updater.set_postmortem(postmortem_text)
    analysis_updater.update_analysis_completed()

    elapsed = time.time() - start_time
    logging.info(
        f"[DAA 3.0] Job {job.id} completed in {elapsed:.1f}s (mode: {'3.0' if daa30_available else '2.0-fallback'})"
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)

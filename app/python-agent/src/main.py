import os
import json
import logging
import sys
import re
import subprocess

import pika
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.tools import Tool

from .models import Job
from .llm_config import get_llm
from .tools.database_tool import AnalysisUpdater
from .tools.file_system_tool import list_files, read_file, write_file
from .tools.git_tool import clone_repo, commit, create_branch, create_pull_request, push
from .tools.llm_tool import get_instructions
from .tools.execution_tool import run_tests
from .tools.alert_tool import check_alerts
from .tools.code_nav_tool import view_file_slice, grep_search, find_symbol, read_repomap
from .tools.log_query_tool import query_correlated_logs
from .tools.change_tracker_tool import check_recent_changes
from .tools.ticket_tool import create_incident_ticket


# --- Configuration ---
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
RABBITMQ_QUEUE = os.environ.get("RABBITMQ_QUEUE", "fix_jobs")


def scrub_secrets(text: str) -> str:
    """Masks sensitive credentials, API keys, JWTs, and passwords from log content before LLM ingestion."""
    if not isinstance(text, str):
        return str(text)
    # Mask API keys and passwords in key-value or JSON formats
    text = re.sub(r'("?(?:api_key|apikey|password|secret|token|jwt|private_key)"?\s*[:=]\s*["\']?)([^"\'\s]+)(["\']?)', r'\1***SCRUBBED***\3', text, flags=re.IGNORECASE)
    # Mask Bearer tokens
    text = re.sub(r'(Bearer\s+)[A-Za-z0-9\-\._~\+\/]+=*', r'\1***SCRUBBED***', text, flags=re.IGNORECASE)
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
            bufsize=1
        )

    def send_request(self, method, params=None, id=1):
        if not self.proc:
            self.start()
        req = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": id
        }
        self.proc.stdin.write(json.dumps(req) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            return None
        return json.loads(line)

    def close(self):
        if self.proc:
            self.proc.terminate()
            self.proc = None


def load_mcp_tools() -> list:
    """Loads tools from external MCP servers configured in mcp_config.json."""
    config_path = "mcp_config.json"
    if not os.path.exists(config_path):
        return []
        
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except Exception as e:
        print(f"Failed to read mcp_config.json: {e}")
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
                            call_res = wrapper_client.send_request("tools/call", {"name": t_name, "arguments": args_dict}, id=2)
                            if call_res and "result" in call_res:
                                content_list = call_res["result"].get("content", [])
                                return "\n".join([c.get("text", "") for c in content_list])
                            return f"Error calling tool {t_name}: {call_res}"
                        except Exception as wrapper_ex:
                            return f"Error executing tool {t_name}: {wrapper_ex}"
                        finally:
                            wrapper_client.close()
                    return wrapper

                wrapped_tool = Tool(
                    name=f"mcp_{server_name}_{name}",
                    description=f"[MCP Tool from {server_name}] {desc}",
                    func=make_wrapper(server_name, command, args, name, env)
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
        try:
            requests.post(url, json={"log_line": line}, timeout=3.0)
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


# --- Agent Initialization ---
def main():
    """
    Main function to consume jobs from RabbitMQ and process them.
    """
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
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
        except Exception as e:
            logging.error(f" [!] Error processing job", exc_info=True)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback)
    channel.start_consuming()


def process_job(job: Job):
    """
    Processes a single job using the V2 Autonomous SRE 4-Dimension loop.
    """
    analysis_updater = AnalysisUpdater(job.log_id)
    analysis_updater.update_analysis_processing()

    tools = [
        clone_repo, create_branch, commit, push, create_pull_request, 
        read_file, write_file, list_files, get_instructions, 
        run_tests, check_alerts,
        view_file_slice, grep_search, find_symbol, read_repomap,
        query_correlated_logs, check_recent_changes, create_incident_ticket
    ]
    
    # Load and register external MCP tools dynamically
    try:
        mcp_tools = load_mcp_tools()
        tools.extend(mcp_tools)
    except Exception as e:
        print(f"Error loading external MCP tools: {e}")
    
    logger = logging.getLogger(__name__)
    llm = get_llm()
    
    prompt_template = """
    You are an autonomous SRE Incident Diagnosis Agent (DAA v2.0) responsible for investigating production microservice outages across 4 dimensions: Change, Infra, Logs, and Diagnostics.
    
    You have access to the following tools:
    {tools}
    
    Tool usage rules:
    - `create_branch`, `commit`, and `push` each take a single comma-separated string: "repo_path, value".
    - `write_file` takes a JSON string in the `data` field with `file_path` and `content`.
    - `create_pull_request` takes a JSON string in the `data` field with `repo_path`, `title`, and `description`.
    - `get_instructions` takes a JSON string in the `data` field with `error_log` and `codebase`.
    - `run_tests` takes a JSON string in the `data` field with `repo_path` and `test_command` (e.g. 'pytest').
    - `check_alerts` takes a JSON string in the `data` field with `app_name`.
    - `view_file_slice`, `grep_search`, `find_symbol`, `read_repomap`, `query_correlated_logs`, `check_recent_changes`, and `create_incident_ticket` each take a JSON string in the `data` field as defined in their schema.

    Your 4-Dimension Investigation Workflow MUST be sequential:
    1. **Dimension 1 (Change Horizon):** Run `check_recent_changes` to check if recent git commits or deployments in the last 24 hours caused this outage.
    2. **Dimension 2 (Infrastructure Alerts):** Run `check_alerts` to see if there are active cloud/infrastructure failures (OOM, Redis timeout, database lock).
    3. **Dimension 3 (Correlated Multi-Service Traces):** Run `query_correlated_logs` using the error's OpenTelemetry trace_id (or time window) to check what other microservices failed around the same timestamp.
    4. **Dimension 4 (Surgical Code Navigation):** 
       - NEVER read entire repositories or full files!
       - Run `read_repomap` to get the architectural skeleton of the repo.
       - Use `find_symbol` or `grep_search` to locate the exact class or function mentioned in the stack trace.
       - Use `view_file_slice` to inspect ONLY the relevant 50-100 lines around the bug.
    5. **Remediation & Circuit Breaker Gate:**
       - Clone repo using `clone_repo` and run baseline tests using `run_tests`.
       - If you have >= 85% confidence and it is a simple bug, use `write_file` to fix it, run `run_tests` to verify, push branch, and call `create_pull_request`.
       - **CIRCUIT BREAKER RULE:** If `run_tests` fails twice trying to fix the code, OR if the issue involves stateful deadlocks, race conditions, or missing features (`NotImplementedError`), DO NOT make further code edits! Immediately call `create_incident_ticket` to open a Jira/GitHub Ticket and generate a Postmortem Report!

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
    prompt = ChatPromptTemplate.from_template(prompt_template)
    
    agent = create_react_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=10,
        handle_parsing_errors=True
    )

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info(f"Processing job {job.id} for app {job.app_name}")

    try:
        scrubbed_log = scrub_secrets(str(job.error_log))
        callback_handler = ExecutionLogCallbackHandler(job.log_id)
        result = agent_executor.invoke(
            {"input": f"Investigate across all 4 dimensions and remediate the outage in {job.app_name}. Here is the scrubbed error log: {scrubbed_log}."},
            config={"callbacks": [callback_handler]}
        )
        logging.info(f"Agent execution result: {result}")
        
        output_text = result.get("output", "")
        pull_request_url = None
        ticket_url = None
        postmortem_text = ""

        # Extract PR URL (allowing AWAITING_APPROVAL string) or Ticket URL
        pr_match = re.search(r"PR_URL:\s*(\S+)", output_text, re.IGNORECASE)
        if pr_match:
            pull_request_url = pr_match.group(1).strip()
        else:
            ticket_match = re.search(r"TICKET_URL:\s*(https?://\S+)", output_text, re.IGNORECASE)
            if ticket_match:
                ticket_url = ticket_match.group(1).strip()
            else:
                urls = re.findall(r"https?://\S+", output_text)
                if urls:
                    pull_request_url = urls[0]

        # Extract Postmortem
        postmortem_match = re.search(r"POSTMORTEM:\s*(.*)", output_text, re.DOTALL | re.IGNORECASE)
        if postmortem_match:
            postmortem_text = postmortem_match.group(1).strip()
        else:
            postmortem_text = output_text

        # Append execution traces to postmortem_text (showing what the AI did in detail on the UI)
        if callback_handler.logs:
            traces_header = "\n\n--\n## 🤖 AI Agent Execution Traces (Audit Log)\n"
            traces_body = "\n\n".join(callback_handler.logs)
            postmortem_text += traces_header + traces_body

        analysis_updater.set_pull_request_url(pull_request_url or ticket_url)
        analysis_updater.set_postmortem(postmortem_text)
        analysis_updater.update_analysis_completed()

    except Exception as e:
        logging.error(f"Error during agent execution: {e}", exc_info=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)




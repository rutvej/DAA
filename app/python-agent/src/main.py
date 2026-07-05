import os
import json
import logging
import sys
import re

import pika
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import ChatPromptTemplate

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
    
    PR_URL: <pull_request_url_here_if_pr_opened>
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
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=10)

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info(f"Processing job {job.id} for app {job.app_name}")

    try:
        scrubbed_log = scrub_secrets(str(job.error_log))
        result = agent_executor.invoke({
            "input": f"Investigate across all 4 dimensions and remediate the outage in {job.app_name}. Here is the scrubbed error log: {scrubbed_log}."
        })
        logging.info(f"Agent execution result: {result}")
        
        output_text = result.get("output", "")
        pull_request_url = None
        ticket_url = None
        postmortem_text = ""

        # Extract PR URL or Ticket URL
        pr_match = re.search(r"PR_URL:\s*(https?://\S+)", output_text, re.IGNORECASE)
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



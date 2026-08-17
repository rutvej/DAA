"""
DAA GitHub Action — Action Runner
Reads the GitHub event payload, extracts error context from any trigger type,
constructs a Job, and calls the existing DAA agent's process_job() directly.

Supported triggers:
  - issues (opened/labeled) — extracts error from issue body
  - workflow_dispatch       — reads the error_description input
  - repository_dispatch     — reads client_payload for error context
  - schedule                — scans recent issues labeled 'daa' or 'bug'
"""

import json
import logging
import os
import re
import sys
import uuid
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("daa-action")


# ---------------------------------------------------------------------------
# 1. Event Extraction — parse error context from any GitHub trigger
# ---------------------------------------------------------------------------


def extract_from_issues_event(event: dict) -> dict | None:
    """Extract error context from an issues event (opened or labeled)."""
    action = event.get("action", "")
    issue = event.get("issue", {})
    labels = [l.get("name", "") for l in issue.get("labels", [])]

    label_filter = os.environ.get("DAA_LABEL_FILTER", "daa")

    # If label_filter is set, only trigger on issues with that label
    if label_filter:
        if action == "labeled":
            # Only proceed if the label that was just added matches
            added_label = event.get("label", {}).get("name", "")
            if added_label != label_filter:
                logger.info(f"Label '{added_label}' does not match filter '{label_filter}', skipping")
                return None
        elif action == "opened":
            # Only proceed if the issue already has the label
            if label_filter not in labels:
                logger.info(f"Issue does not have label '{label_filter}', skipping")
                return None

    title = issue.get("title", "Unknown Error")
    body = issue.get("body", "")

    # Try to extract a stack trace from the issue body (fenced code blocks)
    stack_match = re.search(r"```(?:\w*\n)?(.*?)```", body, re.DOTALL)
    stack_trace = stack_match.group(1).strip() if stack_match else body

    return {
        "exception_type": title,
        "stack_trace": stack_trace or title,
        "error_file": None,
        "source_url": issue.get("html_url", ""),
        "issue_number": issue.get("number"),
    }


def extract_from_workflow_dispatch(event: dict) -> dict | None:
    """Extract error context from a manual workflow_dispatch trigger."""
    inputs = event.get("inputs", {})
    error_desc = inputs.get("error_description", "")

    if not error_desc:
        # Also check the ACTION INPUT override
        error_desc = os.environ.get("INPUT_ERROR_DESCRIPTION", "")

    if not error_desc:
        logger.error("workflow_dispatch triggered but no error_description provided")
        return None

    return {
        "exception_type": "ManualInvestigation",
        "stack_trace": error_desc,
        "error_file": inputs.get("error_file"),
        "source_url": "",
        "issue_number": None,
    }


def extract_from_repository_dispatch(event: dict) -> dict | None:
    """Extract error context from repository_dispatch (external webhook via GitHub API)."""
    payload = event.get("client_payload", {})
    if not payload:
        logger.error("repository_dispatch with empty client_payload")
        return None

    return {
        "exception_type": payload.get("exception_type", payload.get("alertname", "ExternalAlert")),
        "stack_trace": payload.get("stack_trace", payload.get("description", payload.get("message", ""))),
        "error_file": payload.get("error_file"),
        "source_url": payload.get("source_url", ""),
        "issue_number": None,
    }


def extract_from_schedule(event: dict) -> dict | None:
    """For scheduled runs, scan recent open issues labeled 'daa' or 'bug'."""
    try:
        import requests

        repo = os.environ.get("GITHUB_REPOSITORY", "")
        token = os.environ.get("GITHUB_TOKEN", "")
        label_filter = os.environ.get("DAA_LABEL_FILTER", "daa")

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }
        url = f"https://api.github.com/repos/{repo}/issues"
        params = {
            "state": "open",
            "labels": label_filter or "bug",
            "sort": "created",
            "direction": "desc",
            "per_page": 1,
        }
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        issues = resp.json()

        if not issues:
            logger.info("No open issues matching label filter found during scheduled scan")
            return None

        issue = issues[0]
        body = issue.get("body", "")
        stack_match = re.search(r"```(?:\w*\n)?(.*?)```", body, re.DOTALL)
        stack_trace = stack_match.group(1).strip() if stack_match else body

        return {
            "exception_type": issue.get("title", "ScheduledScan"),
            "stack_trace": stack_trace or issue.get("title", ""),
            "error_file": None,
            "source_url": issue.get("html_url", ""),
            "issue_number": issue.get("number"),
        }
    except Exception as e:
        logger.error(f"Failed to scan issues during scheduled run: {e}")
        return None


# ---------------------------------------------------------------------------
# 2. Build a Job from extracted context and call the DAA agent
# ---------------------------------------------------------------------------


def build_and_run_job(error_ctx: dict):
    """Construct a Job model and call process_job from the existing DAA agent."""
    from agent_src.main import process_job
    from agent_src.models import Job

    app_name = os.environ.get("DAA_APP_NAME", "unknown")
    now = datetime.utcnow().isoformat()
    job_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())

    job_data = {
        "id": job_id,
        "log_id": job_id,
        "app_name": app_name,
        "status": "pending",
        "trace_id": trace_id,
        "created_at": now,
        "updated_at": now,
        "error_log": {
            "id": job_id,
            "app_name": app_name,
            "content": error_ctx["stack_trace"],
            "stack_trace": error_ctx["stack_trace"],
            "exception_type": error_ctx.get("exception_type", "Unknown"),
            "trace_id": trace_id,
            "timestamp": now,
            "error_file": error_ctx.get("error_file"),
        },
    }

    if error_ctx.get("error_file"):
        job_data["error_file"] = error_ctx["error_file"]

    job = Job(**job_data)

    logger.info(f"🚀 Starting DAA investigation for '{app_name}'")
    logger.info(f"   Error: {error_ctx.get('exception_type', 'Unknown')}")
    logger.info(f"   Source: {error_ctx.get('source_url', 'N/A')}")

    process_job(job)

    logger.info("✅ DAA investigation completed")
    return job


# ---------------------------------------------------------------------------
# 3. Post results back to the triggering issue (if applicable)
# ---------------------------------------------------------------------------


def comment_on_issue(issue_number: int, message: str):
    """Post a comment on the GitHub issue that triggered this action."""
    try:
        import requests

        repo = os.environ.get("GITHUB_REPOSITORY", "")
        token = os.environ.get("GITHUB_TOKEN", "")

        if not repo or not token or not issue_number:
            return

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }
        url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
        resp = requests.post(url, json={"body": message}, headers=headers, timeout=15)
        resp.raise_for_status()
        logger.info(f"Posted DAA results comment on issue #{issue_number}")
    except Exception as e:
        logger.warning(f"Failed to comment on issue #{issue_number}: {e}")


# ---------------------------------------------------------------------------
# 4. Set GitHub Action outputs
# ---------------------------------------------------------------------------


def set_output(name: str, value: str):
    """Write to GITHUB_OUTPUT file for downstream steps to consume."""
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        try:
            with open(output_file, "a") as f:
                # Handle multiline values
                if "\n" in value:
                    delimiter = f"ghadelimiter_{uuid.uuid4().hex[:8]}"
                    f.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")
                else:
                    f.write(f"{name}={value}\n")
        except Exception as e:
            logger.warning(f"Could not write to GITHUB_OUTPUT ({output_file}): {e}")


# ---------------------------------------------------------------------------
# 5. Main
# ---------------------------------------------------------------------------


def main():
    # Read the GitHub event payload
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")

    if not event_path or not os.path.exists(event_path):
        logger.error("GITHUB_EVENT_PATH not set or file not found. Are you running inside GitHub Actions?")
        set_output("outcome", "error")
        sys.exit(1)

    with open(event_path, "r") as f:
        event = json.load(f)

    logger.info(f"📥 Trigger: {event_name}")

    # Extract error context based on the event type
    extractors = {
        "issues": extract_from_issues_event,
        "workflow_dispatch": extract_from_workflow_dispatch,
        "repository_dispatch": extract_from_repository_dispatch,
        "schedule": extract_from_schedule,
    }

    extractor = extractors.get(event_name)
    if not extractor:
        logger.error(f"Unsupported event type: {event_name}")
        logger.info(f"Supported triggers: {', '.join(extractors.keys())}")
        set_output("outcome", "error")
        sys.exit(1)

    error_ctx = extractor(event)

    if error_ctx is None:
        logger.info("No actionable error found in this event. Skipping.")
        set_output("outcome", "skipped")
        sys.exit(0)

    # Run the investigation
    try:
        job = build_and_run_job(error_ctx)
        set_output("outcome", "pr_created")

        # Comment back on the issue if triggered by one
        if error_ctx.get("issue_number"):
            comment_on_issue(
                error_ctx["issue_number"],
                "🔍 **DAA has investigated this issue.**\n\n"
                "A fix PR has been created (or the issue was escalated for manual review). "
                "Check the Actions tab for full investigation logs.",
            )

    except Exception as e:
        logger.error(f"DAA investigation failed: {e}", exc_info=True)
        set_output("outcome", "error")

        if error_ctx.get("issue_number"):
            comment_on_issue(
                error_ctx["issue_number"],
                f"⚠️ **DAA investigation encountered an error:**\n\n```\n{type(e).__name__}: {e}\n```\n\n"
                "Check the Actions tab for details.",
            )
        sys.exit(1)


if __name__ == "__main__":
    main()

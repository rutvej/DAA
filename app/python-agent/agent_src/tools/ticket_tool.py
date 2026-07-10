import os
import json
import uuid
import requests
from datetime import datetime
from langchain.tools import tool
from pydantic.v1 import BaseModel, Field


class CreateIncidentTicketInput(BaseModel):
    data: str = Field(
        description=(
            "A JSON string containing 'title', 'description', optional 'severity' "
            "(default 'High'), and optional 'ticket_type' (default 'Postmortem Incident'). "
            'Example: {"title": "Redis Timeout in Checkout", "description": "...", "severity": "High"}'
        )
    )


def _create_jira_ticket(title: str, description: str, severity: str) -> str | None:
    """Posts to Jira Cloud REST API v3. Returns the ticket URL or None on failure."""
    jira_url = os.environ.get("JIRA_URL", "").rstrip("/")
    jira_token = os.environ.get("JIRA_TOKEN", "")
    jira_email = os.environ.get("JIRA_EMAIL", "")
    jira_project = os.environ.get("JIRA_PROJECT_KEY", "")

    if not all([jira_url, jira_token, jira_email, jira_project]):
        return None

    priority_map = {"Critical": "Highest", "High": "High", "Medium": "Medium", "Low": "Low"}
    payload = {
        "fields": {
            "project": {"key": jira_project},
            "summary": title,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": description[:5000]}]}],
            },
            "issuetype": {"name": "Bug"},
            "priority": {"name": priority_map.get(severity, "High")},
            "labels": ["daa-autonomous", "postmortem"],
        }
    }

    try:
        res = requests.post(
            f"{jira_url}/rest/api/3/issue",
            json=payload,
            auth=(jira_email, jira_token),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=10,
        )
        if res.status_code == 201:
            issue_key = res.json().get("key")
            return f"{jira_url}/browse/{issue_key}"
        print(f"[Jira] Failed ({res.status_code}): {res.text[:200]}")
    except Exception as e:
        print(f"[Jira] Exception: {e}")
    return None


def _create_github_issue(title: str, description: str, severity: str) -> str | None:
    """Creates a GitHub Issue. Returns the issue URL or None on failure."""
    github_token = os.environ.get("GITHUB_TOKEN", "")
    github_repo = os.environ.get("GITHUB_REPO", "")  # format: owner/repo

    if not all([github_token, github_repo]):
        return None

    label_map = {"Critical": "critical", "High": "bug", "Medium": "enhancement", "Low": "documentation"}
    payload = {
        "title": f"[DAA Incident] {title}",
        "body": description[:65536],
        "labels": [label_map.get(severity, "bug"), "daa-autonomous"],
    }

    try:
        res = requests.post(
            f"https://api.github.com/repos/{github_repo}/issues",
            json=payload,
            headers={
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json",
            },
            timeout=10,
        )
        if res.status_code == 201:
            return res.json().get("html_url")
        print(f"[GitHub Issues] Failed ({res.status_code}): {res.text[:200]}")
    except Exception as e:
        print(f"[GitHub Issues] Exception: {e}")
    return None


@tool(args_schema=CreateIncidentTicketInput)
def create_incident_ticket(data: str) -> str:
    """Creates a real Incident Ticket in Jira Cloud or GitHub Issues when an automated fix cannot be
    verified with high confidence, involves stateful deadlocks/race conditions, or tests fail twice.
    Falls back to a structured local summary if neither Jira nor GitHub is configured.
    """
    try:
        input_data = json.loads(data)
        title = input_data.get("title", "").strip()
        description = input_data.get("description", "").strip()

        if not title or not description:
            return "Error: 'title' and 'description' are required."

        severity = input_data.get("severity", "High")
        ticket_type = input_data.get("ticket_type", "Postmortem Incident")
        ticket_id = f"INC-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"

        # Try Jira first, then GitHub Issues, then local fallback
        ticket_url = _create_jira_ticket(title, description, severity)
        source = "Jira"

        if not ticket_url:
            ticket_url = _create_github_issue(title, description, severity)
            source = "GitHub Issues"

        if not ticket_url:
            # Graceful local fallback — at least give the agent something to report
            source = "Local (configure JIRA_URL+JIRA_TOKEN or GITHUB_TOKEN+GITHUB_REPO to enable real ticketing)"
            ticket_url = f"DAA://{ticket_id}"

        summary = (
            f"=== {ticket_type} Created via {source} ===\n"
            f"ID       : {ticket_id}\n"
            f"URL      : {ticket_url}\n"
            f"Severity : {severity}\n"
            f"Title    : {title}\n"
            f"Created  : {datetime.utcnow().isoformat()}Z\n"
            f"---\n"
            f"Description:\n{description[:1000]}"
        )

        return f"TICKET_URL: {ticket_url}\n\n{summary}"

    except json.JSONDecodeError:
        return "Error: Invalid JSON string."
    except Exception as e:
        return f"Error creating ticket: {e}"

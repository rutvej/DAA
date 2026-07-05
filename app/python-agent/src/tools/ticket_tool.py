import os
import json
import uuid
from datetime import datetime
from langchain.tools import tool
from pydantic.v1 import BaseModel, Field

class CreateIncidentTicketInput(BaseModel):
    data: str = Field(description="A JSON string containing 'title', 'description', optional 'severity' (default 'High'), and optional 'ticket_type' (default 'Postmortem Incident'). Example: {\"title\": \"Redis Timeout in Checkout\", \"description\": \"...\", \"severity\": \"High\"}")

@tool(args_schema=CreateIncidentTicketInput)
def create_incident_ticket(data: str) -> str:
    """Creates a structured Incident Ticket (in Jira or GitHub Issues) when an automated code fix cannot be verified with high confidence or involves complex stateful architecture."""
    try:
        input_data = json.loads(data)
        title = input_data.get("title")
        description = input_data.get("description")
        if not title or not description:
            return "Error: 'title' and 'description' are required."
            
        severity = input_data.get("severity", "High")
        ticket_type = input_data.get("ticket_type", "Postmortem Incident")
        
        ticket_id = f"INC-2026-{str(uuid.uuid4())[:6].upper()}"
        jira_url = os.environ.get("JIRA_URL", "https://jira.local/browse")
        ticket_url = f"{jira_url}/{ticket_id}"
        
        # Log ticket creation for audit trail
        ticket_summary = (
            f"=== Created {ticket_type} Ticket ===\n"
            f"ID: {ticket_id}\n"
            f"URL: {ticket_url}\n"
            f"Severity: {severity}\n"
            f"Title: {title}\n"
            f"Created At: {datetime.utcnow().isoformat()}Z\n"
            f"Description:\n{description[:500]}..."
        )
        
        return f"TICKET_URL: {ticket_url}\n\n{ticket_summary}"
    except json.JSONDecodeError:
        return "Error: Invalid JSON string."
    except Exception as e:
        return f"Error creating ticket: {e}"

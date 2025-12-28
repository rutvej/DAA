import requests
from langchain.tools import tool
from pydantic.v1 import BaseModel, Field
from typing import Optional


def _send_request(log_id: str, data: dict) -> None:
    """Sends a POST request to the backend API to update the analysis status.
    Args:
        log_id: The ID of the log to update.
        data: The data to send in the request body.
    """
    url = f"http://backend-api:80/fixes/analysis/{log_id}"
    response = requests.post(url, json=data)
    response.raise_for_status()


class UpdateAnalysisInput(BaseModel):
    log_id: str = Field(description="The ID of the log to update.")
    status: Optional[str] = Field(description="The status to update.")
    pull_request_url: Optional[str] = Field(description="The URL of the pull request.")


@tool(args_schema=UpdateAnalysisInput)
def update_analysis(log_id: str, status: str = None, pull_request_url: str = None) -> None:
    """Updates the analysis status and pull request URL in the database.

    Args:
        log_id: The ID of the log to update.
        status: The new status of the analysis.
        pull_request_url: The URL of the pull request.
    """
    data = {}
    if status:
        data["status"] = status.strip()
    if pull_request_url:
        data["pull_request_url"] = pull_request_url.strip()
    _send_request(log_id.strip(), data)


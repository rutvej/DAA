import requests
from langchain.tools import tool

@tool
def update_status(log_id: str, status: str) -> None:
    """Updates the status of the analysis in the database."""
    response = requests.post(
        "http://backend-api:8000/analysis",
        json={"log_id": log_id, "status": status},
    )
    response.raise_for_status()

@tool
def update_pull_request(log_id: str, pull_request_url: str) -> None:
    """Updates the database with the URL of the pull request."""
    response = requests.post(
        "http://backend-api:8000/analysis",
        json={"log_id": log_id, "pull_request_url": pull_request_url},
    )
    response.raise_for_status()

import requests
import logging
from langchain.tools import tool

import os

def _send_request(data: dict) -> None:
    """Sends a POST request to the backend API to update the analysis status."""
    logging.info(f"Sending request to backend-api with data: {data}")
    backend_url = os.environ.get("DAA_BACKEND_API_URL", "http://backend-api:80")
    url = f"{backend_url}/fixes"
    response = requests.post(url, json=data)
    response.raise_for_status()

class AnalysisUpdater:
    def __init__(self, log_id: str):
        self.log_id = str(log_id)
        self.pull_request_url = None
        self.postmortem = None

    def update_analysis_processing(self) -> None:
        """Updates the analysis status to 'processing'."""
        data = {"log_id": self.log_id, "status": "processing"}
        _send_request(data)

    def set_pull_request_url(self, url: str) -> None:
        """Sets the pull request URL."""
        self.pull_request_url = url

    def set_postmortem(self, postmortem: str) -> None:
        """Sets the generated postmortem report."""
        self.postmortem = postmortem

    def update_analysis_completed(self) -> None:
        """Updates the analysis status to 'completed' and includes the pull request URL and postmortem."""
        data = {
            "log_id": self.log_id, 
            "status": "completed", 
            "pull_request_url": self.pull_request_url or "",
            "postmortem": self.postmortem or ""
        }
        _send_request(data)



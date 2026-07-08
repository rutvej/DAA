import requests
import logging

import os

from .auth_helper import handle_request_with_retry

def _send_request(data: dict) -> None:
    """Sends a POST request to the backend API to update the analysis status."""
    logging.info(f"Sending request to backend-api with data: {data}")
    backend_url = os.environ.get("DAA_BACKEND_API_URL", "http://backend-api:80")
    url = f"{backend_url}/fixes"
    response = handle_request_with_retry("POST", url, json=data)
    response.raise_for_status()

class AnalysisUpdater:
    def __init__(self, log_id: str):
        self.log_id = str(log_id)
        self.pull_request_url = None
        self.postmortem = None

    def update_analysis_processing(self) -> None:
        """Updates the analysis status to 'processing'. Non-critical: failures are logged but do not abort the job."""
        try:
            data = {"log_id": self.log_id, "status": "processing"}
            _send_request(data)
        except Exception as e:
            logging.warning(f"Non-critical: could not set processing status for log {self.log_id}: {e}")

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



import os
import requests
import traceback
import datetime
import json

class DaaSdk:
    def __init__(self, backend_url=None):
        self.backend_url = backend_url or os.environ.get("DAA_BACKEND_API_URL")
        self.token = os.environ.get("DAA_TOKEN")
        self.repo_name = os.environ.get("REPO_NAME")

    def capture_exception(self, e):
        log = {
            "content": json.dumps({
                "message": str(e),
                "stack_trace": traceback.format_exc(),
                "context": {},
                "timestamp": str(datetime.datetime.now()),
            }),
            "app_name": self.repo_name or "default-app",
        }
        self.send_log(log)

    def send_log(self, log):
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            curl_command = f"curl -X POST '{self.backend_url}/logs/' -H 'Authorization: Bearer {self.token}' -H 'Content-Type: application/json' -d '{json.dumps(log)}'"
            print(f"Executing equivalent curl command:\n{curl_command}")
            requests.post(f"{self.backend_url}/logs/", json=log, headers=headers)
        except Exception as e:
            print(f"Failed to send log to Daa backend: {e}")

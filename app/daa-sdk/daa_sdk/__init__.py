import os
import requests
import traceback
import datetime
import json

class DaaSdk:
    def __init__(self):
        self.backend_url = os.environ.get("DAA_BACKEND_API_URL")
        self.token = os.environ.get("DAA_TOKEN")
        self.repo_name = os.environ.get("REPO_NAME")

    def capture_exception(self, e):
        log = {
            "message": str(e),
            "stack_trace": traceback.format_exc(),
            "context": {},
            "timestamp": str(datetime.datetime.now()),
            "token": self.token,
            "repo_name": self.repo_name,
        }
        self.send_log(log)

    def send_log(self, log):
        try:
            requests.post(f"{self.backend_url}/logs", json=log)
        except Exception as e:
            print(f"Failed to send log to Daa backend: {e}")

import requests
import time

API_URL = "http://localhost:8000"


def test_log_ingestion():
    error_log = {
        "content": "Error: Something went wrong!",
    }

    response = requests.post(f"{API_URL}/logs", json=error_log)
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    time.sleep(1)  # Allow time for worker to pick up job

    response = requests.get(f"{API_URL}/status/{job_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "In Progress"

    time.sleep(6)  # Allow time for worker to complete job

    response = requests.get(f"{API_URL}/status/{job_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "Completed"
    assert "summary" in response.json()
    assert "fix_suggestion" in response.json()


test_log_ingestion()

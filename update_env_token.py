#!/usr/bin/env python3
import requests
import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent / ".env"

def main():
    payload = {"username": "testuser", "password": "testpassword"}
    # Try register first
    try:
        requests.post("http://localhost:8000/auth/register", json=payload, timeout=5)
    except Exception:
        pass

    # Login to get token
    res = requests.post("http://localhost:8000/auth/login", json=payload, timeout=5)
    res.raise_for_status()
    token = res.json()["token"]
    print(f"Obtained fresh DAA_TOKEN: {token}")

    # Read and update .env
    lines = []
    updated = False
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if line.startswith("DAA_TOKEN="):
                lines.append(f"DAA_TOKEN={token}")
                updated = True
            else:
                lines.append(line)
    
    if not updated:
        lines.append(f"DAA_TOKEN={token}")

    ENV_FILE.write_text("\n".join(lines) + "\n")
    print("Updated .env file successfully!")

if __name__ == "__main__":
    main()

import argparse
import json
import os
import secrets
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests


ROOT_DIR = Path(__file__).resolve().parents[2]
TEST_APP_DIR = ROOT_DIR / "app" / "test-app"
ENV_FILE = ROOT_DIR / ".env"
ENV_EXAMPLE_FILE = ROOT_DIR / ".env.example"

DEFAULT_ENV_VALUES = {
    "SECRET_KEY": "demo_secret_key",
    "POSTGRES_PASSWORD": "demo_postgres_password",
    "GITLAB_ROOT_PASSWORD": "StrongPassword123",
    "GITLAB_USER": "root",
    "GITLAB_HOST": "gitlab",
    "GIT_REPO_URL": "http://gitlab:80/root/test-app.git",
    "REPO_NAME": "test-app",
    "RABBITMQ_HOST": "rabbitmq",
}

PLACEHOLDER_PREFIXES = (
    "your_",
    "<your_",
)

PLACEHOLDER_VALUES = {
    "",
    "changeme",
    "None",
    "null",
}

TEST_APP_SCENARIOS = {
    "1": {
        "label": "attribute-error",
        "method": "GET",
        "path": "/attribute-error",
        "description": "Trigger an attribute error in the test app.",
    },
    "2": {
        "label": "import-error",
        "method": "GET",
        "path": "/import-error",
        "description": "Trigger an import error in the test app.",
    },
    "3": {
        "label": "index-error",
        "method": "GET",
        "path": "/index-error",
        "description": "Trigger an index error in the test app.",
    },
    "4": {
        "label": "name-error",
        "method": "GET",
        "path": "/name-error",
        "description": "Trigger a name error in the test app.",
    },
    "5": {
        "label": "key-error",
        "method": "GET",
        "path": "/key-error",
        "description": "Trigger a key error in the test app.",
    },
    "6": {
        "label": "type-error",
        "method": "GET",
        "path": "/type-error",
        "description": "Trigger a type error in the test app.",
    },
    "7": {
        "label": "value-error",
        "method": "GET",
        "path": "/value-error",
        "description": "Trigger a value error in the test app.",
    },
    "8": {
        "label": "new-error",
        "method": "POST",
        "path": "/new-error?param=10",
        "json": {"number": 0},
        "description": "Trigger the richer POST error flow and a divide-by-zero.",
    },
}


@dataclass
class Step:
    number: int
    title: str
    notes: list[str] = field(default_factory=list)


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def write_env_file(path: Path, values: dict[str, str]) -> None:
    output_lines = [f"{key}={value}" for key, value in sorted(values.items())]
    path.write_text("\n".join(output_lines).rstrip() + "\n")


def is_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    stripped = value.strip()
    if stripped in PLACEHOLDER_VALUES:
        return True
    return any(stripped.startswith(prefix) for prefix in PLACEHOLDER_PREFIXES)


def print_step(step: Step) -> None:
    print(f"\nStep {step.number}. {step.title}")
    print("-" * (len(step.title) + 8))
    for note in step.notes:
        print(f"- {note}")


def run_command(
    command: str,
    cwd: Path = ROOT_DIR,
    extra_env: dict[str, str] | None = None,
    check: bool = True,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    print(f"$ {command}")
    completed = subprocess.run(
        command,
        cwd=cwd,
        shell=True,
        env={**os.environ, **(extra_env or {})},
        text=True,
        capture_output=capture_output,
    )
    if completed.stdout and not capture_output:
        print(completed.stdout, end="")
    if completed.stderr and not capture_output:
        print(completed.stderr, end="")
    if check and completed.returncode != 0:
        if capture_output:
            if completed.stdout:
                print(completed.stdout, end="")
            if completed.stderr:
                print(completed.stderr, end="")
        raise RuntimeError(f"Command failed: {command}")
    return completed


def wait_for_http(url: str, timeout_seconds: int = 600) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=5)
            if response.ok:
                return
        except requests.RequestException:
            pass
        time.sleep(5)
    raise TimeoutError(f"Timed out waiting for {url}")


def load_demo_env_values() -> dict[str, str]:
    env_values = load_env_file(ENV_EXAMPLE_FILE) if ENV_EXAMPLE_FILE.exists() else {}
    env_values.update(load_env_file(ENV_FILE))

    for key, default_value in DEFAULT_ENV_VALUES.items():
        if is_placeholder(env_values.get(key)):
            env_values[key] = default_value

    if is_placeholder(env_values.get("GEMINI_API_KEY")):
        print("Warning: GEMINI_API_KEY is not configured in .env. The demo stack can start, but agent fixes will need a real key.")

    return env_values


def create_runtime_env_file(env_values: dict[str, str]) -> Path:
    runtime_file = Path(tempfile.gettempdir()) / "daa-demo-runtime.env"
    write_env_file(runtime_file, env_values)
    return runtime_file


def compose_command(runtime_env_file: Path, subcommand: str) -> str:
    return f"docker-compose --env-file {runtime_env_file} {subcommand}"


def docker_compose_up(env_values: dict[str, str], runtime_env_file: Path) -> None:
    run_command(compose_command(runtime_env_file, "up -d"), extra_env=env_values)
    wait_for_http("http://localhost:8082/users/sign_in", timeout_seconds=900)
    wait_for_http("http://localhost:8000/health", timeout_seconds=180)


def build_gitlab_api_url(path: str) -> str:
    return f"http://localhost:8082/api/v4{path}"


def ensure_gitlab_token(env_values: dict[str, str], runtime_env_file: Path) -> str:
    existing_token = env_values.get("GITLAB_PRIVATE_TOKEN")
    if not is_placeholder(existing_token):
        headers = {"PRIVATE-TOKEN": existing_token}
        user_response = requests.get(
            build_gitlab_api_url("/user"),
            headers=headers,
            timeout=10,
        )
        if user_response.ok:
            self_response = requests.get(
                build_gitlab_api_url("/personal_access_tokens/self"),
                headers=headers,
                timeout=10,
            )
            if self_response.ok:
                scopes = set(self_response.json().get("scopes", []))
                if "write_repository" in scopes:
                    return existing_token

    print("Creating a GitLab API token automatically through the GitLab container...")
    raw_token = secrets.token_hex(20)
    runner = (
        "require 'securerandom'; "
        "user = User.find_by_username('root'); "
        f"token = user.personal_access_tokens.create!(scopes: [:api, :read_repository, :write_repository], name: 'demo-cli-token-{int(time.time())}', expires_at: 365.days.from_now.to_date); "
        f"token.set_token('{raw_token}'); "
        "token.save!; "
        "puts token.token"
    )
    quoted_runner = runner.replace("'", "'\"'\"'")
    result = run_command(
        f"{compose_command(runtime_env_file, 'exec -T gitlab')} gitlab-rails runner '{quoted_runner}'",
        extra_env=env_values,
        capture_output=True,
    )
    token = result.stdout.strip().splitlines()[-1].strip()
    if not token:
        raise RuntimeError("Failed to create GitLab token automatically.")

    env_values["GITLAB_PRIVATE_TOKEN"] = token
    write_env_file(runtime_env_file, env_values)
    persisted_env_values = load_env_file(ENV_FILE) if ENV_FILE.exists() else {}
    persisted_env_values["GITLAB_PRIVATE_TOKEN"] = token
    write_env_file(ENV_FILE, persisted_env_values)
    return token


def ensure_gitlab_project(token: str) -> None:
    headers = {"PRIVATE-TOKEN": token}
    project_response = requests.get(
        build_gitlab_api_url("/projects/root%2Ftest-app"),
        headers=headers,
        timeout=15,
    )
    if project_response.ok:
        return

    create_response = requests.post(
        build_gitlab_api_url("/projects"),
        headers=headers,
        data={"name": "test-app", "visibility": "public"},
        timeout=15,
    )
    if create_response.status_code not in {201, 400}:
        raise RuntimeError(f"Failed to create GitLab project: {create_response.text}")


def get_gitlab_project(token: str) -> dict:
    response = requests.get(
        build_gitlab_api_url("/projects/root%2Ftest-app"),
        headers={"PRIVATE-TOKEN": token},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def ensure_test_app_remote(env_values: dict[str, str]) -> None:
    remote_url = f"http://root:{env_values['GITLAB_ROOT_PASSWORD']}@localhost:8082/root/test-app.git"
    run_command("git init", cwd=TEST_APP_DIR)

    remote_check = run_command(
        "git remote get-url origin",
        cwd=TEST_APP_DIR,
        check=False,
        capture_output=True,
    )
    current_remote = remote_check.stdout.strip()
    if current_remote != remote_url:
        if remote_check.returncode == 0:
            run_command("git remote remove origin", cwd=TEST_APP_DIR)
        run_command(f"git remote add origin {remote_url}", cwd=TEST_APP_DIR)


def ensure_test_app_commit(env_values: dict[str, str]) -> None:
    for pycache_dir in TEST_APP_DIR.rglob("__pycache__"):
        for compiled_file in pycache_dir.iterdir():
            if compiled_file.is_file():
                compiled_file.unlink()
        pycache_dir.rmdir()

    for compiled_file in TEST_APP_DIR.rglob("*.pyc"):
        compiled_file.unlink()

    run_command('git config user.email "demo@example.com"', cwd=TEST_APP_DIR)
    run_command('git config user.name "Demo CLI"', cwd=TEST_APP_DIR)
    run_command("git add .", cwd=TEST_APP_DIR)

    status = run_command(
        "git status --porcelain",
        cwd=TEST_APP_DIR,
        capture_output=True,
    ).stdout.strip()
    if status:
        run_command('git commit -m "Initial commit"', cwd=TEST_APP_DIR)
    else:
        print("No new git changes to commit in test-app.")

    for attempt in range(1, 6):
        push_result = run_command(
            "git push -u origin master",
            cwd=TEST_APP_DIR,
            extra_env=env_values,
            check=False,
            capture_output=True,
        )
        combined_output = "\n".join(
            part for part in [push_result.stdout.strip(), push_result.stderr.strip()] if part
        )
        if push_result.returncode == 0 or "Everything up-to-date" in combined_output:
            if combined_output:
                print(combined_output)
            return

        print(combined_output)
        if "GitLab is not responding" not in combined_output and "502" not in combined_output:
            raise RuntimeError("Failed to push test-app to GitLab.")

        print(f"GitLab is still warming up, retrying push ({attempt}/5)...")
        time.sleep(10)

    raise RuntimeError("Failed to push test-app to GitLab after retries.")


def restart_services(env_values: dict[str, str], runtime_env_file: Path) -> None:
    run_command(
        compose_command(runtime_env_file, "up -d --force-recreate backend-api python-agent test-app admin-panel"),
        extra_env=env_values,
    )
    wait_for_http("http://localhost:8000/health", timeout_seconds=180)


def cleanup_demo_stack(env_values: dict[str, str], runtime_env_file: Path) -> None:
    print("\nCleaning up demo stack...")
    run_command(
        compose_command(runtime_env_file, "down -v --remove-orphans"),
        extra_env=env_values,
        check=False,
    )


def ensure_backend_token(env_values: dict[str, str]) -> str:
    payload = {"username": "testuser", "password": "testpassword"}
    register_response = requests.post(
        "http://localhost:8000/auth/register",
        json=payload,
        timeout=10,
    )
    if register_response.status_code not in {200, 400}:
        raise RuntimeError(f"Failed to register backend user: {register_response.text}")

    login_response = requests.post(
        "http://localhost:8000/auth/login",
        json=payload,
        timeout=10,
    )
    login_response.raise_for_status()
    token = login_response.json()["token"]

    env_values["DAA_TOKEN"] = token
    return token


def refresh_test_app(env_values: dict[str, str], runtime_env_file: Path) -> None:
    run_command(
        compose_command(runtime_env_file, "up -d --force-recreate test-app"),
        extra_env=env_values,
    )


def send_dummy_log(token: str) -> dict[str, str]:
    response = requests.post(
        "http://localhost:8000/logs/",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        json={
            "content": json.dumps({"message": "test error"}),
            "app_name": "test-app",
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def build_curl_command(method: str, url: str, json_body: dict | None = None) -> str:
    command = f"curl -X {method} '{url}'"
    if json_body is not None:
        command += " -H 'Content-Type: application/json'"
        command += f" -d '{json.dumps(json_body)}'"
    return command


def fetch_latest_log() -> dict | None:
    response = requests.get(
        "http://localhost:8000/logs/?page=1&limit=100",
        timeout=10,
    )
    response.raise_for_status()
    logs = response.json()
    if not logs:
        return None
    return max(logs, key=lambda item: item["timestamp"])


def fetch_project_merge_requests(token: str) -> list[dict]:
    project = get_gitlab_project(token)
    response = requests.get(
        build_gitlab_api_url(f"/projects/{project['id']}/merge_requests"),
        headers={"PRIVATE-TOKEN": token},
        params={"state": "opened", "order_by": "updated_at", "sort": "desc"},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def choose_test_app_scenario() -> dict | None:
    print("\nInteractive Demo")
    print("----------------")
    for key, scenario in TEST_APP_SCENARIOS.items():
        print(f"{key}. {scenario['label']} - {scenario['description']}")
    print("q. quit")

    choice = input("Choose a test-app API to call: ").strip().lower()
    if choice in {"q", "quit", "exit"}:
        return None
    return TEST_APP_SCENARIOS.get(choice)


def trigger_test_app_scenario(scenario: dict) -> requests.Response:
    url = f"http://localhost:8081{scenario['path']}"
    curl_command = build_curl_command(scenario["method"], url, scenario.get("json"))
    print(f"\nCalling test-app with:\n{curl_command}")

    if scenario["method"] == "POST":
        response = requests.post(url, json=scenario.get("json"), timeout=15)
    else:
        response = requests.get(url, timeout=15)

    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.text}")
    return response


def monitor_pr_creation(gitlab_token: str, baseline_log_id: str | None) -> None:
    print("\nWatching backend logs and GitLab merge requests...")
    print("GitLab merge requests page: http://localhost:8082/root/test-app/-/merge_requests")
    existing_merge_requests = fetch_project_merge_requests(gitlab_token)
    existing_urls = {mr["web_url"] for mr in existing_merge_requests}
    seen_new_log = baseline_log_id is None

    deadline = time.time() + 180
    latest_log_id = baseline_log_id

    while time.time() < deadline:
        latest_log = fetch_latest_log()
        if latest_log:
            latest_log_id = latest_log["id"]
            if latest_log_id != baseline_log_id:
                seen_new_log = True
                print(f"Latest log id: {latest_log_id} | status: {latest_log['status']}")

        merge_requests = fetch_project_merge_requests(gitlab_token)
        for merge_request in merge_requests:
            if merge_request["web_url"] not in existing_urls and seen_new_log:
                print(f"\nMerge request created: {merge_request['web_url']}")
                print(f"Check it in GitLab: {merge_request['web_url']}")
                return

        time.sleep(5)

    if latest_log_id and latest_log_id != baseline_log_id:
        print(f"\nA new log was created ({latest_log_id}), but no merge request appeared within the wait window.")
    else:
        print("\nNo new log or merge request was detected within the wait window.")
    print("Check GitLab manually: http://localhost:8082/root/test-app/-/merge_requests")


def interactive_demo_loop(gitlab_token: str) -> None:
    while True:
        latest_log = fetch_latest_log()
        baseline_log_id = latest_log["id"] if latest_log else None
        scenario = choose_test_app_scenario()
        if scenario is None:
            print("Exiting interactive demo.")
            return

        trigger_test_app_scenario(scenario)
        monitor_pr_creation(gitlab_token, baseline_log_id)


def build_steps() -> list[Step]:
    return [
        Step(1, "Start the services", ["Bring up the docker-compose stack and wait for GitLab and backend-api."]),
        Step(2, "Create the test-app project in GitLab", ["Reuse the GitLab token from .env or create one automatically.", "Ensure the test-app project exists through the GitLab API."]),
        Step(3, "Push the test-app to the GitLab repository", ["Initialize git if needed.", "Make the origin remote idempotent.", "Commit and push only when there are local changes."]),
        Step(4, "Set the environment variables", ["Create a temporary runtime env file for the demo.", "Keep generated GitLab and backend tokens out of the project .env file."]),
        Step(5, "Restart the services", ["Restart the compose stack so services reload updated environment values."]),
        Step(6, "Create a new user and get a token", ["Register the demo backend user if needed.", "Log in and keep DAA_TOKEN in the demo runtime environment.", "Recreate test-app so it receives the fresh token."]),
        Step(7, "Send a dummy log to the backend-api", ["Post a demo log to verify the setup end to end."]),
    ]


def run_demo(start_step: int) -> None:
    env_values = load_demo_env_values()
    runtime_env_file = create_runtime_env_file(env_values)
    gitlab_token = env_values.get("GITLAB_PRIVATE_TOKEN", "")
    backend_token = env_values.get("DAA_TOKEN", "")

    try:
        for step in build_steps():
            if step.number < start_step:
                continue

            print_step(step)

            if step.number == 1:
                docker_compose_up(env_values, runtime_env_file)
            elif step.number == 2:
                gitlab_token = ensure_gitlab_token(env_values, runtime_env_file)
                write_env_file(runtime_env_file, env_values)
                ensure_gitlab_project(gitlab_token)
            elif step.number == 3:
                ensure_test_app_remote(env_values)
                ensure_test_app_commit(env_values)
            elif step.number == 4:
                write_env_file(runtime_env_file, env_values)
                print(f"Runtime demo env: {runtime_env_file}")
            elif step.number == 5:
                restart_services(env_values, runtime_env_file)
            elif step.number == 6:
                backend_token = ensure_backend_token(env_values)
                write_env_file(runtime_env_file, env_values)
                refresh_test_app(env_values, runtime_env_file)
                print(f"Stored backend token in runtime env: {runtime_env_file}")
            elif step.number == 7:
                response = send_dummy_log(backend_token)
                print(f"Dummy log submitted: {response}")

        interactive_demo_loop(gitlab_token)
    finally:
        cleanup_demo_stack(env_values, runtime_env_file)
        if runtime_env_file.exists():
            runtime_env_file.unlink()

    print("\nDemo setup flow complete.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automated demo CLI for the DAA setup flow.")
    parser.add_argument(
        "--start-step",
        type=int,
        default=1,
        help="Start running from a specific step number.",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Print the automated steps without running them.",
    )
    return parser.parse_args()


def ensure_prerequisites() -> None:
    print("DAA Demo CLI")
    print("This CLI automates the setup flow from SETUP.md.")

    if not ENV_EXAMPLE_FILE.exists():
        print(f"Warning: {ENV_EXAMPLE_FILE} was not found.")

    if not (ROOT_DIR / "docker-compose.yml").exists():
        raise FileNotFoundError("docker-compose.yml was not found in the repository root.")


def main() -> None:
    args = parse_args()
    ensure_prerequisites()

    if args.list_only:
        for step in build_steps():
            if step.number >= args.start_step:
                print_step(step)
        return

    run_demo(start_step=args.start_step)


if __name__ == "__main__":
    main()

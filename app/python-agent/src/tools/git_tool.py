import os
import git
import gitlab
import requests
from urllib.parse import urlparse, urlunparse
from langchain.tools import tool
from pydantic.v1 import BaseModel, Field


def get_project_connection(app_name: str) -> dict:
    """Fetches the project connection configuration from the backend API."""
    backend_url = os.environ.get("DAA_BACKEND_API_URL", "http://backend-api:80")
    try:
        response = requests.get(f"{backend_url}/projects/{app_name}", timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching project connection: {e}")
    return {}


def _parse_github_repo(repo_url: str) -> tuple[str, str]:
    """Parses owner and repository name from a GitHub URL."""
    path = urlparse(repo_url).path
    if path.endswith(".git"):
        path = path[:-4]
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    return "owner", "repo"


def _build_repo_url(app_name: str) -> str:
    """Builds the authenticated repository URL for PAT-based auth dynamically."""
    app_name = app_name.strip()
    proj = get_project_connection(app_name)
    if proj and proj.get("repo_url"):
        provider = proj.get("repo_provider", "gitlab")
        repo_url = proj.get("repo_url")
        token = proj.get("repo_token")
        
        parsed = urlparse(repo_url)
        netloc = parsed.netloc
        if provider == "gitlab":
            netloc = f"root:{token}@{netloc}"
        else:
            netloc = f"{token}@{netloc}"
        return urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
    
    # Fallback to local environment variables
    gitlab_user = os.getenv("GITLAB_USER", "root")
    gitlab_token = os.getenv("GITLAB_PRIVATE_TOKEN")
    gitlab_host = os.getenv("GITLAB_HOST", "gitlab")
    return f"http://{gitlab_user}:{gitlab_token}@{gitlab_host}:80/{gitlab_user}/{app_name}.git"


def _split_repo_input(value: str) -> tuple[str, str]:
    """Splits a `repo_path,<payload>` tool input without breaking on later commas."""
    repo_path, payload = value.split(",", 1)
    return repo_path.strip(), payload.strip()


def _get_repo(repo_path: str) -> git.Repo:
    """Gets the repository object.

    Args:
        repo_path: The path to the repository.

    Returns:
        The repository object.
    """
    return git.Repo(repo_path)


@tool
def clone_repo(app_name: str) -> str:
    """Clones the repository for the given app name.

    Args:
        app_name: The name of the app to clone.

    Returns:
        The path to the cloned repository.
    """
    app_name = app_name.strip()
    if ":" in app_name:
        app_name = app_name.split(":")[1].strip()
    repo_url = _build_repo_url(app_name)
    temp_dir = f"/tmp/{app_name}"
    if os.path.exists(temp_dir):
        repo = _get_repo(temp_dir)
        repo.remotes.origin.set_url(repo_url)
    else:
        repo = git.Repo.clone_from(repo_url, temp_dir)
    with repo.config_writer() as git_config:
        git_config.set_value("user", "email", "agent@example.com")
        git_config.set_value("user", "name", "Fix Agent")
    return temp_dir


class CreateBranchInput(BaseModel):
    repo_path_and_branch_name: str = Field(description="The path to the repository and the name of the branch to create, separated by a comma.")


@tool(args_schema=CreateBranchInput)
def create_branch(repo_path_and_branch_name: str) -> None:
    """Creates a new branch in the repository.

    Args:
        repo_path_and_branch_name: A string containing the repository path and the branch name, separated by a comma.
    """
    repo_path, branch_name = _split_repo_input(repo_path_and_branch_name)
    repo = _get_repo(repo_path)
    
    # Delete the branch if it exists locally
    if branch_name in repo.branches:
        repo.delete_head(branch_name, force=True)

    # Delete the branch on the remote if it exists
    if f"origin/{branch_name}" in repo.remotes.origin.refs:
        repo.git.push("origin", "--delete", branch_name)

    repo.git.checkout("-b", branch_name)


class CommitInput(BaseModel):
    repo_path_and_message: str = Field(description="The path to the repository and the commit message, separated by a comma.")


@tool(args_schema=CommitInput)
def commit(repo_path_and_message: str) -> None:
    """Commits the changes to the current branch.

    Args:
        repo_path_and_message: A string containing the repository path and the commit message, separated by a comma.
    """
    repo_path, message = _split_repo_input(repo_path_and_message)
    repo = _get_repo(repo_path)
    repo.git.add(A=True)
    repo.git.commit(m=message)


class PushInput(BaseModel):
    repo_path_and_branch_name: str = Field(description="The path to the repository and the name of the branch to push, separated by a comma.")


@tool(args_schema=PushInput)
def push(repo_path_and_branch_name: str) -> None:
    """Pushes the changes to the remote repository.

    Args:
        repo_path_and_branch_name: A string containing the repository path and the branch name, separated by a comma.
    """
    repo_path, branch_name = _split_repo_input(repo_path_and_branch_name)
    repo = _get_repo(repo_path)
    repo.git.push("--set-upstream", "origin", branch_name)


class CreatePullRequestInput(BaseModel):
    data: str = Field(description='A JSON string containing `repo_path`, `title`, and `description`.')


@tool(args_schema=CreatePullRequestInput)
def create_pull_request(data: str) -> str:
    """Creates a pull request (GitHub or GitLab).

    Args:
        data: A JSON string containing `repo_path`, `title`, and `description`.

    Returns:
        The URL of the pull request.
    """
    import json
    input_data = json.loads(data)
    repo_path = input_data.get("repo_path")
    title = input_data.get("title")
    description = input_data.get("description")

    if not all([repo_path, title, description]):
        return "Error: 'repo_path', 'title', and 'description' are required."

    repo = _get_repo(repo_path.strip())
    branch_name = repo.active_branch.name
    project_name = repo.working_dir.split('/')[-1]

    # Intercept for Human-in-the-Loop Mode
    if os.environ.get("DAA_HITL_MODE", "false").lower() == "true":
        return f"AWAITING_APPROVAL:{branch_name}"

    # Fetch configuration dynamically
    proj = get_project_connection(project_name)
    provider = proj.get("repo_provider", "gitlab")
    token = proj.get("repo_token") or os.getenv('GITLAB_PRIVATE_TOKEN')

    if provider == "github":
        owner, r_name = _parse_github_repo(proj.get("repo_url", ""))
        prs_url = f"https://api.github.com/repos/{owner}/{r_name}/pulls"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Check if a PR already exists
        try:
            check_res = requests.get(prs_url, headers=headers, params={"head": f"{owner}:{branch_name}"})
            if check_res.status_code == 200 and check_res.json():
                return check_res.json()[0]["html_url"]
        except Exception as e:
            print(f"Error checking existing PRs: {e}")

        # Create the PR
        pr_payload = {
            "title": title.strip(),
            "body": description.strip(),
            "head": branch_name,
            "base": "master"  # default base branch
        }
        try:
            res = requests.post(prs_url, headers=headers, json=pr_payload)
            if res.status_code == 201:
                return res.json().get("html_url")
            else:
                # Try fallback base branch 'main'
                pr_payload["base"] = "main"
                res_fallback = requests.post(prs_url, headers=headers, json=pr_payload)
                if res_fallback.status_code == 201:
                    return res_fallback.json().get("html_url")
                return f"Error creating GitHub PR: {res.text} (Fallback error: {res_fallback.text})"
        except Exception as e:
            return f"Exception while creating GitHub PR: {e}"

    else:
        # GitLab Integration
        gl_host = os.getenv('GITLAB_HOST', 'gitlab')
        gl = gitlab.Gitlab(f"http://{gl_host}", private_token=token)
        project = gl.projects.get(f"{os.getenv('GITLAB_USER','root')}/{project_name}")
        
        # Check if a merge request already exists
        mrs = project.mergerequests.list(source_branch=branch_name)
        if mrs:
            return mrs[0].web_url

        mr = project.mergerequests.create({
            'source_branch': branch_name,
            'target_branch': 'master',
            'title': title.strip(),
            'description': description.strip()
        })
        return mr.web_url


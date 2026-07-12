import os
from urllib.parse import urlparse, urlunparse

from .git_api_providers import build_project_connection

try:
    from langchain.tools import tool
except Exception:

    class _LocalToolWrapper:
        def __init__(self, func):
            self.func = func

        def run(self, *args, **kwargs):
            return self.func(*args, **kwargs)

        def __call__(self, *args, **kwargs):
            return self.func(*args, **kwargs)

    def tool(*dargs, **dkwargs):
        if dargs and callable(dargs[0]) and not dkwargs:
            return _LocalToolWrapper(dargs[0])

        def decorator(func):
            return _LocalToolWrapper(func)

        return decorator


try:
    from pydantic.v1 import BaseModel, Field
except Exception:

    class BaseModel:
        pass

    def Field(default=None, **kwargs):
        return default


try:
    import git as _git
except Exception:

    class _GitStub:
        Repo = None

    _git = _GitStub()

git = _git


def _infer_provider_from_repo_url(repo_url: str) -> str:
    """Infer a sensible provider from the repository URL host."""
    repo_url = (repo_url or "").strip().lower()
    if "github.com" in repo_url:
        return "github"
    return "gitea"


def _resolve_provider(provider: str, repo_url: str = "") -> str:
    """Normalize known aliases while preserving gitea as a distinct API shape."""
    provider = (provider or "").strip().lower()
    if provider in ("github", "gitea", "gitlab"):
        return provider
    return _infer_provider_from_repo_url(repo_url)


def get_project_connection(app_name: str) -> dict:
    return build_project_connection(app_name)


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
        return urlunparse(
            (
                parsed.scheme,
                netloc,
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment,
            )
        )

    # Fallback to local environment variables
    gitlab_user = os.getenv("GITLAB_USER", "root")
    gitlab_token = os.getenv("GITLAB_PRIVATE_TOKEN")
    gitlab_host = os.getenv("GITLAB_HOST", "gitlab")
    return f"http://{gitlab_user}:{gitlab_token}@{gitlab_host}:80/{gitlab_user}/{app_name}.git"


def _split_repo_input(value: str) -> tuple[str, str]:
    """Splits a `repo_path,<payload>` tool input without breaking on later commas."""
    repo_path, payload = value.split(",", 1)
    return repo_path.strip(), payload.strip()


def _get_repo(repo_path: str):
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

    if os.environ.get("DAA_GIT_MODE") == "api":
        return f"/tmp/{app_name}"

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
    repo_path_and_branch_name: str = Field(
        description="The path to the repository and the name of the branch to create, separated by a comma."
    )


@tool(args_schema=CreateBranchInput)
def create_branch(repo_path_and_branch_name: str) -> None:
    """Creates a new branch in the repository.

    Args:
        repo_path_and_branch_name: A string containing the repository path and the branch name, separated by a comma.
    """
    repo_path, branch_name = _split_repo_input(repo_path_and_branch_name)

    if os.environ.get("DAA_GIT_MODE") == "api":
        app_name = repo_path.split("/")[-1]
        from .clonefree_client import ACTIVE_BRANCHES, CloneFreeGitClient

        client = CloneFreeGitClient(app_name)
        client.create_branch(branch_name)
        ACTIVE_BRANCHES[app_name] = branch_name
        return

    repo = _get_repo(repo_path)

    # Delete the branch if it exists locally
    if branch_name in repo.branches:
        repo.delete_head(branch_name, force=True)

    # Delete the branch on the remote if it exists
    if f"origin/{branch_name}" in repo.remotes.origin.refs:
        repo.git.push("origin", "--delete", branch_name)

    repo.git.checkout("-b", branch_name)


class CommitInput(BaseModel):
    repo_path_and_message: str = Field(
        description="The path to the repository and the commit message, separated by a comma."
    )


@tool(args_schema=CommitInput)
def commit(repo_path_and_message: str) -> None:
    """Commits the changes to the current branch.

    Args:
        repo_path_and_message: A string containing the repository path and the commit message, separated by a comma.
    """
    if os.environ.get("DAA_GIT_MODE") == "api":
        # In API mode, write_file directly commits, so commit is a no-op
        return

    repo_path, message = _split_repo_input(repo_path_and_message)
    repo = _get_repo(repo_path)
    repo.git.add(A=True)
    repo.git.commit(m=message)


class PushInput(BaseModel):
    repo_path_and_branch_name: str = Field(
        description="The path to the repository and the name of the branch to push, separated by a comma."
    )


@tool(args_schema=PushInput)
def push(repo_path_and_branch_name: str) -> None:
    """Pushes the changes to the remote repository.

    Args:
        repo_path_and_branch_name: A string containing the repository path and the branch name, separated by a comma.
    """
    if os.environ.get("DAA_GIT_MODE") == "api":
        # In API mode, write_file directly commits and pushes, so push is a no-op
        return

    repo_path, branch_name = _split_repo_input(repo_path_and_branch_name)
    repo = _get_repo(repo_path)
    repo.git.push("--set-upstream", "--force", "origin", branch_name)


class CreatePullRequestInput(BaseModel):
    data: str = Field(
        description="A JSON string containing `repo_path`, `title`, and `description`."
    )


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

    project_name = repo_path.strip().split("/")[-1]
    client = None

    # Handle API Mode or Local Mode for determining branch name
    if os.environ.get("DAA_GIT_MODE") == "api":
        from .clonefree_client import ACTIVE_BRANCHES, CloneFreeGitClient

        client = CloneFreeGitClient(project_name)
        branch_name = (
            ACTIVE_BRANCHES.get(project_name) or client.default_branch or "fix-branch"
        )
    else:
        repo = _get_repo(repo_path.strip())
        branch_name = repo.active_branch.name

    # Intercept for Human-in-the-Loop Mode
    if os.environ.get("DAA_HITL_MODE", "false").lower() == "true":
        return f"AWAITING_APPROVAL:{branch_name}"

    from .clonefree_client import CloneFreeGitClient

    if client is None:
        client = CloneFreeGitClient(project_name)
    pr_url = client.create_pull_request(
        branch_name,
        title.strip(),
        description.strip(),
        base_branch=client.default_branch,
    )
    return pr_url or "Error: pull request creation failed."

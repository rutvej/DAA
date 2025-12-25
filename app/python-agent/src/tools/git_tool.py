import os
import git
from langchain.tools import tool

@tool
def clone_repo(app_name: str) -> str:
    """Clones the repository for the given app name."""
    repo_url = f"https://gitlab.com/{os.getenv('GITLAB_USER','root')}/{app_name}.git"
    temp_dir = f"/tmp/{app_name}"
    if os.path.exists(temp_dir):
        return temp_dir
    git.Repo.clone_from(repo_url, temp_dir)
    return temp_dir

@tool
def create_branch(repo_path: str, branch_name: str) -> None:
    """Creates a new branch in the repository."""
    repo = git.Repo(repo_path)
    repo.git.checkout("-b", branch_name)

@tool
def commit(repo_path: str, message: str) -> None:
    """Commits the changes to the current branch."""
    repo = git.Repo(repo_path)
    repo.git.add(A=True)
    repo.git.commit(m=message)

@tool
def push(repo_path: str, branch_name: str) -> None:
    """Pushes the changes to the remote repository."""
    repo = git.Repo(repo_path)
    repo.git.push("--set-upstream", "origin", branch_name)

@tool
def create_pull_request(repo_path: str, title: str, description: str) -> None:
    """Creates a pull request."""
    # This is a placeholder for the actual implementation.
    # The implementation will depend on the Git hosting service (e.g., GitLab, GitHub).
    print(f"Creating pull request with title: {title}")
    print(f"Description: {description}")

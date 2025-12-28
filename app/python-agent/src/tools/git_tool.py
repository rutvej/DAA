import os
import git
import gitlab
from langchain.tools import tool
from pydantic.v1 import BaseModel, Field

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
    if ":" in app_name:
        app_name = app_name.split(":")[1].strip()
    repo_url = f"http://oauth2:{os.getenv('GITLAB_PRIVATE_TOKEN')}@gitlab:80/{os.getenv('GITLAB_USER','root')}/{app_name}.git"
    temp_dir = f"/tmp/{app_name}"
    if os.path.exists(temp_dir):
        repo = _get_repo(temp_dir)
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
    repo_path, branch_name = repo_path_and_branch_name.split(',')
    repo = _get_repo(repo_path.strip())
    branch_name = branch_name.strip()
    
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
    repo_path, message = repo_path_and_message.split(',')
    repo = _get_repo(repo_path.strip())
    repo.git.add(A=True)
    repo.git.commit(m=message.strip())


class PushInput(BaseModel):
    repo_path_and_branch_name: str = Field(description="The path to the repository and the name of the branch to push, separated by a comma.")


@tool(args_schema=PushInput)
def push(repo_path_and_branch_name: str) -> None:
    """Pushes the changes to the remote repository.

    Args:
        repo_path_and_branch_name: A string containing the repository path and the branch name, separated by a comma.
    """
    repo_path, branch_name = repo_path_and_branch_name.split(',')
    repo = _get_repo(repo_path.strip())
    repo.git.push("--set-upstream", "origin", branch_name.strip())





class CreatePullRequestInput(BaseModel):
    data: str = Field(description='A JSON string containing `repo_path`, `title`, and `description`.')


@tool(args_schema=CreatePullRequestInput)
def create_pull_request(data: str) -> str:
    """Creates a pull request.

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
    gl = gitlab.Gitlab(f"http://{os.getenv('GITLAB_HOST','gitlab')}", private_token=os.getenv('GITLAB_PRIVATE_TOKEN'))
    project_name = repo.working_dir.split('/')[-1]
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

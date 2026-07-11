import logging
from typing import Optional

from .git_api_providers import build_project_connection, create_provider_client

logger = logging.getLogger(__name__)

# Shared state to keep track of active branches in API mode.
ACTIVE_BRANCHES: dict[str, str] = {}


def get_project_connection(app_name: str) -> dict:
    return build_project_connection(app_name)


class CloneFreeGitClient:
    """Thin facade over provider-specific API clients."""

    def __init__(self, app_name: str):
        self.app_name = app_name
        self.proj = get_project_connection(app_name)
        self._client = create_provider_client(app_name)
        self.provider = getattr(self._client, "provider", "unknown")
        self.repo_url = getattr(self._client, "repo_url", "")
        self.token = getattr(self._client, "token", "")
        self.api_base = getattr(self._client, "api_base", "")
        self.headers = getattr(self._client, "headers", {})
        self.default_branch = getattr(self._client, "default_branch", "main")
        ACTIVE_BRANCHES.setdefault(app_name, self.default_branch)

    def __getattr__(self, name: str):
        return getattr(self._client, name)

    def get_file_sha(self, file_path: str, ref: str) -> Optional[str]:
        getter = getattr(self._client, "get_file_sha", None)
        if callable(getter):
            return getter(file_path, ref)
        return None

    def get_file_content(self, file_path: str, ref: str = "main") -> Optional[str]:
        return self._client.get_file_content(file_path, ref=ref)

    def list_files(self, path: str, ref: str = "main") -> list[str]:
        return self._client.list_files(path, ref=ref)

    def list_all_files(self, ref: str = "main") -> list[str]:
        return self._client.list_all_files(ref=ref)

    def search_code(self, query: str, ref: str = "main") -> list[str]:
        return self._client.search_code(query, ref=ref)

    def get_branch_sha(self, branch_name: str) -> Optional[str]:
        return self._client.get_branch_sha(branch_name)

    def create_branch(self, new_branch: str, base_branch: Optional[str] = None) -> bool:
        return self._client.create_branch(new_branch, base_branch=base_branch)

    def create_branch_lock(self, new_branch: str, base_branch: Optional[str] = None) -> bool:
        return self._client.create_branch_lock(new_branch, base_branch=base_branch)

    def write_file_content(self, file_path: str, content: str, branch_name: str, commit_message: str) -> bool:
        return self._client.write_file_content(file_path, content, branch_name, commit_message)

    def create_pull_request(self, branch_name: str, title: str, description: str, base_branch: Optional[str] = None) -> str:
        return self._client.create_pull_request(branch_name, title, description, base_branch=base_branch)

import base64
import logging
import os
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote, urlparse

import requests
from tenacity import (retry, retry_if_exception_type, stop_after_attempt,
                      wait_exponential)

logger = logging.getLogger(__name__)


def _infer_provider_from_repo_url(repo_url: str) -> str:
    repo_url = (repo_url or "").strip().lower()
    if "github.com" in repo_url:
        return "github"
    if "bitbucket.org" in repo_url:
        return "bitbucket"
    if "gitlab" in repo_url:
        return "gitlab"
    return "gitea"


def _resolve_provider(provider: str, repo_url: str = "") -> str:
    provider = (provider or "").strip().lower()
    if provider in ("github", "gitea", "gitlab", "bitbucket"):
        return provider
    return _infer_provider_from_repo_url(repo_url)


def build_project_connection(app_name: str) -> dict:
    """Build the project connection configuration from environment only."""
    app_name = app_name.strip()
    if ":" in app_name:
        app_name = app_name.split(":", 1)[1].strip()

    env_safe_name = app_name.upper().replace("-", "_")
    env_repo_url = os.getenv(f"DAA_REPO_URL_{env_safe_name}")
    if env_repo_url:
        return {
            "app_name": app_name,
            "repo_url": env_repo_url,
            "repo_token": os.getenv(f"DAA_REPO_TOKEN_{env_safe_name}"),
            "repo_provider": _resolve_provider(
                os.getenv(
                    f"DAA_REPO_PROVIDER_{env_safe_name}",
                    os.getenv("DAA_REPO_PROVIDER", ""),
                ),
                env_repo_url,
            ),
            "jira_url": os.getenv(f"DAA_JIRA_URL_{env_safe_name}"),
            "jira_token": os.getenv(f"DAA_JIRA_TOKEN_{env_safe_name}"),
            "jira_project_key": os.getenv(f"DAA_JIRA_PROJECT_KEY_{env_safe_name}"),
        }

    generic_repo_url = os.getenv("DAA_REPO_URL")
    if generic_repo_url:
        return {
            "app_name": app_name,
            "repo_url": generic_repo_url,
            "repo_token": os.getenv("DAA_REPO_TOKEN"),
            "repo_provider": _resolve_provider(
                os.getenv("DAA_REPO_PROVIDER", ""), generic_repo_url
            ),
            "jira_url": os.getenv("DAA_JIRA_URL"),
            "jira_token": os.getenv("DAA_JIRA_TOKEN"),
            "jira_project_key": os.getenv("DAA_JIRA_PROJECT_KEY"),
        }

    git_host = os.getenv("GIT_HOST", "").strip()
    git_org = os.getenv("GIT_ORG", "").strip()
    if git_host and git_org:
        if not git_host.startswith(("http://", "https://")):
            git_host = f"https://{git_host}"
        git_host = git_host.rstrip("/")
        repo_url = f"{git_host}/{git_org}/{app_name}.git"
        return {
            "app_name": app_name,
            "repo_url": repo_url,
            "repo_token": os.getenv("DAA_GIT_TOKEN")
            or os.getenv("GITHUB_TOKEN")
            or os.getenv("GITLAB_PRIVATE_TOKEN"),
            "repo_provider": _resolve_provider(
                os.getenv("DAA_REPO_PROVIDER", ""), repo_url
            ),
            "jira_url": os.getenv("DAA_JIRA_URL"),
            "jira_token": os.getenv("DAA_JIRA_TOKEN"),
            "jira_project_key": os.getenv("DAA_JIRA_PROJECT_KEY"),
        }

    git_repo_url_template = os.getenv("GIT_REPO_URL", "").strip()
    if git_repo_url_template:
        parsed = urlparse(git_repo_url_template)
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(parts) >= 2 and parsed.scheme and parsed.netloc:
            repo_url = f"{parsed.scheme}://{parsed.netloc}/{parts[0]}/{app_name}.git"
            return {
                "app_name": app_name,
                "repo_url": repo_url,
                "repo_token": os.getenv("DAA_GIT_TOKEN")
                or os.getenv("GITHUB_TOKEN")
                or os.getenv("GITLAB_PRIVATE_TOKEN"),
                "repo_provider": _resolve_provider(
                    os.getenv("DAA_REPO_PROVIDER", ""), repo_url
                ),
                "jira_url": os.getenv("DAA_JIRA_URL"),
                "jira_token": os.getenv("DAA_JIRA_TOKEN"),
                "jira_project_key": os.getenv("DAA_JIRA_PROJECT_KEY"),
            }
    return {}


def _repo_parts(repo_url: str, provider: str) -> tuple[str, str]:
    parsed = urlparse(repo_url)
    path = parsed.path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    parts = [p for p in path.split("/") if p]
    if provider == "gitlab":
        if len(parts) >= 2:
            return "/".join(parts), parts[-1]
        return path, path.split("/")[-1] if path else "repo"
    if provider == "bitbucket":
        if len(parts) >= 2:
            return parts[-2], parts[-1]
        return "workspace", "repo"
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    return "owner", "repo"


@dataclass
class RepoInfo:
    provider: str
    repo_url: str
    token: str
    api_base: str
    owner: str = ""
    repo: str = ""
    project_path: str = ""
    workspace: str = ""
    repo_slug: str = ""
    headers: Optional[dict] = None


class BaseGitProvider:
    def __init__(self, info: RepoInfo):
        self.info = info
        self.default_branch = self.get_default_branch()

    @property
    def provider(self) -> str:
        return self.info.provider

    @property
    def repo_url(self) -> str:
        return self.info.repo_url

    @property
    def token(self) -> str:
        return self.info.token

    @property
    def api_base(self) -> str:
        return self.info.api_base

    @property
    def headers(self) -> dict:
        return self.info.headers or {}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        reraise=True,
    )
    def _request(self, method: str, path: str, **kwargs):
        url = (
            path
            if path.startswith("http")
            else f"{self.api_base.rstrip('/')}/{path.lstrip('/')}"
        )
        return requests.request(
            method, url, timeout=kwargs.pop("timeout", 10), **kwargs
        )

    def get_default_branch(self) -> str:
        return "main"

    def get_branch_sha(self, branch_name: str) -> Optional[str]:
        return None

    def _ref_candidates(self, ref: Optional[str] = None) -> list[str]:
        candidates = [
            ref or self.default_branch,
            self.default_branch,
            "main",
            "master",
            "develop",
            "trunk",
        ]
        seen: set[str] = set()
        ordered: list[str] = []
        for candidate in candidates:
            if candidate and candidate not in seen:
                ordered.append(candidate)
                seen.add(candidate)
        return ordered

    def get_file_sha(self, file_path: str, ref: str) -> Optional[str]:
        return None

    def get_file_content(self, file_path: str, ref: str = "main") -> Optional[str]:
        return None

    def list_files(self, path: str, ref: str = "main") -> list[str]:
        return []

    def list_all_files(self, ref: str = "main") -> list[str]:
        return []

    def search_code(self, query: str, ref: str = "main") -> list[str]:
        results: list[str] = []
        try:
            for file_path in self.list_all_files(ref):
                if query.lower() in file_path.lower():
                    results.append(
                        f"{file_path}:1: (File path matches search query '{query}')"
                    )
            if results:
                return results[:15]
            for file_path in self.list_all_files(ref)[:200]:
                content = self.get_file_content(file_path, ref=ref)
                if content and query.lower() in content.lower():
                    for idx, line in enumerate(content.splitlines(), start=1):
                        if query.lower() in line.lower():
                            results.append(f"{file_path}:{idx}: {line.strip()}")
                            break
                if len(results) >= 15:
                    break
        except Exception as e:
            logger.error("Error searching code via API: %s", e)
        return results

    def create_branch(self, new_branch: str, base_branch: Optional[str] = None) -> bool:
        return False

    def create_branch_lock(
        self, new_branch: str, base_branch: Optional[str] = None
    ) -> bool:
        return self.create_branch(new_branch, base_branch)

    def write_file_content(
        self, file_path: str, content: str, branch_name: str, commit_message: str
    ) -> bool:
        return False

    def create_pull_request(
        self,
        branch_name: str,
        title: str,
        description: str,
        base_branch: Optional[str] = None,
    ) -> str:
        return ""


class GitHubLikeProvider(BaseGitProvider):
    def __init__(self, info: RepoInfo):
        super().__init__(info)
        self.owner = info.owner
        self.repo = info.repo

    def get_default_branch(self) -> str:
        try:
            resp = self._request("GET", "", headers=self.headers)
            if resp.status_code == 200:
                data = resp.json()
                branch = data.get("default_branch")
                if branch:
                    return branch
        except Exception as e:
            logger.warning("Error discovering default branch: %s", e)
        for candidate in ("main", "master", "develop", "trunk"):
            if self.get_branch_sha(candidate):
                return candidate
        return "main"

    def get_file_content(self, file_path: str, ref: str = "main") -> Optional[str]:
        try:
            for branch_ref in self._ref_candidates(ref):
                resp = self._request(
                    "GET",
                    f"contents/{file_path}",
                    headers=self.headers,
                    params={"ref": branch_ref},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict) and "content" in data:
                        content_b64 = (
                            data.get("content", "").replace("\n", "").replace("\r", "")
                        )
                        return base64.b64decode(content_b64).decode("utf-8")
                    if isinstance(data, list):
                        return "\n".join(item.get("name", "") for item in data)
        except Exception as e:
            logger.error("Error fetching file via API: %s", e)
        return None

    def list_files(self, path: str, ref: str = "main") -> list[str]:
        try:
            for branch_ref in self._ref_candidates(ref):
                resp = self._request(
                    "GET",
                    f"contents/{path}".strip("/"),
                    headers=self.headers,
                    params={"ref": branch_ref},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        return [item.get("name") for item in data if item.get("name")]
                    if isinstance(data, dict) and data.get("type") == "dir":
                        return [
                            item.get("name")
                            for item in data.get("entries", [])
                            if item.get("name")
                        ]
                    return []
        except Exception as e:
            logger.error("Error listing files via API: %s", e)
        return []

    def list_all_files(self, ref: str = "main") -> list[str]:
        try:
            for branch_ref in self._ref_candidates(ref):
                sha = self.get_branch_sha(branch_ref)
                if not sha:
                    continue
                resp = self._request(
                    "GET",
                    f"git/trees/{sha}",
                    headers=self.headers,
                    params={"recursive": "1"},
                )
                if resp.status_code == 200:
                    tree = resp.json().get("tree", [])
                    return [
                        item.get("path")
                        for item in tree
                        if item.get("type") == "blob" and item.get("path")
                    ]
        except Exception as e:
            logger.error("Error getting recursive tree: %s", e)
        return []

    def get_branch_sha(self, branch_name: str) -> Optional[str]:
        # 1. GitHub-style: GET /git/ref/heads/{branch}  → single object
        try:
            resp = self._request(
                "GET", f"git/ref/heads/{branch_name}", headers=self.headers
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict):
                    sha = data.get("object", {}).get("sha")
                    if sha:
                        return sha
                # Some Gitea versions return a list even for this path
                if isinstance(data, list) and data:
                    sha = data[0].get("object", {}).get("sha")
                    if sha:
                        return sha
        except Exception:
            pass
        # 2. Gitea-style: GET /git/refs/heads/{branch}  → list of ref objects
        try:
            resp = self._request(
                "GET", f"git/refs/heads/{branch_name}", headers=self.headers
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and data:
                    sha = data[0].get("object", {}).get("sha")
                    if sha:
                        return sha
                if isinstance(data, dict):
                    sha = data.get("object", {}).get("sha")
                    if sha:
                        return sha
        except Exception:
            pass
        # 3. Fallback: branches API — works on both GitHub and Gitea
        try:
            resp = self._request("GET", f"branches/{branch_name}", headers=self.headers)
            if resp.status_code == 200:
                data = resp.json()
                commit = data.get("commit", {})
                return commit.get("sha") or commit.get("id")
        except Exception:
            pass
        return None

    def create_branch(self, new_branch: str, base_branch: Optional[str] = None) -> bool:
        base_branch = base_branch or self.default_branch

        if self.provider == "gitea":
            created, already_existed = self._create_branch_gitea(
                new_branch, base_branch
            )
            # Plain (non-locking) create: reusing an existing branch is fine.
            return created or already_existed
        base_sha = self.get_branch_sha(base_branch)
        if not base_sha and base_branch != "master":
            base_sha = self.get_branch_sha("master")
        if not base_sha and base_branch != "main":
            base_sha = self.get_branch_sha("main")
        if not base_sha:
            logger.error("Could not find base branch %s", base_branch)
            return False
        try:
            if self.get_branch_sha(new_branch):
                self._request(
                    "DELETE", f"git/refs/heads/{new_branch}", headers=self.headers
                )
            resp = self._request(
                "POST",
                "git/refs",
                headers=self.headers,
                json={"ref": f"refs/heads/{new_branch}", "sha": base_sha},
            )
            return resp.status_code == 201
        except Exception as e:
            logger.error("Error creating branch via API: %s", e)
        return False

    def create_branch_lock(
        self, new_branch: str, base_branch: Optional[str] = None
    ) -> bool:
        base_branch = base_branch or self.default_branch
        if self.provider == "gitea":
            created, _already_existed = self._create_branch_gitea(
                new_branch, base_branch
            )
            # Atomic-lock semantics: only a *fresh* creation counts as
            # acquiring the lock, mirroring GitHub's 409-on-existing-ref.
            return created

        return super().create_branch_lock(new_branch, base_branch)

    def _create_branch_gitea(
        self, new_branch: str, base_branch: str
    ) -> tuple[bool, bool]:
        """Create a branch via Gitea's dedicated branches endpoint.

        Gitea does NOT implement the GitHub-style `POST /git/refs` write
        path (only reads exist under `git/refs`/`git/ref`), so branch
        creation must go through `POST /repos/{owner}/{repo}/branches`.

        Returns (created, already_existed).
        """
        try:
            resp = self._request(
                "POST",
                "branches",
                headers={**self.headers, "Content-Type": "application/json"},
                json={
                    "new_branch_name": new_branch,
                    # Gitea has used both field names across versions; send both.
                    "old_branch_name": base_branch,
                    "old_ref_name": base_branch,
                },
            )
            if resp.status_code in (200, 201):
                return True, False
            if resp.status_code in (409, 422):
                logger.info("Gitea branch %s already exists", new_branch)
                return False, True
            logger.error(
                "Gitea branch creation failed (%s): %s",
                resp.status_code,
                resp.text[:300],
            )
        except Exception as e:
            logger.error("Error creating branch via Gitea API: %s", e)
        return False, False

    def write_file_content(
        self, file_path: str, content: str, branch_name: str, commit_message: str
    ) -> bool:
        try:
            file_sha = None
            try:
                resp = self._request(
                    "GET",
                    f"contents/{file_path}",
                    headers=self.headers,
                    params={"ref": branch_name},
                )
                if resp.status_code == 200 and isinstance(resp.json(), dict):
                    file_sha = resp.json().get("sha")
            except Exception:
                pass
            payload = {
                "message": commit_message,
                "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
                "branch": branch_name,
            }
            if file_sha:
                payload["sha"] = file_sha
            resp = self._request(
                "PUT", f"contents/{file_path}", headers=self.headers, json=payload
            )
            return resp.status_code in (200, 201)
        except Exception as e:
            logger.error("Error writing file via API: %s", e)
        return False

    def create_pull_request(
        self,
        branch_name: str,
        title: str,
        description: str,
        base_branch: Optional[str] = None,
    ) -> str:
        base_branch = base_branch or self.default_branch
        try:
            resp = self._request(
                "GET",
                "pulls",
                headers=self.headers,
                params={"state": "open", "head": branch_name},
            )
            if resp.status_code == 200:
                existing = resp.json()
                if existing:
                    return existing[0].get("html_url", "")
        except Exception as e:
            logger.warning("PR list check failed: %s", e)

        pr_payload = {
            "title": title,
            "body": description,
            "head": branch_name,
            "base": base_branch,
        }
        try:
            resp = self._request(
                "POST",
                "pulls",
                headers={**self.headers, "Content-Type": "application/json"},
                json=pr_payload,
            )
            if resp.status_code in (200, 201):
                return resp.json().get("html_url", "")
        except Exception as e:
            logger.error("PR creation failed: %s", e)
        return ""


class GitLabProvider(BaseGitProvider):
    def __init__(self, info: RepoInfo):
        super().__init__(info)
        self.project_path = info.project_path

    def get_default_branch(self) -> str:
        try:
            resp = self._request("GET", "", headers=self.headers)
            if resp.status_code == 200:
                data = resp.json()
                branch = data.get("default_branch")
                if branch:
                    return branch
        except Exception as e:
            logger.warning("Error discovering default branch: %s", e)
        for candidate in ("main", "master", "develop", "trunk"):
            if self.get_branch_sha(candidate):
                return candidate
        return "main"

    def get_file_content(self, file_path: str, ref: str = "main") -> Optional[str]:
        encoded_path = quote(file_path, safe="")
        try:
            for branch_ref in self._ref_candidates(ref):
                resp = self._request(
                    "GET",
                    f"repository/files/{encoded_path}/raw",
                    headers=self.headers,
                    params={"ref": branch_ref},
                )
                if resp.status_code == 200:
                    return resp.text
        except Exception as e:
            logger.error("Error fetching file via API: %s", e)
        return None

    def list_files(self, path: str, ref: str = "main") -> list[str]:
        try:
            for branch_ref in self._ref_candidates(ref):
                resp = self._request(
                    "GET",
                    "repository/tree",
                    headers=self.headers,
                    params={"ref": branch_ref, "path": path, "per_page": 100},
                )
                if resp.status_code == 200:
                    return [
                        item.get("name") for item in resp.json() if item.get("name")
                    ]
        except Exception as e:
            logger.error("Error listing files via API: %s", e)
        return []

    def list_all_files(self, ref: str = "main") -> list[str]:
        files: list[str] = []
        try:
            for branch_ref in self._ref_candidates(ref):
                resp = self._request(
                    "GET",
                    "repository/tree",
                    headers=self.headers,
                    params={"ref": branch_ref, "recursive": "true", "per_page": 100},
                )
                if resp.status_code == 200:
                    for item in resp.json():
                        if item.get("type") == "blob" and item.get("path"):
                            files.append(item.get("path"))
                    if files:
                        return files
        except Exception as e:
            logger.error("Error getting recursive tree: %s", e)
        return files

    def get_branch_sha(self, branch_name: str) -> Optional[str]:
        try:
            resp = self._request(
                "GET", f"repository/branches/{branch_name}", headers=self.headers
            )
            if resp.status_code == 200:
                return resp.json().get("commit", {}).get("id")
        except Exception:
            pass
        return None

    def create_branch(self, new_branch: str, base_branch: Optional[str] = None) -> bool:
        base_branch = base_branch or self.default_branch
        if not self.get_branch_sha(base_branch) and base_branch not in (
            "master",
            "main",
        ):
            logger.warning(
                "Base branch %s not confirmed via API; using branch name for GitLab create",
                base_branch,
            )
        ref_name = base_branch or self.default_branch or "main"
        if not ref_name:
            logger.error("Could not determine base branch for %s", new_branch)
            return False
        try:
            if self.get_branch_sha(new_branch):
                self._request(
                    "DELETE", f"repository/branches/{new_branch}", headers=self.headers
                )
            resp = self._request(
                "POST",
                "repository/branches",
                headers={**self.headers, "Content-Type": "application/json"},
                json={"branch": new_branch, "ref": ref_name},
            )
            return resp.status_code == 201
        except Exception as e:
            logger.error("Error creating branch via API: %s", e)
        return False

    def write_file_content(
        self, file_path: str, content: str, branch_name: str, commit_message: str
    ) -> bool:
        try:
            file_exists = self.get_file_content(file_path, branch_name) is not None
            action = "update" if file_exists else "create"
            resp = self._request(
                "POST",
                "repository/commits",
                headers={**self.headers, "Content-Type": "application/json"},
                json={
                    "branch": branch_name,
                    "commit_message": commit_message,
                    "actions": [
                        {
                            "action": action,
                            "file_path": file_path,
                            "content": content,
                        }
                    ],
                },
            )
            return resp.status_code == 201
        except Exception as e:
            logger.error("Error writing file via API: %s", e)
        return False

    def create_pull_request(
        self,
        branch_name: str,
        title: str,
        description: str,
        base_branch: Optional[str] = None,
    ) -> str:
        base_branch = base_branch or self.default_branch
        try:
            resp = self._request(
                "GET",
                "merge_requests",
                headers=self.headers,
                params={"source_branch": branch_name, "state": "opened"},
            )
            if resp.status_code == 200:
                existing = resp.json()
                if existing:
                    return existing[0].get("web_url", "")
        except Exception:
            pass
        try:
            resp = self._request(
                "POST",
                "merge_requests",
                headers={**self.headers, "Content-Type": "application/json"},
                json={
                    "source_branch": branch_name,
                    "target_branch": base_branch,
                    "title": title,
                    "description": description,
                },
            )
            if resp.status_code == 201:
                return resp.json().get("web_url", "")
        except Exception as e:
            logger.error("PR creation failed: %s", e)
        return ""


class BitbucketProvider(BaseGitProvider):
    def __init__(self, info: RepoInfo):
        super().__init__(info)
        self.workspace = info.workspace
        self.repo_slug = info.repo_slug

    def get_default_branch(self) -> str:
        try:
            resp = self._request("GET", "", headers=self.headers)
            if resp.status_code == 200:
                data = resp.json()
                branch = (data.get("mainbranch") or {}).get("name") or data.get(
                    "default_branch"
                )
                if branch:
                    return branch
        except Exception as e:
            logger.warning("Error discovering default branch: %s", e)
        for candidate in ("main", "master", "develop", "trunk"):
            if self.get_branch_sha(candidate):
                return candidate
        return "main"

    def get_branch_sha(self, branch_name: str) -> Optional[str]:
        try:
            resp = self._request(
                "GET", f"refs/branches/{branch_name}", headers=self.headers
            )
            if resp.status_code == 200:
                data = resp.json()
                return (data.get("target") or {}).get("hash") or (
                    data.get("target") or {}
                ).get("commit", {}).get("hash")
        except Exception:
            pass
        return None

    def list_files(self, path: str, ref: str = "main") -> list[str]:
        try:
            target = f"{ref}/{path}".rstrip("/")
            resp = self._request(
                "GET", f"src/{target}", headers=self.headers, params={"pagelen": 100}
            )
            if resp.status_code == 200:
                data = resp.json()
                values = data.get("values", []) if isinstance(data, dict) else data
                names = []
                for item in values:
                    item_path = item.get("path") or ""
                    if item_path:
                        names.append(os.path.basename(item_path))
                return names
            if ref == "main":
                return self.list_files(path, "master")
        except Exception as e:
            logger.error("Error listing files via API: %s", e)
        return []

    def get_file_content(self, file_path: str, ref: str = "main") -> Optional[str]:
        try:
            for branch_ref in self._ref_candidates(ref):
                resp = self._request(
                    "GET", f"src/{branch_ref}/{file_path}", headers=self.headers
                )
                if resp.status_code == 200:
                    if "application/json" in resp.headers.get("Content-Type", ""):
                        data = resp.json()
                        if isinstance(data, dict) and "values" in data:
                            return "\n".join(
                                item.get("path", "") for item in data.get("values", [])
                            )
                    return resp.text
        except Exception as e:
            logger.error("Error fetching file via API: %s", e)
        return None

    def list_all_files(self, ref: str = "main") -> list[str]:
        files: list[str] = []

        def walk(branch_ref: str, prefix: str = ""):
            target = f"{branch_ref}/{prefix}".rstrip("/")
            try:
                resp = self._request(
                    "GET",
                    f"src/{target}",
                    headers=self.headers,
                    params={"pagelen": 100},
                )
                if resp.status_code != 200:
                    return
                data = resp.json()
                values = data.get("values", []) if isinstance(data, dict) else data
                for item in values:
                    item_path = item.get("path") or ""
                    item_type = (item.get("type") or "").lower()
                    if not item_path:
                        continue
                    if "directory" in item_type:
                        walk(branch_ref, item_path)
                    else:
                        files.append(item_path)
            except Exception as e:
                logger.error("Error walking Bitbucket source tree: %s", e)

        for branch_ref in self._ref_candidates(ref):
            files.clear()
            walk(branch_ref, "")
            if files:
                break
        return files

    def search_code(self, query: str, ref: str = "main") -> list[str]:
        results: list[str] = []
        try:
            for file_path in self.list_all_files(ref)[:250]:
                if query.lower() in file_path.lower():
                    results.append(
                        f"{file_path}:1: (File path matches search query '{query}')"
                    )
                    continue
                content = self.get_file_content(file_path, ref=ref)
                if content and query.lower() in content.lower():
                    for idx, line in enumerate(content.splitlines(), start=1):
                        if query.lower() in line.lower():
                            results.append(f"{file_path}:{idx}: {line.strip()}")
                            break
                if len(results) >= 15:
                    break
        except Exception as e:
            logger.error("Error searching code via API: %s", e)
        return results

    def create_branch(self, new_branch: str, base_branch: Optional[str] = None) -> bool:
        base_branch = base_branch or self.default_branch
        base_sha = self.get_branch_sha(base_branch)
        if not base_sha and base_branch != "master":
            base_sha = self.get_branch_sha("master")
        if not base_sha and base_branch != "main":
            base_sha = self.get_branch_sha("main")
        if not base_sha:
            logger.error("Could not find base branch %s", base_branch)
            return False
        try:
            if self.get_branch_sha(new_branch):
                self._request(
                    "DELETE", f"refs/branches/{new_branch}", headers=self.headers
                )
            resp = self._request(
                "POST",
                "refs/branches",
                headers={**self.headers, "Content-Type": "application/json"},
                json={"name": new_branch, "target": {"hash": base_sha}},
            )
            return resp.status_code in (200, 201)
        except Exception as e:
            logger.error("Error creating branch via API: %s", e)
        return False

    def write_file_content(
        self, file_path: str, content: str, branch_name: str, commit_message: str
    ) -> bool:
        try:
            # Bitbucket source API accepts form data with file path fields and commit metadata.
            data = {
                f"/{file_path.lstrip('/')}": content,
                "branch": branch_name,
                "message": commit_message,
            }
            resp = self._request("POST", "src", headers=self.headers, data=data)
            return resp.status_code == 201
        except Exception as e:
            logger.error("Error writing file via API: %s", e)
        return False

    def create_pull_request(
        self,
        branch_name: str,
        title: str,
        description: str,
        base_branch: Optional[str] = None,
    ) -> str:
        base_branch = base_branch or self.default_branch
        try:
            resp = self._request(
                "GET",
                "pullrequests",
                headers=self.headers,
                params={"state": "OPEN", "source.branch.name": branch_name},
            )
            if resp.status_code == 200:
                data = resp.json()
                values = data.get("values", []) if isinstance(data, dict) else data
                if values:
                    return values[0].get("links", {}).get("html", {}).get("href", "")
        except Exception:
            pass
        try:
            payload = {
                "title": title,
                "description": description,
                "source": {"branch": {"name": branch_name}},
                "destination": {"branch": {"name": base_branch}},
            }
            resp = self._request(
                "POST",
                "pullrequests",
                headers={**self.headers, "Content-Type": "application/json"},
                json=payload,
            )
            if resp.status_code == 201:
                return resp.json().get("links", {}).get("html", {}).get("href", "")
        except Exception as e:
            logger.error("PR creation failed: %s", e)
        return ""


class NullProvider(BaseGitProvider):
    def __init__(self):
        super().__init__(
            RepoInfo(provider="unknown", repo_url="", token="", api_base="")
        )


def create_provider_client(app_name: str):
    proj = build_project_connection(app_name)
    provider = _resolve_provider(
        proj.get("repo_provider", ""), proj.get("repo_url", "")
    )
    repo_url = proj.get("repo_url", "")
    token = (
        proj.get("repo_token")
        or os.getenv("GITHUB_TOKEN")
        or os.getenv("GITLAB_PRIVATE_TOKEN")
        or os.getenv("DAA_GIT_TOKEN")
        or ""
    )

    if not repo_url:
        return NullProvider()

    parsed = urlparse(repo_url)
    headers: dict
    if provider in ("github", "gitea"):
        owner, repo = _repo_parts(repo_url, provider)
        if provider == "github":
            api_base = f"https://api.github.com/repos/{owner}/{repo}"
            headers = {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github+json",
            }
        else:
            base_host = (
                f"{parsed.scheme}://{parsed.netloc}"
                if parsed.scheme and parsed.netloc
                else "http://localhost:3000"
            )
            api_base = f"{base_host}/api/v1/repos/{owner}/{repo}"
            headers = {
                "Authorization": f"token {token}",
                "Accept": "application/json",
            }
        return GitHubLikeProvider(
            RepoInfo(
                provider=provider,
                repo_url=repo_url,
                token=token,
                api_base=api_base,
                owner=owner,
                repo=repo,
                headers=headers,
            )
        )

    if provider == "gitlab":
        project_path, repo = _repo_parts(repo_url, provider)
        gl_url = (
            f"{parsed.scheme}://{parsed.netloc}"
            if parsed.scheme and parsed.netloc
            else f"http://{os.getenv('GITLAB_HOST', 'gitlab')}"
        )
        api_base = f"{gl_url}/api/v4/projects/{quote(project_path, safe='')}"
        headers = {"PRIVATE-TOKEN": token}
        return GitLabProvider(
            RepoInfo(
                provider=provider,
                repo_url=repo_url,
                token=token,
                api_base=api_base,
                project_path=project_path,
                repo=repo,
                headers=headers,
            )
        )

    if provider == "bitbucket":
        workspace, repo_slug = _repo_parts(repo_url, provider)
        api_base = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        return BitbucketProvider(
            RepoInfo(
                provider=provider,
                repo_url=repo_url,
                token=token,
                api_base=api_base,
                workspace=workspace,
                repo_slug=repo_slug,
                headers=headers,
            )
        )

    # Default to GitHub-like behavior for unknown providers.
    owner, repo = _repo_parts(repo_url, "github")
    api_base = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }
    return GitHubLikeProvider(
        RepoInfo(
            provider="github",
            repo_url=repo_url,
            token=token,
            api_base=api_base,
            owner=owner,
            repo=repo,
            headers=headers,
        )
    )

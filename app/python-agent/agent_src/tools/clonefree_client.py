import base64
import logging
import os
import requests
import urllib.parse
from typing import Optional, List

logger = logging.getLogger(__name__)

# Shared state to keep track of active branches in API mode
ACTIVE_BRANCHES = {}

def get_project_connection(app_name: str) -> dict:
    """Fetches the project connection configuration from the backend API."""
    backend_url = os.environ.get("DAA_BACKEND_API_URL", "http://backend-api:80")
    app_name = app_name.strip()
    if ":" in app_name:
        app_name = app_name.split(":")[1].strip()
    try:
        response = requests.get(f"{backend_url}/projects/{app_name}", timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.error(f"Error fetching project connection: {e}")
        
    # Stateless env fallback
    env_safe_name = app_name.upper().replace("-", "_")
    env_repo_url = os.getenv(f"DAA_REPO_URL_{env_safe_name}")
    if env_repo_url:
        return {
            "app_name": app_name,
            "repo_url": env_repo_url,
            "repo_token": os.getenv(f"DAA_REPO_TOKEN_{env_safe_name}"),
            "repo_provider": os.getenv(f"DAA_REPO_PROVIDER_{env_safe_name}", "github"),
            "jira_url": os.getenv(f"DAA_JIRA_URL_{env_safe_name}"),
            "jira_token": os.getenv(f"DAA_JIRA_TOKEN_{env_safe_name}"),
            "jira_project_key": os.getenv(f"DAA_JIRA_PROJECT_KEY_{env_safe_name}")
        }
    return {}

def _parse_github_repo(repo_url: str) -> tuple[str, str]:
    """Parses owner and repository name from a GitHub/GitLab URL."""
    path = urllib.parse.urlparse(repo_url).path
    if path.endswith(".git"):
        path = path[:-4]
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    return "owner", "repo"

class CloneFreeGitClient:
    def __init__(self, app_name: str):
        self.app_name = app_name
        self.proj = get_project_connection(app_name)
        self.provider = self.proj.get("repo_provider", "gitlab")
        self.repo_url = self.proj.get("repo_url", "")
        self.token = self.proj.get("repo_token") or os.getenv("GITHUB_TOKEN") or os.getenv("GITLAB_PRIVATE_TOKEN")
        
        parsed = urllib.parse.urlparse(self.repo_url)
        self.api_base = ""
        if self.provider == "github":
            owner, repo = _parse_github_repo(self.repo_url)
            self.api_base = f"https://api.github.com/repos/{owner}/{repo}"
            self.headers = {
                "Authorization": f"token {self.token}",
                "Accept": "application/vnd.github.v3+json"
            }
        else:
            gl_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else f"http://{os.getenv('GITLAB_HOST', 'gitlab')}"
            owner, repo = _parse_github_repo(self.repo_url)
            project_path = urllib.parse.quote(f"{owner}/{repo}", safe="")
            self.api_base = f"{gl_url}/api/v4/projects/{project_path}"
            self.headers = {
                "PRIVATE-TOKEN": self.token
            }

    def get_file_content(self, file_path: str, ref: str = "main") -> Optional[str]:
        """Fetch file content directly via API."""
        try:
            if self.provider == "github":
                url = f"{self.api_base}/contents/{file_path}"
                resp = requests.get(url, headers=self.headers, params={"ref": ref}, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    content_b64 = data.get("content", "")
                    content_b64 = content_b64.replace("\n", "").replace("\r", "")
                    return base64.b64decode(content_b64).decode("utf-8")
                else:
                    if ref == "main":
                        return self.get_file_content(file_path, "master")
            else:
                encoded_path = urllib.parse.quote(file_path, safe="")
                url = f"{self.api_base}/repository/files/{encoded_path}/raw"
                resp = requests.get(url, headers=self.headers, params={"ref": ref}, timeout=10)
                if resp.status_code == 200:
                    return resp.text
                else:
                    if ref == "main":
                        return self.get_file_content(file_path, "master")
        except Exception as e:
            logger.error(f"Error fetching file via API: {e}")
        return None

    def list_files(self, path: str, ref: str = "main") -> List[str]:
        """Lists files in a directory via API."""
        files = []
        try:
            if self.provider == "github":
                url = f"{self.api_base}/contents/{path}"
                resp = requests.get(url, headers=self.headers, params={"ref": ref}, timeout=10)
                if resp.status_code == 200:
                    for item in resp.json():
                        files.append(item.get("name"))
                elif ref == "main":
                    return self.list_files(path, "master")
            else:
                url = f"{self.api_base}/repository/tree"
                params = {"ref": ref, "path": path}
                resp = requests.get(url, headers=self.headers, params=params, timeout=10)
                if resp.status_code == 200:
                    for item in resp.json():
                        files.append(item.get("name"))
                elif ref == "main":
                    return self.list_files(path, "master")
        except Exception as e:
            logger.error(f"Error listing files via API: {e}")
        return files

    def list_all_files(self, ref: str = "main") -> List[str]:
        """Gets all file paths recursively via API."""
        files = []
        try:
            if self.provider == "github":
                sha = self.get_branch_sha(ref)
                if not sha and ref == "main":
                    sha = self.get_branch_sha("master")
                if sha:
                    url = f"{self.api_base}/git/trees/{sha}?recursive=1"
                    resp = requests.get(url, headers=self.headers, timeout=10)
                    if resp.status_code == 200:
                        for item in resp.json().get("tree", []):
                            if item.get("type") == "blob":
                                files.append(item.get("path"))
            else:
                url = f"{self.api_base}/repository/tree"
                params = {"ref": ref, "recursive": "true", "per_page": 100}
                resp = requests.get(url, headers=self.headers, params=params, timeout=10)
                if resp.status_code == 200:
                    for item in resp.json():
                        if item.get("type") == "blob":
                            files.append(item.get("path"))
        except Exception as e:
            logger.error(f"Error getting recursive tree: {e}")
        return files

    def search_code(self, query: str, ref: str = "main") -> List[str]:
        """Search code containing query using search APIs or falling back."""
        results = []
        try:
            if self.provider == "github":
                owner, repo = _parse_github_repo(self.repo_url)
                url = "https://api.github.com/search/code"
                q = f"{query} repo:{owner}/{repo}"
                resp = requests.get(url, headers=self.headers, params={"q": q}, timeout=10)
                if resp.status_code == 200:
                    items = resp.json().get("items", [])
                    for item in items[:15]:
                        path = item.get("path")
                        results.append(f"{path}:1: (Matched query '{query}')")
            else:
                url = f"{self.api_base}/search"
                params = {"scope": "blobs", "search": query}
                resp = requests.get(url, headers=self.headers, params=params, timeout=10)
                if resp.status_code == 200:
                    for item in resp.json()[:15]:
                        path = item.get("filename")
                        results.append(f"{path}:1: (Matched query '{query}')")
        except Exception as e:
            logger.error(f"Error searching code via API: {e}")
            
        # Fallback if search API is empty/failed: list all files and filter by name
        if not results:
            try:
                all_files = self.list_all_files(ref)
                for file_path in all_files:
                    if query.lower() in file_path.lower():
                        results.append(f"{file_path}:1: (File path matches search query '{query}')")
            except Exception:
                pass
        return results

    def get_file_sha(self, file_path: str, ref: str) -> Optional[str]:
        """Get file SHA."""
        if self.provider != "github":
            return None
        try:
            url = f"{self.api_base}/contents/{file_path}"
            resp = requests.get(url, headers=self.headers, params={"ref": ref}, timeout=10)
            if resp.status_code == 200:
                return resp.json().get("sha")
        except Exception:
            pass
        return None

    def get_branch_sha(self, branch_name: str) -> Optional[str]:
        """Gets reference SHA of a branch."""
        try:
            if self.provider == "github":
                url = f"{self.api_base}/git/ref/heads/{branch_name}"
                resp = requests.get(url, headers=self.headers, timeout=10)
                if resp.status_code == 200:
                    return resp.json().get("object", {}).get("sha")
            else:
                url = f"{self.api_base}/repository/branches/{branch_name}"
                resp = requests.get(url, headers=self.headers, timeout=10)
                if resp.status_code == 200:
                    return resp.json().get("commit", {}).get("id")
        except Exception:
            pass
        return None

    def create_branch(self, new_branch: str, base_branch: str = "main") -> bool:
        """Creates a new branch from base_branch."""
        base_sha = self.get_branch_sha(base_branch)
        if not base_sha and base_branch == "main":
            base_sha = self.get_branch_sha("master")
            
        if not base_sha:
            logger.error(f"Could not find base branch {base_branch}")
            return False
            
        try:
            if self.provider == "github":
                if self.get_branch_sha(new_branch):
                    requests.delete(f"{self.api_base}/git/refs/heads/{new_branch}", headers=self.headers, timeout=10)
                
                url = f"{self.api_base}/git/refs"
                payload = {
                    "ref": f"refs/heads/{new_branch}",
                    "sha": base_sha
                }
                resp = requests.post(url, headers=self.headers, json=payload, timeout=10)
                return resp.status_code == 201
            else:
                if self.get_branch_sha(new_branch):
                    requests.delete(f"{self.api_base}/repository/branches/{new_branch}", headers=self.headers, timeout=10)
                
                url = f"{self.api_base}/repository/branches"
                payload = {
                    "branch": new_branch,
                    "ref": base_sha
                }
                resp = requests.post(url, headers=self.headers, json=payload, timeout=10)
                return resp.status_code == 201
        except Exception as e:
            logger.error(f"Error creating branch via API: {e}")
        return False

    def write_file_content(self, file_path: str, content: str, branch_name: str, commit_message: str) -> bool:
        """Writes/commits file content directly to a branch."""
        try:
            if self.provider == "github":
                file_sha = self.get_file_sha(file_path, branch_name)
                url = f"{self.api_base}/contents/{file_path}"
                payload = {
                    "message": commit_message,
                    "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
                    "branch": branch_name
                }
                if file_sha:
                    payload["sha"] = file_sha
                resp = requests.put(url, headers=self.headers, json=payload, timeout=10)
                return resp.status_code in (200, 201)
            else:
                url = f"{self.api_base}/repository/commits"
                file_exists = self.get_file_content(file_path, branch_name) is not None
                action = "update" if file_exists else "create"
                
                payload = {
                    "branch": branch_name,
                    "commit_message": commit_message,
                    "actions": [{
                        "action": action,
                        "file_path": file_path,
                        "content": content
                    }]
                }
                resp = requests.post(url, headers=self.headers, json=payload, timeout=10)
                return resp.status_code == 201
        except Exception as e:
            logger.error(f"Error writing file via API: {e}")
        return False

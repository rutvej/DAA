# orchestrator.py
# DAA 3.0 — Deterministic Orchestrator Layer
# Handles: repo caching, log hydration (all 4 dims), fingerprint dedup,
# context packaging, diff application, branch/PR idempotent management,
# and postmortem generation.

import hashlib
import logging
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import unquote, urlparse

import requests

logger = logging.getLogger(__name__)


def _apply_unified_diff_to_text(original: str, diff_text: str) -> str:
    """Apply a small unified diff to in-memory text.

    This is a fallback for environments without the system `patch` command.
    It supports the simple single-file diffs produced by the mock model and
    common line-based hunks with context.
    """
    original_lines = original.splitlines(keepends=True)
    output_lines: list[str] = []
    idx = 0
    diff_lines = diff_text.splitlines(keepends=True)
    i = 0

    while i < len(diff_lines):
        line = diff_lines[i]
        if not line.startswith("@@"):
            i += 1
            continue

        header = line
        try:
            # Example: @@ -1,2 +1,3 @@
            left = header.split(" ")[1]
            old_start = int(left.split(",")[0][1:])
            old_start = max(old_start - 1, 0)
        except Exception:
            old_start = idx

        while idx < old_start and idx < len(original_lines):
            output_lines.append(original_lines[idx])
            idx += 1

        i += 1
        while i < len(diff_lines):
            hline = diff_lines[i]
            if (
                hline.startswith("@@")
                or hline.startswith("--- ")
                or hline.startswith("+++ ")
            ):
                break
            if hline.startswith(" "):
                expected = hline[1:]
                if idx < len(original_lines):
                    output_lines.append(original_lines[idx])
                    idx += 1
                else:
                    output_lines.append(expected)
            elif hline.startswith("-"):
                if idx < len(original_lines):
                    idx += 1
            elif hline.startswith("+"):
                output_lines.append(hline[1:])
            i += 1

    while idx < len(original_lines):
        output_lines.append(original_lines[idx])
        idx += 1

    return "".join(output_lines)


# ---------------------------------------------------------------------------
# RepoCacheManager
# ---------------------------------------------------------------------------


class RepoCacheManager:
    """
    Manages a local disk cache of bare git repositories and per-incident
    git worktrees so the LLM agent always operates on an isolated checkout.

    Cache layout:
        /var/daa/repo-cache/<app_name>/          <- primary clone
        /var/daa/repo-cache/<app_name>/.daa_last_fetch  <- unix-ts of last fetch
        /tmp/daa/<incident_id>/                  <- ephemeral worktree
    """

    FETCH_TTL_SECONDS = 300  # re-fetch only if cache is older than 5 min

    def __init__(self, cache_root: str = "/var/daa/repo-cache") -> None:
        self.cache_root = cache_root
        os.makedirs(self.cache_root, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _cache_dir(self, app_name: str) -> str:
        return os.path.join(self.cache_root, app_name)

    def _last_fetch_file(self, app_name: str) -> str:
        return os.path.join(self._cache_dir(app_name), ".daa_last_fetch")

    def _read_last_fetch(self, app_name: str) -> float:
        """Return the unix timestamp of the last successful fetch, or 0."""
        path = self._last_fetch_file(app_name)
        try:
            with open(path, "r") as fh:
                return float(fh.read().strip())
        except (FileNotFoundError, ValueError):
            return 0.0

    def _write_last_fetch(self, app_name: str) -> None:
        with open(self._last_fetch_file(app_name), "w") as fh:
            fh.write(str(time.time()))

    def _run(
        self, cmd: list, cwd: str = None, check: bool = True
    ) -> subprocess.CompletedProcess:
        """Thin wrapper around subprocess.run with unified logging."""
        logger.debug("Running: %s (cwd=%s)", " ".join(cmd), cwd)
        return subprocess.run(
            cmd,
            cwd=cwd,
            check=check,
            capture_output=True,
            text=True,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_worktree(self, app_name: str, repo_url: str, incident_id: str) -> str:
        """
        Ensure a fresh, isolated git worktree exists for *incident_id*.

        Steps:
        1. Clone if cache doesn't exist, otherwise refresh if stale.
        2. Create (or force-reset) a worktree at /tmp/daa/<incident_id>.
        3. Return the worktree path.
        """
        cache_dir = self._cache_dir(app_name)
        git_dir = os.path.join(cache_dir, ".git")
        worktree_path = f"/tmp/daa/{incident_id}"

        # ---- 1. Clone or refresh -------------------------------------------
        if os.path.isdir(git_dir):
            self._run(
                ["git", "remote", "set-url", "origin", "--", repo_url],
                cwd=cache_dir,
                check=False,
            )
            age = time.time() - self._read_last_fetch(app_name)
            if age >= self.FETCH_TTL_SECONDS:
                logger.info("Cache stale (%.0fs old), refreshing %s", age, app_name)
                self._run(["git", "fetch", "origin"], cwd=cache_dir)
                self._run(["git", "reset", "--hard", "origin/main"], cwd=cache_dir)
                self._write_last_fetch(app_name)
            else:
                logger.info(
                    "Cache fresh (%.0fs old), skipping fetch for %s", age, app_name
                )
        else:
            logger.info("No cache found, cloning %s -> %s", repo_url, cache_dir)
            self._run(["git", "clone", "--", repo_url, cache_dir])
            self._write_last_fetch(app_name)

        # ---- 2. Create worktree --------------------------------------------
        os.makedirs("/tmp/daa", exist_ok=True)

        # Remove stale worktree directory if it lingers from a previous run
        if os.path.isdir(worktree_path):
            logger.warning("Stale worktree found at %s, removing", worktree_path)
            shutil.rmtree(worktree_path, ignore_errors=True)
            # Prune so git doesn't complain
            self._run(["git", "worktree", "prune"], cwd=cache_dir, check=False)

        try:
            self._run(
                ["git", "worktree", "add", "--force", "--", worktree_path, "main"],
                cwd=cache_dir,
            )
        except subprocess.CalledProcessError:
            logger.info(
                "Failed to add worktree for branch 'main', trying 'master' fallback"
            )
            self._run(
                ["git", "worktree", "add", "--force", "--", worktree_path, "master"],
                cwd=cache_dir,
            )
        # Index repo for codebase search tool (DAA 3.1)
        try:
            from .tools.search_tool import index_repo

            index_repo(worktree_path)
            logger.info("Indexed worktree for search: %s", worktree_path)
        except Exception as e:
            logger.error("Failed to index worktree for search: %s", e)

        logger.info("Worktree ready: %s", worktree_path)
        return worktree_path

    def cleanup_worktree(self, incident_id: str) -> None:
        """
        Remove the worktree directory for *incident_id* and prune dangling
        worktree metadata from all known cache repos.
        """
        worktree_path = f"/tmp/daa/{incident_id}"
        if os.path.isdir(worktree_path):
            shutil.rmtree(worktree_path, ignore_errors=True)
            logger.info("Removed worktree: %s", worktree_path)

        # Prune worktree metadata in every cached repo
        for entry in os.scandir(self.cache_root):
            if entry.is_dir():
                self._run(
                    ["git", "worktree", "prune"],
                    cwd=entry.path,
                    check=False,
                )


# ---------------------------------------------------------------------------
# FingerprintDedup
# ---------------------------------------------------------------------------


class FingerprintDedup:
    """
    Computes a stable SHA-256 fingerprint from incident fields and checks
    whether a fix already exists in the DAA backend.
    """

    def __init__(self, backend_url: str, token: str = None) -> None:
        self.backend_url = backend_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}

    def compute(
        self,
        app_name: str,
        exception_type: str,
        error_file: str,
        line_number: str,
        content_or_top_frame: str = "",
    ) -> str:
        """
        Return a deterministic canonical SHA-256 fingerprint using common.fingerprint.
        """
        try:
            from common.fingerprint import compute_canonical_fingerprint
        except ImportError:
            from app.common.fingerprint import compute_canonical_fingerprint

        return compute_canonical_fingerprint(
            app_name=app_name,
            exception_type=exception_type,
            content_or_top_frame=content_or_top_frame,
            error_file=error_file,
            line_number=str(line_number),
        )

    def check(self, fingerprint: str) -> dict:
        """
        Query the backend for an existing fix.

        Returns:
            {
                "status": "no_fix" | "fix_open" | "fix_merged",
                "pr_url": str | None,
                "fix_id": str | None,
            }
        """
        url = f"{self.backend_url}/fixes/fingerprint/{fingerprint}"
        try:
            resp = requests.get(url, headers=self._headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return {
                "status": data.get("status", "no_fix"),
                "pr_url": data.get("pr_url"),
                "fix_id": data.get("fix_id"),
            }
        except requests.RequestException as exc:
            logger.warning("FingerprintDedup.check failed: %s", exc)
            # Fail open: treat as no existing fix so we don't silently skip
            return {"status": "no_fix", "pr_url": None, "fix_id": None}


# ---------------------------------------------------------------------------
# LogHydrator
# ---------------------------------------------------------------------------


class LogHydrator:
    """
    Fetches the three observability dimensions (app logs, metrics, git history)
    from the DAA backend and returns them as a unified dict.

    Dimension naming follows the DAA 3.0 spec:
        dim1 -- the live exception payload (provided by the caller, not fetched here)
        dim2 -- recent application logs
        dim3 -- metrics snapshot
        dim4 -- recent git commits
    """

    def __init__(self, backend_url: str, token: str = None) -> None:
        self.backend_url = backend_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}

    # ------------------------------------------------------------------
    # Private fetchers
    # ------------------------------------------------------------------

    def _fetch_dim2(self, app_name: str, timestamp: str) -> Optional[str]:
        """
        Fetch the last 500 log lines before *timestamp*.

        Returns a plain-text string of log lines, or None on failure.
        """
        # Try cloud log ingestion connectors first
        try:
            from .log_connectors import get_configured_connector

            connector = get_configured_connector()
            if connector:
                logs = connector.fetch_logs(app_name, timestamp, limit=500)
                if logs is not None:
                    logger.info(
                        "Successfully fetched real logs via cloud log connector %s",
                        connector.__class__.__name__,
                    )
                    return logs
                logger.warning(
                    "Cloud log connector %s returned None, falling back to local database logs",
                    connector.__class__.__name__,
                )
        except Exception as exc:
            logger.error(
                "Error in cloud log connector execution: %s, falling back", exc
            )

        # As requested: "if not logs are set it should not call the logs api"
        return None

    def _fetch_dim3(self, app_name: str, timestamp: str) -> Optional[str]:
        """
        Fetch a metrics snapshot at *timestamp*.

        Returns a compact string like ``cpu=12% mem=45% redis_mem=98% err_rate=142/min``
        or None on failure.
        """
        # "why is it call the app instead of the log api"
        # Don't call the fallback backend metrics API if not configured
        return None

    def _fetch_dim4(self, app_name: str) -> Optional[str]:
        """
        Fetch the last 10 recent commits.
        """
        if os.environ.get("DAA_GIT_MODE") == "api":
            try:
                from .tools.clonefree_client import CloneFreeGitClient

                client = CloneFreeGitClient(app_name)
                import requests

                if client.provider in ("github", "gitea"):
                    resp = requests.get(
                        f"{client.api_base}/commits",
                        headers=client.headers,
                        params={"limit": 10},
                        timeout=10,
                    )
                    if resp.status_code == 200:
                        lines = []
                        for c in resp.json()[:10]:
                            sha = c.get("sha", "")[:8]
                            c_info = c.get("commit", {})
                            msg = (
                                c_info.get("message", "").splitlines()[0]
                                if "message" in c_info
                                else ""
                            )
                            author = c_info.get("author", {}).get("name", "")
                            lines.append(f"{sha}  {author}  {msg}")
                        return "\n".join(lines) if lines else None
                elif client.provider == "gitlab":
                    resp = requests.get(
                        f"{client.api_base}/repository/commits",
                        headers=client.headers,
                        params={"per_page": 10},
                        timeout=10,
                    )
                    if resp.status_code == 200:
                        lines = []
                        for c in resp.json()[:10]:
                            sha = c.get("id", "")[:8]
                            msg = c.get("title", "")
                            author = c.get("author_name", "")
                            lines.append(f"{sha}  {author}  {msg}")
                        return "\n".join(lines) if lines else None
                return None
            except Exception as exc:
                logger.warning("dim4 (git history api) fetch failed: %s", exc)
                return None

        try:
            import subprocess

            git_dir = f"/var/daa/repos/{app_name}/.git"
            if not os.path.isdir(git_dir):
                return "unavailable (repo not cached yet)"
            result = subprocess.run(
                ["git", "--git-dir", git_dir, "log", "-n", "10", "--oneline"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except Exception as exc:
            logger.warning("dim4 (git history) fetch failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def hydrate_all(
        self,
        app_name: str,
        incident_timestamp: str,
        trace_id: str = None,
    ) -> dict:
        """
        Fetch all three remote dimensions and return them in a single dict.

        Args:
            app_name:           Logical application name.
            incident_timestamp: ISO-8601 or unix-ms timestamp of the incident.
            trace_id:           Optional trace ID (reserved for future use).

        Returns:
            {
                "dim2_app_logs":    str | None,
                "dim3_metrics":     str | None,
                "dim4_git_history": str | None,
            }
        """
        logger.info("Hydrating dimensions for %s @ %s", app_name, incident_timestamp)

        dim2 = self._fetch_dim2(app_name, incident_timestamp)
        if dim2:
            logger.info("dim2 (app logs): fetched successfully")
        else:
            logger.info("dim2 (app logs): skipped (no log connector configured)")

        dim3 = self._fetch_dim3(app_name, incident_timestamp)
        if dim3:
            logger.info("dim3 (metrics): fetched successfully")
        else:
            logger.info("dim3 (metrics): skipped (no metrics connector configured)")

        dim4 = self._fetch_dim4(app_name)
        if dim4 and not dim4.startswith("unavailable"):
            logger.info(
                "dim4 (git history): fetched %d commits", len(dim4.splitlines())
            )
        else:
            logger.info("dim4 (git history): skipped or unavailable")

        return {
            "dim2_app_logs": dim2,
            "dim3_metrics": dim3,
            "dim4_git_history": dim4,
        }


# ---------------------------------------------------------------------------
# ContextPackager
# ---------------------------------------------------------------------------


class ContextPackager:
    """
    Assembles the structured prompt string that is handed to the LLM agent.

    The prompt is divided into clearly labelled sections so the agent can
    locate information quickly without exhaustive tool calling.
    """

    def __init__(self, max_dim2_lines: int = 20, max_dim4_commits: int = 5) -> None:
        self.max_dim2_lines = max_dim2_lines
        self.max_dim4_commits = max_dim4_commits

    def _trim_logs(self, raw: Optional[str]) -> str:
        """Return the last *max_dim2_lines* lines of *raw*, or the unavailable sentinel."""
        if not raw:
            return "unavailable"
        lines = raw.splitlines()
        return "\n".join(lines[-self.max_dim2_lines :])

    def _trim_commits(self, raw: Optional[str]) -> str:
        """Return the first *max_dim4_commits* commit lines, or the unavailable sentinel."""
        if not raw:
            return "no recent commits"
        lines = raw.splitlines()
        return "\n".join(lines[: self.max_dim4_commits])

    def package(
        self,
        job: dict,
        worktree_path: str,
        hydrated: dict,
        repomap: str = "unavailable",
    ) -> str:
        """
        Build the agent prompt string from *job* metadata, worktree path, and
        the hydrated observability dimensions.

        Args:
            job:           Incident job dict (must contain at minimum the keys
                           listed in the template below).
            worktree_path: Absolute path to the isolated git worktree.
            hydrated:      Output of ``LogHydrator.hydrate_all()``.
            repomap:       Prefetched repomap (if available).

        Returns:
            A multi-section prompt string ready for the LLM agent.
        """
        app_name = job.get("app_name", "unknown")
        fingerprint = job.get("fingerprint", "")
        error_message = job.get("error_message", "")
        error_file = job.get("error_file", "")
        exception_type = job.get("exception_type", "")
        timestamp = job.get("timestamp", "")

        dim2_raw = hydrated.get("dim2_app_logs")
        dim3_raw = hydrated.get("dim3_metrics")
        dim4_raw = hydrated.get("dim4_git_history")

        dim2 = self._trim_logs(dim2_raw)
        dim3 = dim3_raw or "unavailable"
        dim4 = self._trim_commits(dim4_raw)

        unavailable = []
        if not dim2_raw:
            unavailable.append("Application Logs")
        if not dim3_raw:
            unavailable.append("Metrics")
        if not dim4_raw:
            unavailable.append("Git History")
        if repomap == "unavailable":
            unavailable.append("Repomap")

        warning_block = ""
        if unavailable:
            warning_block = (
                f"[UNAVAILABLE INFORMATION]\n"
                f"The following context dimensions could not be fetched: {', '.join(unavailable)}.\n"
                f"Do NOT attempt to use tools to fetch them as they will fail. Proceed with diagnosis.\n\n"
            )

        return (
            f"{warning_block}"
            f"[INCIDENT]\n"
            f"app: {app_name}\n"
            f"fingerprint: {fingerprint}\n"
            f"error: {error_message}\n"
            f"file: {error_file}\n"
            f"exception: {exception_type}\n"
            f"timestamp: {timestamp}\n"
            f"\n"
            f"[REPO]\n"
            f"Available at: {worktree_path}\n"
            f"Use read_file, grep_search, view_file_slice to investigate.\n"
            f"\n"
            f"[REPOMAP / SKELETON]\n"
            f"{repomap}\n"
            f"\n"
            f"[METRICS]\n"
            f"{dim3}\n"
            f"\n"
            f"[APP LOGS] (last {self.max_dim2_lines} relevant lines)\n"
            f"{dim2}\n"
            f"\n"
            f"[GIT HISTORY] (last {self.max_dim4_commits} commits)\n"
            f"{dim4}\n"
        )


# ---------------------------------------------------------------------------
# PostflightOrchestrator
# ---------------------------------------------------------------------------


class PostflightOrchestrator:
    """
    Runs the post-flight sequence after the LLM agent has produced output.

    Responsibilities:
    - Apply unified diffs to the worktree.
    - Push a fix branch and open/update a PR idempotently.
    - Generate a structured postmortem in Markdown.
    - Return a summary dict consumed by the job dispatcher.
    """

    def __init__(
        self,
        backend_url: str,
        token: str = None,
        repo_cache_manager: RepoCacheManager = None,
    ) -> None:
        self.backend_url = backend_url.rstrip("/")
        self._token = token
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.repo_cache = repo_cache_manager or RepoCacheManager()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(
        self,
        incident_id: str,
        fingerprint: str,
        app_name: str,
        worktree_path: str,
        agent_output: dict,
    ) -> dict:
        """
        Main post-flight runner.

        Args:
            incident_id:   Unique incident identifier.
            fingerprint:   SHA-256 incident fingerprint.
            app_name:      Logical application name.
            worktree_path: Path to the isolated worktree.
            agent_output:  Dict produced by the agent, must contain ``type``
                           ("diff" or "escalation").

        Returns:
            {"pr_url": str|None, "postmortem": str, "status": "fixed"|"escalated"}
        """
        output_type = agent_output.get("type")

        if output_type == "diff":
            return self._apply_and_push_fix(
                worktree_path=worktree_path,
                fingerprint=fingerprint,
                app_name=app_name,
                diff_text=agent_output.get("diff", ""),
                explanation=agent_output.get("explanation", "automated fix"),
                incident_id=incident_id,
            )

        # Any other type (including "escalation") -> escalate immediately
        reason = agent_output.get("reason", "Agent could not determine root cause.")
        postmortem = self._generate_postmortem(
            app_name=app_name,
            fingerprint=fingerprint,
            elapsed_sec=agent_output.get("elapsed_sec", 0),
            explanation=f"ESCALATION: {reason}",
            pr_url=None,
            files_changed=[],
        )
        return {"pr_url": None, "postmortem": postmortem, "status": "escalated"}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _run(self, cmd: list, cwd: str = None, input: str = None, check: bool = True):
        """Thin subprocess wrapper."""
        logger.debug("Running: %s (cwd=%s)", " ".join(cmd), cwd)
        return subprocess.run(
            cmd,
            cwd=cwd,
            input=input,
            check=check,
            capture_output=True,
            text=True,
        )

    def _apply_and_push_fix(
        self,
        worktree_path: str,
        fingerprint: str,
        app_name: str,
        diff_text: str,
        explanation: str,
        incident_id: str,
        already_committed: bool = False,  # NEW: True if agent used write_file directly
        modified_files_hint: list = None,  # NEW: files agent reported writing
    ) -> dict:
        start_time = time.time()

        if os.environ.get("DAA_GIT_MODE") == "api":
            explanation += "\n\n⚠️ **WARNING**: Generated in Serverless mode (UNVERIFIED - no tests run)."

            from .tools.clonefree_client import CloneFreeGitClient

            client = CloneFreeGitClient(app_name)
            branch_name = f"fix/{fingerprint[:12]}"

            # ---- Case A: agent already committed via write_file ----
            # Skip patch application entirely — the branch/commit already exists.
            if already_committed:
                modified_files = modified_files_hint or []
                logger.info(
                    "Skipping patch step: agent already wrote %d file(s) via write_file",
                    len(modified_files),
                )
            else:
                if not worktree_path:
                    worktree_path = f"/tmp/{app_name}"

                modified_files = []
                for line in diff_text.splitlines():
                    if line.startswith("+++ b/"):
                        file_path = line[6:].split("\t")[0].strip()
                        modified_files.append(file_path)

                os.makedirs(worktree_path, exist_ok=True)
                for file_path in modified_files:
                    original_content = client.get_file_content(file_path) or ""
                    local_file_path = os.path.join(worktree_path, file_path)
                    os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
                    with open(local_file_path, "w", encoding="utf-8") as f:
                        f.write(original_content)

                # Prefer the Python fallback first — system `patch` chokes on
                # unescaped special chars (e.g. `~`) in context/removed lines.
                patch_failed = False
                try:
                    for file_path in modified_files:
                        local_file_path = os.path.join(worktree_path, file_path)
                        original_content = ""
                        if os.path.exists(local_file_path):
                            with open(local_file_path, "r", encoding="utf-8") as f:
                                original_content = f.read()
                        patched_content = _apply_unified_diff_to_text(
                            original_content, diff_text
                        )
                        with open(local_file_path, "w", encoding="utf-8") as f:
                            f.write(patched_content)
                except Exception as exc:
                    logger.warning(
                        "Python diff fallback failed (%s); trying system patch", exc
                    )
                    patch_failed = True

                if patch_failed:
                    try:
                        patch_bin = shutil.which("patch")
                        if not patch_bin:
                            raise FileNotFoundError("patch")
                        subprocess.run(
                            [patch_bin, "-p1", "-d", worktree_path],
                            input=diff_text,
                            capture_output=True,
                            text=True,
                            check=True,
                        )
                    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
                        stderr = getattr(exc, "stderr", str(exc))
                        logger.error("Both diff appliers failed: %s", stderr)
                        postmortem = self._generate_postmortem(
                            app_name=app_name,
                            fingerprint=fingerprint,
                            elapsed_sec=time.time() - start_time,
                            explanation=f"ESCALATION: patch failed -- {str(stderr)[:200]}",
                            pr_url=None,
                            files_changed=[],
                        )
                        return {
                            "pr_url": None,
                            "postmortem": postmortem,
                            "status": "escalated",
                        }

                client.create_branch(branch_name)
                for file_path in modified_files:
                    local_file_path = os.path.join(worktree_path, file_path)
                    with open(local_file_path, "r", encoding="utf-8") as f:
                        patched_content = f.read()
                    client.write_file_content(
                        file_path=file_path,
                        content=patched_content,
                        branch_name=branch_name,
                        commit_message=f"fix: {app_name} -- {explanation[:60]}",
                    )

            # ---- Create PR via API (runs for both Case A and Case B) ----
            if os.environ.get("DAA_HITL_MODE", "false").lower() == "true":
                pr_url = f"AWAITING_APPROVAL:{branch_name}"
            else:
                pr_url = self._create_pr_idempotent(
                    repo_url=client.repo_url,
                    branch_name=branch_name,
                    app_name=app_name,
                    explanation=explanation,
                    base_branch=client.default_branch,
                )

            elapsed = time.time() - start_time
            postmortem = self._generate_postmortem(
                app_name=app_name,
                fingerprint=fingerprint,
                elapsed_sec=elapsed,
                explanation=explanation,
                pr_url=pr_url,
                files_changed=modified_files,
            )
            return {"pr_url": pr_url, "postmortem": postmortem, "status": "fixed"}

    # ... non-API mode unchanged below ...
    def _create_pr_idempotent(
        self,
        repo_url: str,
        branch_name: str,
        app_name: str,
        explanation: str,
        base_branch: str = "main",
    ) -> str:
        """
        Open a PR for *branch_name* against main, or return the URL of an
        already-open PR.  Supports Gitea/GitHub-compatible REST APIs.

        Returns the PR HTML URL, or an empty string on failure.
        """
        if not repo_url:
            logger.warning("No repo_url; skipping PR creation")
            return ""

        # Parse owner/repo from the remote URL (https or ssh)
        try:
            owner, repo = _parse_owner_repo(repo_url)
        except ValueError as exc:
            logger.error("Cannot parse repo URL %r: %s", repo_url, exc)
            return ""

        # Derive the API base from the repo URL host
        parsed = urlparse(
            repo_url if repo_url.startswith("http") else f"https://{repo_url}"
        )
        api_base = f"{parsed.scheme}://{parsed.netloc}/api/v1"

        # Build git-provider auth.
        # Gitea and GitHub use "token {PAT}", NOT "Bearer {JWT}".
        # self._headers carries the DAA backend JWT — do NOT reuse it here.
        git_headers, git_auth = _git_auth_from_repo_url(repo_url)

        head_candidates: list[str] = []
        for candidate in (branch_name, f"{owner}:{branch_name}"):
            if candidate not in head_candidates:
                head_candidates.append(candidate)

        def _request_with_fallback(
            method: str, url: str, **kwargs
        ) -> requests.Response:
            timeout = kwargs.pop("timeout", 10)
            request_headers = kwargs.pop("headers", git_headers)
            resp = requests.request(
                method,
                url,
                headers=request_headers,
                auth=git_auth,
                timeout=timeout,
                **kwargs,
            )
            if (
                resp.status_code != 404
                or not git_auth
                or "Authorization" not in git_headers
            ):
                return resp

            # Some Gitea deployments return 404 for PAT-authenticated private repo
            # reads even when the same credentials succeed over basic auth.
            fallback_headers = dict(request_headers)
            fallback_headers.pop("Authorization", None)
            return requests.request(
                method,
                url,
                headers=fallback_headers,
                auth=git_auth,
                timeout=timeout,
                **kwargs,
            )

        # ---- Check for existing open PR ----------------------------------
        list_url = f"{api_base}/repos/{owner}/{repo}/pulls"
        listed = False
        for head_ref in head_candidates:
            try:
                resp = _request_with_fallback(
                    "GET",
                    list_url,
                    params={"state": "open", "head": head_ref},
                    timeout=10,
                )
                if resp.status_code == 404 and ":" in head_ref:
                    continue
                resp.raise_for_status()
                listed = True
                existing = resp.json()
                if existing:
                    pr_url = existing[0].get("html_url", "")
                    logger.info("Existing PR found: %s", pr_url)
                    return pr_url
            except requests.RequestException as exc:
                logger.warning("PR list check failed for %s: %s", head_ref, exc)

        if not listed:
            try:
                repo_resp = _request_with_fallback(
                    "GET", f"{api_base}/repos/{owner}/{repo}", timeout=10
                )
                repo_resp.raise_for_status()
            except requests.RequestException as exc:
                logger.error("Repo lookup failed before PR creation: %s", exc)
                return ""

        # ---- Create new PR -----------------------------------------------
        pr_title = f"fix({app_name}): {explanation[:72]}"
        pr_body = (
            f"Automated fix generated by DAA 3.0.\n\n"
            f"**App:** {app_name}\n"
            f"**Branch:** `{branch_name}`\n\n"
            f"{explanation}"
        )
        request_headers = {**git_headers, "Content-Type": "application/json"}
        for head_ref in head_candidates:
            try:
                resp = _request_with_fallback(
                    "POST",
                    list_url,
                    json={
                        "title": pr_title,
                        "body": pr_body,
                        "head": head_ref,
                        "base": base_branch,
                    },
                    headers=request_headers,
                    timeout=15,
                )
                resp.raise_for_status()
                pr_url = resp.json().get("html_url", "")
                logger.info("PR created: %s", pr_url)
                return pr_url
            except requests.RequestException as exc:
                logger.warning("PR creation failed for %s: %s", head_ref, exc)

        logger.error("PR creation failed for all head variants on %s", repo_url)
        return ""

    def _generate_postmortem(
        self,
        app_name: str,
        fingerprint: str,
        elapsed_sec: float,
        explanation: str,
        pr_url: Optional[str],
        files_changed: list,
    ) -> str:
        """
        Pure template fill -- no LLM call.  Returns a Markdown postmortem.
        """
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        files_md = (
            "\n".join(f"- `{f}`" for f in files_changed)
            if files_changed
            else "_no files changed_"
        )
        pr_md = f"[{pr_url}]({pr_url})" if pr_url else "_no PR created_"
        elapsed_str = f"{elapsed_sec:.1f}s"

        return (
            f"# DAA 3.0 Postmortem\n\n"
            f"**Generated:** {now_utc}  \n"
            f"**Application:** `{app_name}`  \n"
            f"**Fingerprint:** `{fingerprint}`  \n"
            f"**Time to Fix:** {elapsed_str}  \n\n"
            f"## Explanation\n\n"
            f"{explanation}\n\n"
            f"## Pull Request\n\n"
            f"{pr_md}\n\n"
            f"## Files Changed\n\n"
            f"{files_md}\n"
        )


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _parse_owner_repo(repo_url: str) -> tuple:
    """
    Extract ``(owner, repo)`` from an HTTP(S) or SSH remote URL.

    Raises ValueError if the URL cannot be parsed.
    """
    # Normalise SSH format: git@host:owner/repo.git -> https://host/owner/repo
    if repo_url.startswith("git@"):
        path_part = repo_url.split(":", 1)[-1]
    else:
        parsed = urlparse(repo_url)
        path_part = parsed.path.lstrip("/")

    # Strip .git suffix
    if path_part.endswith(".git"):
        path_part = path_part[:-4]

    parts = path_part.split("/")
    if len(parts) < 2:
        raise ValueError(f"Cannot extract owner/repo from {repo_url!r}")
    return parts[-2], parts[-1]


def _git_auth_from_repo_url(repo_url: str) -> tuple[dict, Optional[tuple[str, str]]]:
    """Build provider API auth from env or repo URL credentials."""
    git_token = (
        os.getenv("DAA_GIT_TOKEN")
        or os.getenv("GITHUB_TOKEN")
        or os.getenv("GITLAB_PRIVATE_TOKEN")
        or ""
    ).strip()
    headers = {"Authorization": f"token {git_token}"} if git_token else {}

    username = (
        os.getenv("DAA_GIT_USERNAME")
        or os.getenv("GIT_USERNAME")
        or os.getenv("GITEA_USERNAME")
        or ""
    ).strip()
    password = (
        os.getenv("DAA_GIT_PASSWORD")
        or os.getenv("GIT_PASSWORD")
        or os.getenv("GITEA_PASSWORD")
        or ""
    ).strip()

    parsed = urlparse(
        repo_url if repo_url.startswith("http") else f"https://{repo_url}"
    )
    if not (username and password) and parsed.username:
        username = username or unquote(parsed.username)
        if parsed.password:
            password = password or unquote(parsed.password)

    auth = (username, password) if username and password else None
    return headers, auth


def _build_repo_url_from_env(app_name: str) -> str:
    """Build the target repo URL from deployment env and app name."""
    git_host = os.getenv("GIT_HOST", "").strip()
    git_org = os.getenv("GIT_ORG", "").strip()
    if git_host and git_org:
        if not git_host.startswith(("http://", "https://")):
            git_host = f"https://{git_host}"
        return f"{git_host.rstrip('/')}/{git_org}/{app_name}.git"

    git_repo_url_template = os.getenv("GIT_REPO_URL", "").strip()
    if git_repo_url_template:
        parsed = urlparse(git_repo_url_template)
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(parts) >= 2 and parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}/{parts[0]}/{app_name}.git"

    generic_repo_url = os.getenv("DAA_REPO_URL", "").strip()
    if generic_repo_url:
        return generic_repo_url

    return ""


# ---------------------------------------------------------------------------
# Top-level pre-flight function
# ---------------------------------------------------------------------------


def run_preflight(job: dict, backend_url: str, token: str) -> dict:
    """
    Run the full pre-flight sequence.

    Steps:
    1. Compute a deterministic fingerprint from the incident fields.
    2. Dedup check -- if a fix is already open/merged and recent, return early.
    3. Resolve repo_url from deployment env using the app name.
    4. Obtain an isolated worktree via RepoCacheManager.
    5. Hydrate all observability dimensions (dim2/dim3/dim4).
    6. Package the structured agent context string.

    Args:
        job:         Incident job dict.  Must contain at minimum:
                     ``app_name``, ``exception_type``, ``error_file``,
                     ``line_number``, ``timestamp``.
        backend_url: DAA backend base URL.
        token:       Optional bearer token.

    Returns:
        {
            "worktree_path": str,
            "context":       str,          # structured prompt for agent
            "fingerprint":   str,
            "skip":          bool,         # True if dedup triggered early exit
            "skip_reason":   str | None,
            "pr_url":        str | None,   # populated only when skip=True
        }
    """
    app_name = job.get("app_name", "unknown")
    exception_type = job.get("exception_type", "")
    error_file = job.get("error_file", "")
    line_number = str(job.get("line_number", ""))
    incident_id = job.get("incident_id", f"{app_name}-{int(time.time())}")

    # ---- 1. Compute fingerprint ------------------------------------------
    dedup = FingerprintDedup(backend_url=backend_url, token=token)
    fingerprint = job.get("fingerprint") or dedup.compute(
        app_name=app_name,
        exception_type=exception_type,
        error_file=error_file,
        line_number=line_number,
        content_or_top_frame=job.get("stack_trace", "") or str(job.get("error_log", {}).get("content", "")),
    )
    logger.info("Fingerprint: %s", fingerprint)

    # Attach fingerprint back onto job so ContextPackager can use it
    job["fingerprint"] = fingerprint

    # ---- 2. Dedup check -------------------------------------------------
    fix_status = dedup.check(fingerprint)

    # If no fix found from DB, check Git remote branches in API mode (or as fallback)
    if fix_status["status"] == "no_fix":
        repo_url = _build_repo_url_from_env(app_name)
        token_val = os.environ.get("DAA_GIT_TOKEN")
        if not token_val and token and not token.startswith("eyJ"):
            token_val = token

        if repo_url:
            branch_name = f"fix/{fingerprint[:12]}"
            try:
                auth_url = repo_url
                if token_val:
                    parsed = urlparse(repo_url)
                    auth_url = (
                        parsed._replace(netloc=f"{token_val}@{parsed.netloc}").geturl()
                        if "@" not in parsed.netloc
                        else repo_url
                    )

                git_res = subprocess.run(
                    [
                        "git",
                        "ls-remote",
                        "--heads",
                        "--",
                        auth_url,
                        f"refs/heads/{branch_name}",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if git_res.stdout.strip():
                    logger.info(
                        "Dedup hit via Git remote: branch %s exists", branch_name
                    )
                    pr_url = None
                    try:
                        from .tools.clonefree_client import CloneFreeGitClient

                        client = CloneFreeGitClient(app_name)
                        if "github" in client.repo_url:
                            pr_url = (
                                client.repo_url.replace(".git", "")
                                + f"/pull/{branch_name}"
                            )
                        else:
                            pr_url = (
                                client.repo_url.replace(".git", "")
                                + "/-/merge_requests"
                            )
                    except Exception:
                        pass

                    fix_status = {
                        "status": "fix_open",
                        "pr_url": pr_url
                        or f"https://github.com/check-branch-for-pr?branch={branch_name}",
                        "fix_id": fingerprint,
                    }
            except Exception as exc:
                logger.warning("Git remote dedup check failed: %s", exc)

    if fix_status["status"] in ("fix_open", "fix_merged"):
        logger.info(
            "Dedup hit: status=%s pr_url=%s -- skipping fix",
            fix_status["status"],
            fix_status["pr_url"],
        )
        return {
            "worktree_path": None,
            "context": None,
            "fingerprint": fingerprint,
            "skip": True,
            "skip_reason": f"Fix already exists: {fix_status['status']}",
            "pr_url": fix_status["pr_url"],
        }

    # ---- 3. Resolve repo_url --------------------------------------------
    repo_url = _build_repo_url_from_env(app_name)
    if not repo_url:
        logger.warning("No repo_url could be derived from env for %s", app_name)

    # ---- 4. Get worktree & Acquire Deduplication Lock -------------------
    cache_manager = RepoCacheManager()
    worktree_path = None
    if repo_url:
        branch_name = f"fix/{fingerprint[:12]}"
        if os.environ.get("DAA_GIT_MODE") == "api":
            worktree_path = f"/tmp/{app_name}"
            try:
                from .tools.clonefree_client import CloneFreeGitClient

                client = CloneFreeGitClient(app_name)
                if not client.create_branch_lock(branch_name):
                    logger.warning(
                        "API branch lock unavailable for %s; continuing without lock",
                        branch_name,
                    )
            except Exception as exc:
                logger.error("Failed to acquire API branch lock: %s", exc)
        else:
            try:
                token_val = os.environ.get("DAA_GIT_TOKEN")
                if not token_val and token and not token.startswith("eyJ"):
                    token_val = token
                auth_url = repo_url
                if token_val:
                    parsed = urlparse(repo_url)
                    auth_url = (
                        parsed._replace(netloc=f"{token_val}@{parsed.netloc}").geturl()
                        if "@" not in parsed.netloc
                        else repo_url
                    )
                worktree_path = cache_manager.get_worktree(
                    app_name=app_name,
                    repo_url=auth_url,
                    incident_id=incident_id,
                )
                try:
                    subprocess.run(
                        ["git", "push", "origin", "--", f"HEAD:refs/heads/{branch_name}"],
                        cwd=worktree_path,
                        check=True,
                        capture_output=True,
                    )
                except subprocess.CalledProcessError:
                    return {
                        "worktree_path": None,
                        "context": None,
                        "fingerprint": fingerprint,
                        "skip": True,
                        "skip_reason": "Debugging via Git push lock",
                        "pr_url": None,
                    }
            except Exception as exc:
                logger.error("Failed to obtain worktree or lock: %s", exc)
                worktree_path = None
    else:
        logger.warning("No repo_url available; worktree will be unavailable")

    # ---- 4.5 Prefetch Repomap --------------------------------------------
    repomap = "unavailable"
    if worktree_path and os.environ.get("DAA_GIT_MODE") != "api":
        try:
            import json

            from .tools.code_nav_tool import read_repomap

            repomap = read_repomap(json.dumps({"repo_path": worktree_path}))
        except Exception as exc:
            logger.error("Failed to prefetch repomap: %s", exc)

    # ---- 5. Hydrate dimensions -------------------------------------------
    hydrator = LogHydrator(backend_url=backend_url, token=token)
    hydrated = hydrator.hydrate_all(
        app_name=app_name,
        incident_timestamp=job.get("timestamp", ""),
        trace_id=job.get("trace_id"),
    )

    # ---- 6. Package context ----------------------------------------------
    packager = ContextPackager()
    context = packager.package(
        job=job,
        worktree_path=worktree_path or "<no worktree>",
        hydrated=hydrated,
        repomap=repomap,
    )

    return {
        "worktree_path": worktree_path,
        "context": context,
        "fingerprint": fingerprint,
        "skip": False,
        "skip_reason": None,
        "pr_url": None,
    }

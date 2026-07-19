"""
git_provider.py — Lightweight Git PR/MR reader for DAA admin panel fallback.

When DAA_DB_PROVIDER=none, existing endpoints call fetch_prs() here to
assemble incident/fix/dashboard data directly from the configured Git provider.

Supports: GitHub · GitLab · Gitea · Bitbucket
Filter:   returns only PRs whose title starts with "[DAA]" or that carry
          a "daa-fix" / "daa-automated" label (configurable via DAA_PR_LABEL).

Caching:  60-second in-process TTL cache — avoids Git API rate limits without
          requiring Redis. A manual ?refresh=1 query param bypasses the cache.
"""

import os
import time
import urllib.parse
from typing import Any, Dict, List, Optional

import requests

# ── Cache ─────────────────────────────────────────────────────────────────────
_cache: Dict[str, Any] = {}
_CACHE_TTL = 60  # seconds


def _cached(key: str, builder, ttl: int = _CACHE_TTL, force: bool = False):
    now = time.monotonic()
    if not force and key in _cache:
        value, expires_at = _cache[key]
        if now < expires_at:
            return value
    value = builder()
    _cache[key] = (value, now + ttl)
    return value


# ── Provider detection ────────────────────────────────────────────────────────


def _detect_provider() -> str:
    """Return the active git provider name based on env vars.

    Checks both the canonical names (GITEA_TOKEN, GITHUB_TOKEN, etc.) and
    the standalone-image aliases (DAA_GIT_TOKEN + GIT_HOST/GIT_REPO_URL).
    """
    # Canonical provider env vars
    if os.getenv("GITHUB_TOKEN") and os.getenv("GITHUB_REPO"):
        return "github"
    if os.getenv("GITLAB_PRIVATE_TOKEN"):
        return "gitlab"
    if os.getenv("GITEA_TOKEN") and os.getenv("GITEA_HOST"):
        return "gitea"
    if os.getenv("BITBUCKET_APP_PASSWORD") and os.getenv("BITBUCKET_USERNAME"):
        return "bitbucket"
    # Standalone-image aliases: DAA_GIT_TOKEN + GIT_HOST or GIT_REPO_URL
    if os.getenv("DAA_GIT_TOKEN") and (
        os.getenv("GIT_HOST") or os.getenv("GIT_REPO_URL")
    ):
        return "gitea"  # standalone always targets a Gitea instance
    return "none"


def get_provider_info() -> Dict[str, Any]:
    """Return provider name and whether git is usably configured."""
    provider = _detect_provider()
    return {
        "git_provider": provider,
        "git_configured": provider != "none",
    }


# ── PR label / title filter ───────────────────────────────────────────────────

DAA_PR_LABEL = os.getenv("DAA_PR_LABEL", "daa-fix")
DAA_PR_TITLE_PREFIX = "[DAA]"

# Branch prefixes that DAA always uses when creating fix branches
_DAA_BRANCH_PREFIXES = ("fix/", "remediation/", "daa-fix/", "daa/", "autofix/")


def _is_daa_pr(title: str, labels: List[str], branch: str = "") -> bool:
    """Return True if this PR was created by DAA.

    Matches on:
    - Title prefix  [DAA]
    - Label         daa-fix / daa-automated (or DAA_PR_LABEL env)
    - Branch name   starts with a known DAA remediation prefix
    """
    if title.startswith(DAA_PR_TITLE_PREFIX):
        return True
    label_lower = [lab.lower() for lab in labels]
    if DAA_PR_LABEL.lower() in label_lower or "daa-automated" in label_lower:
        return True
    if branch and any(branch.startswith(p) for p in _DAA_BRANCH_PREFIXES):
        return True
    return False


# ── Normalised PR dict ────────────────────────────────────────────────────────


def _normalise(
    *,
    pr_id: str,
    title: str,
    body: str,
    state: str,  # "open" | "closed" | "merged"
    pr_url: str,
    app_name: str,
    branch: str,
    created_at: str,
    updated_at: str,
    merged_at: Optional[str],
    labels: List[str],
) -> Dict[str, Any]:
    if merged_at:
        status = "resolved"
    elif state == "open":
        status = "pr_open"
    else:
        status = "resolved"

    return {
        "id": pr_id,
        "source": "git",
        "fingerprint": branch,
        "app_name": app_name,
        "status": status,
        "occurrence_count": 1,
        "first_seen_at": created_at,
        "last_seen_at": updated_at or created_at,
        "agent_attempts": 1,
        "root_cause_summary": (body or "")[:500] or None,
        "confidence_score": None,
        "pr_url": pr_url,
        "ticket_url": None,
        "postmortem_md": body or None,
        "fix_id": pr_id,
        "labels": labels,
        "title": title,
    }


# ── GitHub ────────────────────────────────────────────────────────────────────


def _fetch_github(state: str = "all") -> List[Dict[str, Any]]:
    token = os.getenv("GITHUB_TOKEN", "")
    repo = os.getenv("GITHUB_REPO", "")  # "owner/repo"
    if not token or not repo:
        return []

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    url = f"https://api.github.com/repos/{repo}/pulls"
    params = {"state": state, "per_page": 50, "sort": "updated", "direction": "desc"}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=10)
        res.raise_for_status()
        prs = res.json()
    except Exception:
        return []

    results = []
    for pr in prs:
        labels = [lbl["name"] for lbl in pr.get("labels", [])]
        title = pr.get("title", "")
        branch = pr.get("head", {}).get("ref", "")
        if not _is_daa_pr(title, labels, branch=branch):
            continue
        parts = branch.split("/")
        app_name = parts[1] if len(parts) >= 3 else repo.split("/")[-1]
        results.append(
            _normalise(
                pr_id=f"gh-{pr['number']}",
                title=title,
                body=pr.get("body") or "",
                state="open" if pr.get("state") == "open" else "closed",
                pr_url=pr.get("html_url", ""),
                app_name=app_name,
                branch=branch,
                created_at=pr.get("created_at", ""),
                updated_at=pr.get("updated_at", ""),
                merged_at=pr.get("merged_at"),
                labels=labels,
            )
        )
    return results


# ── GitLab ────────────────────────────────────────────────────────────────────


def _fetch_gitlab(state: str = "all") -> List[Dict[str, Any]]:
    token = os.getenv("GITLAB_PRIVATE_TOKEN", "")
    host = os.getenv("GITLAB_HOST", "https://gitlab.com").rstrip("/")
    repo_url = os.getenv("DAA_REPO_URL", "")
    if not token:
        return []

    # Derive project path from DAA_REPO_URL or GITLAB_USER + env
    if repo_url:
        parsed = urllib.parse.urlparse(repo_url)
        project_path = parsed.path.lstrip("/").rstrip("/").replace(".git", "")
    else:
        gl_user = os.getenv("GITLAB_USER", "root")
        repo_name = os.getenv("REPO_NAME", "")
        if not repo_name:
            return []
        project_path = f"{gl_user}/{repo_name}"

    project_id = urllib.parse.quote_plus(project_path)
    headers = {"PRIVATE-TOKEN": token}

    # GitLab state: "opened" | "closed" | "merged" | "all"
    gl_state = {"open": "opened", "closed": "merged", "all": "all"}.get(state, "all")
    url = f"{host}/api/v4/projects/{project_id}/merge_requests"
    params = {
        "state": gl_state,
        "per_page": 50,
        "order_by": "updated_at",
        "sort": "desc",
    }
    try:
        res = requests.get(url, headers=headers, params=params, timeout=10)
        res.raise_for_status()
        mrs = res.json()
    except Exception:
        return []

    results = []
    for mr in mrs:
        labels = mr.get("labels", [])
        title = mr.get("title", "")
        branch = mr.get("source_branch", "")
        if not _is_daa_pr(title, labels, branch=branch):
            continue
        parts = branch.split("/")
        app_name = parts[1] if len(parts) >= 3 else project_path.split("/")[-1]
        mr_state = mr.get("state", "opened")
        merged_at = mr.get("merged_at")
        results.append(
            _normalise(
                pr_id=f"gl-{mr['iid']}",
                title=title,
                body=mr.get("description") or "",
                state="open" if mr_state == "opened" else "closed",
                pr_url=mr.get("web_url", ""),
                app_name=app_name,
                branch=branch,
                created_at=mr.get("created_at", ""),
                updated_at=mr.get("updated_at", ""),
                merged_at=merged_at,
                labels=labels,
            )
        )
    return results


# ── Gitea ─────────────────────────────────────────────────────────────────────


def _fetch_gitea(state: str = "all") -> List[Dict[str, Any]]:
    import re

    # Prefer canonical GITEA_TOKEN; fall back to DAA_GIT_TOKEN (standalone image)
    token = os.getenv("GITEA_TOKEN") or os.getenv("DAA_GIT_TOKEN", "")
    # Prefer canonical GITEA_HOST; fall back to GIT_HOST (standalone image)
    host = (
        os.getenv("GITEA_HOST") or os.getenv("GIT_HOST", "http://localhost:3000")
    ).rstrip("/")
    # Prefer DAA_REPO_URL; fall back to GIT_REPO_URL (standalone image)
    repo_url = os.getenv("DAA_REPO_URL") or os.getenv("GIT_REPO_URL", "")
    if not token:
        return []

    if repo_url:
        parsed = urllib.parse.urlparse(repo_url)
        path = parsed.path.lstrip("/").rstrip("/").replace(".git", "")
        parts = [p for p in path.split("/") if p]
        owner = parts[-2] if len(parts) >= 2 else ""
        repo_name = parts[-1] if len(parts) >= 2 else ""
    else:
        owner = os.getenv("GITLAB_USER") or os.getenv("GIT_ORG", "root")
        repo_name = os.getenv("REPO_NAME", "")
    if not owner and not repo_name:
        return []

    headers = {"Authorization": f"token {token}"}
    gt_state = "open" if state == "open" else ("closed" if state == "closed" else "all")

    try:
        if owner and repo_name:
            url = f"{host}/api/v1/repos/{owner}/{repo_name}/pulls"
            params = {"state": gt_state, "limit": 50}
        else:
            # Standalone fallback: search across all accessible repos
            url = f"{host}/api/v1/repos/issues/search"
            params = {"type": "pulls", "state": gt_state, "limit": 50}

        res = requests.get(url, headers=headers, params=params, timeout=10)
        res.raise_for_status()
        prs = res.json()
    except Exception:
        return []

    results = []
    for pr in prs:
        labels = [lbl["name"] for lbl in pr.get("labels", [])]
        title = pr.get("title", "")
        branch = pr.get("head", {}).get("ref", "")
        if not branch:
            m = re.search(r"\*\*Branch:\*\*\s+`([^`]+)`", pr.get("body") or "")
            if m:
                branch = m.group(1)
        if not _is_daa_pr(title, labels, branch=branch):
            continue

        repo_obj = pr.get("repository", {})
        actual_repo_name = repo_obj.get("name") or repo_name
        parts_branch = branch.split("/")
        app_name = parts_branch[1] if len(parts_branch) >= 3 else actual_repo_name

        merged_at = pr.get("merged") and pr.get("updated")
        # Global issue search wraps PR specific fields
        is_merged = pr.get("merged", False) or pr.get("pull_request", {}).get(
            "merged", False
        )
        is_closed = pr.get("state") == "closed" or pr.get("closed")

        results.append(
            _normalise(
                pr_id=f"gt-{pr['number']}",
                title=title,
                body=pr.get("body") or "",
                state="open" if not is_merged and not is_closed else "closed",
                pr_url=pr.get("html_url", ""),
                app_name=app_name,
                branch=branch,
                created_at=pr.get("created_at", ""),
                updated_at=pr.get("updated_at", ""),
                merged_at=pr.get("pull_request", {}).get("merged_at") or merged_at
                if is_merged
                else None,
                labels=labels,
            )
        )
    return results


# ── Bitbucket ─────────────────────────────────────────────────────────────────


def _fetch_bitbucket(state: str = "all") -> List[Dict[str, Any]]:
    username = os.getenv("BITBUCKET_USERNAME", "")
    app_password = os.getenv("BITBUCKET_APP_PASSWORD", "")
    repo_url = os.getenv("DAA_REPO_URL", "")
    if not username or not app_password:
        return []

    if repo_url:
        parsed = urllib.parse.urlparse(repo_url)
        path = parsed.path.lstrip("/").rstrip("/").replace(".git", "")
        parts = [p for p in path.split("/") if p]
        workspace = parts[-2] if len(parts) >= 2 else username
        repo_slug = parts[-1] if len(parts) >= 2 else ""
    else:
        workspace = username
        repo_slug = os.getenv("REPO_NAME", "")
    if not repo_slug:
        return []

    auth = (username, app_password)
    # Bitbucket state: "OPEN" | "MERGED" | "DECLINED" | "SUPERSEDED"
    bb_states = {
        "open": ["OPEN"],
        "closed": ["MERGED", "DECLINED"],
        "all": ["OPEN", "MERGED"],
    }.get(state, ["OPEN", "MERGED"])

    results = []
    for bb_state in bb_states:
        url = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/pullrequests"
        params = {"state": bb_state, "pagelen": 50}
        try:
            res = requests.get(url, auth=auth, params=params, timeout=10)
            res.raise_for_status()
            prs = res.json().get("values", [])
        except Exception:
            continue

        for pr in prs:
            title = pr.get("title", "")
            # Bitbucket has no labels — rely on title prefix only
            if not title.startswith(DAA_PR_TITLE_PREFIX):
                continue
            branch = pr.get("source", {}).get("branch", {}).get("name", "")
            parts_branch = branch.split("/")
            app_name = parts_branch[1] if len(parts_branch) >= 3 else repo_slug
            merged_at = pr.get("updated_on") if bb_state == "MERGED" else None
            results.append(
                _normalise(
                    pr_id=f"bb-{pr['id']}",
                    title=title,
                    body=pr.get("description") or "",
                    state="open" if bb_state == "OPEN" else "closed",
                    pr_url=pr.get("links", {}).get("html", {}).get("href", ""),
                    app_name=app_name,
                    branch=branch,
                    created_at=pr.get("created_on", ""),
                    updated_at=pr.get("updated_on", ""),
                    merged_at=merged_at,
                    labels=[],
                )
            )
    return results


# ── Public API ────────────────────────────────────────────────────────────────


def fetch_prs(state: str = "all", force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Return DAA-created PRs from the configured git provider.

    Args:
        state: "open" | "closed" | "all"
        force_refresh: bypass the 60-second cache

    Returns:
        List of normalised PR dicts (same shape as IncidentResponse + source="git").
        Returns [] if no git provider is configured.
    """
    provider = _detect_provider()
    cache_key = f"{provider}:{state}"

    fetchers = {
        "github": _fetch_github,
        "gitlab": _fetch_gitlab,
        "gitea": _fetch_gitea,
        "bitbucket": _fetch_bitbucket,
    }

    fetcher = fetchers.get(provider)
    if fetcher is None:
        return []

    return _cached(cache_key, lambda: fetcher(state), force=force_refresh)


def fetch_dashboard_stats(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Compute dashboard-compatible stats purely from git PRs.
    Shape mirrors GET /dashboard response so the admin panel needs zero changes.
    """
    all_prs = fetch_prs("all", force_refresh=force_refresh)
    open_prs = [p for p in all_prs if p["status"] == "pr_open"]
    resolved = [p for p in all_prs if p["status"] == "resolved"]
    total = len(all_prs)

    fix_rate = round(len(resolved) / total * 100, 1) if total > 0 else 0.0

    # Most recent 5, sorted by last_seen_at descending
    recent = sorted(all_prs, key=lambda p: p["last_seen_at"], reverse=True)[:5]
    recent_list = [
        {
            "id": p["id"],
            "app_name": p["app_name"],
            "status": p["status"],
            "occurrence_count": p["occurrence_count"],
            "last_seen_at": p["last_seen_at"],
        }
        for p in recent
    ]

    return {
        "active_incidents": len(open_prs),
        "total_incidents": total,
        "resolved_incidents": len(resolved),
        "fix_rate_percent": fix_rate,
        # Logs genuinely don't exist without a DB — return 0 honestly
        "logs_last_24h": 0,
        "total_logs": 0,
        "open_prs": len(open_prs),
        "active_alerts": 0,
        "recent_incidents": recent_list,
        # Extra fields (ignored by panel, useful for debugging)
        "_source": "git",
        "_provider": _detect_provider(),
    }

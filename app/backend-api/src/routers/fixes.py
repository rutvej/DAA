import logging
import os
import urllib.parse
from datetime import datetime
from typing import Optional

import requests
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import Fix as DBFix
from ..database import Incident as DBIncident
from ..database import Log as DBLog
from ..database import ProjectConnection as DBProjectConnection
from ..database import get_db
from ..notifications.webhook import send_outbound_webhook
from .auth import get_current_user

router = APIRouter()


class FixResponse(BaseModel):
    id: str
    logId: str
    timestamp: datetime
    generatedFix: Optional[str] = None
    postmortem: Optional[str] = None
    status: Optional[str] = None
    pull_request_url: Optional[str] = None


class AnalysisReport(BaseModel):
    log_id: str
    status: str = None
    pull_request_url: str = None
    postmortem: str = None


@router.get("/{id}", response_model=FixResponse)
def get_fix(
    id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") == "application":
        raise HTTPException(
            status_code=403,
            detail="Applications are not authorized to perform this action",
        )
    fix = db.query(DBFix).filter(DBFix.id == id).first()
    if fix is None:
        raise HTTPException(status_code=404, detail="Fix not found")
    return fix


@router.get("/by-log/{log_id}", response_model=FixResponse)
def get_fix_by_log(
    log_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") == "application":
        raise HTTPException(
            status_code=403,
            detail="Applications are not authorized to perform this action",
        )
    fix = db.query(DBFix).filter(DBFix.logId == log_id).first()
    if fix is None:
        raise HTTPException(status_code=404, detail="Fix not found")
    return fix


def create_pr_on_provider(
    app_name: str, branch_name: str, title: str, description: str, db: Session
) -> str:
    proj = (
        db.query(DBProjectConnection)
        .filter(DBProjectConnection.app_name == app_name)
        .first()
    )
    provider = proj.repo_provider if proj else "gitlab"
    token = (
        proj.repo_token
        if (proj and proj.repo_token)
        else os.getenv("GITLAB_PRIVATE_TOKEN")
    )

    if provider == "github" or provider == "gitea":
        repo_url = proj.repo_url if proj else ""
        parsed = urllib.parse.urlparse(repo_url)
        path = parsed.path
        if path.endswith(".git"):
            path = path[:-4]
        parts = [p for p in path.split("/") if p]
        owner = parts[-2] if len(parts) >= 2 else "owner"
        r_name = parts[-1] if len(parts) >= 2 else "repo"

        if provider == "github":
            prs_url = f"https://api.github.com/repos/{owner}/{r_name}/pulls"
            headers = {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
            }
        else:
            prs_url = (
                f"{parsed.scheme}://{parsed.netloc}/api/v1/repos/{owner}/{r_name}/pulls"
            )
            headers = {
                "Authorization": f"token {token}",
                "Content-Type": "application/json",
            }

        try:
            check_res = requests.get(
                prs_url, headers=headers, params={"head": f"{owner}:{branch_name}"}
            )
            if check_res.status_code == 200 and check_res.json():
                return check_res.json()[0]["html_url"]
        except Exception:
            pass

        pr_payload = {
            "title": title,
            "body": description,
            "head": branch_name,
            "base": "master",
        }
        try:
            res = requests.post(prs_url, headers=headers, json=pr_payload)
            if res.status_code == 201:
                return res.json().get("html_url")
            else:
                pr_payload["base"] = "main"
                res_fallback = requests.post(prs_url, headers=headers, json=pr_payload)
                if res_fallback.status_code == 201:
                    return res_fallback.json().get("html_url")
                raise Exception(
                    f"{provider} API Error: {res.text} / {res_fallback.text}"
                )
        except Exception as e:
            raise Exception(f"Exception creating {provider} PR: {e}")
    else:
        scheme = "http"
        gl_host = os.getenv("GITLAB_HOST", "gitlab")
        if proj and proj.repo_url:
            try:
                parsed = urllib.parse.urlparse(proj.repo_url)
                gl_host = parsed.netloc
                scheme = parsed.scheme or "http"
            except Exception:
                pass
        gl_user = os.getenv("GITLAB_USER", "root")
        project_path = f"{gl_user}/{app_name}"
        project_id = urllib.parse.quote_plus(project_path)

        mr_url = f"{scheme}://{gl_host}/api/v4/projects/{project_id}/merge_requests"
        print(
            f"[create_pr_on_provider] app_name={app_name}, gl_host={gl_host}, scheme={scheme}, repo_url={proj.repo_url if proj else None}, mr_url={mr_url}",
            flush=True,
        )
        headers = {"PRIVATE-TOKEN": token}
        try:
            check_url = f"{mr_url}?source_branch={branch_name}"
            check_res = requests.get(check_url, headers=headers)
            if check_res.status_code == 200 and check_res.json():
                return check_res.json()[0]["web_url"]
        except Exception:
            pass

        mr_payload = {
            "source_branch": branch_name,
            "target_branch": "master",
            "title": title,
            "description": description,
        }
        try:
            res = requests.post(mr_url, headers=headers, json=mr_payload)
            if res.status_code == 201:
                return res.json().get("web_url")
            else:
                mr_payload["target_branch"] = "main"
                res_fallback = requests.post(mr_url, headers=headers, json=mr_payload)
                if res_fallback.status_code == 201:
                    return res_fallback.json().get("web_url")
                raise Exception(f"GitLab API Error: {res.text} / {res_fallback.text}")
        except Exception as e:
            raise Exception(f"Exception creating GitLab MR: {e}")


@router.post("/{id}/approve")
def approve_fix(
    id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") == "application":
        raise HTTPException(
            status_code=403,
            detail="Applications are not authorized to perform this action",
        )
    fix = db.query(DBFix).filter(DBFix.id == id).first()
    if fix is None:
        raise HTTPException(status_code=404, detail="Fix not found")

    if fix.status == "Approved" or (
        fix.pull_request_url and fix.pull_request_url.startswith("http")
    ):
        return {"status": "success", "pull_request_url": fix.pull_request_url}

    log = db.query(DBLog).filter(DBLog.id == fix.logId).first()
    if log is None:
        raise HTTPException(status_code=404, detail="Log not found")

    branch_name = fix.generatedFix or f"remediation/fix-{fix.id[:8]}"
    app_name = log.app_name

    try:
        pr_url = create_pr_on_provider(
            app_name=app_name,
            branch_name=branch_name,
            title=f"Remediation Fix for {app_name} Incident",
            description=fix.postmortem or "Automated fix proposed by DAA v2.0.",
            db=db,
        )
    except Exception as e:
        logging.error(f"Error creating PR/MR: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create MR/PR: {e}")

    fix.isApproved = True
    fix.status = "completed"
    fix.pull_request_url = pr_url

    # Also update associated Log and Incident status if they exist
    log.status = "Resolved (Approved)"

    # Try finding an active incident
    incident = (
        db.query(DBIncident)
        .filter(
            DBIncident.app_name == app_name,
            DBIncident.status.in_(
                ["investigating", "fix_proposed", "awaiting_approval"]
            ),
        )
        .first()
    )
    if incident:
        incident.status = "pr_open"
        incident.pr_url = pr_url
        incident.root_cause_summary = fix.postmortem[:500] if fix.postmortem else None

    db.commit()
    return {"status": "success", "pull_request_url": pr_url}


@router.post("")
async def post_analysis(
    report: AnalysisReport,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") == "application":
        raise HTTPException(
            status_code=403,
            detail="Applications are not authorized to perform this action",
        )
    logging.info(f"Received analysis report: {report}")
    log = db.query(DBLog).filter(DBLog.id == report.log_id).first()
    if log is None:
        if os.environ.get("DAA_DB_PROVIDER") == "none":
            log = DBLog(id=report.log_id, app_name="unknown", status="Pending")
        else:
            logging.error(f"Log with id {report.log_id} not found in the database.")
            raise HTTPException(status_code=404, detail="Log not found")

    status = report.status
    pr_url = report.pull_request_url
    branch_name = None

    if pr_url and pr_url.startswith("AWAITING_APPROVAL:"):
        branch_name = pr_url.split(":", 1)[1]
        status = "awaiting_approval"
        pr_url = ""
        log.status = "Awaiting Approval"

    fix = db.query(DBFix).filter(DBFix.logId == report.log_id).first()
    if fix is None:
        fix = DBFix(
            logId=report.log_id,
            status=status,
            pull_request_url=pr_url,
            postmortem=report.postmortem,
            generatedFix=branch_name,
        )
        db.add(fix)
    else:
        if status is not None:
            fix.status = status
        if pr_url is not None:
            fix.pull_request_url = pr_url
        if report.postmortem is not None:
            fix.postmortem = report.postmortem
        if branch_name is not None:
            fix.generatedFix = branch_name

    # Propagate findings to the active Incident record if it exists
    incident = (
        db.query(DBIncident)
        .filter(
            DBIncident.app_name == log.app_name,
            DBIncident.status.in_(
                ["investigating", "processing", "awaiting_approval", "fix_proposed"]
            ),
        )
        .first()
    )
    if incident:
        if status == "awaiting_approval":
            incident.status = "fix_proposed"
        elif pr_url and (
            "ticket" in pr_url
            or "issue" in pr_url
            or pr_url.startswith("https://example.com/ticket")
        ):
            incident.status = "ticket_created"
            incident.ticket_url = pr_url
        elif pr_url and pr_url.startswith("http"):
            incident.status = "pr_open"
            incident.pr_url = pr_url
        else:
            incident.status = "resolved" if status == "completed" else status

        if report.postmortem:
            incident.postmortem_md = report.postmortem
            incident.root_cause_summary = report.postmortem[:500]

    db.commit()

    # Trigger outbound webhook if investigation finished
    if status == "completed":
        status_val = "fixed" if (pr_url and pr_url.startswith("http")) else "escalated"
        fingerprint_val = incident.fingerprint if incident else ""
        webhook_payload = {
            "event": "daa.investigation.completed",
            "job_id": report.log_id,
            "fingerprint": fingerprint_val,
            "app_name": log.app_name if log else "unknown",
            "status": status_val,
            "pr_url": pr_url or "",
            "postmortem": report.postmortem or "",
        }
        background_tasks.add_task(send_outbound_webhook, webhook_payload)

    return {"status": "success"}


class AppendLogRequest(BaseModel):
    log_line: str


@router.post("/{log_id}/append-log")
def append_log(
    log_id: str,
    payload: AppendLogRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") == "application":
        raise HTTPException(
            status_code=403,
            detail="Applications are not authorized to perform this action",
        )
    fix = db.query(DBFix).filter(DBFix.logId == log_id).first()
    if fix is None:
        fix = DBFix(
            logId=log_id,
            status="processing",
            postmortem=payload.log_line + "\n\n",
            pull_request_url="",
        )
        db.add(fix)
    else:
        if not fix.postmortem:
            fix.postmortem = ""
        # Append the line
        fix.postmortem += payload.log_line + "\n\n"
        if fix.status == "Pending":
            fix.status = "processing"
    db.commit()
    try:
        from .status import thought_broadcaster
        thought_broadcaster.publish(log_id, payload.log_line)
    except Exception:
        pass
    return {"status": "success"}


@router.get("/fingerprint/{fingerprint}")
def get_fix_by_fingerprint(fingerprint: str, db: Session = Depends(get_db)):
    incident = (
        db.query(DBIncident)
        .filter(DBIncident.fingerprint == fingerprint)
        .order_by(DBIncident.last_seen_at.desc())
        .first()
    )
    if not incident:
        return {"status": "no_fix", "pr_url": None, "fix_id": None}

    if incident.pr_url or incident.status in ("pr_open", "cooldown", "resolved"):
        status_val = "fix_open" if incident.status == "pr_open" else "fix_merged"
        return {"status": status_val, "pr_url": incident.pr_url, "fix_id": incident.id}
    return {"status": "no_fix", "pr_url": None, "fix_id": None}

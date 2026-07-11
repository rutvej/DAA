from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ..database import ProjectConnection as DBProjectConnection
from ..database import get_db
from .auth import get_current_user

router = APIRouter()


class ProjectConnectionCreate(BaseModel):
    app_name: str
    repo_provider: str = "gitlab"  # "github", "gitlab"
    repo_url: str
    repo_token: str
    jira_url: Optional[str] = None
    jira_token: Optional[str] = None
    jira_project_key: Optional[str] = None


class ProjectConnectionResponse(BaseModel):
    id: str
    app_name: str
    repo_provider: str
    repo_url: str
    repo_token: str
    jira_url: Optional[str]
    jira_token: Optional[str]
    jira_project_key: Optional[str]
    model_config = ConfigDict(from_attributes=True)


@router.post("/", response_model=ProjectConnectionResponse)
def create_or_update_project(
    project: ProjectConnectionCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") == "application":
        raise HTTPException(
            status_code=403,
            detail="Applications are not authorized to perform this action",
        )

    db_project = (
        db.query(DBProjectConnection)
        .filter(DBProjectConnection.app_name == project.app_name)
        .first()
    )
    if db_project:
        db_project.repo_provider = project.repo_provider
        db_project.repo_url = project.repo_url
        db_project.repo_token = project.repo_token
        db_project.jira_url = project.jira_url
        db_project.jira_token = project.jira_token
        db_project.jira_project_key = project.jira_project_key
    else:
        db_project = DBProjectConnection(
            app_name=project.app_name,
            repo_provider=project.repo_provider,
            repo_url=project.repo_url,
            repo_token=project.repo_token,
            jira_url=project.jira_url,
            jira_token=project.jira_token,
            jira_project_key=project.jira_project_key,
        )
        db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


@router.get("/{app_name}", response_model=ProjectConnectionResponse)
def get_project(
    app_name: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") == "application":
        raise HTTPException(
            status_code=403,
            detail="Applications are not authorized to perform this action",
        )

    project = (
        db.query(DBProjectConnection)
        .filter(DBProjectConnection.app_name == app_name)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project connection not found")
    return project


@router.get("/", response_model=List[ProjectConnectionResponse])
def list_projects(
    db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)
):
    if current_user.get("role") == "application":
        raise HTTPException(
            status_code=403,
            detail="Applications are not authorized to perform this action",
        )

    return db.query(DBProjectConnection).all()

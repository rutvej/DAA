from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from ..database import get_db, Application as DBApplication, EscalationPolicy as DBEscalationPolicy
import json

router = APIRouter()

class ApplicationCreate(BaseModel):
    name: str
    description: Optional[str] = None
    language: Optional[str] = None
    repository_url: Optional[str] = None
    spec_file_path: Optional[str] = None
    team_owner: Optional[str] = None

class ApplicationResponse(ApplicationCreate):
    id: str
    created_at: str
    model_config = ConfigDict(from_attributes=True)

class EscalationPolicyCreate(BaseModel):
    rule_type: str = "error_rate_threshold"
    condition_value: Optional[int] = 15
    window_seconds: Optional[int] = 120
    severity_keywords: Optional[List[str]] = ["FATAL", "OOMKill", "PANIC", "DatabaseDeadlock"]
    cooldown_minutes: Optional[int] = 30
    is_active: Optional[bool] = True

class EscalationPolicyResponse(BaseModel):
    id: str
    application_id: str
    rule_type: str
    condition_value: Optional[int]
    window_seconds: int
    severity_keywords: Optional[str]
    cooldown_minutes: int
    is_active: bool
    model_config = ConfigDict(from_attributes=True)

@router.post("/", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
def create_application(app: ApplicationCreate, db: Session = Depends(get_db)):
    existing = db.query(DBApplication).filter(DBApplication.name == app.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Application with this name already exists")
    db_app = DBApplication(
        name=app.name,
        description=app.description,
        language=app.language,
        repository_url=app.repository_url,
        spec_file_path=app.spec_file_path,
        team_owner=app.team_owner
    )
    db.add(db_app)
    db.commit()
    db.refresh(db_app)
    return ApplicationResponse(
        id=db_app.id,
        name=db_app.name,
        description=db_app.description,
        language=db_app.language,
        repository_url=db_app.repository_url,
        spec_file_path=db_app.spec_file_path,
        team_owner=db_app.team_owner,
        created_at=db_app.created_at.isoformat()
    )

@router.get("/", response_model=List[ApplicationResponse])
def list_applications(db: Session = Depends(get_db)):
    apps = db.query(DBApplication).all()
    res = []
    for a in apps:
        res.append(ApplicationResponse(
            id=a.id,
            name=a.name,
            description=a.description,
            language=a.language,
            repository_url=a.repository_url,
            spec_file_path=a.spec_file_path,
            team_owner=a.team_owner,
            created_at=a.created_at.isoformat()
        ))
    return res

@router.get("/{id}", response_model=ApplicationResponse)
def get_application(id: str, db: Session = Depends(get_db)):
    a = db.query(DBApplication).filter(DBApplication.id == id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Application not found")
    return ApplicationResponse(
        id=a.id,
        name=a.name,
        description=a.description,
        language=a.language,
        repository_url=a.repository_url,
        spec_file_path=a.spec_file_path,
        team_owner=a.team_owner,
        created_at=a.created_at.isoformat()
    )

@router.post("/{id}/escalation-policies", response_model=EscalationPolicyResponse, status_code=status.HTTP_201_CREATED)
def create_escalation_policy(id: str, policy: EscalationPolicyCreate, db: Session = Depends(get_db)):
    app = db.query(DBApplication).filter(DBApplication.id == id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    kw_str = json.dumps(policy.severity_keywords) if policy.severity_keywords else '["FATAL", "OOMKill"]'
    db_policy = DBEscalationPolicy(
        application_id=app.id,
        rule_type=policy.rule_type,
        condition_value=policy.condition_value,
        window_seconds=policy.window_seconds,
        severity_keywords=kw_str,
        cooldown_minutes=policy.cooldown_minutes,
        is_active=policy.is_active
    )
    db.add(db_policy)
    db.commit()
    db.refresh(db_policy)
    return db_policy

@router.get("/{id}/escalation-policies", response_model=List[EscalationPolicyResponse])
def list_escalation_policies(id: str, db: Session = Depends(get_db)):
    policies = db.query(DBEscalationPolicy).filter(DBEscalationPolicy.application_id == id).all()
    return policies

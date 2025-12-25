from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db, Fix as DBFix
from datetime import datetime

router = APIRouter()

class FixResponse(BaseModel):
    id: str
    logId: str
    timestamp: datetime
    generatedFix: str

class AnalysisReport(BaseModel):
    log_id: str
    status: str = None
    pull_request_url: str = None

@router.get("/{id}", response_model=FixResponse)
def get_fix(id: str, db: Session = Depends(get_db)):
    fix = db.query(DBFix).filter(DBFix.id == id).first()
    if fix is None:
        raise HTTPException(status_code=404, detail="Fix not found")
    return fix

@router.post("/analysis")
def post_analysis(report: AnalysisReport, db: Session = Depends(get_db)):
    fix = db.query(DBFix).filter(DBFix.logId == report.log_id).first()
    if fix is None:
        fix = DBFix(
            logId=report.log_id,
            status=report.status,
            pull_request_url=report.pull_request_url,
        )
        db.add(fix)
    else:
        if report.status:
            fix.status = report.status
        if report.pull_request_url:
            fix.pull_request_url = report.pull_request_url
    db.commit()
    return {"status": "success"}

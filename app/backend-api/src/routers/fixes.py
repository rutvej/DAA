import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import Fix as DBFix
from ..database import Log as DBLog
from ..database import get_db

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
def get_fix(id: str, db: Session = Depends(get_db)):
    fix = db.query(DBFix).filter(DBFix.id == id).first()
    if fix is None:
        raise HTTPException(status_code=404, detail="Fix not found")
    return fix

@router.get("/by-log/{log_id}", response_model=FixResponse)
def get_fix_by_log(log_id: str, db: Session = Depends(get_db)):
    fix = db.query(DBFix).filter(DBFix.logId == log_id).first()
    if fix is None:
        raise HTTPException(status_code=404, detail="Fix not found")
    return fix

@router.post("")
def post_analysis(report: AnalysisReport, db: Session = Depends(get_db)):
    logging.info(f"Received analysis report: {report}")
    log = db.query(DBLog).filter(DBLog.id == report.log_id).first()
    if log is None:
        logging.error(f"Log with id {report.log_id} not found in the database.")
        raise HTTPException(status_code=404, detail="Log not found")

    fix = db.query(DBFix).filter(DBFix.logId == report.log_id).first()
    if fix is None:
        fix = DBFix(
            logId=report.log_id,
            status=report.status,
            pull_request_url=report.pull_request_url,
            postmortem=report.postmortem
        )
        db.add(fix)
    else:
        if report.status is not None:
            fix.status = report.status
        if report.pull_request_url is not None:
            fix.pull_request_url = report.pull_request_url
        if report.postmortem is not None:
            fix.postmortem = report.postmortem
    db.commit()
    return {"status": "success"}


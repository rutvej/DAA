import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db, Fix as DBFix, Log as DBLog
from datetime import datetime
import re

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
        )
        db.add(fix)
    else:
        if report.status is not None:
            fix.status = report.status
        if report.pull_request_url is not None:
            fix.pull_request_url = report.pull_request_url
    db.commit()
    return {"status": "success"}

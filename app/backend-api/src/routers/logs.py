from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db, Log as DBLog
import uuid

router = APIRouter()

class Log(BaseModel):
    content: str

@router.post("/")
def submit_log(log: Log, db: Session = Depends(get_db)):
    log_id = str(uuid.uuid4())
    db_log = DBLog(id=log_id, content=log.content)
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return {"logId": log_id, "status": "Pending"}

@router.get("/")
def get_logs(db: Session = Depends(get_db)):
    return db.query(DBLog).all()

@router.get("/{id}")
def get_log(id: str, db: Session = Depends(get_db)):
    log = db.query(DBLog).filter(DBLog.id == id).first()
    if log is None:
        raise HTTPException(status_code=404, detail="Log not found")
    return log
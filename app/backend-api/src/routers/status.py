from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db, Log as DBLog

router = APIRouter()

class StatusResponse(BaseModel):
    status: str

@router.get("/{id}", response_model=StatusResponse)
def get_status(id: str, db: Session = Depends(get_db)):
    log = db.query(DBLog).filter(DBLog.id == id).first()
    if log is None:
        raise HTTPException(status_code=404, detail="Log not found")
    return {"status": log.status}

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import Log as DBLog
from ..database import get_db
from .auth import get_current_user

router = APIRouter()

class StatusResponse(BaseModel):
    status: str

@router.get("/{id}", response_model=StatusResponse)
def get_status(id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if current_user.get("role") == "application":
        raise HTTPException(status_code=403, detail="Applications are not authorized to perform this action")
    log = db.query(DBLog).filter(DBLog.id == id).first()
    if log is None:
        raise HTTPException(status_code=404, detail="Log not found")
    return {"status": log.status}

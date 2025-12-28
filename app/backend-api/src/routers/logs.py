import json
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db, Log as DBLog
from routers.auth import User
import pika
import os
from typing import List
from datetime import datetime
from fastapi.security import OAuth2PasswordBearer

router = APIRouter()

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST")

class LogCreate(BaseModel):
    content: str
    app_name: str

class LogResponse(BaseModel):
    id: str
    status: str
    timestamp: str

    class Config:
        orm_mode = True

class LogDetailsResponse(LogResponse):
    content: str

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

import jwt
from routers.auth import SECRET_KEY, ALGORITHM

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: str = payload.get("id")
        if username is None or user_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        return {"username": username, "id": user_id}
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

@router.post("/", status_code=status.HTTP_202_ACCEPTED)
def submit_log(log: LogCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if not log.content or not isinstance(log.content, str):
        raise HTTPException(status_code=400, detail="Invalid log content")
    db_log = DBLog(content=log.content, userId=current_user["id"], app_name=log.app_name)
    db.add(db_log)
    db.commit()
    db.refresh(db_log)

    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
        channel = connection.channel()
        channel.queue_declare(queue='fix_jobs', durable=True)
        job_data = {
            "id": str(db_log.id),
            "log_id": str(db_log.id),
            "app_name": db_log.app_name,
            "status": "pending",
            "created_at": db_log.timestamp.isoformat(),
            "updated_at": db_log.timestamp.isoformat(),
            "error_log": {
                "id": str(db_log.id),
                "app_name": db_log.app_name,
                "content": db_log.content,
                "stack_trace": "",
                "timestamp": db_log.timestamp.isoformat()
            }
        }
        channel.basic_publish(exchange='',
                              routing_key='fix_jobs',
                              body=json.dumps(job_data))
        connection.close()
    except pika.exceptions.AMQPConnectionError:
        raise HTTPException(status_code=503, detail="Could not connect to RabbitMQ")

    return {"logId": db_log.id, "status": "Pending"}

@router.get("/", response_model=List[LogResponse])
def get_logs(db: Session = Depends(get_db), page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=100), status: str = Query(None)):
    query = db.query(DBLog)
    if status:
        query = query.filter(DBLog.status == status)
    
    logs = query.offset((page - 1) * limit).limit(limit).all()
    return [LogResponse(id=log.id, status=log.status, timestamp=log.timestamp.isoformat()) for log in logs]

@router.get("/{id}", response_model=LogDetailsResponse)
def get_log(id: str, db: Session = Depends(get_db)):
    log = db.query(DBLog).filter(DBLog.id == id).first()
    if log is None:
        raise HTTPException(status_code=404, detail="Log not found")
    return LogDetailsResponse(id=log.id, status=log.status, timestamp=log.timestamp.isoformat(), content=log.content)

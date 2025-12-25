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

def get_current_user(token: str = Depends(lambda x: x)):
    # This is a placeholder for a real authentication implementation
    # In a real application, you would decode the JWT and get the user
    return User(username="testuser")

@router.post("/", status_code=status.HTTP_202_ACCEPTED)
def submit_log(log: LogCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not log.content or not isinstance(log.content, str):
        raise HTTPException(status_code=400, detail="Invalid log content")
    db_log = DBLog(content=log.content, userId=current_user.username, app_name=log.app_name)
    db.add(db_log)
    db.commit()
    db.refresh(db_log)

    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
        channel = connection.channel()
        channel.queue_declare(queue='fix_jobs')
        job_data = {
            "id": db_log.id,
            "log_id": db_log.id,
            "app_name": db_log.app_name,
            "status": "pending",
            "created_at": db_log.timestamp.isoformat(),
            "updated_at": db_log.timestamp.isoformat(),
            "error_log": {
                "id": db_log.id,
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

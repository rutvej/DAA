from fastapi import APIRouter
from datetime import datetime

router = APIRouter()

@router.get("/{id}")
def get_fix(id: str):
    return {"id": id, "logId": "dummy-log-id", "timestamp": datetime.now(), "generatedFix": "dummy fix content"}
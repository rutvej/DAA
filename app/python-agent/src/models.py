from pydantic import BaseModel
from typing import Optional

class ErrorLog(BaseModel):
    id: int
    app_name: str
    content: str
    stack_trace: str
    timestamp: str

class Job(BaseModel):
    id: int
    log_id: int
    app_name: str
    status: str
    created_at: str
    updated_at: str
    error_log: ErrorLog
    pull_request_url: Optional[str] = None

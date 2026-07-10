from pydantic import BaseModel
from uuid import UUID
from typing import Optional

class ErrorLog(BaseModel):
    id: UUID
    app_name: str
    content: str
    stack_trace: str
    timestamp: str
    exception_type: Optional[str] = None
    trace_id: Optional[str] = None
    error_file: Optional[str] = None

class Job(BaseModel):
    id: UUID
    log_id: UUID
    app_name: str
    status: str
    created_at: str
    updated_at: str
    error_log: ErrorLog
    pull_request_url: Optional[str] = None
    incident_id: Optional[str] = None
    fingerprint: Optional[str] = None
    trace_id: Optional[str] = None

class MissingModelError(Exception):
    """
    Exception raised when a required model is missing.
    """
    pass

class NotSupportedError(Exception):
    """
    Exception raised when a feature is not supported.
    """
    pass


from uuid import UUID

from pydantic import BaseModel


class ErrorLog(BaseModel):
    id: UUID
    app_name: str
    content: str
    stack_trace: str
    timestamp: str
    exception_type: str | None = None
    trace_id: str | None = None
    error_file: str | None = None


class Job(BaseModel):
    id: UUID
    log_id: UUID
    app_name: str
    status: str
    created_at: str
    updated_at: str
    error_log: ErrorLog
    pull_request_url: str | None = None
    incident_id: str | None = None
    fingerprint: str | None = None
    trace_id: str | None = None


class MissingModelError(Exception):
    """
    Exception raised when a required model is missing.
    """


class NotSupportedError(Exception):
    """
    Exception raised when a feature is not supported.
    """

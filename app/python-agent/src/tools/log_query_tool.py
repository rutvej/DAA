import os
import json
from datetime import datetime, timedelta
from typing import List, Optional
from langchain.tools import tool
from pydantic.v1 import BaseModel, Field
from sqlalchemy import create_engine, Column, String, DateTime, Text
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./test.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class LogModel(Base):
    __tablename__ = "logs"
    id = Column(String, primary_key=True)
    app_name = Column(String)
    content = Column(Text)
    status = Column(String)
    timestamp = Column(DateTime)
    exception_type = Column(String, nullable=True)
    trace_id = Column(String, nullable=True)
    correlation_id = Column(String, nullable=True)

class QueryCorrelatedLogsInput(BaseModel):
    data: str = Field(description="A JSON string containing optional 'trace_id', optional 'timestamp' (ISO format string), optional 'window_seconds' (default 300), and optional 'app_name'. Example: {\"trace_id\": \"trace-abc-123\", \"window_seconds\": 300}")

@tool(args_schema=QueryCorrelatedLogsInput)
def query_correlated_logs(data: str) -> str:
    """Queries multi-service logs correlated by OpenTelemetry trace_id or within a +/- time window across all microservices."""
    try:
        input_data = json.loads(data)
        trace_id = input_data.get("trace_id")
        timestamp_str = input_data.get("timestamp")
        window_sec = int(input_data.get("window_seconds", 300))
        app_name = input_data.get("app_name")

        db = SessionLocal()
        try:
            logs = []
            if trace_id:
                logs = db.query(LogModel).filter(LogModel.trace_id == trace_id).order_by(LogModel.timestamp.asc()).all()

            if not logs and timestamp_str:
                try:
                    if timestamp_str.endswith("Z"):
                        timestamp_str = timestamp_str[:-1]
                    target_time = datetime.fromisoformat(timestamp_str)
                    start_time = target_time - timedelta(seconds=window_sec)
                    end_time = target_time + timedelta(seconds=window_sec)
                    
                    query = db.query(LogModel).filter(LogModel.timestamp >= start_time, LogModel.timestamp <= end_time)
                    if app_name:
                        query = query.filter(LogModel.app_name == app_name)
                    logs = query.order_by(LogModel.timestamp.asc()).limit(100).all()
                except Exception as parse_err:
                    return f"Error parsing timestamp '{timestamp_str}': {parse_err}"

            if not logs and app_name:
                logs = db.query(LogModel).filter(LogModel.app_name == app_name).order_by(LogModel.timestamp.desc()).limit(20).all()
                logs.reverse()

            if not logs:
                return "No correlated logs found matching the specified trace_id or time window."

            output = [f"=== Correlated Logs ({len(logs)} entries) ==="]
            for l in logs:
                ts = l.timestamp.isoformat() if l.timestamp else "N/A"
                tid = f" [TraceID: {l.trace_id}]" if l.trace_id else ""
                output.append(f"[{ts}] ({l.app_name}){tid}: {l.content}")

            return "\n".join(output)
        finally:
            db.close()
    except json.JSONDecodeError:
        return "Error: Invalid JSON string."
    except Exception as e:
        return f"Error querying correlated logs: {e}"

from sqlalchemy import create_engine, Column, String, DateTime, Text, Boolean, ForeignKey, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
import uuid

def generate_uuid():
    return str(uuid.uuid4())

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./test.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    username = Column(String, unique=True, index=True)
    passwordHash = Column(String)
    role = Column(String, default="User")

class Log(Base):
    __tablename__ = "logs"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    userId = Column(String, ForeignKey("users.id"))
    app_name = Column(String)
    content = Column(Text)
    status = Column(String, default="Pending")
    timestamp = Column(DateTime, default=datetime.utcnow)
    exception_type = Column(String, nullable=True)
    trace_id = Column(String, nullable=True, index=True)
    correlation_id = Column(String, nullable=True)
    metadata_json = Column(Text, nullable=True)

    user = relationship("User")

class Fix(Base):
    __tablename__ = "fixes"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    logId = Column(String, ForeignKey("logs.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    generatedFix = Column(Text)
    postmortem = Column(Text)
    isApproved = Column(Boolean, default=False)
    status = Column(String, default="Pending")
    pull_request_url = Column(String)

    log = relationship("Log")

class ProjectConnection(Base):
    __tablename__ = "project_connections"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    app_name = Column(String, unique=True, index=True)
    repo_provider = Column(String, default="gitlab")  # "github", "gitlab"
    repo_url = Column(String)
    repo_token = Column(String)
    jira_url = Column(String)
    jira_token = Column(String)
    jira_project_key = Column(String)

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    app_name = Column(String, index=True)
    summary = Column(String)
    description = Column(Text)
    severity = Column(String, default="warning")  # "info", "warning", "critical"
    status = Column(String, default="firing")  # "firing", "resolved"
    timestamp = Column(DateTime, default=datetime.utcnow)

class Application(Base):
    __tablename__ = "applications"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(String, nullable=True)
    language = Column(String, nullable=True)
    repository_url = Column(String, nullable=True)
    spec_file_path = Column(String, nullable=True)
    team_owner = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    escalation_policies = relationship("EscalationPolicy", back_populates="application")

class EscalationPolicy(Base):
    __tablename__ = "escalation_policies"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    application_id = Column(String, ForeignKey("applications.id"))
    rule_type = Column(String)  # "error_rate_threshold", "severity_immediate", "external_webhook", "error_rate_spike"
    condition_value = Column(Integer, nullable=True)
    window_seconds = Column(Integer, default=120)
    severity_keywords = Column(Text, nullable=True)  # JSON string e.g. '["FATAL", "OOMKill"]'
    cooldown_minutes = Column(Integer, default=30)
    is_active = Column(Boolean, default=True)

    application = relationship("Application", back_populates="escalation_policies")

class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    fingerprint = Column(String, index=True, nullable=False)
    app_name = Column(String, index=True, nullable=False)
    status = Column(String, default="investigating")  # "investigating", "pr_open", "ticket_created", "cooldown", "resolved", "human_required"
    occurrence_count = Column(Integer, default=1)
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)
    cooldown_until = Column(DateTime, nullable=True)
    agent_attempts = Column(Integer, default=0)
    root_cause_summary = Column(Text, nullable=True)
    confidence_score = Column(Integer, nullable=True)
    pr_url = Column(String, nullable=True)
    ticket_url = Column(String, nullable=True)
    postmortem_md = Column(Text, nullable=True)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



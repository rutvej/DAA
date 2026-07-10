from sqlalchemy import create_engine, Column, String, DateTime, Text, Boolean, ForeignKey, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
import uuid

def generate_uuid():
    return str(uuid.uuid4())

DAA_DB_PROVIDER = os.environ.get("DAA_DB_PROVIDER")
if not DAA_DB_PROVIDER:
    db_url = os.environ.get("DATABASE_URL", "")
    if "postgresql" in db_url or "postgres" in db_url:
        DAA_DB_PROVIDER = "postgres"
    else:
        DAA_DB_PROVIDER = "sqlite"
else:
    DAA_DB_PROVIDER = DAA_DB_PROVIDER.lower()

default_policy = "true" if DAA_DB_PROVIDER in ("sqlite", "postgres", "internal-postgres", "external-postgres") else "false"
default_auth = "true" if DAA_DB_PROVIDER in ("sqlite", "postgres", "internal-postgres", "external-postgres") else "false"

DAA_POLICY_ENABLED = os.environ.get("DAA_POLICY_ENABLED", default_policy).lower() == "true"
DAA_AUTH_ENABLED = os.environ.get("DAA_AUTH_ENABLED", default_auth).lower() == "true"

class MockQuery:
    def __init__(self, model_class=None, data=None):
        self.model_class = model_class
        self.data = data or []

    def filter(self, *args, **kwargs):
        return self

    def filter_by(self, *args, **kwargs):
        return self

    def join(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def offset(self, *args, **kwargs):
        return self

    def first(self):
        return None

    def all(self):
        return []

    def count(self):
        return 0

class MockSession:
    def __init__(self, *args, **kwargs):
        pass

    def query(self, model_class):
        return MockQuery(model_class)

    def add(self, instance):
        import uuid
        from datetime import datetime
        if hasattr(instance, "id") and not getattr(instance, "id"):
            instance.id = str(uuid.uuid4())
        if hasattr(instance, "timestamp") and not getattr(instance, "timestamp"):
            instance.timestamp = datetime.utcnow()
        if hasattr(instance, "created_at") and not getattr(instance, "created_at"):
            instance.created_at = datetime.utcnow()
        if hasattr(instance, "first_seen_at") and not getattr(instance, "first_seen_at"):
            instance.first_seen_at = datetime.utcnow()
        if hasattr(instance, "last_seen_at") and not getattr(instance, "last_seen_at"):
            instance.last_seen_at = datetime.utcnow()

    def delete(self, instance):
        pass

    def commit(self):
        pass

    def rollback(self):
        pass

    def refresh(self, instance):
        pass

    def close(self):
        pass

    def begin(self):
        class MockTransaction:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass
        return MockTransaction()

if DAA_DB_PROVIDER in ("none", "internal-redis", "external-redis"):
    engine = None
    SessionLocal = MockSession
elif DAA_DB_PROVIDER == "sqlite":
    DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./daa.db")
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": 30.0}
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Configure SQLite WAL mode
    from sqlalchemy import event
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()
else:
    DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://daa:daa_pass@localhost:5432/daa_db")
    engine = create_engine(DATABASE_URL)
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
    allowed_ip = Column(String, nullable=True)
    token = Column(String, nullable=True)
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


def run_db_migrations(engine):
    from sqlalchemy import text, inspect
    with engine.begin() as conn:
        try:
            inspector = inspect(engine)
            if 'applications' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('applications')]
                if 'allowed_ip' not in columns:
                    print("Adding column 'allowed_ip' to applications table...")
                    conn.execute(text("ALTER TABLE applications ADD COLUMN allowed_ip VARCHAR(255) NULL"))
                if 'token' not in columns:
                    print("Adding column 'token' to applications table...")
                    conn.execute(text("ALTER TABLE applications ADD COLUMN token TEXT NULL"))
        except Exception as e:
            print(f"Error checking/running database migrations: {e}")



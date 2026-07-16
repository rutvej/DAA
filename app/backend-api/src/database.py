import os
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker


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

default_policy = (
    "true"
    if DAA_DB_PROVIDER
    in ("sqlite", "postgres", "internal-postgres", "external-postgres", "redis", "internal-redis", "external-redis", "upstash")
    else "false"
)
default_auth = (
    "true"
    if DAA_DB_PROVIDER
    in ("sqlite", "postgres", "internal-postgres", "external-postgres", "redis", "internal-redis", "external-redis", "upstash")
    else "false"
)

DAA_POLICY_ENABLED = (
    os.environ.get("DAA_POLICY_ENABLED", default_policy).lower() == "true"
)
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
        if hasattr(instance, "first_seen_at") and not getattr(
            instance, "first_seen_at"
        ):
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


if DAA_DB_PROVIDER == "none":
    engine = None
    SessionLocal = MockSession
elif DAA_DB_PROVIDER in ("redis", "internal-redis", "external-redis", "upstash"):
    try:
        from redis_storage import StatelessRedisSession
    except ImportError:
        import sys
        _repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        if _repo_root not in sys.path:
            sys.path.insert(0, _repo_root)
        from app.backend_api.src.redis_storage import StatelessRedisSession
    engine = None
    SessionLocal = StatelessRedisSession
elif DAA_DB_PROVIDER == "sqlite":
    if "K_SERVICE" in os.environ:
        import logging

        logging.warning(
            "SQLite is fundamentally incompatible with bucket-mounted storage (GCS FUSE) "
            "due to lack of advisory POSIX locking and mmap support. This will cause "
            "database corruption or lock errors on Cloud Run. "
            "Please migrate to an external Postgres database, or libSQL/Turso."
        )

    DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./daa.db")
    try:
        from common.db_factory import create_unified_engine
    except ImportError:
        import sys
        _repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        if _repo_root not in sys.path:
            sys.path.insert(0, _repo_root)
        from app.common.db_factory import create_unified_engine

    engine = create_unified_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Configure SQLite WAL mode (disabled on Cloud Run and ephemeral/cloud storage to prevent mmap crashes)
    if (
        "K_SERVICE" not in os.environ
        and os.environ.get("DAA_DISABLE_WAL", "false").lower() != "true"
        and not DATABASE_URL.startswith("sqlite:////tmp")
    ):

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

elif DAA_DB_PROVIDER in ("postgres", "postgresql", "internal-postgres", "external-postgres"):
    DATABASE_URL = os.environ.get(
        "DATABASE_URL", "postgresql://daa:daa_pass@localhost:5432/daa_db"
    )
    try:
        from common.db_factory import create_unified_engine
    except ImportError:
        import sys
        _repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        if _repo_root not in sys.path:
            sys.path.insert(0, _repo_root)
        from app.common.db_factory import create_unified_engine

    engine = create_unified_engine(DATABASE_URL, pool_size=20, max_overflow=40)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
else:
    raise RuntimeError(
        f"Invalid DAA_DB_PROVIDER configured: '{DAA_DB_PROVIDER}'. Valid choices: sqlite, postgres, redis, upstash, or none (stateless/serverless mode)."
    )

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
    rule_type = Column(
        String
    )  # "error_rate_threshold", "severity_immediate", "external_webhook", "error_rate_spike"
    condition_value = Column(Integer, nullable=True)
    window_seconds = Column(Integer, default=120)
    severity_keywords = Column(
        Text, nullable=True
    )  # JSON string e.g. '["FATAL", "OOMKill"]'
    cooldown_minutes = Column(Integer, default=30)
    is_active = Column(Boolean, default=True)

    application = relationship("Application", back_populates="escalation_policies")


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    fingerprint = Column(String, index=True, nullable=False)
    app_name = Column(String, index=True, nullable=False)
    status = Column(
        String, default="investigating"
    )  # "investigating", "pr_open", "ticket_created", "cooldown", "resolved", "human_required"
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
    active_lock = Column(String, default="active")

    __table_args__ = (
        UniqueConstraint(
            "fingerprint", "active_lock", name="uq_incident_fingerprint_active_lock"
        ),
    )


@event.listens_for(Incident.status, "set")
def on_incident_status_change(target, value, oldvalue, initiator):
    active_statuses = [
        "investigating",
        "pr_open",
        "ticket_created",
        "cooldown",
        "fix_proposed",
        "processing",
        "awaiting_approval",
        "fix_open",
    ]
    if value not in active_statuses:
        target.active_lock = target.id or str(uuid.uuid4())
    else:
        target.active_lock = "active"


def get_db():
    if SessionLocal is None:
        raise RuntimeError("Valid database provider required (sqlite, postgres, redis, upstash, or none for stateless mode)")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_db_migrations(engine):
    from sqlalchemy import inspect, text

    with engine.begin() as conn:
        try:
            inspector = inspect(engine)
            if "applications" in inspector.get_table_names():
                columns = [col["name"] for col in inspector.get_columns("applications")]
                if "allowed_ip" not in columns:
                    print("Adding column 'allowed_ip' to applications table...")
                    conn.execute(
                        text(
                            "ALTER TABLE applications ADD COLUMN allowed_ip VARCHAR(255) NULL"
                        )
                    )
                if "token" not in columns:
                    print("Adding column 'token' to applications table...")
                    conn.execute(
                        text("ALTER TABLE applications ADD COLUMN token TEXT NULL")
                    )

            if "incidents" in inspector.get_table_names():
                columns = [col["name"] for col in inspector.get_columns("incidents")]
                if "active_lock" not in columns:
                    print("Adding column 'active_lock' to incidents table...")
                    conn.execute(
                        text(
                            "ALTER TABLE incidents ADD COLUMN active_lock VARCHAR(255) DEFAULT 'active'"
                        )
                    )
                    conn.execute(
                        text(
                            "CREATE UNIQUE INDEX IF NOT EXISTS uq_incident_fingerprint_active_lock ON incidents(fingerprint, active_lock)"
                        )
                    )
        except Exception as e:
            print(f"Error checking/running database migrations: {e}")

    # When auth is disabled, get_current_user() returns a synthetic user with
    # id="admin-id".  The logs table has a FK → users.id, so any INSERT with
    # userId="admin-id" fails with ForeignKeyViolation unless that row exists.
    # Seed it here so the constraint is always satisfied regardless of auth mode.
    if not DAA_AUTH_ENABLED:
        try:
            with engine.begin() as conn:
                # Use INSERT … ON CONFLICT DO NOTHING (works for both Postgres and SQLite)
                conn.execute(
                    text(
                        'INSERT INTO users (id, username, "passwordHash", role) '
                        "VALUES ('admin-id', 'admin', 'disabled', 'admin') "
                        "ON CONFLICT (id) DO NOTHING"
                    )
                )
                print("Seeded synthetic admin-id user (auth disabled).")
        except Exception as e:
            print(f"Warning: could not seed admin-id user: {e}")

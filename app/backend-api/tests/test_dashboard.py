from fastapi.testclient import TestClient
from src.main import app
from src.database import get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def setup():
    from src.database import Base

    Base.metadata.create_all(bind=engine)


def teardown():
    from src.database import Base

    Base.metadata.drop_all(bind=engine)


def test_dashboard_endpoint():
    setup()

    # Check the dashboard endpoint
    res = client.get("/dashboard")
    assert res.status_code == 200
    data = res.json()
    assert "active_incidents" in data
    assert "total_incidents" in data
    assert "resolved_incidents" in data
    assert "fix_rate_percent" in data
    assert "logs_last_24h" in data
    assert "total_logs" in data
    assert "open_prs" in data
    assert "active_alerts" in data
    assert "recent_incidents" in data

    assert data["active_incidents"] == 0
    assert data["total_incidents"] == 0
    assert data["fix_rate_percent"] == 0.0

    teardown()

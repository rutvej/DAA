from fastapi.testclient import TestClient
from main import app
from database import get_db, Log
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid
from routers.auth import User
from unittest.mock import patch

DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

def override_get_current_user():
    return User(username="testuser")

app.dependency_overrides[get_db] = override_get_db
from routers.logs import get_current_user
app.dependency_overrides[get_current_user] = override_get_current_user

client = TestClient(app)

def setup():
    from database import Base
    Base.metadata.create_all(bind=engine)

def teardown():
    from database import Base
    Base.metadata.drop_all(bind=engine)

@patch('pika.BlockingConnection')
def test_submit_log(mock_pika):
    setup()
    response = client.post("/logs/", json={"content": "test log content"})
    assert response.status_code == 202
    assert "logId" in response.json()
    assert "status" in response.json()
    teardown()

@patch('pika.BlockingConnection')
def test_get_logs(mock_pika):
    setup()
    client.post("/logs/", json={"content": "test log content"})
    response = client.get("/logs/")
    assert response.status_code == 200
    assert len(response.json()) == 1
    teardown()

@patch('pika.BlockingConnection')
def test_get_log(mock_pika):
    setup()
    post_response = client.post("/logs/", json={"content": "test log content"})
    log_id = post_response.json()["logId"]
    get_response = client.get(f"/logs/{log_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == log_id
    teardown()

def test_get_nonexistent_log():
    setup()
    response = client.get(f"/logs/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Log not found"}
    teardown()

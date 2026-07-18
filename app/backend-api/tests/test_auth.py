from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database import get_db
from src.main import app

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


def test_register_user():
    setup()
    response = client.post(
        "/auth/register", json={"username": "testuser", "password": "testpassword"}
    )
    assert response.status_code == 200
    assert response.json() == {"message": "User registered successfully"}
    teardown()


def test_register_existing_user():
    setup()
    client.post(
        "/auth/register", json={"username": "testuser", "password": "testpassword"}
    )
    response = client.post(
        "/auth/register", json={"username": "testuser", "password": "testpassword"}
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Username already registered"}
    teardown()


def test_login_user():
    setup()
    client.post(
        "/auth/register", json={"username": "testuser", "password": "testpassword"}
    )
    response = client.post(
        "/auth/login", json={"username": "testuser", "password": "testpassword"}
    )
    assert response.status_code == 200
    assert "token" in response.json()
    teardown()


def test_login_incorrect_password():
    setup()
    client.post(
        "/auth/register", json={"username": "testuser", "password": "testpassword"}
    )
    response = client.post(
        "/auth/login", json={"username": "testuser", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect username or password"}
    teardown()


from unittest.mock import patch  # noqa: E402


@patch("src.routers.auth.DAA_DB_PROVIDER", "none")
def test_stateless_auth_mode_disabled():
    response_reg = client.post(
        "/auth/register", json={"username": "testuser", "password": "testpassword"}
    )
    assert response_reg.status_code == 503
    assert "stateless/serverless mode" in response_reg.json()["detail"]

    response_log = client.post(
        "/auth/login", json={"username": "testuser", "password": "testpassword"}
    )
    assert response_log.status_code == 503
    assert "stateless/serverless mode" in response_log.json()["detail"]

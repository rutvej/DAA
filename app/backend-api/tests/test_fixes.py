from fastapi.testclient import TestClient
from src.main import app
from src.database import get_db, Fix, Log
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid

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

def test_get_fix():
    setup()
    db = TestingSessionLocal()
    log_id = str(uuid.uuid4())
    db.add(Log(id=log_id, content="test log content"))
    fix_id = str(uuid.uuid4())
    db.add(Fix(id=fix_id, logId=log_id, generatedFix="test fix"))
    db.commit()
    db.close()

    response = client.get(f"/fixes/{fix_id}")
    assert response.status_code == 200
    assert response.json()["id"] == fix_id
    teardown()

def test_get_nonexistent_fix():
    setup()
    response = client.get(f"/fixes/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Fix not found"}
    teardown()

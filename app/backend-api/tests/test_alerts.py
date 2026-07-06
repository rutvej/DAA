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

def test_alerts_crud():
    setup()
    
    # 1. Create alert
    res = client.post("/alerts/", json={
        "app_name": "checkout-service",
        "summary": "High CPU utilization",
        "description": "CPU > 90%",
        "severity": "critical"
    })
    assert res.status_code == 201
    assert res.json()["app_name"] == "checkout-service"
    assert res.json()["status"] == "firing"
    
    # 2. Get alerts
    res_get = client.get("/alerts/")
    assert res_get.status_code == 200
    assert len(res_get.json()) == 1
    assert res_get.json()[0]["summary"] == "High CPU utilization"
    
    teardown()

def test_alertmanager_webhook():
    setup()
    
    # Send webhook payload
    res = client.post("/alerts/webhook/alertmanager", json={
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "RedisInstanceDown",
                    "app_name": "checkout-service",
                    "severity": "critical"
                },
                "annotations": {
                    "summary": "Redis is down on production",
                    "description": "Connection pool exhausted to redis-master:6379"
                }
            }
        ]
    })
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "success"
    assert data["alerts_created"] == 1
    assert data["details"][0]["app_name"] == "checkout-service"
    assert data["details"][0]["summary"] == "Redis is down on production"
    
    # Get active alerts
    res_get = client.get("/alerts/")
    assert res_get.status_code == 200
    assert len(res_get.json()) == 1
    assert res_get.json()[0]["app_name"] == "checkout-service"
    assert res_get.json()[0]["summary"] == "Redis is down on production"
    
    teardown()

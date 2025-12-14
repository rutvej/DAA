from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
def health_check():
    return [{"serviceName": "backend-api", "status": "ok"}]

@router.get("/{id}")
def get_status(id: str):
    return {"status": "Pending"}
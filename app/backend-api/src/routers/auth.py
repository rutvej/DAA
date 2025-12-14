from fastapi import APIRouter

router = APIRouter()

@router.post("/register")
def register_user():
    return {"message": "User registered successfully"}

@router.post("/login")
def login_user():
    return {"token": "dummy-jwt-token"}
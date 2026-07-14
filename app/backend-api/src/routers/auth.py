import os
import time

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import DAA_AUTH_ENABLED, Application, User, get_db

router = APIRouter()

SECRET_KEY = os.environ.get("SECRET_KEY", "a_secret_key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserCreate(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


@router.post("/register")
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    hashed_password = pwd_context.hash(user.password)
    db_user = User(username=user.username, passwordHash=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"message": "User registered successfully"}


@router.post("/login")
def login_user(user: UserLogin, db: Session = Depends(get_db)):
    if not DAA_AUTH_ENABLED:
        return {"token": "dummy_token"}
    db_user = db.query(User).filter(User.username == user.username).first()
    if not db_user or not pwd_context.verify(user.password, db_user.passwordHash):
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    to_encode = {
        "sub": db_user.username,
        "id": db_user.id,
        "exp": time.time() + ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return {"token": encoded_jwt}


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def get_current_user(
    request: Request, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    if not DAA_AUTH_ENABLED:
        iam_user = request.headers.get("X-Forwarded-User") or request.headers.get("X-DAA-User")
        iam_role = request.headers.get("X-Forwarded-Role") or request.headers.get("X-DAA-Role")
        if iam_user:
            return {
                "username": iam_user,
                "id": f"iam-{iam_user}",
                "role": iam_role if iam_role in ("admin", "user", "readonly") else os.getenv("DAA_DEFAULT_ROLE", "user")
            }
        default_role = os.getenv("DAA_DEFAULT_ROLE_WHEN_NO_AUTH", "readonly")
        return {"username": "anonymous", "id": "anonymous-id", "role": default_role}

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        role = payload.get("role")
        if role == "application":
            app_name = payload.get("sub")
            app_id = payload.get("id")
            if not app_name or not app_id:
                raise HTTPException(
                    status_code=401, detail="Invalid application credentials"
                )

            # Fetch application to verify it exists and check allowed_ip
            app_db = db.query(Application).filter(Application.id == app_id).first()
            if not app_db:
                raise HTTPException(status_code=401, detail="Application not found")

            # Check allowed IP if configured
            if app_db.allowed_ip:
                client_ip = request.headers.get("x-forwarded-for")
                if client_ip:
                    client_ip = client_ip.split(",")[0].strip()
                else:
                    client_ip = request.client.host if request.client else None

                # Check loopback addresses and direct match
                loopbacks = {
                    "127.0.0.1",
                    "localhost",
                    "::1",
                    "test-app",
                    "checkout-service",
                    "backend-api",
                }
                if client_ip != app_db.allowed_ip and not (
                    client_ip in loopbacks and app_db.allowed_ip in loopbacks
                ):
                    raise HTTPException(
                        status_code=403,
                        detail=f"IP address {client_ip} not allowed for application {app_name}",
                    )

            return {"username": app_name, "id": app_id, "role": "application"}

        # Standard user
        username: str = payload.get("sub")
        user_id: str = payload.get("id")
        if username is None or user_id is None:
            raise HTTPException(
                status_code=403, detail="Invalid authentication credentials"
            )
        return {"username": username, "id": user_id, "role": "user"}
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=401, detail="Invalid authentication credentials"
        )

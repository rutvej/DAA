from sqlalchemy import create_engine, Column, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
import uuid

def generate_uuid():
    return str(uuid.uuid4())

DATABASE_URL = os.environ.get("DATABASE_URL")

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

    user = relationship("User")

class Fix(Base):
    __tablename__ = "fixes"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    logId = Column(String, ForeignKey("logs.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    generatedFix = Column(Text)
    isApproved = Column(Boolean, default=False)

    log = relationship("Log")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


import time
import base64
import json
import hmac
import hashlib
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Dict, Any

from backend.database.database import get_db
from backend.database.models import UserDB

router = APIRouter(prefix="/api/v1/auth", tags=["User Authentication"])

SECRET_KEY = "vignan-university-emergency-intelligence-secret-key"

class LoginRequest(BaseModel):
    username: str
    password: str

class SignupRequest(BaseModel):
    username: str
    password: str
    role: str = "operator"  # "operator" | "student"
    full_name: str = ""

def create_token(payload: dict) -> str:
    # Token valid for 24 hours
    payload["exp"] = time.time() + 86400
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    signature = hmac.new(SECRET_KEY.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"

def verify_token(token: str) -> bool:
    try:
        payload_b64, signature = token.split(".")
        expected_sig = hmac.new(SECRET_KEY.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return False
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode()).decode())
        if payload.get("exp", 0) < time.time():
            return False
        return True
    except Exception:
        return False

@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Authenticates a user and returns a signed payload token."""
    user = db.query(UserDB).filter(UserDB.username == payload.username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid username or password."
        )

    hashed = hashlib.sha256(payload.password.encode()).hexdigest()
    if user.hashed_password != hashed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid username or password."
        )

    token = create_token({
        "username": user.username,
        "role": user.role,
        "full_name": user.full_name
    })

    return {
        "token": token,
        "user": {
            "username": user.username,
            "role": user.role,
            "full_name": user.full_name
        }
    }

@router.post("/signup")
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    """Registers a new campus user (hashing password via SHA-256)."""
    # 1. Check duplicate username
    existing = db.query(UserDB).filter(UserDB.username == payload.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username is already taken."
        )

    # 2. Hash password and save user
    hashed = hashlib.sha256(payload.password.encode()).hexdigest()
    new_user = UserDB(
        username=payload.username,
        hashed_password=hashed,
        role=payload.role,
        full_name=payload.full_name
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "status": "success",
        "username": new_user.username,
        "role": new_user.role,
        "full_name": new_user.full_name
    }

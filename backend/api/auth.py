"""Authentication API for AITAM Disaster Response AI.

Endpoints (all under /api/v1/auth):

  Legacy / command-center
    POST /login              username + password        -> command/admin token
    POST /signup             username + password         -> citizen (role clamped)

  Citizen / user portal (Part 4: email + phone identity)
    POST /user/register      email + phone + full_name   -> community token
    POST /user/login         email + phone               -> user token

  Department staff (Part 5: email + password + department)
    POST /department/login   email + password + dept     -> department token
    POST /department/register email + password + dept     -> admin-only provisioning

  Session
    GET  /me                 (bearer token)              -> current principal

Token creation / verification / password hashing all delegate to
backend.services.auth_service so there is exactly one implementation. The RBAC
enforcement lives in backend.api.deps.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, field_validator

from backend.database.database import get_db
from backend.database.models import UserDB, DepartmentUserDB, DepartmentDB
from backend.api.deps import get_current_principal, get_optional_principal
from backend.services.auth_service import (
    Principal,
    PRIVILEGED_ROLES,
    DEPARTMENT_ROLES,
    ROLE_USER,
    ROLE_DEPARTMENT,
    create_token,
    decode_token,  # re-exported for backward compatibility
    verify_token,  # re-exported for backward compatibility
    hash_password,
    verify_password,
    token_payload_for_user,
    token_payload_for_department_user,
)
from backend.services.departments import (
    normalize_department,
    is_valid_department,
    DEPARTMENT_LABELS,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

# Backward-compatible module-level secret (some tooling references it).
from backend.config import settings  # noqa: E402
SECRET_KEY = settings.AUTH_SECRET_KEY


# --------------------------------------------------------------------------
# Request models
# --------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


class SignupRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field(default="user", max_length=30)  # requested role; clamped server-side (see signup)
    full_name: str = Field(default="", max_length=100)


class UserRegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=120)
    phone: str = Field(..., min_length=7, max_length=30)
    full_name: str = Field(default="", max_length=100)


class UserLoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=120)
    phone: str = Field(..., min_length=7, max_length=30)


class DepartmentLoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=120)
    password: str = Field(..., min_length=1, max_length=128)
    department: str = Field(..., min_length=2, max_length=50)


class DepartmentRegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=120)
    password: str = Field(..., min_length=8, max_length=128)
    department: str = Field(..., min_length=2, max_length=50)
    full_name: str = Field(default="", max_length=100)
    role: str = Field(default=ROLE_DEPARTMENT, max_length=30)


# --------------------------------------------------------------------------
# Legacy / command-center
# --------------------------------------------------------------------------

@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate an operator/admin (or any username account) by password."""
    user = db.query(UserDB).filter(UserDB.username == payload.username).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid username or password.",
        )
    if (getattr(user, "status", "active") or "active") != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is suspended.")

    token = create_token(token_payload_for_user(user))
    return {
        "token": token,
        "user": {
            "username": user.username,
            "role": user.role,
            "full_name": user.full_name,
            "email": getattr(user, "email", None),
            "department": getattr(user, "department", None),
        },
    }


@router.post("/signup")
def signup(
    payload: SignupRequest,
    db: Session = Depends(get_db),
    actor: Optional[Principal] = Depends(get_optional_principal),
):
    """Register a new account.

    Security: the role is clamped to a plain citizen ("user") unless the caller
    is an authenticated admin/operator. This closes the previous privilege-
    escalation hole where anyone could self-assign the operator role.
    """
    requested_role = (payload.role or ROLE_USER).strip().lower()
    privileged_or_dept = requested_role in PRIVILEGED_ROLES or requested_role in DEPARTMENT_ROLES
    if privileged_or_dept and not (actor and actor.is_privileged):
        # Silently downgrade rather than leaking which roles exist.
        requested_role = ROLE_USER

    existing = db.query(UserDB).filter(UserDB.username == payload.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username is already taken.",
        )

    new_user = UserDB(
        username=payload.username,
        hashed_password=hash_password(payload.password),
        role=requested_role,
        full_name=payload.full_name,
        status="active",
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "status": "success",
        "username": new_user.username,
        "role": new_user.role,
        "full_name": new_user.full_name,
    }


# --------------------------------------------------------------------------
# Citizen / user portal — identity is email + phone
# --------------------------------------------------------------------------

def _issue_user_token(user: UserDB) -> dict:
    token = create_token(token_payload_for_user(user))
    return {
        "token": token,
        "user": {
            "id": str(user.id),
            "role": user.role,
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
        },
    }


@router.post("/user/register")
def user_register(payload: UserRegisterRequest, db: Session = Depends(get_db)):
    """Register a community member (email + phone). Returns a session token."""
    email = payload.email.strip().lower()
    phone = payload.phone.strip()
    if not email or not phone:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email and phone are required.")

    existing = db.query(UserDB).filter(UserDB.email == email).first()
    if existing:
        # Already registered — verify phone and log them in instead of erroring.
        if (existing.phone or "") != phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email already exists.",
            )
        return _issue_user_token(existing)

    # username must be unique & non-null; use the email as the username.
    if db.query(UserDB).filter(UserDB.username == email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    new_user = UserDB(
        username=email,
        email=email,
        phone=phone,
        # No password for citizens; store a derived hash so the column is non-null.
        hashed_password=hash_password(f"phone:{phone}"),
        role=ROLE_USER,
        full_name=payload.full_name,
        status="active",
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return _issue_user_token(new_user)


@router.post("/user/login")
def user_login(payload: UserLoginRequest, db: Session = Depends(get_db)):
    """Log a citizen in with email + phone (no password)."""
    email = payload.email.strip().lower()
    phone = payload.phone.strip()
    user = db.query(UserDB).filter(UserDB.email == email, UserDB.role == ROLE_USER).first()
    if not user or (user.phone or "") != phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No account found for that email and phone.",
        )
    if (getattr(user, "status", "active") or "active") != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is suspended.")
    return _issue_user_token(user)


# --------------------------------------------------------------------------
# Department staff — email + password + department
# --------------------------------------------------------------------------

@router.post("/department/login")
def department_login(payload: DepartmentLoginRequest, db: Session = Depends(get_db)):
    """Authenticate department staff. The department must match the account."""
    email = payload.email.strip().lower()
    dept = normalize_department(payload.department)
    if dept is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown department.")

    staff = db.query(DepartmentUserDB).filter(DepartmentUserDB.email == email).first()
    if not staff or not verify_password(payload.password, staff.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email or password.",
        )
    if normalize_department(staff.department) != dept:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not registered to that department.",
        )
    department_row = db.query(DepartmentDB).filter(DepartmentDB.code == dept).first()
    if department_row is not None and department_row.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This department is inactive.")
    if (staff.status or "active") != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is suspended.")

    token = create_token(token_payload_for_department_user(staff))
    return {
        "token": token,
        "user": {
            "id": str(staff.id),
            "role": staff.role,
            "full_name": staff.full_name,
            "email": staff.email,
            "department": normalize_department(staff.department),
            "department_label": DEPARTMENT_LABELS.get(normalize_department(staff.department), ""),
        },
    }


@router.post("/department/register")
def department_register(
    payload: DepartmentRegisterRequest,
    db: Session = Depends(get_db),
    admin: Principal = Depends(get_current_principal),
):
    """Provision a department staff account. Admin/operator only."""
    if not admin.is_privileged:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an administrator can create department accounts.",
        )
    email = payload.email.strip().lower()
    dept = normalize_department(payload.department)
    if dept is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown department.")
    department_row = db.query(DepartmentDB).filter(DepartmentDB.code == dept).first()
    if department_row is not None and department_row.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Department is not active.")
    if db.query(DepartmentUserDB).filter(DepartmentUserDB.email == email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered.")

    role = payload.role if payload.role in DEPARTMENT_ROLES else ROLE_DEPARTMENT
    staff = DepartmentUserDB(
        email=email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        department=dept,
        role=role,
        status="active",
    )
    db.add(staff)
    db.commit()
    db.refresh(staff)
    return {
        "status": "success",
        "id": str(staff.id),
        "email": staff.email,
        "department": dept,
        "role": staff.role,
    }


# --------------------------------------------------------------------------
# Session introspection
# --------------------------------------------------------------------------

@router.get("/me")
def me(principal: Principal = Depends(get_current_principal)):
    """Return the currently authenticated principal (verified server-side)."""
    data = principal.to_public_dict()
    if principal.department:
        data["department_label"] = DEPARTMENT_LABELS.get(principal.department, "")
    return data

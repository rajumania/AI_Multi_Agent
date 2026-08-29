"""Authoritative AITAM organization and department administration API.

This is deliberately additive to the existing authentication architecture. The
existing ``UserDB`` and ``DepartmentUserDB`` rows remain the identity source;
this module persists the organization registry and provides admin-only CRUD
around those rows without ever returning password material.
"""

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.api.deps import require_privileged
from backend.database.database import get_db
from backend.database.models import (
    CampusResourceDB,
    DepartmentDB,
    DepartmentResponseDB,
    DepartmentUserDB,
    IncidentDB,
    OrganizationDB,
    UserDB,
)
from backend.services.auth_service import Principal, ROLE_DEPARTMENT, ROLE_DEPARTMENT_HEAD, hash_password
from backend.services.audit_service import audit_service
from backend.services.departments import DEPARTMENT_LABELS, DEPARTMENTS, is_valid_department, normalize_department, register_department

router = APIRouter(prefix="/api/v1/organization", tags=["Organization Administration"])


class DepartmentCreatePayload(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=120)
    department_type: str = Field(..., min_length=2, max_length=80)
    description: Optional[str] = None


class DepartmentUpdatePayload(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    department_type: Optional[str] = Field(default=None, min_length=2, max_length=80)
    description: Optional[str] = None
    status: Optional[str] = None


class AccountCreatePayload(BaseModel):
    email: str = Field(..., min_length=5, max_length=120)
    password: str = Field(..., min_length=8, max_length=200)
    full_name: str = Field(..., min_length=2, max_length=100)
    role: str = ROLE_DEPARTMENT


class AccountUpdatePayload(BaseModel):
    password: Optional[str] = Field(default=None, min_length=8, max_length=200)
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    department: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None


class UserDepartmentPayload(BaseModel):
    department: Optional[str] = None


def _now():
    return datetime.now(timezone.utc)


def _org(db: Session) -> OrganizationDB:
    row = db.query(OrganizationDB).filter(OrganizationDB.code == "AITAM").first()
    if row is None:
        raise HTTPException(status_code=503, detail="AITAM organization registry is not initialized.")
    return row


def _department(db: Session, code: str) -> DepartmentDB:
    normalized = normalize_department(code)
    row = db.query(DepartmentDB).filter(DepartmentDB.code == (normalized or str(code).strip().upper())).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Department not found.")
    return row


def _account_public(row: DepartmentUserDB) -> dict:
    return {
        "id": str(row.id),
        "email": row.email,
        "full_name": row.full_name,
        "department": row.department,
        "role": row.role,
        "status": row.status,
        "created_at": row.created_at,
    }


def _actor(admin: Principal) -> str:
    return admin.full_name or admin.username or admin.email or str(admin.id)


def _department_public(db: Session, row: DepartmentDB) -> dict:
    active_statuses = {"reported", "analyzing", "assessing", "classified", "planning", "response_planning", "awaiting_approval", "approved", "authorized", "in_progress", "response_in_progress", "dispatched", "monitoring"}
    active_incidents = db.query(IncidentDB).filter(IncidentDB.status.in_(active_statuses)).all()
    routed_active = 0
    for incident in active_incidents:
        try:
            routed = json.loads(incident.required_departments or "[]")
        except (TypeError, ValueError):
            routed = []
        if row.code in {str(item).upper() for item in routed}:
            routed_active += 1
    return {
        "id": str(row.id),
        "code": row.code,
        "name": row.name,
        "department_type": row.department_type,
        "description": row.description,
        "status": row.status,
        "account_count": db.query(DepartmentUserDB).filter(DepartmentUserDB.department == row.code).count(),
        "active_incidents": routed_active,
        "resource_count": db.query(CampusResourceDB).filter(CampusResourceDB.department == row.code).count(),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


@router.get("")
def organization_overview(db: Session = Depends(get_db), _admin: Principal = Depends(require_privileged)):
    organization = _org(db)
    departments = db.query(DepartmentDB).filter(DepartmentDB.organization_id == organization.id).order_by(DepartmentDB.id).all()
    return {
        "code": organization.code,
        "name": organization.name,
        "status": organization.status,
        "departments": [_department_public(db, row) for row in departments],
        "active_department_count": sum(row.status == "active" for row in departments),
    }


@router.get("/departments")
def list_departments(db: Session = Depends(get_db), _admin: Principal = Depends(require_privileged)):
    organization = _org(db)
    rows = db.query(DepartmentDB).filter(DepartmentDB.organization_id == organization.id).order_by(DepartmentDB.id).all()
    return [_department_public(db, row) for row in rows]


@router.post("/departments", status_code=status.HTTP_201_CREATED)
def create_department(payload: DepartmentCreatePayload, db: Session = Depends(get_db), _admin: Principal = Depends(require_privileged)):
    code = payload.code.strip().upper().replace(" ", "_")
    if is_valid_department(code) or db.query(DepartmentDB).filter(DepartmentDB.code == code).first():
        raise HTTPException(status_code=409, detail="Department code already exists.")
    organization = _org(db)
    row = DepartmentDB(code=code, organization_id=organization.id, name=payload.name.strip(), department_type=payload.department_type.strip(), description=payload.description, status="active")
    register_department(code, payload.name.strip())
    db.add(row)
    audit_service.log("organization_department_created", f"Department {code} created in the AITAM organization registry.", actor=_actor(_admin), details={"department": code, "name": row.name}, db=db)
    db.commit()
    db.refresh(row)
    return _department_public(db, row)


@router.patch("/departments/{department_code}")
def update_department(department_code: str, payload: DepartmentUpdatePayload, db: Session = Depends(get_db), _admin: Principal = Depends(require_privileged)):
    row = _department(db, department_code)
    if payload.name is not None:
        row.name = payload.name.strip()
    if payload.department_type is not None:
        row.department_type = payload.department_type.strip()
    if payload.description is not None:
        row.description = payload.description.strip()
    if payload.status is not None:
        normalized_status = payload.status.strip().lower()
        if normalized_status not in {"active", "inactive"}:
            raise HTTPException(status_code=400, detail="Department status must be active or inactive.")
        row.status = normalized_status
    row.updated_at = _now()
    audit_service.log("organization_department_updated", f"Department {row.code} profile/status updated.", actor=_actor(_admin), details={"department": row.code, "status": row.status}, db=db)
    db.commit()
    db.refresh(row)
    return _department_public(db, row)


@router.get("/departments/{department_code}/accounts")
def list_department_accounts(department_code: str, db: Session = Depends(get_db), _admin: Principal = Depends(require_privileged)):
    row = _department(db, department_code)
    accounts = db.query(DepartmentUserDB).filter(DepartmentUserDB.department == row.code).order_by(DepartmentUserDB.id).all()
    return [_account_public(account) for account in accounts]


@router.post("/departments/{department_code}/accounts", status_code=status.HTTP_201_CREATED)
def create_department_account(department_code: str, payload: AccountCreatePayload, db: Session = Depends(get_db), _admin: Principal = Depends(require_privileged)):
    row = _department(db, department_code)
    if row.status != "active":
        raise HTTPException(status_code=400, detail="Cannot create an account for an inactive department.")
    email = payload.email.strip().lower()
    if db.query(DepartmentUserDB).filter(DepartmentUserDB.email == email).first():
        raise HTTPException(status_code=409, detail="Email already registered.")
    role = payload.role if payload.role in {ROLE_DEPARTMENT, ROLE_DEPARTMENT_HEAD} else ROLE_DEPARTMENT
    account = DepartmentUserDB(email=email, hashed_password=hash_password(payload.password), full_name=payload.full_name.strip(), department=row.code, role=role, status="active")
    db.add(account)
    audit_service.log("organization_account_created", f"Department account {email} created for {row.code}.", actor=_actor(_admin), details={"department": row.code, "account": email, "role": role}, db=db)
    db.commit()
    db.refresh(account)
    return _account_public(account)


@router.patch("/accounts/{account_id}")
def update_department_account(account_id: int, payload: AccountUpdatePayload, db: Session = Depends(get_db), _admin: Principal = Depends(require_privileged)):
    account = db.query(DepartmentUserDB).filter(DepartmentUserDB.id == account_id).first()
    if account is None:
        raise HTTPException(status_code=404, detail="Department account not found.")
    if payload.password is not None:
        account.hashed_password = hash_password(payload.password)
    if payload.full_name is not None:
        account.full_name = payload.full_name.strip()
    if payload.department is not None:
        target = _department(db, payload.department)
        if target.status != "active":
            raise HTTPException(status_code=400, detail="Cannot assign an account to an inactive department.")
        account.department = target.code
    if payload.role is not None:
        if payload.role not in {ROLE_DEPARTMENT, ROLE_DEPARTMENT_HEAD}:
            raise HTTPException(status_code=400, detail="Invalid department role.")
        account.role = payload.role
    if payload.status is not None:
        if payload.status not in {"active", "suspended"}:
            raise HTTPException(status_code=400, detail="Account status must be active or suspended.")
        account.status = payload.status
    audit_service.log("organization_account_updated", f"Department account {account.email} updated.", actor=_actor(_admin), details={"account_id": account.id, "department": account.department, "status": account.status, "password_reset": payload.password is not None}, db=db)
    db.commit()
    db.refresh(account)
    return _account_public(account)


@router.get("/users")
def list_organization_users(db: Session = Depends(get_db), _admin: Principal = Depends(require_privileged)):
    return [{"id": row.id, "username": row.username, "email": row.email, "full_name": row.full_name, "role": row.role, "department": row.department, "status": row.status} for row in db.query(UserDB).order_by(UserDB.id).all()]


@router.patch("/users/{user_id}/department")
def assign_user_department(user_id: int, payload: UserDepartmentPayload, db: Session = Depends(get_db), _admin: Principal = Depends(require_privileged)):
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if payload.department is None or not payload.department.strip():
        user.department = None
    else:
        user.department = _department(db, payload.department).code
    audit_service.log("organization_user_department_assigned", f"User {user.username} department assignment updated.", actor=_actor(_admin), details={"user_id": user.id, "department": user.department}, db=db)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "username": user.username, "email": user.email, "full_name": user.full_name, "role": user.role, "department": user.department, "status": user.status}

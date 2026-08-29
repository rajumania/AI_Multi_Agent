"""FastAPI authentication & RBAC dependencies for AITAM Disaster Response AI (Increment 1).

These dependencies are the *backend* enforcement point for role-based access
control. Endpoints declare what they require (an authenticated principal, a
privileged actor, a specific department, ...) and these callables resolve the
signed token into a live :class:`Principal`, re-checking the database on every
request so a disabled/deleted account loses access immediately.

Nothing here trusts the frontend: the role and department always come from the
server-verified token + DB row, never from request bodies or query params.

Legacy compatibility: existing command-center endpoints predate auth. The
``get_command_principal`` dependency keeps them working during migration — when
``settings.ALLOW_ANONYMOUS_ADMIN`` is True an unauthenticated caller is treated
as the privileged operator. Flip that flag to False to fully lock the API down.
"""

from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database.database import get_db
from backend.database.models import UserDB, DepartmentUserDB, DepartmentDB
from backend.services.auth_service import (
    Principal,
    PRIVILEGED_ROLES,
    ROLE_OPERATOR,
    SUBJECT_DEPARTMENT,
    SUBJECT_OPERATOR,
    SUBJECT_USER,
    decode_token,
)
from backend.services.departments import normalize_department, is_valid_department


# --------------------------------------------------------------------------
# Token extraction + principal resolution
# --------------------------------------------------------------------------

def _extract_token(request: Request) -> Optional[str]:
    """Pull a bearer token from the Authorization or X-Auth-Token header."""
    auth = request.headers.get("Authorization") or request.headers.get("authorization")
    if auth:
        parts = auth.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
        # Tolerate a raw token in the Authorization header.
        if len(parts) == 1 and parts[0]:
            return parts[0].strip()
    x_token = request.headers.get("X-Auth-Token") or request.headers.get("x-auth-token")
    if x_token:
        return x_token.strip()
    return None


def _principal_from_claims(claims: dict, db: Session) -> Optional[Principal]:
    """Load the live DB row referenced by a decoded token and build a Principal.

    Returns None if the referenced account no longer exists or is suspended.
    """
    subject_type = claims.get("typ")
    sub = claims.get("sub")

    # Department staff account.
    if subject_type == SUBJECT_DEPARTMENT:
        dept_user = None
        if sub is not None:
            try:
                dept_user = db.query(DepartmentUserDB).filter(DepartmentUserDB.id == int(sub)).first()
            except (ValueError, TypeError):
                dept_user = None
        if dept_user is None and claims.get("email"):
            dept_user = db.query(DepartmentUserDB).filter(DepartmentUserDB.email == claims["email"]).first()
        if dept_user is None or (dept_user.status or "active") != "active":
            return None
        department = normalize_department(dept_user.department)
        if department is None:
            return None
        department_row = db.query(DepartmentDB).filter(DepartmentDB.code == department).first()
        if department_row is not None and department_row.status != "active":
            return None
        return Principal(
            subject_type=SUBJECT_DEPARTMENT,
            id=str(dept_user.id),
            role=dept_user.role or "department",
            email=dept_user.email,
            full_name=dept_user.full_name,
            department=department,
            claims=claims,
        )

    # Citizen/user or legacy operator account (both live in UserDB).
    user = None
    if sub is not None:
        try:
            user = db.query(UserDB).filter(UserDB.id == int(sub)).first()
        except (ValueError, TypeError):
            user = None
    if user is None and claims.get("username"):
        # Legacy tokens carried username but no subject id.
        user = db.query(UserDB).filter(UserDB.username == claims["username"]).first()
    if user is None and claims.get("email"):
        user = db.query(UserDB).filter(UserDB.email == claims["email"]).first()
    if user is None:
        return None
    if (getattr(user, "status", "active") or "active") != "active":
        return None

    resolved_subject = SUBJECT_OPERATOR if user.role in PRIVILEGED_ROLES else SUBJECT_USER
    return Principal(
        subject_type=resolved_subject,
        id=str(user.id),
        role=user.role,
        username=user.username,
        email=getattr(user, "email", None),
        phone=getattr(user, "phone", None),
        full_name=user.full_name,
        department=normalize_department(getattr(user, "department", None)),
        claims=claims,
    )


def get_optional_principal(
    request: Request, db: Session = Depends(get_db)
) -> Optional[Principal]:
    """Resolve a Principal if a valid token is present; otherwise None.

    Never raises — use for endpoints that adapt to auth rather than requiring it.
    """
    token = _extract_token(request)
    claims = decode_token(token)
    if not claims:
        return None
    return _principal_from_claims(claims, db)


def get_current_principal(
    request: Request, db: Session = Depends(get_db)
) -> Principal:
    """Strictly require a valid, live authenticated principal (401 otherwise)."""
    principal = get_optional_principal(request, db)
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return principal


def get_command_principal(
    request: Request, db: Session = Depends(get_db)
) -> Principal:
    """Principal for legacy command-center (privileged) endpoints.

    * A valid privileged token -> that principal.
    * A valid NON-privileged token (e.g. a citizen) -> 403.
    * No/invalid token + ALLOW_ANONYMOUS_ADMIN -> synthesized operator (migration).
    * No/invalid token + flag off -> 401.
    """
    principal = get_optional_principal(request, db)
    if principal is not None:
        if principal.is_privileged:
            return principal
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires an operator or admin account.",
        )
    if settings.ALLOW_ANONYMOUS_ADMIN:
        # Migration shim: preserve pre-auth single-operator behavior.
        return Principal(
            subject_type=SUBJECT_OPERATOR,
            id="anonymous-operator",
            role=ROLE_OPERATOR,
            username="anonymous",
            full_name="AITAM Response Commander",
            claims={"anonymous": True},
        )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_approval_viewer(
    request: Request, db: Session = Depends(get_db)
) -> Principal:
    """Resolve a principal allowed to view approval work.

    Command operators can see all pending plans. Department heads can see the
    plans routed to their department (the endpoint applies that scope), while
    community accounts never receive the command approval queue.
    """
    principal = get_optional_principal(request, db)
    if principal is not None:
        if principal.is_privileged or principal.is_department:
            return principal
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Command approval access is not available to community accounts.")
    if settings.ALLOW_ANONYMOUS_ADMIN:
        return Principal(subject_type=SUBJECT_OPERATOR, id="anonymous-operator", role=ROLE_OPERATOR, username="anonymous", full_name="AITAM Response Commander", claims={"anonymous": True})
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.", headers={"WWW-Authenticate": "Bearer"})


# --------------------------------------------------------------------------
# RBAC guard factories
# --------------------------------------------------------------------------

def require_roles(*roles: str) -> Callable[..., Principal]:
    """Dependency: authenticated principal whose role is in ``roles``."""
    allowed = frozenset(roles)

    def _dep(principal: Principal = Depends(get_current_principal)) -> Principal:
        if principal.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return principal

    return _dep


def require_privileged(
    principal: Principal = Depends(get_current_principal),
) -> Principal:
    """Dependency: admin or operator only (strict — no anonymous shim)."""
    if not principal.is_privileged:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator or operator access required.",
        )
    return principal


def require_department_member(
    principal: Principal = Depends(get_current_principal),
) -> Principal:
    """Dependency: an authenticated department staff account."""
    if not principal.is_department:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Department account required.",
        )
    return principal


def resolve_department_scope(principal: Principal, requested_department: Optional[str]) -> Optional[str]:
    """Return the department a principal may query, enforcing isolation.

    * Privileged actors may request any department (or None for 'all').
    * Department staff are pinned to their own department; requesting another
      raises 403, and omitting it defaults to their own.
    """
    requested = normalize_department(requested_department) if requested_department else None
    if requested_department and requested is None and not is_valid_department(requested_department):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown department.")

    if principal.is_privileged:
        return requested  # None => all departments
    # Department staff.
    own = normalize_department(principal.department)
    if own is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No department assigned.")
    if requested is not None and requested != own:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own department's data.",
        )
    return own

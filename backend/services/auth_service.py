"""Authentication & authorization core for AITAM Disaster Response AI (Increment 1).

Centralizes everything security-related so both the auth API and the RBAC
dependencies share one implementation:

  * password hashing/verification
  * signed token creation/decoding (HMAC-SHA256, same wire format as the
    legacy tokens so nothing minted earlier is invalidated)
  * the ``Principal`` value object describing an authenticated actor
  * pure, DB-free authorization predicates used by the guards in api/deps.py

Security model (Part 3 of the requirements):
  RBAC is enforced on the BACKEND. The frontend role / localStorage is never
  trusted — every protected endpoint resolves a Principal from the signed token
  and checks role + department + resource ownership server-side.

Password verification remains compatible with already-seeded accounts while
newly created credentials use a salted, computationally expensive KDF. Legacy
SHA-256 values are accepted only for migration compatibility.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from backend.config import settings
from backend.services.departments import normalize_department

# --- Role constants -------------------------------------------------------
# "operator" is the legacy privileged command-center account (the Campus Safety
# Director). We treat it as admin-equivalent so existing seeded logins keep
# their full access, while "admin" is the explicit Main Admin role going forward.
ROLE_ADMIN = "admin"
ROLE_OPERATOR = "operator"
ROLE_USER = "user"
ROLE_DEPARTMENT = "department"
ROLE_DEPARTMENT_HEAD = "department_head"

PRIVILEGED_ROLES = frozenset({ROLE_ADMIN, ROLE_OPERATOR})
DEPARTMENT_ROLES = frozenset({ROLE_DEPARTMENT, ROLE_DEPARTMENT_HEAD})

# Subject types carried in the token ("typ" claim).
SUBJECT_USER = "user"          # citizen / student portal (email + phone)
SUBJECT_DEPARTMENT = "department"  # department staff (email + password + dept)
SUBJECT_OPERATOR = "operator"  # legacy command-center / admin (username + pwd)


_PBKDF2_ITERATIONS = 310_000


def hash_password(password: str) -> str:
    """Hash new passwords with salted PBKDF2-SHA256.

    Existing installations contain legacy unsalted SHA-256 hashes. Verification
    remains backward compatible so a deployment can rotate credentials without
    locking out the current operator/department accounts.
    """
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", (password or "").encode(), salt, _PBKDF2_ITERATIONS)
    encode = lambda value: base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${encode(salt)}${encode(digest)}"


def verify_password(password: str, hashed: str) -> bool:
    """Verify PBKDF2 hashes and legacy SHA-256 hashes in constant time."""
    stored = hashed or ""
    if stored.startswith("pbkdf2_sha256$"):
        try:
            _, iterations_raw, salt_raw, digest_raw = stored.split("$", 3)
            iterations = int(iterations_raw)
            if iterations < 100_000 or iterations > 1_000_000:
                return False
            padding = "=" * (-len(salt_raw) % 4)
            salt = base64.urlsafe_b64decode((salt_raw + padding).encode("ascii"))
            padding = "=" * (-len(digest_raw) % 4)
            expected = base64.urlsafe_b64decode((digest_raw + padding).encode("ascii"))
            candidate = hashlib.pbkdf2_hmac("sha256", (password or "").encode(), salt, iterations)
            return hmac.compare_digest(candidate, expected)
        except (ValueError, TypeError, UnicodeError):
            return False
    # Backward-compatible verification only; all newly created accounts use
    # the stronger format above.
    return hmac.compare_digest(hashlib.sha256((password or "").encode()).hexdigest(), stored)


def _secret() -> bytes:
    return settings.AUTH_SECRET_KEY.encode()


def create_token(payload: Dict[str, Any], expires_seconds: Optional[int] = None) -> str:
    """Create a signed token: base64url(json_payload) + '.' + HMAC-SHA256.

    Backward compatible with the legacy format (same algorithm, same key), so
    tokens minted before Increment 1 still validate and vice versa.
    """
    data = dict(payload)
    ttl = settings.AUTH_TOKEN_TTL_SECONDS if expires_seconds is None else expires_seconds
    data["exp"] = time.time() + ttl
    payload_b64 = base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
    signature = hmac.new(_secret(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def decode_token(token: Optional[str]) -> Optional[Dict[str, Any]]:
    """Validate signature + expiry and return the payload dict, else None."""
    if not token:
        return None
    try:
        payload_b64, signature = token.split(".")
        expected_sig = hmac.new(_secret(), payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode()).decode())
        if float(payload.get("exp", 0)) < time.time():
            return None
        return payload
    except Exception:
        return None


def verify_token(token: str) -> bool:
    """Legacy boolean check kept for backward compatibility."""
    return decode_token(token) is not None


@dataclass
class Principal:
    """An authenticated actor resolved from a token + its live DB row."""

    subject_type: str  # SUBJECT_USER | SUBJECT_DEPARTMENT | SUBJECT_OPERATOR
    id: str
    role: str
    username: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    full_name: Optional[str] = None
    department: Optional[str] = None
    claims: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_privileged(self) -> bool:
        """True for admin / operator (full command-center access)."""
        return self.role in PRIVILEGED_ROLES

    @property
    def is_admin(self) -> bool:
        return self.role in PRIVILEGED_ROLES

    @property
    def is_department(self) -> bool:
        return self.role in DEPARTMENT_ROLES or self.subject_type == SUBJECT_DEPARTMENT

    @property
    def is_user(self) -> bool:
        return self.role == ROLE_USER or self.subject_type == SUBJECT_USER

    def can_access_department(self, department: Optional[str]) -> bool:
        """Privileged actors see all departments; dept staff see only theirs."""
        if self.is_privileged:
            return True
        target = normalize_department(department)
        return target is not None and target == normalize_department(self.department)

    def to_public_dict(self) -> Dict[str, Any]:
        """Safe representation for API responses (no secrets)."""
        return {
            "id": self.id,
            "subject_type": self.subject_type,
            "role": self.role,
            "username": self.username,
            "email": self.email,
            "phone": self.phone,
            "full_name": self.full_name,
            "department": self.department,
        }


def token_payload_for_user(user) -> Dict[str, Any]:
    """Build a token payload for a citizen/operator UserDB row."""
    is_operator = user.role in PRIVILEGED_ROLES
    subject_type = SUBJECT_OPERATOR if is_operator else SUBJECT_USER
    return {
        "typ": subject_type,
        "sub": str(user.id),
        "username": user.username,
        "email": getattr(user, "email", None),
        "phone": getattr(user, "phone", None),
        "role": user.role,
        "full_name": user.full_name,
        "department": getattr(user, "department", None),
    }


def token_payload_for_department_user(dept_user) -> Dict[str, Any]:
    """Build a token payload for a DepartmentUserDB row."""
    return {
        "typ": SUBJECT_DEPARTMENT,
        "sub": str(dept_user.id),
        "email": dept_user.email,
        "role": dept_user.role or ROLE_DEPARTMENT,
        "full_name": dept_user.full_name,
        "department": normalize_department(dept_user.department),
    }

"""Authenticated reporter evidence upload and retrieval endpoints."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.api.deps import get_current_principal
from backend.config import settings
from backend.database.database import get_db
from backend.database.models import IncidentDB
from backend.services.auth_service import Principal
from backend.services.evidence_storage import EvidenceNotFound, EvidenceStorageUnavailable, evidence_id_from_reference, get_evidence_storage

router = APIRouter(prefix="/api/v1/evidence", tags=["Evidence"])

_ALLOWED = {
    "image/jpeg": {".jpg", ".jpeg", b"\xff\xd8\xff"},
    "image/png": {".png", b"\x89PNG\r\n\x1a\n"},
    "image/webp": {".webp", b"RIFF", b"WEBP"},
    "image/gif": {".gif", b"GIF87a", b"GIF89a"},
}


def _extension(filename: str | None) -> str:
    # Only the suffix is inspected; the original name is never stored or used
    # as a filesystem path.
    normalized = str(filename or "").replace("\\", "/")
    return Path(PurePosixPath(normalized).name).suffix.lower()


def _signature_matches(mime_type: str, extension: str, content: bytes) -> bool:
    rules = _ALLOWED.get(mime_type)
    if not rules or extension not in {item for item in rules if isinstance(item, str)}:
        return False
    if mime_type == "image/webp":
        return len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"
    return any(isinstance(rule, bytes) and content.startswith(rule) for rule in rules)


def _can_view(evidence_id: str, principal: Principal, db: Session) -> bool:
    if principal.is_privileged:
        return True
    storage = get_evidence_storage()
    metadata = storage.metadata(evidence_id)
    if str(metadata.get("owner_id")) == str(principal.id):
        return True
    incident = db.query(IncidentDB).filter(IncidentDB.image_url == f"evidence:{evidence_id}").first()
    if incident is None or not principal.is_department:
        return False
    try:
        departments = json.loads(incident.required_departments or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        departments = []
    return str(principal.department or "").upper() in {str(item).upper() for item in departments}


def validate_reference_access(reference: str | None, principal: Principal) -> None:
    """Reject a submitted opaque evidence reference not owned by the caller."""
    if not reference or not str(reference).startswith("evidence:") or principal.is_privileged:
        return
    evidence_id = evidence_id_from_reference(reference)
    if not evidence_id:
        raise HTTPException(status_code=400, detail="Evidence reference is invalid.")
    try:
        metadata = get_evidence_storage().metadata(evidence_id)
    except EvidenceNotFound as exc:
        raise HTTPException(status_code=400, detail="Evidence reference is no longer available.") from exc
    if str(metadata.get("owner_id")) != str(principal.id):
        raise HTTPException(status_code=403, detail="You do not have permission to use this evidence.")


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    file: UploadFile = File(...),
    principal: Principal = Depends(get_current_principal),
):
    mime_type = str(file.content_type or "").lower().split(";", 1)[0].strip()
    extension = _extension(file.filename)
    if mime_type not in _ALLOWED or extension not in {item for item in _ALLOWED[mime_type] if isinstance(item, str)}:
        raise HTTPException(status_code=415, detail="Only JPEG, PNG, WebP, and GIF evidence images are accepted.")
    max_bytes = max(1, int(settings.EVIDENCE_MAX_BYTES))
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Evidence image exceeds the {max_bytes // (1024 * 1024)} MB limit.")
    if not _signature_matches(mime_type, extension, content):
        raise HTTPException(status_code=415, detail="Image MIME type and file content do not match.")
    try:
        stored = get_evidence_storage().store(content, mime_type=mime_type, owner_id=str(principal.id))
    except EvidenceStorageUnavailable as exc:
        raise HTTPException(status_code=503, detail="Evidence storage is unavailable.") from exc
    return {
        "evidence_id": stored.evidence_id,
        "reference": stored.reference,
        "provider": stored.provider,
        "status": "STORED",
        "mime_type": stored.mime_type,
        "size_bytes": stored.size_bytes,
        "sha256": stored.sha256,
        "uploaded_at": stored.uploaded_at,
    }


@router.get("/{evidence_id}")
def retrieve_evidence(
    evidence_id: str,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    try:
        storage = get_evidence_storage()
        metadata = storage.metadata(evidence_id)
        if not _can_view(evidence_id, principal, db):
            raise HTTPException(status_code=403, detail="You do not have permission to view this evidence.")
        path = storage.binary_path(evidence_id)
    except EvidenceNotFound as exc:
        raise HTTPException(status_code=404, detail="Evidence was not found.") from exc
    return FileResponse(path, media_type=metadata["mime_type"], headers={"X-Evidence-Id": metadata["evidence_id"]})

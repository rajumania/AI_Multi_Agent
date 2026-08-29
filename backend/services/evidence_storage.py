"""Secure evidence storage boundary for reporter-uploaded images.

Local storage is the development implementation.  The interface deliberately
returns opaque evidence references so an object-storage implementation can be
introduced later without exposing filesystem paths to API clients.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import settings


class EvidenceStorageUnavailable(RuntimeError):
    pass


class EvidenceNotFound(FileNotFoundError):
    pass


@dataclass(frozen=True)
class StoredEvidence:
    evidence_id: str
    reference: str
    mime_type: str
    size_bytes: int
    sha256: str
    uploaded_at: str
    provider: str
    owner_id: str


_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_MIME_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


class LocalEvidenceStorage:
    provider = "local"

    def __init__(self, root: Path | None = None):
        configured = Path(settings.EVIDENCE_STORAGE_DIR)
        self.root = root or (configured if configured.is_absolute() else settings.PROJECT_ROOT / configured)

    def _validate_id(self, evidence_id: str) -> str:
        value = str(evidence_id or "").strip().lower()
        if not _ID_RE.fullmatch(value):
            raise EvidenceNotFound("Evidence was not found")
        return value

    def _metadata_path(self, evidence_id: str) -> Path:
        return self.root / f"{self._validate_id(evidence_id)}.json"

    def _binary_path(self, evidence_id: str, mime_type: str) -> Path:
        extension = _MIME_EXTENSIONS.get(mime_type)
        if extension is None:
            raise EvidenceStorageUnavailable("Unsupported stored evidence type")
        return self.root / f"{self._validate_id(evidence_id)}{extension}"

    def store(self, content: bytes, *, mime_type: str, owner_id: str) -> StoredEvidence:
        if settings.EVIDENCE_STORAGE_PROVIDER.strip().lower() != "local":
            raise EvidenceStorageUnavailable("Configured evidence storage provider is not available")
        if not content:
            raise EvidenceStorageUnavailable("Evidence content is empty")
        self.root.mkdir(parents=True, exist_ok=True)
        evidence_id = uuid.uuid4().hex
        uploaded_at = datetime.now(timezone.utc).isoformat()
        digest = hashlib.sha256(content).hexdigest()
        binary_path = self._binary_path(evidence_id, mime_type)
        metadata_path = self._metadata_path(evidence_id)
        metadata: dict[str, Any] = {
            "evidence_id": evidence_id,
            "reference": f"evidence:{evidence_id}",
            "mime_type": mime_type,
            "size_bytes": len(content),
            "sha256": digest,
            "uploaded_at": uploaded_at,
            "provider": self.provider,
            "owner_id": str(owner_id),
        }
        temp_paths: list[str] = []
        try:
            for target, payload in ((binary_path, content), (metadata_path, json.dumps(metadata, separators=(",", ":")).encode("utf-8"))):
                with tempfile.NamedTemporaryFile(dir=self.root, prefix=".upload-", delete=False) as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                    temporary = handle.name
                temp_paths.append(temporary)
                os.replace(temporary, target)
                temp_paths.remove(temporary)
        finally:
            for temporary in temp_paths:
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    pass
        return StoredEvidence(
            evidence_id=evidence_id,
            reference=metadata["reference"],
            mime_type=mime_type,
            size_bytes=len(content),
            sha256=digest,
            uploaded_at=uploaded_at,
            provider=self.provider,
            owner_id=str(owner_id),
        )

    def metadata(self, evidence_id: str) -> dict[str, Any]:
        path = self._metadata_path(evidence_id)
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as exc:
            raise EvidenceNotFound("Evidence was not found") from exc
        if not isinstance(value, dict) or value.get("evidence_id") != self._validate_id(evidence_id):
            raise EvidenceNotFound("Evidence was not found")
        return value

    def binary_path(self, evidence_id: str) -> Path:
        metadata = self.metadata(evidence_id)
        path = self._binary_path(evidence_id, str(metadata.get("mime_type") or ""))
        if not path.is_file():
            raise EvidenceNotFound("Evidence was not found")
        return path

    def delete(self, evidence_id: str) -> None:
        """Delete an evidence object by opaque ID, for test cleanup/admin use."""
        metadata = self.metadata(evidence_id)
        for path in (self._binary_path(evidence_id, str(metadata.get("mime_type") or "")), self._metadata_path(evidence_id)):
            try:
                path.unlink()
            except FileNotFoundError:
                pass


def get_evidence_storage() -> LocalEvidenceStorage:
    if settings.EVIDENCE_STORAGE_PROVIDER.strip().lower() == "local":
        return LocalEvidenceStorage()
    raise EvidenceStorageUnavailable("No implementation exists for the configured evidence storage provider")


def evidence_id_from_reference(reference: str | None) -> str | None:
    value = str(reference or "")
    if not value.startswith("evidence:"):
        return None
    evidence_id = value.split(":", 1)[1].strip().lower()
    return evidence_id if _ID_RE.fullmatch(evidence_id) else None

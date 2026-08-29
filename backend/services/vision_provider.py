"""Backend-only multimodal image evidence provider boundary."""

from __future__ import annotations

import base64
import json
import time
from datetime import datetime, timezone
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field, ValidationError

from backend.config import settings
from backend.services.evidence_storage import EvidenceNotFound, evidence_id_from_reference, get_evidence_storage
from backend.services.provider_health import provider_health


class VisionProviderUnavailable(RuntimeError):
    pass


class ImageEvidenceResult(BaseModel):
    scene_description: str = Field(default="", max_length=2000)
    possible_hazards: list[str] = Field(default_factory=list, max_length=20)
    visible_damage: list[str] = Field(default_factory=list, max_length=20)
    waterlogging: bool = False
    flood_evidence: bool = False
    landslide_evidence: bool = False
    road_blockage: bool = False
    fire_evidence: bool = False
    structural_damage: bool = False
    crowd_or_people_at_risk: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    limitations: list[str] = Field(default_factory=list, max_length=20)


def image_hazard_class(result: dict[str, Any] | None) -> str | None:
    """Return a conservative class only when the vision result has a signal."""
    if not result or str(result.get("status", "")).upper() != "LIVE":
        return None
    if result.get("fire_evidence"):
        return "fire"
    if result.get("landslide_evidence") or result.get("road_blockage"):
        return "landslide"
    if result.get("flood_evidence") or result.get("waterlogging"):
        return "flood"
    if result.get("crowd_or_people_at_risk"):
        return "crowd"
    return None


class VisionProvider(Protocol):
    name: str

    def analyze(self, content: bytes, mime_type: str, description: str) -> ImageEvidenceResult: ...


_PROMPT = """Analyze this reporter image as supporting disaster evidence only.
Return JSON matching the requested schema exactly. Do not claim a cyclone,
earthquake, flood, or disaster is confirmed. Describe only visible indicators,
use conservative booleans, keep confidence between 0 and 1, and include
limitations. A photograph cannot establish causation, geographic scope, or
authoritative warning status by itself."""


def _result_payload(result: ImageEvidenceResult, *, provider: str, status: str, timestamp: str, freshness_seconds: float | None, error: str | None = None) -> dict[str, Any]:
    payload = result.model_dump(mode="json")
    payload.update({
        "provider": provider,
        "source": provider,
        "status": status,
        "timestamp": timestamp,
        "freshness_seconds": freshness_seconds,
        "supporting_only": True,
    })
    if "Image analysis is supporting evidence only; it cannot confirm a disaster." not in payload["limitations"]:
        payload["limitations"].append("Image analysis is supporting evidence only; it cannot confirm a disaster.")
    if error:
        payload["error"] = error
    return payload


def unavailable_result(reason: str, provider: str | None = None) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return _result_payload(ImageEvidenceResult(), provider=provider or "NONE", status="IMAGE_ANALYSIS_UNAVAILABLE", timestamp=now, freshness_seconds=None, error=reason)


class OpenAIVisionProvider:
    name = "OPENAI_VISION"

    def analyze(self, content: bytes, mime_type: str, description: str) -> ImageEvidenceResult:
        if not settings.OPENAI_API_KEY:
            raise VisionProviderUnavailable("OPENAI_API_KEY_NOT_CONFIGURED")
        request = {
            "model": settings.VISION_MODEL or "gpt-4o-mini",
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "messages": [
                {"role": "system", "content": _PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": f"Reporter description: {description[:2000]}"},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64.b64encode(content).decode('ascii')}"}},
                ]},
            ],
        }
        with httpx.Client(timeout=settings.VISION_TIMEOUT_SECONDS, trust_env=True) as client:
            response = client.post(settings.VISION_API_URL, headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}, json=request)
        response.raise_for_status()
        payload = response.json()
        raw = ((payload.get("choices") or [{}])[0].get("message") or {}).get("content")
        if not isinstance(raw, str) or not raw.strip():
            raise VisionProviderUnavailable("EMPTY_VISION_RESPONSE")
        try:
            return ImageEvidenceResult.model_validate(json.loads(raw))
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            raise VisionProviderUnavailable("MALFORMED_VISION_RESPONSE") from exc


class GeminiVisionProvider:
    name = "GEMINI_VISION"

    def analyze(self, content: bytes, mime_type: str, description: str) -> ImageEvidenceResult:
        if not settings.GEMINI_API_KEY:
            raise VisionProviderUnavailable("GEMINI_API_KEY_NOT_CONFIGURED")
        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise VisionProviderUnavailable("GEMINI_SDK_UNAVAILABLE") from exc
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(
            model_name=settings.VISION_MODEL or "gemini-2.5-flash",
            generation_config={"response_mime_type": "application/json", "temperature": 0},
        )
        response = model.generate_content(
            [_PROMPT, f"Reporter description: {description[:2000]}", {"mime_type": mime_type, "data": content}],
            request_options={"timeout": settings.VISION_TIMEOUT_SECONDS},
        )
        raw = (getattr(response, "text", "") or "").strip()
        if not raw:
            raise VisionProviderUnavailable("EMPTY_VISION_RESPONSE")
        try:
            return ImageEvidenceResult.model_validate(json.loads(raw))
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            raise VisionProviderUnavailable("MALFORMED_VISION_RESPONSE") from exc


def get_vision_provider() -> VisionProvider | None:
    provider = settings.VISION_PROVIDER.strip().lower()
    if provider in {"openai", "openai_vision"} and settings.OPENAI_API_KEY:
        return OpenAIVisionProvider()
    if provider in {"gemini", "gemini_vision"} and settings.GEMINI_API_KEY:
        return GeminiVisionProvider()
    return None


def analyze_image_reference(reference: str | None, description: str = "") -> dict[str, Any]:
    """Analyze an uploaded evidence reference, never a client filesystem path."""
    evidence_id = evidence_id_from_reference(reference)
    if not evidence_id:
        if reference:
            return unavailable_result("EVIDENCE_REFERENCE_NOT_STORED")
        return _result_payload(ImageEvidenceResult(), provider="NONE", status="NOT_PROVIDED", timestamp=datetime.now(timezone.utc).isoformat(), freshness_seconds=None)
    try:
        storage = get_evidence_storage()
        metadata = storage.metadata(evidence_id)
        content = storage.binary_path(evidence_id).read_bytes()
    except (EvidenceNotFound, OSError, ValueError) as exc:
        return unavailable_result(type(exc).__name__)
    provider = get_vision_provider()
    if provider is None:
        return unavailable_result("VISION_PROVIDER_OR_API_KEY_NOT_CONFIGURED", settings.VISION_PROVIDER.upper() if settings.VISION_PROVIDER else None)
    started = time.perf_counter()
    attempts = max(1, min(int(settings.VISION_RETRIES) + 1, 3))
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            result = provider.analyze(content, str(metadata["mime_type"]), description)
            provider_health.success("VISION", latency_ms=(time.perf_counter() - started) * 1000, freshness_seconds=0, source=provider.name.lower())
            return _result_payload(result, provider=provider.name, status="LIVE", timestamp=datetime.now(timezone.utc).isoformat(), freshness_seconds=0)
        except (VisionProviderUnavailable, httpx.HTTPError, ValidationError, ValueError, TypeError) as exc:
            last_error = exc
            # Retry is bounded and intended for transient provider/network
            # failures. A malformed response is retried at most once because
            # the provider contract still requires validation on every try.
            if attempt + 1 < attempts:
                continue
    assert last_error is not None
    provider_health.failure("VISION", latency_ms=(time.perf_counter() - started) * 1000, error_type=type(last_error).__name__, source=provider.name.lower())
    return unavailable_result(type(last_error).__name__, provider.name)

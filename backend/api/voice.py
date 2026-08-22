import os
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

from backend.services.adapters.voice_adapter import voice_adapter, AUDIO_CACHE_DIR

router = APIRouter(prefix="/api/v1/voice", tags=["AI Voice & Telephony"])


class TTSGenerationRequest(BaseModel):
    text: str
    incident_id: Optional[str] = None


@router.post("/generate-audio")
def generate_voice_announcement(payload: TTSGenerationRequest):
    """
    Capability A: Generates real AI Voice audio announcement for review and playback.
    Returns audio_id and stream URL.
    """
    res = voice_adapter.generate_voice_audio(payload.text)
    return res


@router.get("/audio/{audio_id}")
def stream_voice_audio(audio_id: str):
    """
    Streams generated voice audio file (.wav / .mp3) for frontend playback.
    """
    path = voice_adapter.get_audio_filepath(audio_id)
    if not path or not os.path.exists(path):
        # Check cache dir directly
        for ext in [".wav", ".mp3"]:
            possible = os.path.join(AUDIO_CACHE_DIR, f"{audio_id}{ext}")
            if os.path.exists(possible):
                path = possible
                break

    if not path or not os.path.exists(path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Voice audio '{audio_id}' not found."
        )

    media_type = "audio/mpeg" if path.endswith(".mp3") else "audio/wav"
    return FileResponse(path, media_type=media_type)

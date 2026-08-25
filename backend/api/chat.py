"""Persistent, privacy-scoped personal assistant endpoints."""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import get_current_principal
from backend.database.database import get_db
from backend.database.models import ChatMessageDB
from backend.models.chat import ChatHistoryResponse, ChatMessageRead, ChatMessageRequest, ChatResponse
from backend.services.llm_service import LLMProviderUnavailable, llm_service
from backend.services.memory_service import memory_service

router = APIRouter(prefix="/api/v1/chat", tags=["Personal Assistant"])


def _require_campus_user(principal):
    if principal.is_privileged or principal.is_department:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The personal assistant is available from the campus member profile.",
        )
    return str(principal.id)


def _history(db: Session, user_id: str, conversation_id: str):
    return db.query(ChatMessageDB).filter(
        ChatMessageDB.user_id == user_id,
        ChatMessageDB.conversation_id == conversation_id,
    ).order_by(ChatMessageDB.created_at.asc(), ChatMessageDB.id.asc()).all()


@router.get("/history", response_model=ChatHistoryResponse)
def get_chat_history(db: Session = Depends(get_db), principal=Depends(get_current_principal)):
    user_id = _require_campus_user(principal)
    latest = db.query(ChatMessageDB).filter(ChatMessageDB.user_id == user_id).order_by(
        ChatMessageDB.created_at.desc(), ChatMessageDB.id.desc()
    ).first()
    if latest is None:
        return ChatHistoryResponse(conversation_id=None, messages=[])
    conversation_id = latest.conversation_id or f"conv-{latest.id}"
    rows = _history(db, user_id, conversation_id)
    for row in rows:
        if not row.conversation_id:
            row.conversation_id = conversation_id
    return ChatHistoryResponse(conversation_id=conversation_id, messages=rows)


@router.delete("/history", status_code=status.HTTP_204_NO_CONTENT)
def clear_chat_history(db: Session = Depends(get_db), principal=Depends(get_current_principal)):
    user_id = _require_campus_user(principal)
    db.query(ChatMessageDB).filter(ChatMessageDB.user_id == user_id).delete(synchronize_session=False)
    db.commit()


@router.post("/message", response_model=ChatResponse)
def send_chat_message(
    request: ChatMessageRequest,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
):
    user_id = _require_campus_user(principal)
    conversation_id = request.conversation_id or f"conv-{uuid4().hex[:24]}"
    # The conversation id is only a grouping key. Ownership is always enforced
    # by user_id in every query; a guessed id cannot cross the user boundary.
    prior = _history(db, user_id, conversation_id)[-12:]

    try:
        memories = memory_service.search(user_id=user_id, query=request.message) if memory_service.available else []
    except Exception:
        memories = []

    try:
        assistant_message = llm_service.generate_chat_response(
            user_message=request.message,
            prior_messages=[{"sender": row.sender, "message": row.message} for row in prior],
            memories=memories,
        )
    except LLMProviderUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    now = datetime.now(timezone.utc)
    db.add(ChatMessageDB(user_id=user_id, conversation_id=conversation_id, sender="user", message=request.message, created_at=now))
    db.add(ChatMessageDB(user_id=user_id, conversation_id=conversation_id, sender="assistant", message=assistant_message, created_at=now))
    db.commit()

    memory_used = False
    if memory_service.available:
        try:
            memory_used = memory_service.add(
                user_id=user_id,
                user_message=request.message,
                assistant_message=assistant_message,
            )
        except Exception:
            memory_used = False

    return ChatResponse(
        message=assistant_message,
        conversation_id=conversation_id,
        timestamp=now,
        memory_used=bool(memories) or memory_used,
    )

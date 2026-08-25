from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: Optional[str] = Field(default=None, max_length=50)


class ChatMessageRead(BaseModel):
    id: int
    conversation_id: str
    sender: str
    message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatResponse(BaseModel):
    message: str
    conversation_id: str
    timestamp: datetime
    memory_used: bool


class ChatHistoryResponse(BaseModel):
    conversation_id: Optional[str] = None
    messages: List[ChatMessageRead]


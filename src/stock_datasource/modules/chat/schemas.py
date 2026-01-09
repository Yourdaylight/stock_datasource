"""Chat module schemas."""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ChatMessage(BaseModel):
    """Chat message model."""
    id: str = Field(..., description="Message ID")
    role: str = Field(..., description="Message role: user or assistant")
    content: str = Field(..., description="Message content")
    timestamp: str = Field(..., description="Message timestamp")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class SendMessageRequest(BaseModel):
    """Request to send a message."""
    session_id: str = Field(..., description="Session ID")
    content: str = Field(..., description="Message content")


class SendMessageResponse(BaseModel):
    """Response after sending a message."""
    id: str
    role: str = "assistant"
    content: str
    timestamp: str
    metadata: Optional[Dict[str, Any]] = None


class ChatHistoryResponse(BaseModel):
    """Chat history response."""
    session_id: str
    messages: List[ChatMessage]


class CreateSessionResponse(BaseModel):
    """Create session response."""
    session_id: str

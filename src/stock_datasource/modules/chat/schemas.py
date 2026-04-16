"""Chat module schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Chat message model."""

    id: str = Field(..., description="Message ID")
    role: str = Field(..., description="Message role: user or assistant")
    content: str = Field(..., description="Message content")
    timestamp: str = Field(..., description="Message timestamp")
    metadata: dict[str, Any] | None = Field(
        default=None, description="Additional metadata"
    )


class ChatSession(BaseModel):
    """Chat session model."""

    session_id: str = Field(..., description="Session ID")
    user_id: str = Field(..., description="User ID")
    title: str = Field(default="", description="Session title")
    created_at: datetime = Field(..., description="Created time")
    updated_at: datetime = Field(..., description="Updated time")
    last_message_at: datetime = Field(..., description="Last message time")
    message_count: int = Field(default=0, description="Message count")


class ChatSessionSummary(BaseModel):
    """Chat session summary for list view."""

    session_id: str = Field(..., description="Session ID")
    title: str = Field(default="", description="Session title")
    created_at: datetime = Field(..., description="Created time")
    last_message_at: datetime = Field(..., description="Last message time")
    message_count: int = Field(default=0, description="Message count")


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
    metadata: dict[str, Any] | None = None


class ChatHistoryResponse(BaseModel):
    """Chat history response."""

    session_id: str
    messages: list[ChatMessage]


class CreateSessionRequest(BaseModel):
    """Create session request."""

    title: str | None = Field(default=None, description="Session title (optional)")


class CreateSessionResponse(BaseModel):
    """Create session response."""

    session_id: str


class SessionListResponse(BaseModel):
    """Session list response."""

    sessions: list[ChatSessionSummary]
    total: int

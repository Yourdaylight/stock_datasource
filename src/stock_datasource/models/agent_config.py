"""Pydantic models for agent configuration management."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    active = "active"
    archived = "archived"
    deleted = "deleted"


class ModelConfig(BaseModel):
    """LLM model configuration for an agent."""

    model: str = "DeepSeek-V4-Pro"
    temperature: float = 0.7
    max_tokens: int = 4096
    min_tokens: int = 0


class RuntimeConfig(BaseModel):
    """Runtime execution configuration."""

    type: str = "langgraph"  # langgraph | claude | codebuddy
    command: str = ""  # CLI path (for claude/codebuddy)
    working_dir: str = ""  # Working directory
    env_vars: dict = Field(default_factory=dict)  # Extra env vars


class AgentConfigCreate(BaseModel):
    """Request body for creating a new agent."""

    name: str = Field(..., min_length=1, max_length=50)
    description: str = Field(default="", max_length=500)
    avatar: str = Field(default="", max_length=10)
    system_prompt: str = Field(..., min_length=1)
    skills: list[str] = Field(default_factory=list)
    user_skills: list[str] = Field(default_factory=list)
    model_config_data: ModelConfig = Field(default_factory=ModelConfig)
    runtime_config: RuntimeConfig = Field(default_factory=RuntimeConfig)
    tags: list[str] = Field(default_factory=list)
    is_public: bool = False


class AgentConfigUpdate(BaseModel):
    """Request body for updating an agent."""

    name: Optional[str] = None
    description: Optional[str] = None
    avatar: Optional[str] = None
    system_prompt: Optional[str] = None
    skills: Optional[list[str]] = None
    user_skills: Optional[list[str]] = None
    model_config_data: Optional[ModelConfig] = None
    runtime_config: Optional[RuntimeConfig] = None
    tags: Optional[list[str]] = None
    is_public: Optional[bool] = None
    status: Optional[AgentStatus] = None


class AgentConfigResponse(BaseModel):
    """Response model for agent configuration."""

    id: str
    user_id: str
    name: str
    description: str
    avatar: str
    system_prompt: str
    skills: list[str]
    user_skills: list[str] = Field(default_factory=list)
    model_config_data: ModelConfig
    runtime_config: RuntimeConfig = Field(default_factory=RuntimeConfig)
    tags: list[str]
    is_public: bool
    status: AgentStatus
    version: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

"""Pydantic schemas for user LLM configuration module."""

from pydantic import BaseModel, Field


class LlmConfigCreate(BaseModel):
    """Request to create/update a user's LLM config."""

    provider: str = Field(default="openai", description="LLM provider name")
    api_key: str = Field(..., min_length=1, description="API key")
    base_url: str | None = Field(default="", description="Custom base URL")
    model_name: str | None = Field(default="", description="Preferred model name")


class LlmConfigResponse(BaseModel):
    """Single LLM config response (api_key masked)."""

    provider: str
    api_key_masked: str
    base_url: str = ""
    model_name: str = ""
    is_active: bool = True
    updated_at: str = ""


class LlmConfigListResponse(BaseModel):
    """List of user's LLM configs."""

    configs: list[LlmConfigResponse]


class LlmConfigTestRequest(BaseModel):
    """Request to test an LLM config."""

    provider: str = "openai"
    api_key: str
    base_url: str | None = ""
    model_name: str | None = ""


class LlmConfigTestResponse(BaseModel):
    """Result of LLM config test."""

    success: bool
    message: str
    model_name: str = ""

"""Pydantic models for orchestration pipelines and execution."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    agent = "agent"
    input = "input"
    output = "output"
    condition = "condition"
    aggregator = "aggregator"


class PipelineNode(BaseModel):
    """A node in the orchestration pipeline."""

    id: str
    type: NodeType
    label: str
    position: dict = Field(default_factory=lambda: {"x": 0, "y": 0})
    data: dict = Field(default_factory=dict)
    # For agent nodes: data.agent_id, data.input_mapping
    # For condition nodes: data.condition_expression
    # For aggregator: data.merge_strategy


class PipelineEdge(BaseModel):
    """An edge connecting two nodes."""

    id: str
    source: str
    target: str
    source_handle: str = "output"
    target_handle: str = "input"
    label: str = ""


class PipelineStatus(str, Enum):
    draft = "draft"
    active = "active"
    archived = "archived"
    deleted = "deleted"


class PipelineCreate(BaseModel):
    """Request body for creating a pipeline."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    nodes: list[PipelineNode] = Field(default_factory=list)
    edges: list[PipelineEdge] = Field(default_factory=list)
    input_schema: dict = Field(default_factory=dict)
    output_config: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class PipelineUpdate(BaseModel):
    """Request body for updating a pipeline."""

    name: Optional[str] = None
    description: Optional[str] = None
    nodes: Optional[list[PipelineNode]] = None
    edges: Optional[list[PipelineEdge]] = None
    input_schema: Optional[dict] = None
    output_config: Optional[dict] = None
    tags: Optional[list[str]] = None
    status: Optional[PipelineStatus] = None


class PipelineResponse(BaseModel):
    """Response model for a pipeline."""

    id: str
    user_id: str
    name: str
    description: str
    nodes: list[PipelineNode]
    edges: list[PipelineEdge]
    input_schema: dict
    output_config: dict
    tags: list[str]
    is_public: bool
    status: PipelineStatus
    version: int
    created_at: datetime
    updated_at: datetime


class ExecutionStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class PipelineExecuteRequest(BaseModel):
    """Request body for executing a pipeline."""

    input_data: dict = Field(default_factory=dict)


class ExecutionResponse(BaseModel):
    """Response model for a pipeline execution."""

    id: str
    pipeline_id: str
    user_id: str
    status: ExecutionStatus
    current_node_id: str = ""
    node_results: dict[str, Any] = Field(default_factory=dict)
    output_data: Any = None
    error_message: str = ""
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: int = 0

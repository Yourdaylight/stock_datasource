"""Schemas for system logs module."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class LogEntry(BaseModel):
    """Single log entry."""

    timestamp: datetime = Field(..., description="Log timestamp")
    level: str = Field(..., description="Log level (INFO, WARNING, ERROR)")
    module: str = Field(..., description="Module name (e.g., backend, worker, server)")
    message: str = Field(..., description="Log message")
    raw_line: str = Field(..., description="Original raw log line")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class LogFilter(BaseModel):
    """Filter parameters for log queries."""

    level: Optional[str] = Field(None, description="Filter by log level")
    start_time: Optional[datetime] = Field(None, description="Start time filter")
    end_time: Optional[datetime] = Field(None, description="End time filter")
    keyword: Optional[str] = Field(None, description="Keyword search in message")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(50, ge=1, le=1000, description="Page size")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class LogFileInfo(BaseModel):
    """Information about a log file."""

    name: str = Field(..., description="File name")
    size: int = Field(..., description="File size in bytes")
    modified_time: datetime = Field(..., description="Last modified time")
    line_count: int = Field(..., description="Estimated line count")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class LogAnalysisRequest(BaseModel):
    """Request for AI log analysis."""

    log_entries: List[LogEntry] = Field(..., description="Log entries to analyze")
    user_query: Optional[str] = Field(None, description="User's specific question")


class LogAnalysisResponse(BaseModel):
    """Response from AI log analysis."""

    error_type: str = Field(..., description="Type of error")
    possible_causes: List[str] = Field(..., description="Possible causes")
    suggested_fixes: List[str] = Field(..., description="Suggested fixes")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    related_logs: List[str] = Field(default_factory=list, description="Related log entries")


class LogListResponse(BaseModel):
    """Response for log list query."""

    logs: List[LogEntry] = Field(..., description="Log entries")
    total: int = Field(..., description="Total matching logs")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Page size")


class ArchiveListResponse(BaseModel):
    """Response for archive list query."""

    archives: List[LogFileInfo] = Field(..., description="Archive files")

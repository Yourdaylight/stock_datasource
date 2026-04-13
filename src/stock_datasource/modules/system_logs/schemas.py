"""Schemas for system logs module."""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class LogEntry(BaseModel):
    """Single log entry."""

    timestamp: datetime = Field(..., description="Log timestamp")
    level: str = Field(..., description="Log level (INFO, WARNING, ERROR)")
    module: str = Field(..., description="Module name (e.g., backend, worker, server)")
    message: str = Field(..., description="Log message")
    raw_line: str = Field(..., description="Original raw log line")
    request_id: Optional[str] = Field("-", description="Request ID for log correlation")
    user_id: Optional[str] = Field("-", description="User ID for log correlation")
    middleware_trace_id: Optional[str] = Field("-", description="Middleware trace ID for correlation")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class LogFilter(BaseModel):
    """Filter parameters for log queries."""

    level: Optional[str] = Field(None, description="Filter by log level")
    start_time: Optional[datetime] = Field(None, description="Start time filter")
    end_time: Optional[datetime] = Field(None, description="End time filter")
    keyword: Optional[str] = Field(None, max_length=200, description="Keyword search in message")
    request_id: Optional[str] = Field(None, max_length=32, description="Filter by request ID")
    middleware_trace_id: Optional[str] = Field(None, max_length=32, description="Filter by middleware trace ID")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(50, ge=1, le=1000, description="Page size")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class LogInsightFilter(BaseModel):
    """Filter params for stats/clusters/timeline insights."""

    level: Optional[str] = Field(None, description="Filter by log level")
    start_time: Optional[datetime] = Field(None, description="Start time filter")
    end_time: Optional[datetime] = Field(None, description="End time filter")
    keyword: Optional[str] = Field(None, max_length=200, description="Keyword search in message")
    request_id: Optional[str] = Field(None, max_length=32, description="Filter by request ID")
    window_hours: int = Field(2, ge=1, le=72, description="Fallback time window when start/end not provided")
    limit: int = Field(50, ge=1, le=500, description="Result limit")


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


class LogRootCause(BaseModel):
    """Structured root cause candidate."""

    title: str
    module: Optional[str] = None
    function: Optional[str] = None
    evidence: List[str] = Field(default_factory=list)
    confidence: float = Field(0.0, ge=0.0, le=1.0)


class LogFixSuggestion(BaseModel):
    """Structured fix suggestion."""

    title: str
    steps: List[str] = Field(default_factory=list)
    priority: str = Field("medium", description="low/medium/high")


class LogAnalysisRequest(BaseModel):
    """Request for AI log analysis."""

    log_entries: List[LogEntry] = Field(default_factory=list, description="Log entries to analyze")
    user_query: Optional[str] = Field(None, max_length=500, description="User's specific question")
    context: Optional[str] = Field(None, max_length=1000, description="Additional diagnosis context")
    start_time: Optional[datetime] = Field(None, description="Start time filter")
    end_time: Optional[datetime] = Field(None, description="End time filter")
    level: Optional[str] = Field(None, description="Optional level filter")
    query: Optional[str] = Field(None, max_length=200, description="Optional keyword query")
    default_window_hours: int = Field(2, ge=1, le=72)
    include_code_context: bool = Field(True, description="Whether diagnosis should include code hints")
    max_entries: int = Field(50, ge=5, le=500, description="Maximum log entries used for analysis")


class LogAnalysisResponse(BaseModel):
    """Response from AI log analysis."""

    error_type: str = Field(..., description="Type of error")
    possible_causes: List[str] = Field(default_factory=list, description="Possible causes")
    suggested_fixes: List[str] = Field(default_factory=list, description="Suggested fixes")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    related_logs: List[str] = Field(default_factory=list, description="Related log entries")
    summary: str = Field(default="", description="Diagnosis summary")
    analysis_source: str = Field(default="rule_based", description="orchestrator/rule_based/hybrid")
    root_causes: List[LogRootCause] = Field(default_factory=list)
    recent_operations: List[Dict] = Field(default_factory=list)
    fix_suggestions: List[LogFixSuggestion] = Field(default_factory=list)
    risk_level: str = Field(default="low", description="low/medium/high/critical")
    impact_scope: str = Field(default="未识别明显影响范围")
    diagnosis_time: datetime = Field(default_factory=datetime.now)


class LogStatsTrendPoint(BaseModel):
    """Trend point for log level counts."""

    timestamp: datetime
    total: int = 0
    error: int = 0
    warning: int = 0
    info: int = 0
    debug: int = 0


class LogStatsResponse(BaseModel):
    """Aggregated log stats response."""

    total: int = 0
    error: int = 0
    warning: int = 0
    info: int = 0
    debug: int = 0
    by_level: Dict[str, int] = Field(default_factory=dict)
    trend: List[LogStatsTrendPoint] = Field(default_factory=list)


class ErrorClusterItem(BaseModel):
    """Grouped error signature item."""

    signature: str
    count: int
    level: str
    module: str
    latest_time: datetime
    sample_message: str


class ErrorClusterResponse(BaseModel):
    """Error cluster response."""

    clusters: List[ErrorClusterItem] = Field(default_factory=list)


class OperationTimelineItem(BaseModel):
    """Recent operation timeline item."""

    timestamp: datetime
    event_type: str = Field(description="log/schedule")
    level: str
    module: str
    summary: str
    detail: Optional[str] = None
    request_id: Optional[str] = Field(None, description="Request ID for timeline correlation")


class OperationTimelineResponse(BaseModel):
    """Recent operation timeline response."""

    items: List[OperationTimelineItem] = Field(default_factory=list)


class LogListResponse(BaseModel):
    """Response for log list query."""

    logs: List[LogEntry] = Field(..., description="Log entries")
    total: int = Field(..., description="Total matching logs")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Page size")


class ArchiveListResponse(BaseModel):
    """Response for archive list query."""

    archives: List[LogFileInfo] = Field(..., description="Archive files")

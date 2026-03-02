"""Router for system logs API."""

import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from stock_datasource.modules.auth.dependencies import require_admin
from .schemas import (
    ArchiveListResponse,
    ErrorClusterResponse,
    LogAnalysisRequest,
    LogAnalysisResponse,
    LogFileInfo,
    LogFilter,
    LogInsightFilter,
    LogListResponse,
    LogStatsResponse,
    OperationTimelineResponse,
)
from .service import get_log_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system_logs", tags=["system-logs"])


def _parse_iso_time(value: str, field_name: str):
    from datetime import datetime

    if not value:
        return None

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name} format: {value}"
        )


def _build_insight_filter(
    level: str = None,
    start_time: str = None,
    end_time: str = None,
    keyword: str = None,
    window_hours: int = 2,
    limit: int = 50,
) -> LogInsightFilter:
    parsed_start = _parse_iso_time(start_time, "start_time") if start_time else None
    parsed_end = _parse_iso_time(end_time, "end_time") if end_time else None
    return LogInsightFilter(
        level=level,
        start_time=parsed_start,
        end_time=parsed_end,
        keyword=keyword,
        window_hours=window_hours,
        limit=limit,
    )


@router.get(
    "",
    response_model=LogListResponse,
    dependencies=[Depends(require_admin)],
    summary="Get system logs",
    description="Query and filter system logs with pagination"
)
async def get_system_logs(
    level: str = None,
    start_time: str = None,
    end_time: str = None,
    keyword: str = None,
    page: int = 1,
    page_size: int = 50,
    log_service = Depends(get_log_service)
):
    """Get filtered system logs.

    Query params:
    - level: Filter by log level (INFO, WARNING, ERROR)
    - start_time: Start time in ISO format (YYYY-MM-DDTHH:MM:SS)
    - end_time: End time in ISO format (YYYY-MM-DDTHH:MM:SS)
    - keyword: Keyword to search in messages
    - page: Page number (1-indexed)
    - page_size: Number of logs per page (1-1000)
    """
    parsed_start = _parse_iso_time(start_time, "start_time") if start_time else None
    parsed_end = _parse_iso_time(end_time, "end_time") if end_time else None

    filters = LogFilter(
        level=level,
        start_time=parsed_start,
        end_time=parsed_end,
        keyword=keyword,
        page=page,
        page_size=page_size
    )

    # Get logs
    try:
        return log_service.get_logs(filters)
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve logs: {str(e)}"
        )


@router.post(
    "/analyze",
    response_model=LogAnalysisResponse,
    summary="Analyze logs with AI",
    description="Analyze error logs and get AI-powered suggestions"
)
async def analyze_logs(
    request: LogAnalysisRequest,
    current_user: dict = Depends(require_admin),
    log_service = Depends(get_log_service)
):
    """Analyze logs using AI agent."""
    try:
        user_id = str(current_user.get("username") or current_user.get("user_id") or "admin")
        return await log_service.analyze_logs(request, user_id=user_id)
    except Exception as e:
        logger.error(f"Error analyzing logs: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze logs: {str(e)}"
        )


@router.get(
    "/stats",
    response_model=LogStatsResponse,
    dependencies=[Depends(require_admin)],
    summary="Get log stats",
    description="Get overview stats and hourly trends for logs"
)
async def get_log_stats(
    level: str = None,
    start_time: str = None,
    end_time: str = None,
    keyword: str = None,
    window_hours: int = 2,
    limit: int = 200,
    log_service = Depends(get_log_service)
):
    """Get log overview stats and trend."""
    try:
        filters = _build_insight_filter(
            level=level,
            start_time=start_time,
            end_time=end_time,
            keyword=keyword,
            window_hours=window_hours,
            limit=limit,
        )
        return log_service.get_stats(filters)
    except Exception as e:
        logger.error(f"Error getting log stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve log stats: {str(e)}")


@router.get(
    "/clusters",
    response_model=ErrorClusterResponse,
    dependencies=[Depends(require_admin)],
    summary="Get error clusters",
    description="Group recent error/warning logs by signature"
)
async def get_log_clusters(
    level: str = None,
    start_time: str = None,
    end_time: str = None,
    keyword: str = None,
    window_hours: int = 2,
    limit: int = 20,
    log_service = Depends(get_log_service)
):
    """Get clustered recent errors."""
    try:
        filters = _build_insight_filter(
            level=level,
            start_time=start_time,
            end_time=end_time,
            keyword=keyword,
            window_hours=window_hours,
            limit=limit,
        )
        return log_service.get_error_clusters(filters)
    except Exception as e:
        logger.error(f"Error getting log clusters: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve log clusters: {str(e)}")


@router.get(
    "/timeline",
    response_model=OperationTimelineResponse,
    dependencies=[Depends(require_admin)],
    summary="Get operation timeline",
    description="Get recent operations timeline from logs and scheduler executions"
)
async def get_operation_timeline(
    level: str = None,
    start_time: str = None,
    end_time: str = None,
    keyword: str = None,
    window_hours: int = 2,
    limit: int = 50,
    log_service = Depends(get_log_service)
):
    """Get merged operation timeline."""
    try:
        filters = _build_insight_filter(
            level=level,
            start_time=start_time,
            end_time=end_time,
            keyword=keyword,
            window_hours=window_hours,
            limit=limit,
        )
        return log_service.get_operation_timeline(filters)
    except Exception as e:
        logger.error(f"Error getting operation timeline: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve operation timeline: {str(e)}")


@router.get(
    "/files",
    response_model=list[LogFileInfo],
    dependencies=[Depends(require_admin)],
    summary="Get log files",
    description="Get list of available log files"
)
async def get_log_files(
    log_service = Depends(get_log_service)
):
    """Get list of log files."""
    try:
        return log_service.get_log_files()
    except Exception as e:
        logger.error(f"Error getting log files: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve log files: {str(e)}"
        )


@router.get(
    "/archives",
    response_model=ArchiveListResponse,
    dependencies=[Depends(require_admin)],
    summary="Get archived logs",
    description="Get list of archived log files"
)
async def get_archived_logs(
    log_service = Depends(get_log_service)
):
    """Get list of archived log files."""
    try:
        archives = log_service.get_archives()
        return ArchiveListResponse(archives=archives)
    except Exception as e:
        logger.error(f"Error getting archives: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve archives: {str(e)}"
        )


@router.post(
    "/archive",
    dependencies=[Depends(require_admin)],
    summary="Archive old logs",
    description="Archive logs older than retention period"
)
async def archive_logs(
    retention_days: int = 30,
    log_service = Depends(get_log_service)
):
    """Manually trigger log archiving."""
    try:
        result = log_service.archive_logs(retention_days=retention_days)
        return result
    except Exception as e:
        logger.error(f"Error archiving logs: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to archive logs: {str(e)}"
        )


@router.get(
    "/export",
    dependencies=[Depends(require_admin)],
    summary="Export logs",
    description="Export filtered logs to CSV or JSON"
)
async def export_logs(
    level: str = None,
    start_time: str = None,
    end_time: str = None,
    keyword: str = None,
    format: str = "csv",
    log_service = Depends(get_log_service)
):
    """Export filtered logs to file."""
    parsed_start = _parse_iso_time(start_time, "start_time") if start_time else None
    parsed_end = _parse_iso_time(end_time, "end_time") if end_time else None

    filters = LogFilter(
        level=level,
        start_time=parsed_start,
        end_time=parsed_end,
        keyword=keyword,
        page=1,
        page_size=100000
    )

    # Export logs
    try:
        filepath = log_service.export_logs(filters, format=format)
        filename = Path(filepath).name

        return FileResponse(
            filepath,
            filename=filename,
            media_type='application/octet-stream'
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error exporting logs: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export logs: {str(e)}"
        )


@router.get(
    "/download/{filename}",
    dependencies=[Depends(require_admin)],
    summary="Download archive",
    description="Download an archived log file"
)
async def download_archive(
    filename: str,
    log_service = Depends(get_log_service)
):
    """Download an archived log file."""
    from pathlib import Path
    archive_dir = Path("logs") / "archive"
    filepath = archive_dir / filename

    if not filepath.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Archive not found: {filename}"
        )

    return FileResponse(
        filepath,
        filename=filename,
        media_type='application/gzip'
    )

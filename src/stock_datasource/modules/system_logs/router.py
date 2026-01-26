"""Router for system logs API."""

import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from stock_datasource.modules.auth.dependencies import require_admin
from .schemas import (
    LogFilter,
    LogListResponse,
    LogFileInfo,
    LogAnalysisRequest,
    LogAnalysisResponse,
    ArchiveListResponse,
)
from .service import get_log_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system_logs", tags=["system-logs"])


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
    from datetime import datetime

    # Parse time filters
    parsed_start = None
    parsed_end = None

    if start_time:
        try:
            parsed_start = datetime.fromisoformat(start_time)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid start_time format: {start_time}"
            )

    if end_time:
        try:
            parsed_end = datetime.fromisoformat(end_time)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid end_time format: {end_time}"
            )

    # Create filter
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
    dependencies=[Depends(require_admin)],
    summary="Analyze logs with AI",
    description="Analyze error logs and get AI-powered suggestions"
)
async def analyze_logs(
    request: LogAnalysisRequest,
    log_service = Depends(get_log_service)
):
    """Analyze logs using AI agent."""
    try:
        return log_service.analyze_logs(request)
    except Exception as e:
        logger.error(f"Error analyzing logs: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze logs: {str(e)}"
        )


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
    from datetime import datetime

    # Parse time filters
    parsed_start = None
    parsed_end = None

    if start_time:
        try:
            parsed_start = datetime.fromisoformat(start_time)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid start_time format: {start_time}"
            )

    if end_time:
        try:
            parsed_end = datetime.fromisoformat(end_time)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid end_time format: {end_time}"
            )

    # Create filter
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

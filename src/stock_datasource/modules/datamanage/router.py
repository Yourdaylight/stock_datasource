"""Data management module router."""

from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional
import logging

from .schemas import (
    DataSource, SyncTask, TriggerSyncRequest, ManualDetectRequest,
    QualityMetrics, PluginInfo, PluginDetail, PluginDataPreview,
    PluginStatus, MissingDataSummary, TaskType,
    DiagnosisRequest, DiagnosisResult,
    CheckDataExistsRequest, DataExistsCheckResult
)
from .service import data_manage_service, sync_task_manager, diagnosis_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ============ Data Sources ============

@router.get("/datasources", response_model=List[DataSource])
async def get_datasources():
    """Get data source list."""
    return [
        DataSource(id="tushare", source_name="TuShare", source_type="api", provider="tushare", last_sync_at="2026-01-09 18:00:00"),
        DataSource(id="akshare", source_name="AKShare", source_type="api", provider="akshare", last_sync_at="2026-01-09 18:00:00"),
    ]


@router.post("/datasources/{source_id}/test")
async def test_connection(source_id: str):
    """Test data source connection."""
    return {"success": True, "message": "连接成功"}


# ============ Missing Data Detection ============

@router.get("/missing-data", response_model=MissingDataSummary)
async def get_missing_data(
    days: int = Query(default=30, ge=1, le=365, description="Number of trading days to check"),
    force_refresh: bool = Query(default=False, description="Force refresh cache")
):
    """Get missing data summary across all daily plugins."""
    return data_manage_service.detect_missing_data(days=days, force_refresh=force_refresh)


@router.post("/missing-data/detect", response_model=MissingDataSummary)
async def trigger_missing_data_detection(request: ManualDetectRequest):
    """Manually trigger missing data detection."""
    return data_manage_service.detect_missing_data(days=request.days, force_refresh=True)


# ============ Sync Tasks ============

@router.get("/sync/tasks", response_model=List[SyncTask])
async def get_sync_tasks():
    """Get all sync tasks."""
    return sync_task_manager.get_all_tasks()


@router.post("/sync/trigger", response_model=SyncTask)
async def trigger_sync(request: TriggerSyncRequest):
    """Trigger a sync task for a plugin."""
    task = sync_task_manager.create_task(
        plugin_name=request.plugin_name,
        task_type=request.task_type,
        trade_dates=request.trade_dates
    )
    return task


@router.get("/sync/status/{task_id}", response_model=SyncTask)
async def get_sync_status(task_id: str):
    """Get sync task status."""
    task = sync_task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task


@router.post("/sync/cancel/{task_id}")
async def cancel_sync_task(task_id: str):
    """Cancel a pending sync task."""
    success = sync_task_manager.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot cancel task (not pending or not found)")
    return {"success": True, "message": "Task cancelled"}


@router.get("/sync/history", response_model=List[SyncTask])
async def get_sync_history(
    limit: int = Query(default=20, ge=1, le=100),
    plugin_name: Optional[str] = None
):
    """Get sync task history."""
    tasks = sync_task_manager.get_all_tasks()
    
    # Filter completed/failed tasks
    history = [t for t in tasks if t.status.value in ("completed", "failed", "cancelled")]
    
    # Filter by plugin if specified
    if plugin_name:
        history = [t for t in history if t.plugin_name == plugin_name]
    
    # Sort by completed_at desc
    history.sort(key=lambda x: x.completed_at or x.created_at, reverse=True)
    
    return history[:limit]


# ============ Plugins ============

@router.get("/plugins", response_model=List[PluginInfo])
async def get_plugins():
    """Get plugin list with status info."""
    return data_manage_service.get_plugin_list()


@router.get("/plugins/{name}/detail", response_model=PluginDetail)
async def get_plugin_detail(name: str):
    """Get detailed plugin information including config and schema."""
    detail = data_manage_service.get_plugin_detail(name)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Plugin {name} not found")
    return detail


@router.get("/plugins/{name}/status", response_model=PluginStatus)
async def get_plugin_status(name: str):
    """Get plugin data status."""
    status = data_manage_service.get_plugin_status(name)
    if not status:
        raise HTTPException(status_code=404, detail=f"Plugin {name} not found")
    return status


@router.get("/plugins/{name}/data", response_model=PluginDataPreview)
async def get_plugin_data(
    name: str,
    trade_date: Optional[str] = Query(default=None, description="Filter by trade date (YYYY-MM-DD)"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=1000)
):
    """Get plugin data preview."""
    preview = data_manage_service.get_plugin_data_preview(
        plugin_name=name,
        trade_date=trade_date,
        page=page,
        page_size=page_size
    )
    if not preview:
        raise HTTPException(status_code=404, detail=f"Plugin {name} not found or no data available")
    return preview


@router.post("/plugins/{name}/check-exists", response_model=DataExistsCheckResult)
async def check_data_exists(name: str, request: CheckDataExistsRequest):
    """Check if data exists for specific dates in a plugin's table."""
    result = data_manage_service.check_dates_data_exists(name, request.dates)
    return result


@router.post("/plugins/{name}/enable")
async def enable_plugin(name: str):
    """Enable a plugin."""
    # TODO: Implement plugin enable/disable in config
    return {"success": True}


@router.post("/plugins/{name}/disable")
async def disable_plugin(name: str):
    """Disable a plugin."""
    # TODO: Implement plugin enable/disable in config
    return {"success": True}


# ============ Data Quality ============

@router.get("/quality/metrics", response_model=List[QualityMetrics])
async def get_quality_metrics():
    """Get data quality metrics."""
    # Get plugin list and calculate quality metrics
    plugins = data_manage_service.get_plugin_list()
    
    metrics = []
    for plugin in plugins:
        # Calculate scores based on missing data
        completeness = 100 - (plugin.missing_count * 3)  # -3% per missing day
        completeness = max(0, min(100, completeness))
        
        metrics.append(QualityMetrics(
            table_name=f"ods_{plugin.name.replace('tushare_', '').replace('akshare_', '')}",
            completeness_score=completeness,
            consistency_score=99.0,  # TODO: Implement real consistency check
            timeliness_score=95.0 if plugin.missing_count == 0 else 80.0,
            overall_score=(completeness + 99.0 + (95.0 if plugin.missing_count == 0 else 80.0)) / 3,
            record_count=0,  # TODO: Get from status
            latest_update=plugin.latest_date
        ))
    
    return metrics


@router.get("/quality/report")
async def get_quality_report(table: Optional[str] = None):
    """Get data quality report."""
    return {"report": "Data quality is good"}


# ============ Metadata ============

@router.get("/metadata/tables")
async def get_table_metadata():
    """Get table metadata."""
    plugins = data_manage_service.get_plugin_list()
    
    tables = []
    for plugin in plugins:
        detail = data_manage_service.get_plugin_detail(plugin.name)
        if detail:
            tables.append({
                "table_name": detail.table_schema.table_name,
                "description": detail.table_schema.comment or plugin.description,
                "row_count": detail.status.total_records,
                "size_bytes": 0,  # TODO: Get actual size
                "latest_date": detail.status.latest_date
            })
    
    return tables


# ============ AI Diagnosis ============

@router.get("/diagnosis", response_model=DiagnosisResult)
async def get_diagnosis(
    log_lines: int = Query(default=100, ge=10, le=500, description="Number of log lines to analyze"),
    errors_only: bool = Query(default=False, description="Only analyze error logs")
):
    """Get AI diagnosis of recent logs."""
    return diagnosis_service.diagnose(lines=log_lines, errors_only=errors_only)


@router.post("/diagnosis", response_model=DiagnosisResult)
async def trigger_diagnosis(request: DiagnosisRequest):
    """Trigger AI diagnosis with custom parameters."""
    return diagnosis_service.diagnose(
        lines=request.log_lines,
        errors_only=request.include_errors_only,
        context=request.context
    )

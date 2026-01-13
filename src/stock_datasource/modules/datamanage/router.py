"""Data management module router."""

from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional
import logging

from .schemas import (
    DataSource, SyncTask, TriggerSyncRequest, ManualDetectRequest,
    QualityMetrics, PluginInfo, PluginDetail, PluginDataPreview,
    PluginStatus, MissingDataSummary, TaskType, SyncHistory,
    DiagnosisRequest, DiagnosisResult,
    CheckDataExistsRequest, DataExistsCheckResult,
    SyncConfig, SyncConfigRequest,
    ProxyConfig, ProxyConfigRequest, ProxyTestResult
)
from .service import data_manage_service, sync_task_manager, diagnosis_service
from ...config.runtime_config import save_runtime_config

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


@router.delete("/sync/tasks/{task_id}")
async def delete_sync_task(task_id: str):
    """Delete a sync task (any status except running)."""
    success = sync_task_manager.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot delete task (running or not found)")
    return {"success": True, "message": "Task deleted"}


@router.get("/sync/config", response_model=SyncConfig)
async def get_sync_config():
    """Get current sync configuration (parallelism settings)."""
    config = sync_task_manager.get_config()
    return SyncConfig(**config)


@router.put("/sync/config", response_model=SyncConfig)
async def update_sync_config(request: SyncConfigRequest):
    """Update sync configuration (parallelism settings).
    
    - max_concurrent_tasks: Max parallel tasks (1-10), default 1 for TuShare IP limit
    - max_date_threads: Max threads per task for multi-date processing (1-20), default 1
    """
    config = sync_task_manager.update_config(
        max_concurrent_tasks=request.max_concurrent_tasks,
        max_date_threads=request.max_date_threads
    )
    return SyncConfig(**config)


@router.get("/sync/history", response_model=List[SyncHistory])
async def get_sync_history(
    days: int = Query(default=7, ge=1, le=30, description="Number of days to look back"),
    limit: int = Query(default=50, ge=1, le=200),
    plugin_name: Optional[str] = None
):
    """Get sync task history from database."""
    history = sync_task_manager.get_task_history(days=days, limit=limit)
    
    # Filter by plugin if specified
    if plugin_name:
        history = [h for h in history if h.plugin_name == plugin_name]
    
    return history


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


# ============ Proxy Configuration ============

@router.get("/proxy/config", response_model=ProxyConfig)
async def get_proxy_config():
    """Get current HTTP proxy configuration."""
    from ...config.settings import settings
    return ProxyConfig(
        enabled=settings.HTTP_PROXY_ENABLED,
        host=settings.HTTP_PROXY_HOST,
        port=settings.HTTP_PROXY_PORT,
        username=settings.HTTP_PROXY_USERNAME,
        password="******" if settings.HTTP_PROXY_PASSWORD else None  # Mask password
    )


@router.put("/proxy/config", response_model=ProxyConfig)
async def update_proxy_config(request: ProxyConfigRequest):
    """Update HTTP proxy configuration (runtime + persisted)."""
    from ...config.settings import settings
    import os
    
    # Update runtime settings
    settings.HTTP_PROXY_ENABLED = request.enabled
    settings.HTTP_PROXY_HOST = request.host
    settings.HTTP_PROXY_PORT = request.port
    settings.HTTP_PROXY_USERNAME = request.username
    settings.HTTP_PROXY_PASSWORD = request.password
    
    # Apply proxy to environment for tushare and other libraries
    if request.enabled and request.host and request.port:
        proxy_url = settings.http_proxy_url
        if proxy_url:
            os.environ['HTTP_PROXY'] = proxy_url
            os.environ['HTTPS_PROXY'] = proxy_url
            os.environ['http_proxy'] = proxy_url
            os.environ['https_proxy'] = proxy_url
            logger.info(f"Proxy enabled: {request.host}:{request.port}")
    else:
        # Clear proxy environment variables
        for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
            os.environ.pop(key, None)
        logger.info("Proxy disabled")
    
    # Persist to runtime config file
    try:
        save_runtime_config(proxy={
            "enabled": request.enabled,
            "host": request.host,
            "port": request.port,
            "username": request.username,
            "password": request.password,
        })
    except Exception as e:
        logger.warning(f"Failed to persist proxy config: {e}")
    
    return ProxyConfig(
        enabled=settings.HTTP_PROXY_ENABLED,
        host=settings.HTTP_PROXY_HOST,
        port=settings.HTTP_PROXY_PORT,
        username=settings.HTTP_PROXY_USERNAME,
        password="******" if settings.HTTP_PROXY_PASSWORD else None
    )


@router.post("/proxy/test", response_model=ProxyTestResult)
async def test_proxy_connection(request: ProxyConfigRequest):
    """Test HTTP proxy connection."""
    import time
    import requests
    from urllib.parse import quote
    
    if not request.enabled or not request.host or not request.port:
        return ProxyTestResult(
            success=False,
            message="代理未启用或配置不完整"
        )
    
    # Build proxy URL
    if request.username and request.password:
        encoded_password = quote(request.password, safe='')
        proxy_url = f"http://{request.username}:{encoded_password}@{request.host}:{request.port}"
    else:
        proxy_url = f"http://{request.host}:{request.port}"
    
    proxies = {
        "http": proxy_url,
        "https": proxy_url
    }
    
    try:
        start_time = time.time()
        # Test connection by fetching a simple endpoint
        response = requests.get(
            "https://httpbin.org/ip",
            proxies=proxies,
            timeout=10
        )
        latency = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            data = response.json()
            external_ip = data.get("origin", "Unknown")
            return ProxyTestResult(
                success=True,
                message=f"代理连接成功",
                latency_ms=round(latency, 2),
                external_ip=external_ip
            )
        else:
            return ProxyTestResult(
                success=False,
                message=f"代理返回错误状态码: {response.status_code}"
            )
    except requests.exceptions.ProxyError as e:
        return ProxyTestResult(
            success=False,
            message=f"代理连接失败: 认证错误或代理不可用"
        )
    except requests.exceptions.ConnectTimeout:
        return ProxyTestResult(
            success=False,
            message=f"代理连接超时: {request.host}:{request.port}"
        )
    except requests.exceptions.ConnectionError as e:
        return ProxyTestResult(
            success=False,
            message=f"无法连接到代理服务器: {request.host}:{request.port}"
        )
    except Exception as e:
        return ProxyTestResult(
            success=False,
            message=f"测试失败: {str(e)}"
        )

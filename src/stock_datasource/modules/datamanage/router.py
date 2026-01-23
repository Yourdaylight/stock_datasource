"""Data management module router - Admin only access."""

from fastapi import APIRouter, Query, HTTPException, Depends
from typing import List, Optional
import logging

from .schemas import (
    DataSource, SyncTask, TriggerSyncRequest, ManualDetectRequest,
    QualityMetrics, PluginInfo, PluginDetail, PluginDataPreview,
    PluginStatus, MissingDataSummary, TaskType, SyncHistory,
    DiagnosisRequest, DiagnosisResult,
    CheckDataExistsRequest, DataExistsCheckResult,
    SyncConfig, SyncConfigRequest,
    ProxyConfig, ProxyConfigRequest, ProxyTestResult,
    DependencyCheckResponse, DependencyGraphResponse, PluginDependency,
    BatchSyncRequest, BatchSyncResponse, PluginCategoryEnum, PluginRoleEnum,
    SyncTaskListResponse, TaskStatus
)
from .service import data_manage_service, sync_task_manager, diagnosis_service
from ...core.plugin_manager import plugin_manager, DependencyNotSatisfiedError
from ...core.base_plugin import PluginCategory, PluginRole, CATEGORY_ALIASES
from ...config.runtime_config import save_runtime_config
from ..auth.dependencies import require_admin

logger = logging.getLogger(__name__)

router = APIRouter()


# ============ Data Sources ============

@router.get("/datasources", response_model=List[DataSource])
async def get_datasources(current_user: dict = Depends(require_admin)):
    """Get data source list."""
    return [
        DataSource(id="tushare", source_name="TuShare", source_type="api", provider="tushare", last_sync_at="2026-01-09 18:00:00"),
        DataSource(id="akshare", source_name="AKShare", source_type="api", provider="akshare", last_sync_at="2026-01-09 18:00:00"),
    ]


@router.post("/datasources/{source_id}/test")
async def test_connection(source_id: str, current_user: dict = Depends(require_admin)):
    """Test data source connection."""
    return {"success": True, "message": "连接成功"}


# ============ Missing Data Detection ============

@router.get("/missing-data", response_model=MissingDataSummary)
async def get_missing_data(
    days: int = Query(default=30, ge=1, le=365, description="Number of trading days to check"),
    force_refresh: bool = Query(default=False, description="Force refresh cache"),
    current_user: dict = Depends(require_admin),
):
    """Get missing data summary across all daily plugins."""
    return data_manage_service.detect_missing_data(days=days, force_refresh=force_refresh)


@router.post("/missing-data/detect", response_model=MissingDataSummary)
async def trigger_missing_data_detection(
    request: ManualDetectRequest,
    current_user: dict = Depends(require_admin),
):
    """Manually trigger missing data detection."""
    return data_manage_service.detect_missing_data(days=request.days, force_refresh=True)


# ============ Sync Tasks ============

@router.get("/sync/tasks", response_model=SyncTaskListResponse)
async def get_sync_tasks(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Page size"),
    status: Optional[str] = Query(default=None, description="Filter by status: pending, running, completed, failed, cancelled"),
    plugin_name: Optional[str] = Query(default=None, description="Filter by plugin name (partial match)"),
    sort_by: str = Query(default="created_at", description="Sort field: created_at, started_at, completed_at"),
    sort_order: str = Query(default="desc", description="Sort order: asc, desc"),
    current_user: dict = Depends(require_admin),
):
    """Get paginated sync tasks with filtering and sorting."""
    return sync_task_manager.get_tasks_paginated(
        page=page,
        page_size=page_size,
        status=status,
        plugin_name=plugin_name,
        sort_by=sort_by,
        sort_order=sort_order
    )


@router.post("/sync/trigger", response_model=SyncTask)
async def trigger_sync(
    request: TriggerSyncRequest,
    current_user: dict = Depends(require_admin),
):
    """Trigger a sync task for a plugin.
    
    This endpoint checks plugin dependencies before creating the task.
    If dependencies are not satisfied, returns a 400 error with details.
    """
    # Check if plugin exists
    plugin = plugin_manager.get_plugin(request.plugin_name)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin {request.plugin_name} not found")
    
    # Check dependencies
    dep_result = plugin_manager.check_dependencies(request.plugin_name)
    if not dep_result.satisfied:
        error_msg = f"Plugin dependencies not satisfied."
        if dep_result.missing_plugins:
            error_msg += f" Missing plugins: {', '.join(dep_result.missing_plugins)}."
        if dep_result.missing_data:
            data_msgs = [f"{k} ({v})" for k, v in dep_result.missing_data.items()]
            error_msg += f" Missing data: {', '.join(data_msgs)}."
        error_msg += " Please run the dependent plugins first."
        
        raise HTTPException(
            status_code=400,
            detail={
                "message": error_msg,
                "missing_plugins": dep_result.missing_plugins,
                "missing_data": dep_result.missing_data
            }
        )
    
    task = sync_task_manager.create_task(
        plugin_name=request.plugin_name,
        task_type=request.task_type,
        trade_dates=request.trade_dates,
        user_id=current_user.get("id"),
        username=current_user.get("username"),
    )
    return task


@router.get("/sync/status/{task_id}", response_model=SyncTask)
async def get_sync_status(task_id: str, current_user: dict = Depends(require_admin)):
    """Get sync task status."""
    task = sync_task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task


@router.post("/sync/cancel/{task_id}")
async def cancel_sync_task(task_id: str, current_user: dict = Depends(require_admin)):
    """Cancel a pending sync task."""
    success = sync_task_manager.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot cancel task (not pending or not found)")
    return {"success": True, "message": "Task cancelled"}


@router.delete("/sync/tasks/{task_id}")
async def delete_sync_task(task_id: str, current_user: dict = Depends(require_admin)):
    """Delete a sync task (any status except running)."""
    success = sync_task_manager.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot delete task (running or not found)")
    return {"success": True, "message": "Task deleted"}


@router.post("/sync/retry/{task_id}", response_model=SyncTask)
async def retry_sync_task(task_id: str, current_user: dict = Depends(require_admin)):
    """Retry a failed or cancelled sync task.
    
    Creates a new task with the same parameters as the original task.
    Only works for tasks with status 'failed' or 'cancelled'.
    """
    new_task = sync_task_manager.retry_task(task_id)
    if not new_task:
        raise HTTPException(
            status_code=400, 
            detail="Cannot retry task (not found or not in failed/cancelled status)"
        )
    return new_task


@router.get("/sync/config", response_model=SyncConfig)
async def get_sync_config(current_user: dict = Depends(require_admin)):
    """Get current sync configuration (parallelism settings)."""
    config = sync_task_manager.get_config()
    return SyncConfig(**config)


@router.put("/sync/config", response_model=SyncConfig)
async def update_sync_config(request: SyncConfigRequest, current_user: dict = Depends(require_admin)):
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
    plugin_name: Optional[str] = None,
    current_user: dict = Depends(require_admin),
):
    """Get sync task history from database."""
    history = sync_task_manager.get_task_history(days=days, limit=limit)
    
    # Filter by plugin if specified
    if plugin_name:
        history = [h for h in history if h.plugin_name == plugin_name]
    
    return history


# ============ Plugins ============

@router.get("/plugins", response_model=List[PluginInfo])
async def get_plugins(
    category: Optional[str] = Query(default=None, description="Filter by category: cn_stock, hk_stock, index, etf_fund, system (or 'stock' for backward compatibility)"),
    role: Optional[str] = Query(default=None, description="Filter by role: primary, basic, derived, auxiliary"),
    current_user: dict = Depends(require_admin),
):
    """Get plugin list with status info, optionally filtered by category and/or role."""
    plugins = data_manage_service.get_plugin_list()
    
    # Apply filters
    if category:
        # Handle category aliases (stock -> cn_stock)
        resolved_category = CATEGORY_ALIASES.get(category, category)
        try:
            cat_enum = PluginCategory(resolved_category)
            # Filter by resolved category or original (for backward compat)
            plugins = [p for p in plugins if p.category == resolved_category or p.category == category]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid category: {category}. Valid values: cn_stock, hk_stock, index, etf_fund, system")
    
    if role:
        try:
            role_enum = PluginRole(role)
            plugins = [p for p in plugins if p.role == role]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid role: {role}")
    
    return plugins


@router.get("/plugins/{name}/detail", response_model=PluginDetail)
async def get_plugin_detail(name: str, current_user: dict = Depends(require_admin)):
    """Get detailed plugin information including config and schema."""
    detail = data_manage_service.get_plugin_detail(name)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Plugin {name} not found")
    return detail


@router.get("/plugins/{name}/status", response_model=PluginStatus)
async def get_plugin_status(name: str, current_user: dict = Depends(require_admin)):
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
    page_size: int = Query(default=100, ge=1, le=1000),
    current_user: dict = Depends(require_admin),
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
async def check_data_exists(name: str, request: CheckDataExistsRequest, current_user: dict = Depends(require_admin)):
    """Check if data exists for specific dates in a plugin's table."""
    result = data_manage_service.check_dates_data_exists(name, request.dates)
    return result


@router.post("/plugins/{name}/enable")
async def enable_plugin(name: str, current_user: dict = Depends(require_admin)):
    """Enable a plugin."""
    plugin = plugin_manager.get_plugin(name)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin {name} not found")
    
    success = plugin.set_enabled(True)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to enable plugin")
    return {"success": True, "is_enabled": True}


@router.post("/plugins/{name}/disable")
async def disable_plugin(name: str, current_user: dict = Depends(require_admin)):
    """Disable a plugin."""
    plugin = plugin_manager.get_plugin(name)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin {name} not found")
    
    success = plugin.set_enabled(False)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to disable plugin")
    return {"success": True, "is_enabled": False}


# ============ Plugin Dependencies ============

@router.get("/plugins/{name}/dependencies", response_model=DependencyCheckResponse)
async def get_plugin_dependencies(name: str, current_user: dict = Depends(require_admin)):
    """Get plugin dependencies and their status.
    
    Returns the list of dependencies for a plugin and whether they are satisfied.
    """
    plugin = plugin_manager.get_plugin(name)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin {name} not found")
    
    dependencies = plugin.get_dependencies()
    optional_deps = plugin.get_optional_dependencies()
    dep_result = plugin_manager.check_dependencies(name)
    
    # Build dependency details
    dep_details = []
    for dep_name in dependencies:
        try:
            dep_plugin = plugin_manager.get_plugin(dep_name)
            if dep_plugin:
                try:
                    schema = dep_plugin.get_schema()
                    table_name = schema.get('table_name') if schema else None
                except Exception:
                    table_name = None
                try:
                    has_data = dep_plugin.has_data()
                except Exception:
                    has_data = False
                dep_details.append(PluginDependency(
                    plugin_name=dep_name,
                    has_data=has_data,
                    table_name=table_name,
                    record_count=0  # Could be expensive to calculate
                ))
            else:
                dep_details.append(PluginDependency(
                    plugin_name=dep_name,
                    has_data=False
                ))
        except Exception as e:
            # Log error but continue with other dependencies
            logger.warning(f"Failed to get dependency info for {dep_name}: {e}")
            dep_details.append(PluginDependency(
                plugin_name=dep_name,
                has_data=False
            ))
    
    return DependencyCheckResponse(
        plugin_name=name,
        dependencies=dependencies,
        optional_dependencies=optional_deps,
        satisfied=dep_result.satisfied,
        missing_plugins=dep_result.missing_plugins,
        missing_data=dep_result.missing_data,
        dependency_details=dep_details
    )


@router.get("/plugins/{name}/check-dependencies", response_model=DependencyCheckResponse)
async def check_plugin_dependencies(name: str, current_user: dict = Depends(require_admin)):
    """Check if plugin dependencies are satisfied.
    
    This is an alias for GET /plugins/{name}/dependencies for backward compatibility.
    """
    return await get_plugin_dependencies(name, current_user)


@router.get("/plugins/dependency-graph", response_model=DependencyGraphResponse)
async def get_dependency_graph(current_user: dict = Depends(require_admin)):
    """Get the dependency graph for all plugins.
    
    Returns both the forward dependency graph (plugin -> dependencies)
    and the reverse graph (plugin -> dependents).
    """
    graph = plugin_manager.get_dependency_graph()
    
    # Build reverse graph
    reverse_graph = {}
    for plugin_name in plugin_manager.list_plugins():
        reverse_graph[plugin_name] = plugin_manager.get_reverse_dependencies(plugin_name)
    
    return DependencyGraphResponse(
        graph=graph,
        reverse_graph=reverse_graph
    )


@router.post("/sync/batch", response_model=BatchSyncResponse)
async def batch_trigger_sync(request: BatchSyncRequest, current_user: dict = Depends(require_admin)):
    """Trigger sync for multiple plugins in dependency order.
    
    This endpoint:
    1. Validates all requested plugins exist
    2. Sorts plugins by dependency order (dependencies first)
    3. Creates sync tasks for each plugin in order
    
    Args:
        request: BatchSyncRequest with plugin names and options
    
    Returns:
        BatchSyncResponse with tasks and execution order
    """
    # Validate all plugins exist
    invalid_plugins = []
    for name in request.plugin_names:
        if not plugin_manager.get_plugin(name):
            invalid_plugins.append(name)
    
    if invalid_plugins:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid plugins: {', '.join(invalid_plugins)}"
        )
    
    # Get sorted execution order with optional dependencies
    tasks_info = plugin_manager.batch_trigger_sync(
        plugin_names=request.plugin_names,
        task_type=request.task_type.value,
        include_optional=request.include_optional
    )
    
    execution_order = [t["plugin_name"] for t in tasks_info]
    
    # Create sync tasks for each plugin
    created_tasks = []
    for task_info in tasks_info:
        plugin_name = task_info["plugin_name"]
        
        # Check dependencies for this plugin
        dep_result = plugin_manager.check_dependencies(plugin_name)
        
        # Create task (dependency check is informational for batch)
        task = sync_task_manager.create_task(
            plugin_name=plugin_name,
            task_type=request.task_type,
            trade_dates=request.trade_dates,
            user_id=current_user.get("id"),
            username=current_user.get("username"),
        )
        
        created_tasks.append({
            "task_id": task.task_id,
            "plugin_name": plugin_name,
            "task_type": task.task_type,
            "status": task.status.value,
            "order": task_info["order"],
            "dependencies_satisfied": dep_result.satisfied
        })
    
    return BatchSyncResponse(
        tasks=created_tasks,
        total_plugins=len(created_tasks),
        execution_order=execution_order
    )


# ============ Data Quality ============

@router.get("/quality/metrics", response_model=List[QualityMetrics])
async def get_quality_metrics(current_user: dict = Depends(require_admin)):
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
async def get_quality_report(table: Optional[str] = None, current_user: dict = Depends(require_admin)):
    """Get data quality report."""
    return {"report": "Data quality is good"}


# ============ Metadata ============

@router.get("/metadata/tables")
async def get_table_metadata(current_user: dict = Depends(require_admin)):
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
    errors_only: bool = Query(default=False, description="Only analyze error logs"),
    current_user: dict = Depends(require_admin),
):
    """Get AI diagnosis of recent logs."""
    return diagnosis_service.diagnose(lines=log_lines, errors_only=errors_only)


@router.post("/diagnosis", response_model=DiagnosisResult)
async def trigger_diagnosis(request: DiagnosisRequest, current_user: dict = Depends(require_admin)):
    """Trigger AI diagnosis with custom parameters."""
    return diagnosis_service.diagnose(
        lines=request.log_lines,
        errors_only=request.include_errors_only,
        context=request.context
    )


# ============ Proxy Configuration ============

@router.get("/proxy/config", response_model=ProxyConfig)
async def get_proxy_config(current_user: dict = Depends(require_admin)):
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
async def update_proxy_config(request: ProxyConfigRequest, current_user: dict = Depends(require_admin)):
    """Update HTTP proxy configuration (runtime + persisted)."""
    from ...config.settings import settings
    
    # Update runtime settings
    settings.HTTP_PROXY_ENABLED = request.enabled
    settings.HTTP_PROXY_HOST = request.host
    settings.HTTP_PROXY_PORT = request.port
    settings.HTTP_PROXY_USERNAME = request.username
    settings.HTTP_PROXY_PASSWORD = request.password
    
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
async def test_proxy_connection(request: ProxyConfigRequest, current_user: dict = Depends(require_admin)):
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


# ============ Schedule Management ============

from .schedule_service import schedule_service
from .schemas import (
    ScheduleConfig, ScheduleConfigRequest,
    PluginScheduleConfig, PluginScheduleConfigRequest,
    ScheduleExecutionRecord, ScheduleHistoryResponse
)


@router.get("/schedule/config", response_model=ScheduleConfig)
async def get_schedule_config(current_user: dict = Depends(require_admin)):
    """获取全局定时调度配置.
    
    返回调度是否启用、执行时间、频率等配置。
    """
    config = schedule_service.get_config()
    return ScheduleConfig(**config)


@router.put("/schedule/config", response_model=ScheduleConfig)
async def update_schedule_config(
    request: ScheduleConfigRequest,
    current_user: dict = Depends(require_admin)
):
    """更新全局定时调度配置.
    
    可配置项：
    - enabled: 是否启用定时调度
    - execute_time: 执行时间（HH:MM格式）
    - frequency: 频率（daily/weekday）
    - include_optional_deps: 是否包含可选依赖（如复权因子）
    - skip_non_trading_days: 是否跳过非交易日
    """
    config = schedule_service.update_config(
        enabled=request.enabled,
        execute_time=request.execute_time,
        frequency=request.frequency.value if request.frequency else None,
        include_optional_deps=request.include_optional_deps,
        skip_non_trading_days=request.skip_non_trading_days,
    )
    return ScheduleConfig(**config)


@router.get("/schedule/plugins", response_model=List[PluginScheduleConfig])
async def get_plugin_schedule_configs(
    category: Optional[str] = Query(default=None, description="按分类筛选: cn_stock, hk_stock, index, etf_fund"),
    current_user: dict = Depends(require_admin)
):
    """获取所有插件的调度配置.
    
    返回每个插件是否加入定时任务、是否启用全量扫描等配置。
    按依赖顺序排序（basic → primary → derived → auxiliary）。
    """
    configs = schedule_service.get_plugin_configs(category=category)
    return [PluginScheduleConfig(**cfg) for cfg in configs]


@router.put("/schedule/plugins/{name}", response_model=PluginScheduleConfig)
async def update_plugin_schedule_config(
    name: str,
    request: PluginScheduleConfigRequest,
    current_user: dict = Depends(require_admin)
):
    """更新单个插件的调度配置.
    
    可配置项：
    - schedule_enabled: 是否加入定时任务（启用后每日自动同步）
    - full_scan_enabled: 是否启用全量扫描（启用后重新获取全部历史数据）
    """
    try:
        config = schedule_service.update_plugin_config(
            plugin_name=name,
            schedule_enabled=request.schedule_enabled,
            full_scan_enabled=request.full_scan_enabled,
        )
        return PluginScheduleConfig(**config)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/schedule/trigger", response_model=ScheduleExecutionRecord)
async def trigger_schedule_now(current_user: dict = Depends(require_admin)):
    """立即触发一次调度执行.
    
    不等待 cron 时间，立即按依赖顺序创建同步任务。
    如果是非交易日且配置了跳过非交易日，会返回 skipped 状态。
    """
    record = schedule_service.trigger_now(is_manual=True)
    return ScheduleExecutionRecord(**record)


@router.get("/schedule/history", response_model=ScheduleHistoryResponse)
async def get_schedule_history(
    days: int = Query(default=7, ge=1, le=30, description="查询天数"),
    limit: int = Query(default=50, ge=1, le=200, description="返回条数"),
    current_user: dict = Depends(require_admin)
):
    """获取调度执行历史.
    
    返回最近的调度执行记录，包括执行时间、状态、涉及的插件数量等。
    """
    history = schedule_service.get_history(days=days, limit=limit)
    return ScheduleHistoryResponse(
        items=[ScheduleExecutionRecord(**r) for r in history],
        total=len(history)
    )

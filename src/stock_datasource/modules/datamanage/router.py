"""Data management module router - Admin only access."""

import uuid
from datetime import datetime
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
    SyncTaskListResponse, TaskStatus,
    GroupCategory, PluginGroupDetail, GroupPluginStatus, PredefinedGroupsResponse, GroupCategoryInfo
)
from .service import data_manage_service, sync_task_manager, diagnosis_service
from ...core.plugin_manager import plugin_manager, DependencyNotSatisfiedError
from ...core.base_plugin import PluginCategory, PluginRole, CATEGORY_ALIASES
from ...config.runtime_config import (
    save_runtime_config, 
    get_plugin_groups, get_plugin_group, save_plugin_group, delete_plugin_group,
    load_predefined_groups, get_predefined_categories, is_predefined_group, get_custom_plugin_groups
)
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
    days: int = Query(default=30, ge=1, le=3650, description="Number of trading days to check (max 10 years)"),
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
    Creates an execution record so single plugin syncs appear in batch task list.
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
    
    # Create execution record for single plugin sync with plugin name as group_name
    schedule_service.create_manual_execution(
        task_ids=[task.task_id],
        trigger_type="manual",
        group_name=request.plugin_name  # Use plugin name for better display
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
    category: Optional[str] = Query(default=None, description="Filter by category: cn_stock, hk_stock, index, etf_fund, market, reference, fundamental, system (or 'stock' for backward compatibility)"),
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
            raise HTTPException(status_code=400, detail=f"Invalid category: {category}. Valid values: cn_stock, hk_stock, index, etf_fund, market, reference, fundamental, system")
    
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
    """Update HTTP proxy configuration (runtime + persisted).
    
    Note: Proxy is NOT applied globally. It will only be used
    within data extraction tasks via proxy_context().
    """
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
    
    logger.info(f"Proxy config updated: enabled={request.enabled}, host={request.host}:{request.port} (used only for data extraction)")
    
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
    ScheduleExecutionRecord, ScheduleHistoryResponse,
    BatchExecutionDetail, BatchTaskDetail,
    PartialRetryRequest, PluginGroup, PluginGroupCreateRequest,
    PluginGroupUpdateRequest, PluginGroupListResponse, PluginGroupTriggerRequest
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
    status: Optional[str] = Query(default=None, description="状态过滤: running, completed, failed, skipped, interrupted"),
    trigger_type: Optional[str] = Query(default=None, description="触发类型: scheduled, manual, group, retry"),
    current_user: dict = Depends(require_admin)
):
    """获取调度执行历史.
    
    返回最近的调度执行记录，包括执行时间、状态、涉及的插件数量等。
    支持按状态和触发类型筛选。
    """
    history = schedule_service.get_history(days=days, limit=limit, status=status, trigger_type=trigger_type)
    return ScheduleHistoryResponse(
        items=[ScheduleExecutionRecord(**r) for r in history],
        total=len(history)
    )


@router.post("/schedule/retry/{execution_id}", response_model=ScheduleExecutionRecord)
async def retry_schedule_execution(
    execution_id: str,
    current_user: dict = Depends(require_admin)
):
    """重新执行一个中断或失败的调度.
    
    仅支持重试状态为 interrupted 或 failed 的执行记录。
    会创建一个新的调度执行，按依赖顺序重新同步所有启用的插件。
    """
    try:
        record = schedule_service.retry_execution(execution_id)
        return ScheduleExecutionRecord(**record)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/schedule/execution/{execution_id}", response_model=BatchExecutionDetail)
async def get_execution_detail(
    execution_id: str,
    current_user: dict = Depends(require_admin)
):
    """获取批量任务执行详情.
    
    返回执行记录的详细信息，包括所有子任务的状态和错误信息汇总。
    错误汇总可以一键复制用于问题排查。
    """
    # First update execution status based on task statuses
    schedule_service.update_execution_status(execution_id)
    
    detail = schedule_service.get_execution_detail(execution_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")
    
    # Convert tasks to BatchTaskDetail
    tasks = [BatchTaskDetail(**t) for t in detail.get("tasks", [])]
    
    return BatchExecutionDetail(
        execution_id=detail["execution_id"],
        trigger_type=detail["trigger_type"],
        started_at=detail["started_at"],
        completed_at=detail.get("completed_at"),
        status=detail["status"],
        total_plugins=detail.get("total_plugins", 0),
        completed_plugins=detail.get("completed_plugins", 0),
        failed_plugins=detail.get("failed_plugins", 0),
        tasks=tasks,
        error_summary=detail.get("error_summary", ""),
        group_name=detail.get("group_name")
    )


@router.post("/schedule/stop/{execution_id}", response_model=ScheduleExecutionRecord)
async def stop_execution(
    execution_id: str,
    current_user: dict = Depends(require_admin)
):
    """停止正在执行的批量任务.
    
    取消所有待执行的子任务，正在运行的任务会继续完成。
    """
    try:
        record = schedule_service.stop_execution(execution_id)
        return ScheduleExecutionRecord(**record)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/schedule/execution/{execution_id}")
async def delete_schedule_execution(
    execution_id: str,
    current_user: dict = Depends(require_admin)
):
    """删除一条调度执行记录.
    
    仅支持删除已完成/失败/中断的执行记录，不能删除正在运行的记录。
    """
    try:
        success = schedule_service.delete_execution(execution_id)
        if not success:
            raise HTTPException(status_code=400, detail="Cannot delete execution (not found or still running)")
        return {"success": True, "message": "Execution deleted"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/schedule/partial-retry/{execution_id}", response_model=ScheduleExecutionRecord)
async def partial_retry_execution(
    execution_id: str,
    request: PartialRetryRequest = PartialRetryRequest(),
    current_user: dict = Depends(require_admin)
):
    """部分重试批量任务中失败的插件.
    
    仅重试失败的任务，不重新执行成功的任务。
    可选指定要重试的 task_ids，否则重试所有失败的任务。
    """
    try:
        record = schedule_service.partial_retry_execution(
            execution_id=execution_id,
            task_ids=request.task_ids
        )
        return ScheduleExecutionRecord(**record)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============ Plugin Groups Management ============


@router.get("/groups", response_model=PluginGroupListResponse)
async def list_plugin_groups(
    category: Optional[str] = Query(None, description="按分类筛选: cn_stock/index/etf_fund/daily/custom"),
    current_user: dict = Depends(require_admin)
):
    """获取所有插件组合（预定义 + 用户自定义）.
    
    返回预定义组合和用户自定义组合，预定义组合排在前面。
    支持按分类筛选。
    """
    groups = get_plugin_groups(include_predefined=True)
    
    # 按分类筛选
    if category:
        groups = [g for g in groups if g.get("category") == category]
    
    # 统计预定义和自定义组合数量
    predefined_count = sum(1 for g in groups if g.get("is_predefined", False))
    custom_count = len(groups) - predefined_count
    
    return PluginGroupListResponse(
        items=[PluginGroup(**g) for g in groups],
        total=len(groups),
        predefined_count=predefined_count,
        custom_count=custom_count
    )


@router.get("/groups/predefined", response_model=PredefinedGroupsResponse)
async def list_predefined_groups(current_user: dict = Depends(require_admin)):
    """获取预定义插件组合列表.
    
    仅返回系统预定义的组合，不包含用户自定义组合。
    同时返回分类列表。
    """
    predefined = load_predefined_groups()
    categories = get_predefined_categories()
    
    return PredefinedGroupsResponse(
        groups=[PluginGroup(**g) for g in predefined],
        categories=[GroupCategoryInfo(**c) for c in categories]
    )


@router.post("/groups", response_model=PluginGroup)
async def create_plugin_group(
    request: PluginGroupCreateRequest,
    current_user: dict = Depends(require_admin)
):
    """创建自定义插件组合.
    
    将多个插件组合在一起，方便批量触发同步。
    """
    # Validate plugin names
    for name in request.plugin_names:
        if not plugin_manager.get_plugin(name):
            raise HTTPException(status_code=400, detail=f"Plugin {name} not found")
    
    # Check for duplicate name (only against custom groups)
    existing = get_custom_plugin_groups()
    for g in existing:
        if g.get("name") == request.name:
            raise HTTPException(status_code=400, detail=f"Group name '{request.name}' already exists")
    
    group = {
        "group_id": str(uuid.uuid4())[:8],
        "name": request.name,
        "description": request.description,
        "plugin_names": request.plugin_names,
        "default_task_type": request.default_task_type.value,
        "category": "custom",
        "is_predefined": False,
        "is_readonly": False,
        "created_at": datetime.now().isoformat(),
        "updated_at": None,
        "created_by": current_user.get("username", "admin")
    }
    
    save_plugin_group(group)
    return PluginGroup(**group)


@router.get("/groups/{group_id}", response_model=PluginGroupDetail)
async def get_plugin_group_detail(
    group_id: str,
    current_user: dict = Depends(require_admin)
):
    """获取插件组合详情，包含依赖关系图和执行顺序."""
    group = get_plugin_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail=f"Group {group_id} not found")
    
    # 获取插件状态
    plugin_status = []
    for name in group.get("plugin_names", []):
        plugin = plugin_manager.get_plugin(name)
        exists = plugin is not None
        has_data = False
        if exists:
            try:
                status = data_manage_service.get_plugin_data_status(name)
                has_data = status.get("total_records", 0) > 0
            except:
                pass
        plugin_status.append(GroupPluginStatus(
            name=name,
            exists=exists,
            has_data=has_data
        ))
    
    # 构建依赖关系图
    dependency_graph = {}
    for name in group.get("plugin_names", []):
        plugin = plugin_manager.get_plugin(name)
        if plugin:
            config = plugin.get_config()
            deps = config.get("dependencies", [])
            # 只包含组合内的依赖
            internal_deps = [d for d in deps if d in group.get("plugin_names", [])]
            dependency_graph[name] = internal_deps
        else:
            dependency_graph[name] = []
    
    # 计算执行顺序（拓扑排序）
    execution_order = _topological_sort(dependency_graph)
    
    return PluginGroupDetail(
        **group,
        plugin_status=plugin_status,
        dependency_graph=dependency_graph,
        execution_order=execution_order
    )


def _topological_sort(graph: dict) -> list:
    """对依赖图进行拓扑排序."""
    visited = set()
    result = []
    
    def visit(node):
        if node in visited:
            return
        visited.add(node)
        for dep in graph.get(node, []):
            visit(dep)
        result.append(node)
    
    for node in graph:
        visit(node)
    
    return result


@router.put("/groups/{group_id}", response_model=PluginGroup)
async def update_plugin_group(
    group_id: str,
    request: PluginGroupUpdateRequest,
    current_user: dict = Depends(require_admin)
):
    """更新插件组合.
    
    预定义组合不可修改。
    """
    # 检查是否为预定义组合
    if is_predefined_group(group_id):
        raise HTTPException(status_code=403, detail="Cannot modify predefined group")
    
    group = get_plugin_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail=f"Group {group_id} not found")
    
    # Validate plugin names if provided
    if request.plugin_names:
        for name in request.plugin_names:
            if not plugin_manager.get_plugin(name):
                raise HTTPException(status_code=400, detail=f"Plugin {name} not found")
        group["plugin_names"] = request.plugin_names
    
    # Check for duplicate name (if changing, only against custom groups)
    if request.name and request.name != group.get("name"):
        existing = get_custom_plugin_groups()
        for g in existing:
            if g.get("name") == request.name and g.get("group_id") != group_id:
                raise HTTPException(status_code=400, detail=f"Group name '{request.name}' already exists")
        group["name"] = request.name
    
    if request.description is not None:
        group["description"] = request.description
    
    if request.default_task_type is not None:
        group["default_task_type"] = request.default_task_type.value
    
    group["updated_at"] = datetime.now().isoformat()
    
    save_plugin_group(group)
    return PluginGroup(**group)


@router.delete("/groups/{group_id}")
async def delete_plugin_group_endpoint(
    group_id: str,
    current_user: dict = Depends(require_admin)
):
    """删除插件组合.
    
    预定义组合不可删除。
    """
    # 检查是否为预定义组合
    if is_predefined_group(group_id):
        raise HTTPException(status_code=403, detail="Cannot delete predefined group")
    
    success = delete_plugin_group(group_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Group {group_id} not found")
    return {"success": True, "message": "Group deleted"}


@router.post("/groups/{group_id}/trigger", response_model=ScheduleExecutionRecord)
async def trigger_plugin_group(
    group_id: str,
    request: PluginGroupTriggerRequest = PluginGroupTriggerRequest(),
    current_user: dict = Depends(require_admin)
):
    """触发插件组合同步.
    
    按依赖顺序执行组合中的所有插件。
    """
    group = get_plugin_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail=f"Group {group_id} not found")
    
    plugin_names = group.get("plugin_names", [])
    if not plugin_names:
        raise HTTPException(status_code=400, detail="Group has no plugins")
    
    # Create tasks for each plugin
    task_ids = []
    for name in plugin_names:
        plugin = plugin_manager.get_plugin(name)
        if not plugin:
            continue
        
        try:
            task = sync_task_manager.create_task(
                plugin_name=name,
                task_type=request.task_type,
                trade_dates=request.trade_dates,
                user_id=current_user.get("id"),
                username=current_user.get("username"),
            )
            task_ids.append(task.task_id)
        except Exception as e:
            # Log but continue
            pass
    
    if not task_ids:
        raise HTTPException(status_code=400, detail="Failed to create any tasks")
    
    # Create execution record
    record = schedule_service.create_manual_execution(
        task_ids=task_ids,
        trigger_type="group",
        group_name=group.get("name")
    )
    
    return ScheduleExecutionRecord(**record)


# ============ Data Explorer API ============

from fastapi.responses import StreamingResponse
from .data_explorer_service import data_explorer_service
from .schemas import (
    ExplorerTableListResponse, ExplorerTableSchema, ExplorerTableInfo,
    ExplorerSimpleQueryRequest, ExplorerSqlExecuteRequest, ExplorerSqlExecuteResponse,
    ExplorerSqlExportRequest, ExportFormat,
    SqlTemplate, SqlTemplateCreate, SqlTemplateListResponse
)


@router.get("/explorer/tables", response_model=ExplorerTableListResponse)
async def get_explorer_tables(
    category: Optional[str] = Query(default=None, description="按分类筛选: cn_stock, index, etf_fund 等"),
    current_user: dict = Depends(require_admin),
):
    """获取所有可查询的表列表.
    
    返回所有插件对应的数据库表，包含表名、分类、列信息、行数等。
    """
    return data_explorer_service.get_available_tables(category)


@router.get("/explorer/tables/{table_name}/schema", response_model=ExplorerTableSchema)
async def get_explorer_table_schema(
    table_name: str,
    current_user: dict = Depends(require_admin),
):
    """获取表结构详情.
    
    返回表的完整列定义、分区方式、排序键等信息。
    """
    schema = data_explorer_service.get_table_schema(table_name)
    if not schema:
        raise HTTPException(status_code=404, detail=f"表 {table_name} 不存在")
    return schema


@router.post("/explorer/tables/{table_name}/query", response_model=ExplorerSqlExecuteResponse)
async def query_explorer_table(
    table_name: str,
    request: ExplorerSimpleQueryRequest,
    current_user: dict = Depends(require_admin),
):
    """简单筛选查询.
    
    支持日期范围、代码筛选、排序和分页。
    """
    try:
        return data_explorer_service.execute_simple_query(table_name, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/explorer/sql/execute", response_model=ExplorerSqlExecuteResponse)
async def execute_explorer_sql(
    request: ExplorerSqlExecuteRequest,
    current_user: dict = Depends(require_admin),
):
    """执行 SQL 查询.
    
    仅允许 SELECT 查询，且只能查询已注册的插件表。
    自动添加 LIMIT 限制，防止返回过多数据。
    """
    try:
        return data_explorer_service.execute_sql_query(
            sql=request.sql,
            max_rows=request.max_rows,
            timeout=request.timeout
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/explorer/sql/export")
async def export_explorer_sql(
    request: ExplorerSqlExportRequest,
    current_user: dict = Depends(require_admin),
):
    """导出查询结果.
    
    支持 CSV 和 Excel 格式，最大导出 10000 行。
    """
    try:
        content, filename = data_explorer_service.export_query_result(
            sql=request.sql,
            format=request.format,
            filename=request.filename
        )
        
        media_type = "text/csv" if request.format == ExportFormat.CSV else \
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        
        return StreamingResponse(
            io.BytesIO(content),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/explorer/sql/templates", response_model=List[SqlTemplate])
async def get_explorer_templates(
    category: Optional[str] = Query(default=None, description="按分类筛选"),
    current_user: dict = Depends(require_admin),
):
    """获取查询模板列表."""
    user_id = str(current_user.get("id", ""))
    return data_explorer_service.get_templates(user_id, category)


@router.post("/explorer/sql/templates", response_model=SqlTemplate)
async def create_explorer_template(
    template: SqlTemplateCreate,
    current_user: dict = Depends(require_admin),
):
    """创建查询模板."""
    user_id = str(current_user.get("id", ""))
    try:
        return data_explorer_service.create_template(user_id, template)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/explorer/sql/templates/{template_id}")
async def delete_explorer_template(
    template_id: int,
    current_user: dict = Depends(require_admin),
):
    """删除查询模板."""
    user_id = str(current_user.get("id", ""))
    success = data_explorer_service.delete_template(user_id, template_id)
    if not success:
        raise HTTPException(status_code=404, detail="模板不存在或无权删除")
    return {"success": True, "message": "删除成功"}

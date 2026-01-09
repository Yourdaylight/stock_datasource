"""Data management module router."""

from fastapi import APIRouter, Query
from typing import List, Optional
from pydantic import BaseModel
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter()


class DataSource(BaseModel):
    id: str
    source_name: str
    source_type: str
    provider: str
    is_enabled: bool = True
    last_sync_at: str = None


class SyncTask(BaseModel):
    task_id: str
    source_id: str
    plugin_name: str
    task_type: str
    status: str
    progress: float = 0
    records_processed: int = 0
    error_message: str = None
    started_at: str = None
    completed_at: str = None


class TriggerSyncRequest(BaseModel):
    source_id: str
    sync_type: str = "incremental"


class QualityMetrics(BaseModel):
    table_name: str
    completeness_score: float
    consistency_score: float
    timeliness_score: float
    overall_score: float
    record_count: int
    latest_update: str = None


class PluginInfo(BaseModel):
    name: str
    type: str
    is_enabled: bool = True
    last_run_at: str = None
    last_run_status: str = None


@router.get("/datasources", response_model=List[DataSource])
async def get_datasources():
    """Get data source list."""
    return [
        DataSource(id="tushare", source_name="TuShare", source_type="api", provider="tushare", last_sync_at="2024-01-09 18:00:00"),
        DataSource(id="akshare", source_name="AKShare", source_type="api", provider="akshare", last_sync_at="2024-01-09 18:00:00"),
    ]


@router.post("/datasources/{source_id}/test")
async def test_connection(source_id: str):
    """Test data source connection."""
    return {"success": True, "message": "连接成功"}


@router.get("/sync/tasks", response_model=List[SyncTask])
async def get_sync_tasks():
    """Get sync task list."""
    return []


@router.post("/sync/trigger")
async def trigger_sync(request: TriggerSyncRequest):
    """Trigger data sync."""
    return {"task_id": f"task_{request.source_id}_{request.sync_type}"}


@router.get("/sync/status/{task_id}", response_model=SyncTask)
async def get_sync_status(task_id: str):
    """Get sync task status."""
    return SyncTask(
        task_id=task_id,
        source_id="tushare",
        plugin_name="tushare_daily",
        task_type="incremental",
        status="completed",
        progress=100,
        records_processed=1000
    )


@router.get("/sync/history", response_model=List[SyncTask])
async def get_sync_history(limit: int = Query(default=20)):
    """Get sync history."""
    return []


@router.get("/quality/metrics", response_model=List[QualityMetrics])
async def get_quality_metrics():
    """Get data quality metrics."""
    return [
        QualityMetrics(table_name="ods_daily", completeness_score=98.5, consistency_score=99.0, timeliness_score=95.0, overall_score=97.5, record_count=5000000),
        QualityMetrics(table_name="ods_daily_basic", completeness_score=97.0, consistency_score=98.5, timeliness_score=94.0, overall_score=96.5, record_count=5000000),
    ]


@router.get("/quality/report")
async def get_quality_report(table: Optional[str] = None):
    """Get data quality report."""
    return {"report": "Data quality is good"}


@router.get("/plugins", response_model=List[PluginInfo])
async def get_plugins():
    """Get plugin list."""
    plugins_dir = Path(__file__).parent.parent.parent / "plugins"
    plugins = []
    
    if plugins_dir.exists():
        for plugin_dir in plugins_dir.iterdir():
            if plugin_dir.is_dir() and not plugin_dir.name.startswith("_"):
                plugins.append(PluginInfo(
                    name=plugin_dir.name,
                    type="data_source",
                    is_enabled=True
                ))
    
    return plugins


@router.post("/plugins/{name}/enable")
async def enable_plugin(name: str):
    """Enable a plugin."""
    return {"success": True}


@router.post("/plugins/{name}/disable")
async def disable_plugin(name: str):
    """Disable a plugin."""
    return {"success": True}


@router.get("/metadata/tables")
async def get_table_metadata():
    """Get table metadata."""
    return [
        {"table_name": "ods_daily", "description": "A股日线数据", "row_count": 5000000, "size_bytes": 1000000000},
        {"table_name": "ods_daily_basic", "description": "日线基础指标", "row_count": 5000000, "size_bytes": 800000000},
    ]

"""FastAPI router for the sentinel system."""

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sentinel"])


@router.post("/scan")
async def trigger_scan() -> dict[str, Any]:
    """Manually trigger a full sentinel scan cycle."""
    try:
        from .core.registry import get_sentinel_registry

        registry = get_sentinel_registry()
        result = await registry.run_scan_cycle()
        return {
            "status": "ok",
            "message": "Scan cycle completed",
            "result": result,
        }
    except Exception as e:
        logger.error("Manual scan trigger failed: %s", e, exc_info=True)
        return {
            "status": "error",
            "message": str(e),
        }


@router.post("/scan/stream")
async def trigger_scan_stream():
    """Stream scan progress as SSE events for real-time observability."""

    async def generate():
        try:
            from .core.registry import get_sentinel_registry
            from datetime import datetime

            registry = get_sentinel_registry()
            if not registry._initialized:
                await registry.initialize()

            yield f"data: {json.dumps({'phase': 'start', 'message': '扫描开始', 'timestamp': datetime.now().isoformat()})}\n\n"

            # Phase 1: Sentinels scan
            yield f"data: {json.dumps({'phase': 'sentinels_start', 'message': f'启动 {len(registry._sentinels)} 个数据哨兵扫描...', 'count': len(registry._sentinels)})}\n\n"

            total_alerts = 0
            sentinel_details = []
            for sentinel in registry._sentinels:
                s_type = sentinel.SENTINEL_TYPE
                yield f"data: {json.dumps({'phase': 'sentinel_scan', 'sentinel': s_type, 'message': f'扫描中: {s_type}', 'status': 'scanning'})}\n\n"
                try:
                    alerts = await sentinel.execute_scan()
                    alert_count = len(alerts) if isinstance(alerts, list) else 0
                    total_alerts += alert_count
                    status = 'alert' if alert_count > 0 else 'silent'
                    detail = {
                        'sentinel': s_type,
                        'alert_count': alert_count,
                        'status': status,
                        'description': sentinel.DESCRIPTION if hasattr(sentinel, 'DESCRIPTION') else '',
                    }
                    sentinel_details.append(detail)
                    yield f"data: {json.dumps({'phase': 'sentinel_done', **detail, 'message': f'{s_type}: {alert_count}个告警' if alert_count else f'{s_type}: 正常'})}\n\n"
                except Exception as e:
                    sentinel_details.append({'sentinel': s_type, 'alert_count': 0, 'status': 'error', 'error': str(e)})
                    yield f"data: {json.dumps({'phase': 'sentinel_done', 'sentinel': s_type, 'status': 'error', 'message': f'{s_type}: 错误 {str(e)[:50]}'})}\n\n"

            yield f"data: {json.dumps({'phase': 'sentinels_complete', 'total_alerts': total_alerts, 'message': f'哨兵扫描完成: {total_alerts} 个告警', 'details': sentinel_details})}\n\n"

            # Phase 2: Wait
            await asyncio.sleep(0.5)

            # Phase 3: Analysts
            yield f"data: {json.dumps({'phase': 'analysts_start', 'message': f'启动 {len(registry._analysts)} 个分析师...', 'count': len(registry._analysts)})}\n\n"

            reports_produced = 0
            analyst_details = []
            for analyst in registry._analysts:
                a_type = analyst.ANALYST_TYPE
                yield f"data: {json.dumps({'phase': 'analyst_analyze', 'analyst': a_type, 'message': f'分析中: {a_type}', 'status': 'analyzing'})}\n\n"
                try:
                    report = await analyst.run_analysis_cycle()
                    has_report = report is not None and not isinstance(report, Exception)
                    if has_report:
                        reports_produced += 1
                    detail = {'analyst': a_type, 'has_report': has_report, 'status': 'reported' if has_report else 'silent'}
                    analyst_details.append(detail)
                    yield f"data: {json.dumps({'phase': 'analyst_done', **detail, 'message': f'{a_type}: 产出报告' if has_report else f'{a_type}: 无异常'})}\n\n"
                except Exception as e:
                    analyst_details.append({'analyst': a_type, 'has_report': False, 'status': 'error'})
                    yield f"data: {json.dumps({'phase': 'analyst_done', 'analyst': a_type, 'status': 'error', 'message': f'{a_type}: 错误'})}\n\n"

            yield f"data: {json.dumps({'phase': 'analysts_complete', 'reports_produced': reports_produced, 'message': f'分析师完成: {reports_produced} 份报告', 'details': analyst_details})}\n\n"

            # Phase 4: Director decision
            decision_data = None
            if reports_produced > 0 and registry._director:
                yield f"data: {json.dumps({'phase': 'director_start', 'message': '投资总监正在用LLM做决策...'})}\n\n"
                try:
                    trade_date = datetime.now().strftime("%Y%m%d")
                    decision = await registry._director.produce_decision(trade_date)
                    if decision:
                        decision_data = decision.model_dump()
                        await registry._persist_decision(decision)
                        yield f"data: {json.dumps({'phase': 'director_done', 'has_decision': True, 'message': '决策已生成', 'decision_summary': f'仓位建议: {decision.suggested_total_position*100:.0f}%'})}\n\n"
                    else:
                        yield f"data: {json.dumps({'phase': 'director_done', 'has_decision': False, 'message': '未产生决策（信心度不足）'})}\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'phase': 'director_done', 'has_decision': False, 'message': f'决策失败: {str(e)[:50]}'})}\n\n"
            else:
                yield f"data: {json.dumps({'phase': 'director_skip', 'message': '无分析报告，跳过决策'})}\n\n"

            # Final
            yield f"data: {json.dumps({'phase': 'complete', 'message': '扫描周期完成', 'result': {'sentinel_alerts': total_alerts, 'analyst_reports': reports_produced, 'decision_produced': decision_data is not None}})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'phase': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/status")
async def get_status() -> dict[str, Any]:
    """Get sentinel system status."""
    try:
        from .core.registry import get_sentinel_registry

        registry = get_sentinel_registry()
        status = registry.get_status()
        return {
            "status": "ok",
            "data": status,
        }
    except Exception as e:
        logger.error("Failed to get status: %s", e)
        return {
            "status": "error",
            "message": str(e),
            "data": {
                "is_running": False,
                "sentinels_active": 0,
                "analysts_active": 0,
            },
        }


@router.get("/decisions")
async def get_decisions(
    limit: int = Query(default=10, ge=1, le=50, description="Number of recent decisions"),
) -> dict[str, Any]:
    """Get recent investment decisions."""
    try:
        from .persistence.store import get_sentinel_store

        store = get_sentinel_store()
        decisions = store.get_recent_decisions(limit=limit)
        return {
            "status": "ok",
            "count": len(decisions),
            "data": decisions,
        }
    except Exception as e:
        logger.error("Failed to get decisions: %s", e)
        return {
            "status": "error",
            "message": str(e),
            "data": [],
        }


@router.get("/alerts")
async def get_alerts(
    limit: int = Query(default=50, ge=1, le=200, description="Number of recent alerts"),
    sentinel_type: str | None = Query(default=None, description="Filter by sentinel type"),
) -> dict[str, Any]:
    """Get recent sentinel alerts."""
    try:
        from .persistence.store import get_sentinel_store

        store = get_sentinel_store()
        alerts = store.get_recent_alerts(limit=limit, sentinel_type=sentinel_type)
        return {
            "status": "ok",
            "count": len(alerts),
            "data": alerts,
        }
    except Exception as e:
        logger.error("Failed to get alerts: %s", e)
        return {
            "status": "error",
            "message": str(e),
            "data": [],
        }

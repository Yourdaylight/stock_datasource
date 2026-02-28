"""FastAPI router for quant module - /api/quant/*"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .schemas import (
    CorePoolResult,
    DataReadinessResult,
    PipelineRunRequest,
    PipelineRunStatus,
    QuantConfig,
    QuantConfigUpdate,
    ScreeningResult,
    ScreeningRunRequest,
    SignalResult,
)
from .service import get_quant_service

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Health Check
# =============================================================================

@router.get("/health")
async def health():
    return {"status": "ok", "module": "quant"}


# =============================================================================
# Data Readiness
# =============================================================================

@router.get("/data-readiness")
async def check_full_readiness():
    """Check full pipeline data readiness."""
    service = get_quant_service()
    result = await service.check_data_readiness()
    return result


@router.get("/data-readiness/{stage}")
async def check_stage_readiness(stage: str):
    """Check data readiness for a specific stage."""
    if stage not in ("screening", "core_pool", "trading_signals"):
        raise HTTPException(400, f"Invalid stage: {stage}")
    service = get_quant_service()
    result = await service.check_data_readiness(stage)
    return result


# =============================================================================
# Pipeline
# =============================================================================

@router.post("/pipeline/run")
async def run_pipeline(request: PipelineRunRequest):
    """Run the full quantitative pipeline."""
    service = get_quant_service()
    result = await service.run_pipeline(request)
    return result


@router.get("/pipeline/status/{run_id}")
async def get_pipeline_status(run_id: str):
    """Get pipeline run status."""
    service = get_quant_service()
    result = await service.get_pipeline_status(run_id)
    if not result:
        raise HTTPException(404, f"Pipeline run {run_id} not found")
    return result


@router.get("/pipeline/latest")
async def get_latest_pipeline():
    """Get latest pipeline run result."""
    service = get_quant_service()
    result = await service.get_latest_pipeline()
    return result


# =============================================================================
# Screening
# =============================================================================

@router.post("/screening/run")
async def run_screening(request: ScreeningRunRequest = None):
    """Run full-market screening."""
    service = get_quant_service()
    result = await service.run_screening(request or ScreeningRunRequest())
    return result


@router.get("/screening/result")
async def get_screening_result(run_date: Optional[str] = Query(None, description="运行日期 YYYYMMDD")):
    """Get screening result."""
    service = get_quant_service()
    result = await service.get_screening_result(run_date)
    return result


@router.get("/screening/rules")
async def get_screening_rules():
    """Get current screening rules configuration."""
    service = get_quant_service()
    configs = await service.get_config("screening_rules")
    return configs[0] if configs else {}


@router.put("/screening/rules")
async def update_screening_rules(update: QuantConfigUpdate):
    """Update screening rules."""
    update.config_type = "screening_rules"
    service = get_quant_service()
    return await service.update_config(update)


# =============================================================================
# Core Pool
# =============================================================================

@router.get("/pool")
async def get_pool():
    """Get current core pool."""
    service = get_quant_service()
    return await service.get_pool()


@router.post("/pool/refresh")
async def refresh_pool(trade_date: Optional[str] = Query(None)):
    """Refresh core pool (re-run scoring on latest screening results)."""
    service = get_quant_service()
    # Get latest screening passed stocks
    screening = await service.get_screening_result()
    if not screening:
        raise HTTPException(400, "No screening result available. Please run screening first.")

    # Get passed stock codes from screening result table
    from stock_datasource.models.database import db_client
    df = db_client.execute_query(
        f"""SELECT ts_code FROM quant_screening_result
        WHERE run_date = '{screening.run_date}' AND overall_pass = 1"""
    )
    if df.empty:
        raise HTTPException(400, "No passed stocks found in screening result")

    passed_codes = df["ts_code"].tolist()
    return await service.build_core_pool(passed_codes, trade_date)


@router.get("/pool/changes")
async def get_pool_changes(limit: int = Query(50, ge=1, le=200)):
    """Get pool entry/exit change log."""
    service = get_quant_service()
    return await service.get_pool_changes(limit)


@router.get("/pool/history")
async def get_pool_history(limit: int = Query(30, ge=1, le=100)):
    """Get pool history."""
    service = get_quant_service()
    return await service.get_pool_changes(limit)


# =============================================================================
# RPS
# =============================================================================

@router.get("/rps")
async def get_rps(limit: int = Query(100, ge=1, le=500)):
    """Get latest RPS ranking."""
    service = get_quant_service()
    return await service.get_rps(limit)


@router.get("/rps/{ts_code}")
async def get_rps_detail(ts_code: str):
    """Get RPS detail for a stock."""
    try:
        from stock_datasource.models.database import db_client
        df = db_client.execute_query(
            f"""SELECT * FROM quant_rps_rank
            WHERE ts_code = '{ts_code}'
            ORDER BY calc_date DESC LIMIT 10"""
        )
        return df.to_dict("records") if not df.empty else []
    except Exception:
        return []


# =============================================================================
# Deep Analysis
# =============================================================================

@router.post("/analysis/{ts_code}")
async def analyze_stock(ts_code: str):
    """Deep analysis for a single stock."""
    service = get_quant_service()
    return await service.analyze_stock(ts_code)


@router.get("/analysis/dashboard")
async def get_analysis_dashboard():
    """Get analysis dashboard for pool stocks (tech snapshots)."""
    try:
        from stock_datasource.models.database import db_client
        df = db_client.execute_query(
            """SELECT * FROM quant_deep_analysis
            WHERE analysis_date = (SELECT max(analysis_date) FROM quant_deep_analysis)
            ORDER BY tech_score DESC"""
        )
        return df.to_dict("records") if not df.empty else []
    except Exception:
        return []


# =============================================================================
# Trading Signals
# =============================================================================

@router.get("/signals")
async def get_signals(
    signal_date: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Get trading signals."""
    service = get_quant_service()
    return await service.get_signals(signal_date, limit)


@router.get("/signals/history")
async def get_signal_history(
    limit: int = Query(100, ge=1, le=500),
):
    """Get signal history."""
    try:
        from stock_datasource.models.database import db_client
        df = db_client.execute_query(
            f"SELECT * FROM quant_trading_signal ORDER BY signal_date DESC, ts_code LIMIT {limit}"
        )
        return df.to_dict("records") if not df.empty else []
    except Exception:
        return []


@router.get("/risk")
async def get_market_risk():
    """Get current market risk status."""
    from .signal_generator import get_signal_generator
    generator = get_signal_generator()
    return await generator.check_market_risk()


# =============================================================================
# Config
# =============================================================================

@router.get("/config")
async def get_config(config_type: Optional[str] = Query(None)):
    """Get model configuration."""
    service = get_quant_service()
    return await service.get_config(config_type)


@router.put("/config")
async def update_config(update: QuantConfigUpdate):
    """Update model configuration."""
    service = get_quant_service()
    return await service.update_config(update)


@router.get("/report")
async def get_report():
    """Get model run report summary."""
    service = get_quant_service()
    pipeline = await service.get_latest_pipeline()
    pool = await service.get_pool()
    signals = await service.get_signals(limit=10)

    return {
        "latest_pipeline": pipeline,
        "pool_summary": {
            "core_count": len(pool.core_stocks),
            "supplement_count": len(pool.supplement_stocks),
        },
        "latest_signals_count": len(signals),
    }

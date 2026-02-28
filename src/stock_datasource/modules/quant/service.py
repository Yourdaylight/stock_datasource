"""Quant model service - Pipeline orchestration.

Orchestrates the 4-stage pipeline: Screening -> Core Pool -> Deep Analysis -> Signals.
Each stage checks data readiness before execution and records status.
"""

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Optional

import pandas as pd

from stock_datasource.models.database import db_client

from .core_pool_builder import get_core_pool_builder
from .data_readiness import get_data_readiness_checker
from .deep_analyzer import get_deep_analyzer
from .schemas import (
    CorePoolResult,
    DeepAnalysisResult,
    FactorWeight,
    PipelineRunRequest,
    PipelineRunStatus,
    PipelineStageStatus,
    QuantConfig,
    QuantConfigUpdate,
    ScreeningResult,
    ScreeningRunRequest,
    SignalResult,
    TradingSignal,
)
from .screening_engine import get_screening_engine
from .signal_generator import get_signal_generator
from .tables import ensure_quant_tables

logger = logging.getLogger(__name__)


class QuantService:
    """Core service for quant model pipeline orchestration."""

    def __init__(self):
        self._initialized = False

    def _ensure_init(self):
        if not self._initialized:
            ensure_quant_tables()
            self._initialized = True

    # =========================================================================
    # Pipeline
    # =========================================================================

    async def run_pipeline(self, request: PipelineRunRequest) -> PipelineRunStatus:
        """Run the full pipeline (or partial)."""
        self._ensure_init()
        run_id = str(uuid.uuid4())[:8]
        run_date = request.trade_date or datetime.now().strftime("%Y%m%d")

        status = PipelineRunStatus(
            run_id=run_id,
            run_date=run_date,
            pipeline_type=request.pipeline_type,
            overall_status="running",
            triggered_by="manual",
            stages=[
                PipelineStageStatus(name="全市场初筛", stage="screening"),
                PipelineStageStatus(name="核心池构建", stage="core_pool"),
                PipelineStageStatus(name="深度分析", stage="deep_analysis"),
                PipelineStageStatus(name="交易信号", stage="trading_signals"),
            ],
            created_at=datetime.now().isoformat(),
        )

        self._save_pipeline_run(status)

        try:
            # Stage 1: Screening
            stage = status.stages[0]
            stage.status = "running"
            stage.start_time = datetime.now().isoformat()
            self._save_pipeline_run(status)

            screening_result = await self.run_screening(ScreeningRunRequest(trade_date=run_date))

            if screening_result.status == "data_missing":
                stage.status = "data_missing"
                stage.data_readiness = screening_result.data_readiness
                stage.end_time = datetime.now().isoformat()
                status.overall_status = "data_missing"
                self._save_pipeline_run(status)
                return status

            stage.status = "completed"
            stage.end_time = datetime.now().isoformat()
            stage.result_summary = {
                "total": screening_result.total_stocks,
                "passed": screening_result.passed_count,
                "rejected": screening_result.rejected_count,
            }

            if request.pipeline_type == "screening_only":
                status.overall_status = "completed"
                self._save_pipeline_run(status)
                return status

            # Stage 2: Core Pool
            stage = status.stages[1]
            stage.status = "running"
            stage.start_time = datetime.now().isoformat()
            self._save_pipeline_run(status)

            passed_codes = [s.ts_code for s in screening_result.passed_stocks]
            pool_result = await self.build_core_pool(passed_codes, run_date)

            if pool_result.data_readiness and not pool_result.data_readiness.is_ready:
                stage.status = "data_missing"
                stage.data_readiness = pool_result.data_readiness
                stage.end_time = datetime.now().isoformat()
                status.overall_status = "data_missing"
                self._save_pipeline_run(status)
                return status

            stage.status = "completed"
            stage.end_time = datetime.now().isoformat()
            stage.result_summary = {
                "core_count": len(pool_result.core_stocks),
                "supplement_count": len(pool_result.supplement_stocks),
                "changes": len(pool_result.pool_changes),
            }

            # Stage 3: Deep Analysis (optional, lightweight)
            stage = status.stages[2]
            stage.status = "running"
            stage.start_time = datetime.now().isoformat()
            self._save_pipeline_run(status)

            all_pool = [s.ts_code for s in pool_result.core_stocks + pool_result.supplement_stocks]
            # Only analyze top 10 in pipeline to keep it fast
            analyzer = get_deep_analyzer()
            batch_status = await analyzer.batch_analyze(all_pool[:10])

            stage.status = "completed"
            stage.end_time = datetime.now().isoformat()
            stage.result_summary = {
                "analyzed": batch_status.completed,
                "failed": batch_status.failed,
            }

            if request.pipeline_type == "signal_only":
                pass  # Skip to signals

            # Stage 4: Trading Signals
            stage = status.stages[3]
            stage.status = "running"
            stage.start_time = datetime.now().isoformat()
            self._save_pipeline_run(status)

            signal_result = await self.generate_signals(all_pool, run_date)

            if signal_result.data_readiness and not signal_result.data_readiness.is_ready:
                stage.status = "data_missing"
                stage.data_readiness = signal_result.data_readiness
                stage.end_time = datetime.now().isoformat()
                status.overall_status = "data_missing"
                self._save_pipeline_run(status)
                return status

            stage.status = "completed"
            stage.end_time = datetime.now().isoformat()
            stage.result_summary = {
                "signals": len(signal_result.signals),
                "market_risk": signal_result.market_risk.risk_level if signal_result.market_risk else "unknown",
            }

            status.overall_status = "completed"
            status.updated_at = datetime.now().isoformat()
            self._save_pipeline_run(status)
            return status

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            status.overall_status = "error"
            self._save_pipeline_run(status)
            return status

    # =========================================================================
    # Individual Stage Methods
    # =========================================================================

    async def run_screening(self, request: ScreeningRunRequest) -> ScreeningResult:
        self._ensure_init()
        engine = get_screening_engine()
        return await engine.run_screening(request.trade_date)

    async def build_core_pool(
        self, screened_stocks: list[str], update_date: Optional[str] = None
    ) -> CorePoolResult:
        self._ensure_init()
        builder = get_core_pool_builder()
        return await builder.build_core_pool(screened_stocks, update_date)

    async def generate_signals(
        self, pool_stocks: list[str], signal_date: Optional[str] = None
    ) -> SignalResult:
        self._ensure_init()
        generator = get_signal_generator()
        return await generator.generate_signals(pool_stocks, signal_date)

    async def analyze_stock(self, ts_code: str) -> DeepAnalysisResult:
        self._ensure_init()
        analyzer = get_deep_analyzer()
        return await analyzer.analyze_stock(ts_code)

    # =========================================================================
    # Data Readiness
    # =========================================================================

    async def check_data_readiness(self, stage: Optional[str] = None):
        self._ensure_init()
        checker = get_data_readiness_checker()
        if stage:
            if stage == "screening":
                return await checker.check_screening_readiness()
            elif stage == "core_pool":
                return await checker.check_core_pool_readiness()
            elif stage == "trading_signals":
                return await checker.check_signal_readiness()
        return await checker.check_full_pipeline_readiness()

    # =========================================================================
    # Query Methods
    # =========================================================================

    async def get_screening_result(self, run_date: Optional[str] = None) -> Optional[ScreeningResult]:
        """Get latest or specific screening result."""
        self._ensure_init()
        try:
            if run_date:
                date_filter = f"WHERE run_date = '{run_date}'"
            else:
                date_filter = "WHERE run_date = (SELECT max(run_date) FROM quant_screening_run_stats)"

            stats_df = db_client.execute_query(
                f"SELECT * FROM quant_screening_run_stats {date_filter} ORDER BY created_at DESC LIMIT 1"
            )
            if stats_df.empty:
                return None

            row = stats_df.iloc[0]
            rule_stats = json.loads(row.get("rule_stats", "[]")) if row.get("rule_stats") else []

            return ScreeningResult(
                run_date=str(row.get("run_date", "")),
                run_id=str(row.get("run_id", "")),
                total_stocks=int(row.get("total_stocks", 0)),
                passed_count=int(row.get("passed_count", 0)),
                rejected_count=int(row.get("rejected_count", 0)),
                rule_details=[],
                execution_time_ms=int(row.get("execution_time_ms", 0)),
                status=str(row.get("status", "")),
            )
        except Exception as e:
            logger.error(f"Failed to get screening result: {e}")
            return None

    async def get_pool(self) -> CorePoolResult:
        """Get current pool from ClickHouse."""
        self._ensure_init()
        try:
            df = db_client.execute_query(
                """SELECT * FROM quant_core_pool
                WHERE update_date = (SELECT max(update_date) FROM quant_core_pool)
                ORDER BY pool_type, rank"""
            )
            if df.empty:
                return CorePoolResult()

            from .schemas import FactorScoreDetail
            core_stocks = []
            supplement_stocks = []

            for _, row in df.iterrows():
                detail = FactorScoreDetail(
                    ts_code=row["ts_code"],
                    stock_name=row.get("stock_name", ""),
                    quality_score=float(row.get("quality_score", 0)),
                    growth_score=float(row.get("growth_score", 0)),
                    value_score=float(row.get("value_score", 0)),
                    momentum_score=float(row.get("momentum_score", 0)),
                    total_score=float(row.get("total_score", 0)),
                    rank=int(row.get("rank", 0)),
                    pool_type=str(row.get("pool_type", "")),
                    rps_250=float(row.get("rps_250", 0)),
                )
                if row.get("pool_type") == "core":
                    core_stocks.append(detail)
                else:
                    supplement_stocks.append(detail)

            return CorePoolResult(
                update_date=str(df.iloc[0]["update_date"]),
                core_stocks=core_stocks,
                supplement_stocks=supplement_stocks,
            )
        except Exception as e:
            logger.error(f"Failed to get pool: {e}")
            return CorePoolResult()

    async def get_pool_changes(self, limit: int = 50) -> list[dict]:
        """Get recent pool changes."""
        self._ensure_init()
        try:
            df = db_client.execute_query(
                f"""SELECT * FROM quant_core_pool
                WHERE change_type != ''
                ORDER BY update_date DESC, ts_code
                LIMIT {limit}"""
            )
            return df.to_dict("records") if not df.empty else []
        except Exception:
            return []

    async def get_signals(
        self, signal_date: Optional[str] = None, limit: int = 50
    ) -> list[TradingSignal]:
        """Get trading signals."""
        self._ensure_init()
        try:
            if signal_date:
                date_filter = f"WHERE signal_date = '{signal_date}'"
            else:
                date_filter = "WHERE signal_date = (SELECT max(signal_date) FROM quant_trading_signal)"

            df = db_client.execute_query(
                f"SELECT * FROM quant_trading_signal {date_filter} ORDER BY created_at DESC LIMIT {limit}"
            )
            if df.empty:
                return []

            signals = []
            for _, row in df.iterrows():
                ctx = {}
                try:
                    ctx = json.loads(row.get("signal_context", "{}"))
                except (json.JSONDecodeError, TypeError):
                    pass

                signals.append(TradingSignal(
                    signal_date=str(row.get("signal_date", "")),
                    ts_code=row["ts_code"],
                    stock_name=row.get("stock_name", ""),
                    signal_type=row.get("signal_type", ""),
                    signal_source=row.get("signal_source", ""),
                    price=float(row.get("price", 0)),
                    target_position=float(row.get("target_position", 0)),
                    confidence=float(row.get("confidence", 0)),
                    reason=row.get("reason", ""),
                    pool_type=row.get("pool_type", ""),
                    ma25=float(row.get("ma25", 0)),
                    ma120=float(row.get("ma120", 0)),
                    signal_context=ctx,
                ))

            return signals
        except Exception as e:
            logger.error(f"Failed to get signals: {e}")
            return []

    async def get_rps(self, limit: int = 100):
        """Get latest RPS ranking."""
        self._ensure_init()
        try:
            df = db_client.execute_query(
                f"""SELECT * FROM quant_rps_rank
                WHERE calc_date = (SELECT max(calc_date) FROM quant_rps_rank)
                ORDER BY rps_250 DESC
                LIMIT {limit}"""
            )
            return df.to_dict("records") if not df.empty else []
        except Exception:
            return []

    async def get_pipeline_status(self, run_id: str) -> Optional[PipelineRunStatus]:
        """Get pipeline run status."""
        self._ensure_init()
        try:
            df = db_client.execute_query(
                f"SELECT * FROM quant_pipeline_run WHERE run_id = '{run_id}' LIMIT 1"
            )
            if df.empty:
                return None

            row = df.iloc[0]
            stages = json.loads(row.get("stages", "[]")) if row.get("stages") else []

            return PipelineRunStatus(
                run_id=row["run_id"],
                run_date=str(row.get("run_date", "")),
                pipeline_type=row.get("pipeline_type", ""),
                overall_status=row.get("overall_status", ""),
                triggered_by=row.get("triggered_by", ""),
                stages=[PipelineStageStatus(**s) for s in stages],
                created_at=str(row.get("created_at", "")),
                updated_at=str(row.get("updated_at", "")),
            )
        except Exception as e:
            logger.error(f"Failed to get pipeline status: {e}")
            return None

    async def get_latest_pipeline(self) -> Optional[PipelineRunStatus]:
        """Get the latest pipeline run."""
        self._ensure_init()
        try:
            df = db_client.execute_query(
                "SELECT run_id FROM quant_pipeline_run ORDER BY created_at DESC LIMIT 1"
            )
            if df.empty:
                return None
            return await self.get_pipeline_status(df.iloc[0]["run_id"])
        except Exception:
            return None

    # =========================================================================
    # Config
    # =========================================================================

    async def get_config(self, config_type: Optional[str] = None) -> list[QuantConfig]:
        self._ensure_init()
        try:
            where = f"WHERE config_type = '{config_type}'" if config_type else ""
            df = db_client.execute_query(
                f"SELECT * FROM quant_model_config {where} ORDER BY updated_at DESC"
            )
            if df.empty:
                return self._default_configs()

            configs = []
            for _, row in df.iterrows():
                data = {}
                try:
                    data = json.loads(row.get("config_data", "{}"))
                except (json.JSONDecodeError, TypeError):
                    pass
                configs.append(QuantConfig(
                    config_id=row.get("config_id", ""),
                    config_name=row.get("config_name", ""),
                    config_type=row.get("config_type", ""),
                    config_data=data,
                    is_active=bool(row.get("is_active", 1)),
                    updated_at=str(row.get("updated_at", "")),
                ))
            return configs
        except Exception:
            return self._default_configs()

    async def update_config(self, update: QuantConfigUpdate) -> QuantConfig:
        self._ensure_init()
        config_id = f"{update.config_type}_active"
        config = QuantConfig(
            config_id=config_id,
            config_name=update.config_name or update.config_type,
            config_type=update.config_type,
            config_data=update.config_data,
            updated_at=datetime.now().isoformat(),
        )
        try:
            df = pd.DataFrame([{
                "config_id": config.config_id,
                "config_name": config.config_name,
                "config_type": config.config_type,
                "config_data": json.dumps(config.config_data, ensure_ascii=False),
                "is_active": 1,
                "updated_at": datetime.now(),
            }])
            db_client.insert_dataframe("quant_model_config", df)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
        return config

    def _default_configs(self) -> list[QuantConfig]:
        from .screening_engine import default_screening_rules
        return [
            QuantConfig(
                config_id="screening_rules_active",
                config_name="默认筛选规则",
                config_type="screening_rules",
                config_data={"rules": [r.model_dump() for r in default_screening_rules()]},
            ),
            QuantConfig(
                config_id="factor_weights_active",
                config_name="默认因子权重",
                config_type="factor_weights",
                config_data=FactorWeight().model_dump(),
            ),
            QuantConfig(
                config_id="signal_params_active",
                config_name="默认信号参数",
                config_type="signal_params",
                config_data={"ma_short": 25, "ma_long": 120, "stop_loss_pct": 0.15},
            ),
        ]

    # =========================================================================
    # Persistence helpers
    # =========================================================================

    def _save_pipeline_run(self, status: PipelineRunStatus) -> None:
        try:
            df = pd.DataFrame([{
                "run_id": status.run_id,
                "run_date": status.run_date,
                "pipeline_type": status.pipeline_type,
                "stages": json.dumps(
                    [s.model_dump() for s in status.stages], ensure_ascii=False, default=str
                ),
                "overall_status": status.overall_status,
                "triggered_by": status.triggered_by,
                "updated_at": datetime.now(),
            }])
            db_client.insert_dataframe("quant_pipeline_run", df)
        except Exception as e:
            logger.error(f"Failed to save pipeline run: {e}")


# Singleton
_quant_service: Optional[QuantService] = None


def get_quant_service() -> QuantService:
    global _quant_service
    if _quant_service is None:
        _quant_service = QuantService()
    return _quant_service

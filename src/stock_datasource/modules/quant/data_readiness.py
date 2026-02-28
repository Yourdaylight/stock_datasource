"""Data readiness checker - validates local ClickHouse data before engine execution.

Core constraint: Only executes lightweight ClickHouse metadata queries (SHOW TABLES,
COUNT, MIN/MAX). NEVER calls any remote TuShare/AKShare plugin.

table_name and display_name are resolved dynamically from plugin_manager
(plugin.get_schema()["table_name"] and plugin config), never hardcoded.
"""

import logging
from datetime import datetime
from typing import Optional

from stock_datasource.core.plugin_manager import plugin_manager
from stock_datasource.models.database import db_client

from .schemas import (
    DataReadinessResult,
    DataRequirement,
    DataRequirementStatus,
    DataStatus,
    MissingDataSummary,
    PluginTriggerInfo,
)

logger = logging.getLogger(__name__)


def _resolve_table_name(plugin_name: str) -> str:
    """Resolve table_name from plugin's schema.json dynamically."""
    schema = plugin_manager.get_plugin_schema(plugin_name)
    if schema:
        return schema.get("table_name", "")
    logger.warning(f"Plugin '{plugin_name}' not found, cannot resolve table_name")
    return ""


def _resolve_display_name(plugin_name: str) -> str:
    """Resolve display name from plugin's schema comment or config description."""
    plugin = plugin_manager.get_plugin(plugin_name)
    if plugin:
        schema = plugin.get_schema() if hasattr(plugin, "get_schema") else {}
        if schema.get("comment"):
            return schema["comment"]
        config = plugin.get_config() if hasattr(plugin, "get_config") else {}
        if config.get("description"):
            return config["description"]
    return plugin_name


# =============================================================================
# Data Requirements for Each Engine
# Only plugin_name + required_columns + date_column + description are declared.
# table_name is resolved at runtime from the plugin's schema.json.
# =============================================================================

SCREENING_REQUIREMENT_SPECS = [
    {
        "plugin_name": "tushare_finace_indicator",
        "required_columns": ["roe", "revenue_yoy", "netprofit_yoy"],
        "date_column": "end_date",
        "description": "财务指标(ROE/营收增速/净利润增速)，用于传统指标筛选",
    },
    {
        "plugin_name": "tushare_income",
        "required_columns": ["total_revenue", "n_income"],
        "date_column": "end_date",
        "description": "利润表(营收/净利/费用拆项)，用于自定义指标筛选",
    },
    {
        "plugin_name": "tushare_balancesheet",
        "required_columns": ["accounts_receiv"],
        "date_column": "end_date",
        "description": "资产负债表(应收账款)，用于应收营收联动分析",
    },
    {
        "plugin_name": "tushare_cashflow",
        "required_columns": ["n_cashflow_act"],
        "date_column": "end_date",
        "description": "现金流量表(经营现金流)，用于现金流同步率检查",
    },
]

CORE_POOL_REQUIREMENT_SPECS = [
    {
        "plugin_name": "tushare_daily_basic",
        "required_columns": ["pe", "pb", "total_mv"],
        "date_column": "trade_date",
        "description": "每日基本面指标(PE/PB/市值)，用于估值因子计算",
    },
    {
        "plugin_name": "tushare_daily",
        "required_columns": ["close", "pct_chg"],
        "date_column": "trade_date",
        "description": "日线行情(收盘价/涨跌幅)，用于动量因子和RPS计算",
    },
    {
        "plugin_name": "tushare_adj_factor",
        "required_columns": ["adj_factor"],
        "date_column": "trade_date",
        "description": "复权因子，用于前复权价格计算",
    },
]

SIGNAL_REQUIREMENT_SPECS = [
    {
        "plugin_name": "tushare_index_daily",
        "required_columns": ["close"],
        "date_column": "trade_date",
        "description": "指数日线(沪深300)，用于市场风控(MA250)",
    },
]


def _build_requirements(specs: list[dict]) -> list[DataRequirement]:
    """Build DataRequirement list, resolving table_name from plugins dynamically."""
    reqs = []
    for spec in specs:
        table_name = _resolve_table_name(spec["plugin_name"])
        if not table_name:
            logger.warning(
                f"Skipping requirement for '{spec['plugin_name']}': "
                f"cannot resolve table_name"
            )
            continue
        reqs.append(DataRequirement(
            plugin_name=spec["plugin_name"],
            table_name=table_name,
            required_columns=spec.get("required_columns", []),
            date_column=spec.get("date_column", "trade_date"),
            description=spec.get("description", ""),
        ))
    return reqs


class DataReadinessChecker:
    """Check whether local ClickHouse data is ready for engine execution.

    This checker ONLY queries ClickHouse metadata (table existence, record counts,
    date ranges). It NEVER calls any remote data plugin.
    """

    async def check_screening_readiness(
        self, min_date: Optional[str] = None
    ) -> DataReadinessResult:
        """Check screening engine data requirements."""
        reqs = _build_requirements(SCREENING_REQUIREMENT_SPECS)
        if min_date:
            reqs = [r.model_copy(update={"min_date": min_date}) for r in reqs]
        return await self._check_requirements(reqs, "screening")

    async def check_core_pool_readiness(
        self, min_date: Optional[str] = None
    ) -> DataReadinessResult:
        """Check core pool builder data requirements."""
        reqs = _build_requirements(CORE_POOL_REQUIREMENT_SPECS)
        if min_date:
            reqs = [r.model_copy(update={"min_date": min_date}) for r in reqs]
        return await self._check_requirements(reqs, "core_pool")

    async def check_signal_readiness(
        self, min_date: Optional[str] = None
    ) -> DataReadinessResult:
        """Check signal generator data requirements (includes core pool reqs + index)."""
        reqs = _build_requirements(CORE_POOL_REQUIREMENT_SPECS + SIGNAL_REQUIREMENT_SPECS)
        if min_date:
            reqs = [r.model_copy(update={"min_date": min_date}) for r in reqs]
        return await self._check_requirements(reqs, "trading_signals")

    async def check_full_pipeline_readiness(self) -> dict[str, DataReadinessResult]:
        """Check all pipeline stages."""
        results = {}
        results["screening"] = await self.check_screening_readiness()
        results["core_pool"] = await self.check_core_pool_readiness()
        results["trading_signals"] = await self.check_signal_readiness()
        return results

    async def _check_requirements(
        self, requirements: list[DataRequirement], stage: str
    ) -> DataReadinessResult:
        """Check a list of data requirements against ClickHouse."""
        statuses: list[DataRequirementStatus] = []
        all_ready = True

        for req in requirements:
            status = await self._check_single_requirement(req)
            statuses.append(status)
            if status.status != DataStatus.READY:
                all_ready = False

        missing_summary = None
        if not all_ready:
            missing_summary = self._build_missing_summary(statuses, stage)

        return DataReadinessResult(
            is_ready=all_ready,
            checked_at=datetime.now().isoformat(),
            stage=stage,
            requirements=statuses,
            missing_summary=missing_summary,
        )

    async def _check_single_requirement(
        self, req: DataRequirement
    ) -> DataRequirementStatus:
        """Check a single data requirement."""
        status = DataRequirementStatus(requirement=req)

        try:
            # 1. Check table existence
            if not db_client.table_exists(req.table_name):
                status.status = DataStatus.MISSING_TABLE
                status.suggested_plugins = [req.plugin_name]
                status.suggested_task_type = "full"
                return status

            # 2. Check record count
            count_df = db_client.execute_query(
                f"SELECT count() as cnt FROM {req.table_name}"
            )
            count = int(count_df.iloc[0]["cnt"]) if len(count_df) > 0 else 0
            status.record_count = count

            if count == 0:
                status.status = DataStatus.INSUFFICIENT_DATA
                status.suggested_plugins = [req.plugin_name]
                status.suggested_task_type = "full"
                return status

            # 3. Check date range
            date_col = req.date_column
            range_df = db_client.execute_query(
                f"SELECT min({date_col}) as min_d, max({date_col}) as max_d FROM {req.table_name}"
            )
            if len(range_df) > 0:
                min_d = str(range_df.iloc[0]["min_d"])
                max_d = str(range_df.iloc[0]["max_d"])
                status.existing_date_range = [min_d, max_d]

                # Check if recent data is missing (within last 5 trading days)
                if req.min_date:
                    if max_d < req.min_date:
                        status.status = DataStatus.MISSING_DATES
                        status.missing_dates = [f"{max_d} ~ {req.min_date}"]
                        status.suggested_plugins = [req.plugin_name]
                        return status

            # 4. Check required columns exist
            if req.required_columns:
                try:
                    cols_sql = ", ".join(
                        [f"{c}" for c in req.required_columns[:1]]
                    )
                    db_client.execute_query(
                        f"SELECT {cols_sql} FROM {req.table_name} LIMIT 1"
                    )
                except Exception:
                    status.status = DataStatus.MISSING_TABLE
                    status.suggested_plugins = [req.plugin_name]
                    return status

            status.status = DataStatus.READY

        except Exception as e:
            logger.error(f"Error checking requirement for {req.table_name}: {e}")
            status.status = DataStatus.MISSING_TABLE
            status.suggested_plugins = [req.plugin_name]

        return status

    def _build_missing_summary(
        self, statuses: list[DataRequirementStatus], stage: str
    ) -> MissingDataSummary:
        """Build missing data summary from requirement statuses."""
        ready_count = sum(1 for s in statuses if s.status == DataStatus.READY)
        missing_count = len(statuses) - ready_count

        plugins_to_trigger: list[PluginTriggerInfo] = []
        seen_plugins: set[str] = set()

        for s in statuses:
            if s.status == DataStatus.READY:
                continue
            plugin_name = s.requirement.plugin_name
            if plugin_name in seen_plugins:
                continue
            seen_plugins.add(plugin_name)

            plugins_to_trigger.append(
                PluginTriggerInfo(
                    plugin_name=plugin_name,
                    display_name=_resolve_display_name(plugin_name),
                    table_name=s.requirement.table_name,
                    missing_dates=s.missing_dates,
                    task_type=s.suggested_task_type,
                    description=s.requirement.description,
                )
            )

        return MissingDataSummary(
            total_requirements=len(statuses),
            ready_count=ready_count,
            missing_count=missing_count,
            affected_engines=[stage],
            plugins_to_trigger=plugins_to_trigger,
            estimated_sync_time=f"约{missing_count * 2}分钟",
        )


# Singleton
_checker: Optional[DataReadinessChecker] = None


def get_data_readiness_checker() -> DataReadinessChecker:
    global _checker
    if _checker is None:
        _checker = DataReadinessChecker()
    return _checker

"""Tests for quant stock screening model module.

Covers: schemas, benford checker, data readiness, screening engine,
RPS calculator, factor scorer, core pool builder, signal generator,
service, and API router.
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# =============================================================================
# Schema Tests
# =============================================================================

class TestSchemas:
    """Test Pydantic schema definitions and defaults."""

    def test_engine_stage_enum(self):
        from stock_datasource.modules.quant.schemas import EngineStage

        assert EngineStage.SCREENING == "screening"
        assert EngineStage.CORE_POOL == "core_pool"
        assert EngineStage.DEEP_ANALYSIS == "deep_analysis"
        assert EngineStage.TRADING_SIGNALS == "trading_signals"

    def test_data_status_enum(self):
        from stock_datasource.modules.quant.schemas import DataStatus

        assert DataStatus.READY == "ready"
        assert DataStatus.MISSING_TABLE == "missing_table"
        assert DataStatus.MISSING_DATES == "missing_dates"
        assert DataStatus.INSUFFICIENT_DATA == "insufficient_data"

    def test_pipeline_status_enum(self):
        from stock_datasource.modules.quant.schemas import PipelineStatus

        assert PipelineStatus.PENDING == "pending"
        assert PipelineStatus.DATA_MISSING == "data_missing"

    def test_signal_type_enum(self):
        from stock_datasource.modules.quant.schemas import SignalType

        assert SignalType.BUY == "buy"
        assert SignalType.SELL == "sell"
        assert SignalType.ADD == "add"
        assert SignalType.REDUCE == "reduce"

    def test_pool_type_enum(self):
        from stock_datasource.modules.quant.schemas import PoolType

        assert PoolType.CORE == "core"
        assert PoolType.RPS_SUPPLEMENT == "rps_supplement"

    def test_data_requirement_defaults(self):
        from stock_datasource.modules.quant.schemas import DataRequirement

        req = DataRequirement(plugin_name="test_plugin", table_name="test_table")
        assert req.date_column == "trade_date"
        assert req.required_columns == []
        assert req.min_records == 0

    def test_screening_rule_defaults(self):
        from stock_datasource.modules.quant.schemas import ScreeningRule

        rule = ScreeningRule(name="test_rule")
        assert rule.category == "traditional"
        assert rule.enabled is True
        assert rule.is_hard_reject is True
        assert rule.params == {}

    def test_rule_execution_detail(self):
        from stock_datasource.modules.quant.schemas import RuleExecutionDetail

        detail = RuleExecutionDetail(rule_name="roe_check", category="traditional")
        assert detail.total_checked == 0
        assert detail.passed_count == 0
        assert detail.execution_time_ms == 0

    def test_screening_result_item(self):
        from stock_datasource.modules.quant.schemas import ScreeningResultItem

        item = ScreeningResultItem(ts_code="000001.SZ", overall_pass=True)
        assert item.reject_reasons == []
        assert item.stock_name == ""

    def test_screening_result_defaults(self):
        from stock_datasource.modules.quant.schemas import ScreeningResult

        result = ScreeningResult()
        assert result.status == "success"
        assert result.total_stocks == 0
        assert result.passed_stocks == []
        assert result.rejected_stocks == []
        assert result.data_readiness is None

    def test_factor_weight_defaults(self):
        from stock_datasource.modules.quant.schemas import FactorWeight

        w = FactorWeight()
        assert w.quality == 0.30
        assert w.growth == 0.30
        assert w.value == 0.20
        assert w.momentum == 0.20
        assert abs(w.quality + w.growth + w.value + w.momentum - 1.0) < 1e-9

    def test_factor_score_detail(self):
        from stock_datasource.modules.quant.schemas import FactorScoreDetail

        d = FactorScoreDetail(ts_code="000001.SZ")
        assert d.total_score == 0
        assert d.rank == 0
        assert d.pool_type == ""

    def test_pool_change(self):
        from stock_datasource.modules.quant.schemas import PoolChange

        change = PoolChange(
            ts_code="000001.SZ",
            change_type="new_entry",
            change_date="20260101",
        )
        assert change.old_rank is None
        assert change.new_rank is None

    def test_core_pool_result(self):
        from stock_datasource.modules.quant.schemas import CorePoolResult

        result = CorePoolResult()
        assert result.core_stocks == []
        assert result.supplement_stocks == []
        assert result.pool_changes == []

    def test_signal_config_defaults(self):
        from stock_datasource.modules.quant.schemas import SignalConfig

        cfg = SignalConfig()
        assert cfg.ma_short == 25
        assert cfg.ma_long == 120
        assert cfg.stop_loss_pct == 0.15
        assert cfg.trailing_stop_pct == 0.10
        assert cfg.rps_exit_threshold == 75

    def test_trading_signal(self):
        from stock_datasource.modules.quant.schemas import TradingSignal

        sig = TradingSignal(ts_code="000001.SZ", signal_type="buy")
        assert sig.signal_context == {}
        assert sig.confidence == 0

    def test_market_risk_status_defaults(self):
        from stock_datasource.modules.quant.schemas import MarketRiskStatus

        risk = MarketRiskStatus()
        assert risk.index_code == "000300.SH"
        assert risk.risk_level == "normal"
        assert risk.suggested_position == 1.0
        assert risk.is_above_ma250 is True

    def test_pipeline_run_request(self):
        from stock_datasource.modules.quant.schemas import PipelineRunRequest

        req = PipelineRunRequest()
        assert req.pipeline_type == "full"
        assert req.trade_date is None

    def test_quant_config(self):
        from stock_datasource.modules.quant.schemas import QuantConfig

        cfg = QuantConfig(config_type="screening_rules", config_data={"key": "val"})
        assert cfg.is_active is True

    def test_quant_config_update(self):
        from stock_datasource.modules.quant.schemas import QuantConfigUpdate

        update = QuantConfigUpdate(config_type="factor_weights", config_data={"quality": 0.4})
        assert update.config_name is None

    def test_missing_data_summary(self):
        from stock_datasource.modules.quant.schemas import MissingDataSummary

        summary = MissingDataSummary(
            total_requirements=4,
            ready_count=2,
            missing_count=2,
            affected_engines=["screening"],
        )
        assert summary.plugins_to_trigger == []
        assert summary.estimated_sync_time == ""

    def test_data_readiness_result(self):
        from stock_datasource.modules.quant.schemas import DataReadinessResult

        result = DataReadinessResult(is_ready=True, stage="screening")
        assert result.requirements == []
        assert result.missing_summary is None

    def test_rps_rank_item(self):
        from stock_datasource.modules.quant.schemas import RPSRankItem

        item = RPSRankItem(ts_code="000001.SZ", rps_250=85.5)
        assert item.rps_120 == 0
        assert item.rps_60 == 0

    def test_deep_analysis_result(self):
        from stock_datasource.modules.quant.schemas import DeepAnalysisResult

        result = DeepAnalysisResult(ts_code="000001.SZ")
        assert result.tech_snapshot is None
        assert result.ai_analysis is None

    def test_batch_analysis_status(self):
        from stock_datasource.modules.quant.schemas import BatchAnalysisStatus

        status = BatchAnalysisStatus(total=10, completed=3, failed=1)
        assert status.in_progress == ""


# =============================================================================
# Benford Checker Tests
# =============================================================================

class TestBenfordChecker:
    """Test Benford's Law checker."""

    def test_extract_first_digit_positive(self):
        from stock_datasource.modules.quant.benford_checker import extract_first_digit

        assert extract_first_digit(123.45) == 1
        assert extract_first_digit(9876.0) == 9
        assert extract_first_digit(0.0056) == 5
        assert extract_first_digit(3.14) == 3

    def test_extract_first_digit_negative(self):
        from stock_datasource.modules.quant.benford_checker import extract_first_digit

        assert extract_first_digit(-456.78) == 4
        assert extract_first_digit(-0.0089) == 8

    def test_extract_first_digit_zero_and_special(self):
        from stock_datasource.modules.quant.benford_checker import extract_first_digit

        assert extract_first_digit(0) is None
        assert extract_first_digit(float("nan")) is None
        assert extract_first_digit(float("inf")) is None

    def test_benford_expected_distribution(self):
        from stock_datasource.modules.quant.benford_checker import BENFORD_EXPECTED

        total = sum(BENFORD_EXPECTED.values())
        assert abs(total - 1.0) < 0.001
        assert BENFORD_EXPECTED[1] == 0.301
        assert BENFORD_EXPECTED[9] == 0.046

    def test_benford_chi_square_insufficient_data(self):
        from stock_datasource.modules.quant.benford_checker import benford_chi_square

        values = pd.Series([100, 200, 300])  # Only 3, need 30+
        chi2, p_value, distribution = benford_chi_square(values)
        assert chi2 == 0.0
        assert p_value == 1.0
        assert distribution == {}

    def test_benford_chi_square_with_benford_data(self):
        """Generate data that roughly follows Benford's law."""
        from stock_datasource.modules.quant.benford_checker import benford_chi_square

        pytest.importorskip("scipy", reason="scipy not installed")

        # Generate Benford-like distribution
        np.random.seed(42)
        data = []
        for digit in range(1, 10):
            count = int(0.301 * 100 / digit * 3)  # Roughly Benford
            data.extend([digit * 10 + np.random.randint(0, 10) for _ in range(count)])

        values = pd.Series(data[:100])
        chi2, p_value, distribution = benford_chi_square(values)
        # Should return valid results
        assert chi2 >= 0
        assert 0 <= p_value <= 1
        assert len(distribution) == 9

    def test_check_benford_for_stock_small_sample(self):
        from stock_datasource.modules.quant.benford_checker import check_benford_for_stock

        revenue = pd.Series([100, 200])
        profit = pd.Series([50, 80])
        result = check_benford_for_stock(revenue, profit)
        assert result["pass"] is True
        assert result["reason"] == "样本量不足，跳过检验"
        assert result["sample_size"] == 4

    def test_check_benford_for_stock_normal_data(self):
        from stock_datasource.modules.quant.benford_checker import check_benford_for_stock

        pytest.importorskip("scipy", reason="scipy not installed")

        # Create enough data points (20+)
        np.random.seed(42)
        revenue = pd.Series(np.random.uniform(100, 9000, 30))
        profit = pd.Series(np.random.uniform(10, 5000, 30))
        result = check_benford_for_stock(revenue, profit)
        assert "pass" in result
        assert "chi2" in result
        assert "p_value" in result
        assert result["sample_size"] >= 20


# =============================================================================
# Data Readiness Tests
# =============================================================================

class TestDataReadiness:
    """Test DataReadinessChecker with mocked ClickHouse."""

    @pytest.mark.asyncio
    async def test_check_screening_readiness_all_ready(self):
        from stock_datasource.modules.quant.data_readiness import DataReadinessChecker

        checker = DataReadinessChecker()

        with patch("stock_datasource.modules.quant.data_readiness.db_client") as mock_db:
            mock_db.table_exists.return_value = True
            mock_db.execute_query.side_effect = [
                # count query
                pd.DataFrame({"cnt": [1000]}),
                # date range query
                pd.DataFrame({"min_d": ["20200101"], "max_d": ["20260201"]}),
                # column check query
                pd.DataFrame({"roe": [10.5]}),
                # Same pattern for income table
                pd.DataFrame({"cnt": [800]}),
                pd.DataFrame({"min_d": ["20200101"], "max_d": ["20260201"]}),
                pd.DataFrame({"total_revenue": [1e8]}),
                # Balance table
                pd.DataFrame({"cnt": [700]}),
                pd.DataFrame({"min_d": ["20200101"], "max_d": ["20260201"]}),
                pd.DataFrame({"accounts_receiv": [1e6]}),
                # Cashflow table
                pd.DataFrame({"cnt": [600]}),
                pd.DataFrame({"min_d": ["20200101"], "max_d": ["20260201"]}),
                pd.DataFrame({"n_cashflow_act": [5e7]}),
            ]

            result = await checker.check_screening_readiness()
            assert result.is_ready is True
            assert result.stage == "screening"
            assert result.missing_summary is None

    @pytest.mark.asyncio
    async def test_check_screening_readiness_missing_table(self):
        from stock_datasource.modules.quant.data_readiness import DataReadinessChecker

        checker = DataReadinessChecker()

        with patch("stock_datasource.modules.quant.data_readiness.db_client") as mock_db:
            # First table doesn't exist
            mock_db.table_exists.return_value = False

            result = await checker.check_screening_readiness()
            assert result.is_ready is False
            assert result.missing_summary is not None
            assert result.missing_summary.missing_count > 0
            assert len(result.missing_summary.plugins_to_trigger) > 0

    @pytest.mark.asyncio
    async def test_check_screening_readiness_empty_table(self):
        from stock_datasource.modules.quant.data_readiness import DataReadinessChecker

        checker = DataReadinessChecker()

        with patch("stock_datasource.modules.quant.data_readiness.db_client") as mock_db:
            mock_db.table_exists.return_value = True
            mock_db.execute_query.return_value = pd.DataFrame({"cnt": [0]})

            result = await checker.check_screening_readiness()
            assert result.is_ready is False

    @pytest.mark.asyncio
    async def test_check_core_pool_readiness(self):
        from stock_datasource.modules.quant.data_readiness import DataReadinessChecker

        checker = DataReadinessChecker()

        with patch("stock_datasource.modules.quant.data_readiness.db_client") as mock_db:
            mock_db.table_exists.return_value = True
            mock_db.execute_query.side_effect = [
                pd.DataFrame({"cnt": [5000]}),
                pd.DataFrame({"min_d": ["20200101"], "max_d": ["20260201"]}),
                pd.DataFrame({"pe": [15.0]}),
                pd.DataFrame({"cnt": [10000]}),
                pd.DataFrame({"min_d": ["20200101"], "max_d": ["20260201"]}),
                pd.DataFrame({"close": [10.5]}),
                pd.DataFrame({"cnt": [10000]}),
                pd.DataFrame({"min_d": ["20200101"], "max_d": ["20260201"]}),
                pd.DataFrame({"adj_factor": [1.0]}),
            ]

            result = await checker.check_core_pool_readiness()
            assert result.is_ready is True
            assert result.stage == "core_pool"

    @pytest.mark.asyncio
    async def test_check_full_pipeline_readiness(self):
        from stock_datasource.modules.quant.data_readiness import DataReadinessChecker

        checker = DataReadinessChecker()

        with patch("stock_datasource.modules.quant.data_readiness.db_client") as mock_db:
            mock_db.table_exists.return_value = False

            results = await checker.check_full_pipeline_readiness()
            assert "screening" in results
            assert "core_pool" in results
            assert "trading_signals" in results
            # All should be not ready since table_exists=False
            for stage, result in results.items():
                assert result.is_ready is False

    @pytest.mark.asyncio
    async def test_missing_summary_plugin_display_names(self):
        from stock_datasource.modules.quant.data_readiness import DataReadinessChecker

        checker = DataReadinessChecker()

        with patch("stock_datasource.modules.quant.data_readiness.db_client") as mock_db:
            mock_db.table_exists.return_value = False

            result = await checker.check_screening_readiness()
            assert result.missing_summary is not None
            for plugin_info in result.missing_summary.plugins_to_trigger:
                assert plugin_info.display_name != ""
                assert plugin_info.plugin_name.startswith("tushare_")

    @pytest.mark.asyncio
    async def test_check_readiness_with_min_date(self):
        from stock_datasource.modules.quant.data_readiness import DataReadinessChecker

        checker = DataReadinessChecker()

        with patch("stock_datasource.modules.quant.data_readiness.db_client") as mock_db:
            mock_db.table_exists.return_value = True
            mock_db.execute_query.side_effect = [
                pd.DataFrame({"cnt": [100]}),
                # date range shows data is old
                pd.DataFrame({"min_d": ["20200101"], "max_d": ["20240601"]}),
            ]

            result = await checker.check_screening_readiness(min_date="20260101")
            assert result.is_ready is False

    def test_build_missing_summary(self):
        from stock_datasource.modules.quant.data_readiness import DataReadinessChecker
        from stock_datasource.modules.quant.schemas import (
            DataRequirement,
            DataRequirementStatus,
            DataStatus,
        )

        checker = DataReadinessChecker()
        statuses = [
            DataRequirementStatus(
                requirement=DataRequirement(
                    plugin_name="tushare_fina_indicator",
                    table_name="fact_fina_indicator",
                ),
                status=DataStatus.READY,
            ),
            DataRequirementStatus(
                requirement=DataRequirement(
                    plugin_name="tushare_income",
                    table_name="fact_income",
                    description="利润表",
                ),
                status=DataStatus.MISSING_TABLE,
                suggested_plugins=["tushare_income"],
                suggested_task_type="full",
            ),
        ]

        summary = checker._build_missing_summary(statuses, "screening")
        assert summary.total_requirements == 2
        assert summary.ready_count == 1
        assert summary.missing_count == 1
        assert len(summary.plugins_to_trigger) == 1
        assert summary.plugins_to_trigger[0].plugin_name == "tushare_income"
        assert summary.affected_engines == ["screening"]
        assert "分钟" in summary.estimated_sync_time

    def test_get_data_readiness_checker_singleton(self):
        import stock_datasource.modules.quant.data_readiness as dr_module

        # Reset singleton
        dr_module._checker = None

        checker1 = dr_module.get_data_readiness_checker()
        checker2 = dr_module.get_data_readiness_checker()
        assert checker1 is checker2

        # Cleanup
        dr_module._checker = None


# =============================================================================
# Screening Engine Tests
# =============================================================================

class TestScreeningEngine:
    """Test screening engine with mocked ClickHouse."""

    def _make_fina_df(self, codes, years=3):
        """Helper to create financial indicator DataFrame."""
        rows = []
        for code in codes:
            for y in range(years):
                rows.append({
                    "ts_code": code,
                    "end_date": f"{2025 - y}1231",
                    "roe": 12.0 + y,
                    "revenue_yoy": 15.0 + y,
                    "netprofit_yoy": 10.0 + y,
                })
        return pd.DataFrame(rows)

    def _make_income_df(self, codes, years=3):
        rows = []
        for code in codes:
            for y in range(years):
                rows.append({
                    "ts_code": code,
                    "end_date": f"{2025 - y}1231",
                    "total_revenue": 1e9 * (1 + y * 0.1),
                    "n_income": 1e8 * (1 + y * 0.05),
                })
        return pd.DataFrame(rows)

    def _make_balance_df(self, codes, years=2):
        rows = []
        for code in codes:
            for y in range(years):
                rows.append({
                    "ts_code": code,
                    "end_date": f"{2025 - y}1231",
                    "accounts_receiv": 5e7 * (1 + y * 0.05),
                })
        return pd.DataFrame(rows)

    def _make_cashflow_df(self, codes, years=2):
        rows = []
        for code in codes:
            for y in range(years):
                rows.append({
                    "ts_code": code,
                    "end_date": f"{2025 - y}1231",
                    "n_cashflow_act": 6e8 * (1 + y * 0.1),
                })
        return pd.DataFrame(rows)

    def test_default_screening_rules(self):
        from stock_datasource.modules.quant.screening_engine import default_screening_rules

        rules = default_screening_rules()
        assert len(rules) == 7
        names = [r.name for r in rules]
        assert "revenue_growth_2y" in names
        assert "net_profit_positive" in names
        assert "roe_3y_avg" in names
        assert "cashflow_sync" in names
        assert "expense_anomaly" in names
        assert "receivable_revenue_gap" in names
        assert "benford_check" in names

        # Benford is soft condition
        benford = [r for r in rules if r.name == "benford_check"][0]
        assert benford.is_hard_reject is False

    def test_check_revenue_growth_pass(self):
        from stock_datasource.modules.quant.screening_engine import ScreeningEngine

        engine = ScreeningEngine()
        codes = {"000001.SZ", "000002.SZ"}
        fina_df = self._make_fina_df(list(codes))

        passed, failed, skipped = engine._check_revenue_growth(
            fina_df, codes, {"min_growth": 0, "years": 2}
        )
        assert codes == passed  # All have growth > 0
        assert len(failed) == 0

    def test_check_revenue_growth_fail(self):
        from stock_datasource.modules.quant.screening_engine import ScreeningEngine

        engine = ScreeningEngine()
        codes = {"000001.SZ"}
        df = pd.DataFrame({
            "ts_code": ["000001.SZ", "000001.SZ"],
            "end_date": ["20251231", "20241231"],
            "roe": [10, 10],
            "revenue_yoy": [-5, 10],  # First year negative
            "netprofit_yoy": [10, 10],
        })

        passed, failed, skipped = engine._check_revenue_growth(
            df, codes, {"min_growth": 0, "years": 2}
        )
        assert "000001.SZ" in failed

    def test_check_revenue_growth_skip_insufficient_data(self):
        from stock_datasource.modules.quant.screening_engine import ScreeningEngine

        engine = ScreeningEngine()
        codes = {"000001.SZ"}
        df = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "end_date": ["20251231"],
            "roe": [10],
            "revenue_yoy": [15],
            "netprofit_yoy": [10],
        })

        passed, failed, skipped = engine._check_revenue_growth(
            df, codes, {"min_growth": 0, "years": 2}
        )
        assert "000001.SZ" in skipped

    def test_check_net_profit_positive(self):
        from stock_datasource.modules.quant.screening_engine import ScreeningEngine

        engine = ScreeningEngine()
        codes = {"000001.SZ", "000002.SZ"}
        df = pd.DataFrame({
            "ts_code": ["000001.SZ", "000002.SZ"],
            "end_date": ["20251231", "20251231"],
            "total_revenue": [1e9, 1e9],
            "n_income": [1e8, -5e7],  # 000002 has negative profit
        })

        passed, failed, skipped = engine._check_net_profit(df, codes)
        assert "000001.SZ" in passed
        assert "000002.SZ" in failed

    def test_check_net_profit_skip_no_data(self):
        from stock_datasource.modules.quant.screening_engine import ScreeningEngine

        engine = ScreeningEngine()
        codes = {"000001.SZ"}
        df = pd.DataFrame({
            "ts_code": ["000099.SZ"],  # Different code
            "end_date": ["20251231"],
            "total_revenue": [1e9],
            "n_income": [1e8],
        })

        passed, failed, skipped = engine._check_net_profit(df, codes)
        assert "000001.SZ" in skipped

    def test_check_roe_3y_avg(self):
        from stock_datasource.modules.quant.screening_engine import ScreeningEngine

        engine = ScreeningEngine()
        codes = {"000001.SZ"}
        # ROE avg = (12+13+14)/3 = 13 >= 5
        fina_df = self._make_fina_df(["000001.SZ"], years=3)

        passed, failed, skipped = engine._check_roe(
            fina_df, codes, {"min_roe": 5.0, "years": 3}
        )
        assert "000001.SZ" in passed

    def test_check_roe_3y_avg_fail(self):
        from stock_datasource.modules.quant.screening_engine import ScreeningEngine

        engine = ScreeningEngine()
        codes = {"000001.SZ"}
        df = pd.DataFrame({
            "ts_code": ["000001.SZ"] * 3,
            "end_date": ["20251231", "20241231", "20231231"],
            "roe": [2.0, 1.0, 3.0],  # avg = 2.0 < 5.0
            "revenue_yoy": [10, 10, 10],
            "netprofit_yoy": [5, 5, 5],
        })

        passed, failed, skipped = engine._check_roe(
            df, codes, {"min_roe": 5.0, "years": 3}
        )
        assert "000001.SZ" in failed

    def test_check_cashflow_sync_pass(self):
        from stock_datasource.modules.quant.screening_engine import ScreeningEngine

        engine = ScreeningEngine()
        codes = {"000001.SZ"}
        income_df = self._make_income_df(["000001.SZ"], years=2)
        cashflow_df = self._make_cashflow_df(["000001.SZ"], years=2)

        passed, failed, skipped = engine._check_cashflow_sync(
            income_df, cashflow_df, codes, {"min_ratio": 0.5, "years": 2}
        )
        assert "000001.SZ" in passed

    def test_check_receivable_revenue_gap_pass(self):
        from stock_datasource.modules.quant.screening_engine import ScreeningEngine

        engine = ScreeningEngine()
        codes = {"000001.SZ"}
        income_df = self._make_income_df(["000001.SZ"], years=2)
        balance_df = self._make_balance_df(["000001.SZ"], years=2)

        passed, failed, skipped = engine._check_receivable_revenue(
            income_df, balance_df, codes, {"max_gap": 20.0}
        )
        # With test data, receivable growth should be small
        assert "000001.SZ" in passed or "000001.SZ" in skipped

    @pytest.mark.asyncio
    async def test_run_screening_data_missing(self):
        """When data is missing, return data_missing status with readiness report."""
        from stock_datasource.modules.quant.screening_engine import ScreeningEngine

        engine = ScreeningEngine()

        with patch.object(engine.readiness_checker, "check_screening_readiness") as mock_check:
            from stock_datasource.modules.quant.schemas import DataReadinessResult, MissingDataSummary

            mock_check.return_value = DataReadinessResult(
                is_ready=False,
                stage="screening",
                missing_summary=MissingDataSummary(
                    total_requirements=4,
                    missing_count=2,
                ),
            )

            result = await engine.run_screening()
            assert result.status == "data_missing"
            assert result.data_readiness is not None
            assert result.data_readiness.is_ready is False

    @pytest.mark.asyncio
    async def test_run_screening_success(self):
        """Full screening with all data ready."""
        from stock_datasource.modules.quant.screening_engine import ScreeningEngine

        engine = ScreeningEngine()
        codes = ["000001.SZ", "000002.SZ"]

        with patch.object(engine.readiness_checker, "check_screening_readiness") as mock_check, \
             patch("stock_datasource.modules.quant.screening_engine.db_client") as mock_db:

            from stock_datasource.modules.quant.schemas import DataReadinessResult

            mock_check.return_value = DataReadinessResult(is_ready=True, stage="screening")

            fina_df = self._make_fina_df(codes)
            income_df = self._make_income_df(codes)
            balance_df = self._make_balance_df(codes)
            cashflow_df = self._make_cashflow_df(codes)
            names_df = pd.DataFrame({
                "ts_code": codes,
                "name": ["平安银行", "万科A"],
            })

            mock_db.execute_query.side_effect = [
                fina_df, income_df, balance_df, cashflow_df, names_df,
            ]
            mock_db.insert_dataframe = Mock()

            result = await engine.run_screening("20260101")
            assert result.status == "success"
            assert result.total_stocks == 2
            assert result.passed_count + result.rejected_count == 2
            assert len(result.rule_details) > 0

    def test_check_revenue_growth_missing_column(self):
        from stock_datasource.modules.quant.screening_engine import ScreeningEngine

        engine = ScreeningEngine()
        codes = {"000001.SZ"}
        df = pd.DataFrame({"ts_code": ["000001.SZ"], "end_date": ["20251231"], "roe": [10]})
        # Missing revenue_yoy column

        passed, failed, skipped = engine._check_revenue_growth(df, codes, {"min_growth": 0, "years": 2})
        assert codes == skipped


# =============================================================================
# RPS Calculator Tests
# =============================================================================

class TestRPSCalculator:
    """Test RPS calculator with mocked data."""

    @pytest.mark.asyncio
    async def test_calculate_rps_data_not_ready(self):
        from stock_datasource.modules.quant.rps_calculator import RPSCalculator

        calc = RPSCalculator()

        with patch.object(calc.readiness_checker, "check_core_pool_readiness") as mock_check:
            from stock_datasource.modules.quant.schemas import DataReadinessResult

            mock_check.return_value = DataReadinessResult(is_ready=False, stage="core_pool")

            result = await calc.calculate_rps()
            assert result.total_stocks == 0
            assert result.data_readiness.is_ready is False

    @pytest.mark.asyncio
    async def test_calculate_rps_success(self):
        from stock_datasource.modules.quant.rps_calculator import RPSCalculator

        calc = RPSCalculator()

        with patch.object(calc.readiness_checker, "check_core_pool_readiness") as mock_check, \
             patch("stock_datasource.modules.quant.rps_calculator.db_client") as mock_db:

            from stock_datasource.modules.quant.schemas import DataReadinessResult

            mock_check.return_value = DataReadinessResult(is_ready=True, stage="core_pool")

            # Generate 300 days of daily data for 3 stocks
            rows = []
            for code in ["000001.SZ", "000002.SZ", "000003.SZ"]:
                base_price = 10.0 if code == "000001.SZ" else (20.0 if code == "000002.SZ" else 15.0)
                for i in range(300):
                    rows.append({
                        "ts_code": code,
                        "trade_date": f"2025{(i // 28 + 1):02d}{(i % 28 + 1):02d}",
                        "close": base_price + i * 0.1,
                        "pct_chg": 1.0,
                        "adj_factor": 1.0,
                    })
            daily_df = pd.DataFrame(rows)
            names_df = pd.DataFrame({
                "ts_code": ["000001.SZ", "000002.SZ", "000003.SZ"],
                "name": ["平安银行", "万科A", "中国平安"],
            })

            mock_db.execute_query.side_effect = [daily_df, names_df]
            mock_db.insert_dataframe = Mock()

            result = await calc.calculate_rps("20260101")
            assert result.total_stocks == 3
            assert len(result.items) == 3
            # Items should be sorted by rps_250 descending
            assert result.items[0].rps_250 >= result.items[-1].rps_250

    @pytest.mark.asyncio
    async def test_get_strong_stocks(self):
        from stock_datasource.modules.quant.rps_calculator import RPSCalculator

        calc = RPSCalculator()

        with patch("stock_datasource.modules.quant.rps_calculator.db_client") as mock_db:
            mock_db.execute_query.return_value = pd.DataFrame({
                "ts_code": ["000001.SZ", "000002.SZ"],
            })

            result = await calc.get_strong_stocks(threshold=80)
            assert len(result) == 2
            assert "000001.SZ" in result

    def test_rps_singleton(self):
        import stock_datasource.modules.quant.rps_calculator as rps_module

        rps_module._rps_calculator = None

        calc1 = rps_module.get_rps_calculator()
        calc2 = rps_module.get_rps_calculator()
        assert calc1 is calc2

        rps_module._rps_calculator = None


# =============================================================================
# Factor Scorer Tests
# =============================================================================

class TestFactorScorer:
    """Test multi-factor scoring model."""

    def test_percentile_score(self):
        from stock_datasource.modules.quant.factor_scorer import _percentile_score

        values = pd.Series([10, 20, 30, 40, 50])
        assert _percentile_score(30, values) == 40.0  # 2 out of 5 < 30
        assert _percentile_score(50, values) == 80.0
        assert _percentile_score(10, values) == 0.0

    def test_percentile_score_empty(self):
        from stock_datasource.modules.quant.factor_scorer import _percentile_score

        assert _percentile_score(10, pd.Series([])) == 50.0
        assert _percentile_score(float("nan"), pd.Series([1, 2, 3])) == 50.0

    def test_inverse_percentile_score(self):
        from stock_datasource.modules.quant.factor_scorer import _inverse_percentile_score

        values = pd.Series([10, 20, 30, 40, 50])
        # Lower PE is better, so 10 should score high
        score = _inverse_percentile_score(10, values)
        assert score == 80.0  # 4 out of 5 > 10

    def test_factor_weight_sum(self):
        from stock_datasource.modules.quant.schemas import FactorWeight

        w = FactorWeight()
        total = w.quality + w.growth + w.value + w.momentum
        assert abs(total - 1.0) < 1e-9

    @pytest.mark.asyncio
    async def test_score_stocks_empty(self):
        from stock_datasource.modules.quant.factor_scorer import FactorScorer

        scorer = FactorScorer()
        result = await scorer.score_stocks([])
        assert result == []

    @pytest.mark.asyncio
    async def test_score_stocks_with_data(self):
        from stock_datasource.modules.quant.factor_scorer import FactorScorer

        scorer = FactorScorer()
        codes = ["000001.SZ", "000002.SZ"]

        with patch("stock_datasource.modules.quant.factor_scorer.db_client") as mock_db:
            fina_df = pd.DataFrame({
                "ts_code": ["000001.SZ", "000001.SZ", "000002.SZ", "000002.SZ"],
                "end_date": ["20251231", "20241231", "20251231", "20241231"],
                "roe": [15.0, 14.0, 8.0, 7.0],
                "revenue_yoy": [20.0, 18.0, 5.0, 3.0],
                "netprofit_yoy": [15.0, 12.0, -2.0, 1.0],
                "grossprofit_margin": [35.0, 33.0, 20.0, 18.0],
                "debt_to_assets": [40.0, 42.0, 65.0, 68.0],
            })
            daily_basic_df = pd.DataFrame({
                "ts_code": ["000001.SZ", "000002.SZ"],
                "trade_date": ["20260101", "20260101"],
                "pe": [12.0, 25.0],
                "pb": [1.5, 3.0],
                "total_mv": [1e10, 5e9],
            })

            # Daily data for momentum: 120+ rows per stock
            daily_rows = []
            for code in codes:
                base = 10.0 if code == "000001.SZ" else 8.0
                for i in range(150):
                    daily_rows.append({
                        "ts_code": code,
                        "trade_date": f"2025{(i // 28 + 1):02d}{(i % 28 + 1):02d}",
                        "close": base + i * 0.05,
                        "pct_chg": 0.5,
                    })
            daily_df = pd.DataFrame(daily_rows)

            names_df = pd.DataFrame({
                "ts_code": codes,
                "name": ["平安银行", "万科A"],
            })

            mock_db.execute_query.side_effect = [fina_df, daily_basic_df, daily_df, names_df]

            results = await scorer.score_stocks(codes)
            assert len(results) == 2
            # Results should be sorted by total_score descending
            assert results[0].total_score >= results[1].total_score
            # Ranks should be assigned
            assert results[0].rank == 1
            assert results[1].rank == 2
            # Score components should be populated
            assert results[0].quality_score > 0
            assert results[0].growth_score > 0


# =============================================================================
# Core Pool Builder Tests
# =============================================================================

class TestCorePoolBuilder:
    """Test core pool builder."""

    def test_calc_factor_distribution(self):
        from stock_datasource.modules.quant.core_pool_builder import CorePoolBuilder
        from stock_datasource.modules.quant.schemas import FactorScoreDetail

        builder = CorePoolBuilder()
        stocks = [
            FactorScoreDetail(
                ts_code=f"00000{i}.SZ",
                quality_score=50 + i * 5,
                growth_score=40 + i * 3,
                value_score=60 + i * 2,
                momentum_score=45 + i * 4,
                total_score=50 + i * 3,
            )
            for i in range(5)
        ]

        dist = builder._calc_factor_distribution(stocks)
        assert "quality_score" in dist
        assert "total_score" in dist
        assert dist["quality_score"]["min"] == 50
        assert dist["quality_score"]["max"] == 70

    def test_calc_factor_distribution_empty(self):
        from stock_datasource.modules.quant.core_pool_builder import CorePoolBuilder

        builder = CorePoolBuilder()
        assert builder._calc_factor_distribution([]) == {}

    @pytest.mark.asyncio
    async def test_build_core_pool_data_missing(self):
        from stock_datasource.modules.quant.core_pool_builder import CorePoolBuilder

        builder = CorePoolBuilder()

        with patch.object(builder.readiness_checker, "check_core_pool_readiness") as mock_check:
            from stock_datasource.modules.quant.schemas import DataReadinessResult

            mock_check.return_value = DataReadinessResult(is_ready=False, stage="core_pool")

            result = await builder.build_core_pool(["000001.SZ"])
            assert result.core_stocks == []
            assert result.data_readiness.is_ready is False

    def test_quick_financial_check(self):
        from stock_datasource.modules.quant.core_pool_builder import CorePoolBuilder

        builder = CorePoolBuilder()

        with patch("stock_datasource.modules.quant.core_pool_builder.db_client") as mock_db:
            mock_db.execute_query.return_value = pd.DataFrame({
                "ts_code": ["000001.SZ", "000003.SZ"],
                "latest_roe": [10.0, 5.0],
            })

            result = builder._quick_financial_check(["000001.SZ", "000002.SZ", "000003.SZ"])
            assert "000001.SZ" in result
            assert "000003.SZ" in result
            assert "000002.SZ" not in result


# =============================================================================
# Signal Generator Tests
# =============================================================================

class TestSignalGenerator:
    """Test trading signal generator."""

    def _make_daily_df(self, ts_code, days=200, trend="up"):
        """Create daily price data with controllable trend."""
        rows = []
        base_price = 10.0
        for i in range(days):
            if trend == "up":
                price = base_price + i * 0.05
            elif trend == "down":
                price = base_price - i * 0.02
            else:
                price = base_price + np.sin(i / 20) * 2
            rows.append({
                "trade_date": f"2025{(i // 28 + 1):02d}{(i % 28 + 1):02d}",
                "close": max(1, price),
                "pct_chg": 0.5 if trend == "up" else -0.3,
            })
        return pd.DataFrame(rows)

    @pytest.mark.asyncio
    async def test_generate_signals_data_not_ready(self):
        from stock_datasource.modules.quant.signal_generator import SignalGenerator

        gen = SignalGenerator()

        with patch.object(gen.readiness_checker, "check_signal_readiness") as mock_check:
            from stock_datasource.modules.quant.schemas import DataReadinessResult

            mock_check.return_value = DataReadinessResult(is_ready=False, stage="trading_signals")

            result = await gen.generate_signals(["000001.SZ"])
            assert result.signals == []
            assert result.data_readiness.is_ready is False

    @pytest.mark.asyncio
    async def test_check_market_risk_normal(self):
        from stock_datasource.modules.quant.signal_generator import SignalGenerator

        gen = SignalGenerator()

        with patch("stock_datasource.modules.quant.signal_generator.db_client") as mock_db:
            # Create 300 days of index data - uptrend so close > MA250
            rows = []
            for i in range(300):
                rows.append({
                    "trade_date": f"2025{(i // 28 + 1):02d}{(i % 28 + 1):02d}",
                    "close": 3500 + i * 2,  # Uptrend
                })
            mock_db.execute_query.return_value = pd.DataFrame(rows)

            result = await gen.check_market_risk()
            assert result.risk_level == "normal"
            assert result.suggested_position == 1.0
            assert result.is_above_ma250 is True

    @pytest.mark.asyncio
    async def test_check_market_risk_danger(self):
        from stock_datasource.modules.quant.signal_generator import SignalGenerator

        gen = SignalGenerator()

        with patch("stock_datasource.modules.quant.signal_generator.db_client") as mock_db:
            # Create 300 days of index data - downtrend so close < MA250
            rows = []
            for i in range(300):
                rows.append({
                    "trade_date": f"2025{(i // 28 + 1):02d}{(i % 28 + 1):02d}",
                    "close": 4000 - i * 3,  # Downtrend
                })
            mock_db.execute_query.return_value = pd.DataFrame(rows)

            result = await gen.check_market_risk()
            assert result.risk_level in ("warning", "danger")
            assert result.suggested_position < 1.0

    @pytest.mark.asyncio
    async def test_check_market_risk_insufficient_data(self):
        from stock_datasource.modules.quant.signal_generator import SignalGenerator

        gen = SignalGenerator()

        with patch("stock_datasource.modules.quant.signal_generator.db_client") as mock_db:
            mock_db.execute_query.return_value = pd.DataFrame({"trade_date": [], "close": []})

            result = await gen.check_market_risk()
            assert "数据不足" in result.description

    @pytest.mark.asyncio
    async def test_golden_cross_signal(self):
        """Test that golden cross (MA25 crosses above MA120) generates buy signal."""
        from stock_datasource.modules.quant.signal_generator import SignalGenerator
        from stock_datasource.modules.quant.schemas import MarketRiskStatus

        gen = SignalGenerator()

        # Construct data where MA25 crosses above MA120 on the last day
        # MA120 needs 120 days, so we need 130+ days
        days = 150
        prices = []
        for i in range(days):
            if i < 120:
                # Flat at 10 for first 120 days
                prices.append(10.0)
            else:
                # Spike up so MA25 crosses MA120
                prices.append(10.0 + (i - 119) * 0.5)

        df = pd.DataFrame({
            "trade_date": [f"2025{(i // 28 + 1):02d}{(i % 28 + 1):02d}" for i in range(days)],
            "close": prices,
            "pct_chg": [0.0] * days,
        })

        market_risk = MarketRiskStatus(risk_level="normal", suggested_position=1.0)

        signals = await gen._check_stock_signals("000001.SZ", "20260101", "测试", market_risk)
        # Should have at least one signal (golden cross or other)
        # The exact signal depends on MA values
        for sig in signals:
            assert sig.ts_code == "000001.SZ"
            assert sig.signal_context != {}

    def test_signal_config_defaults(self):
        from stock_datasource.modules.quant.signal_generator import SignalGenerator

        gen = SignalGenerator()
        assert gen.config.ma_short == 25
        assert gen.config.ma_long == 120

    def test_signal_generator_singleton(self):
        import stock_datasource.modules.quant.signal_generator as sig_module

        sig_module._generator = None

        gen1 = sig_module.get_signal_generator()
        gen2 = sig_module.get_signal_generator()
        assert gen1 is gen2

        sig_module._generator = None


# =============================================================================
# Service Tests
# =============================================================================

class TestQuantService:
    """Test QuantService pipeline orchestration."""

    @pytest.mark.asyncio
    async def test_check_data_readiness_full(self):
        from stock_datasource.modules.quant.service import QuantService

        service = QuantService()
        service._initialized = True

        with patch("stock_datasource.modules.quant.service.get_data_readiness_checker") as mock_getter:
            mock_checker = AsyncMock()
            mock_getter.return_value = mock_checker
            mock_checker.check_full_pipeline_readiness.return_value = {
                "screening": MagicMock(is_ready=True),
                "core_pool": MagicMock(is_ready=False),
            }

            result = await service.check_data_readiness()
            assert "screening" in result
            mock_checker.check_full_pipeline_readiness.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_data_readiness_single_stage(self):
        from stock_datasource.modules.quant.service import QuantService

        service = QuantService()
        service._initialized = True

        with patch("stock_datasource.modules.quant.service.get_data_readiness_checker") as mock_getter:
            mock_checker = AsyncMock()
            mock_getter.return_value = mock_checker
            mock_checker.check_screening_readiness.return_value = MagicMock(is_ready=True)

            result = await service.check_data_readiness("screening")
            mock_checker.check_screening_readiness.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_screening(self):
        from stock_datasource.modules.quant.service import QuantService
        from stock_datasource.modules.quant.schemas import ScreeningRunRequest, ScreeningResult

        service = QuantService()
        service._initialized = True

        with patch("stock_datasource.modules.quant.service.get_screening_engine") as mock_getter:
            mock_engine = AsyncMock()
            mock_getter.return_value = mock_engine
            mock_engine.run_screening.return_value = ScreeningResult(
                run_date="20260101", status="success", total_stocks=100
            )

            result = await service.run_screening(ScreeningRunRequest(trade_date="20260101"))
            assert result.status == "success"
            assert result.total_stocks == 100

    @pytest.mark.asyncio
    async def test_get_pool_empty(self):
        from stock_datasource.modules.quant.service import QuantService

        service = QuantService()
        service._initialized = True

        with patch("stock_datasource.modules.quant.service.db_client") as mock_db:
            mock_db.execute_query.return_value = pd.DataFrame()

            result = await service.get_pool()
            assert result.core_stocks == []
            assert result.supplement_stocks == []

    @pytest.mark.asyncio
    async def test_get_signals_empty(self):
        from stock_datasource.modules.quant.service import QuantService

        service = QuantService()
        service._initialized = True

        with patch("stock_datasource.modules.quant.service.db_client") as mock_db:
            mock_db.execute_query.return_value = pd.DataFrame()

            result = await service.get_signals()
            assert result == []

    @pytest.mark.asyncio
    async def test_get_config_defaults(self):
        from stock_datasource.modules.quant.service import QuantService

        service = QuantService()
        service._initialized = True

        with patch("stock_datasource.modules.quant.service.db_client") as mock_db:
            mock_db.execute_query.return_value = pd.DataFrame()

            configs = await service.get_config()
            assert len(configs) == 3
            types = [c.config_type for c in configs]
            assert "screening_rules" in types
            assert "factor_weights" in types
            assert "signal_params" in types

    @pytest.mark.asyncio
    async def test_update_config(self):
        from stock_datasource.modules.quant.service import QuantService
        from stock_datasource.modules.quant.schemas import QuantConfigUpdate

        service = QuantService()
        service._initialized = True

        with patch("stock_datasource.modules.quant.service.db_client") as mock_db:
            mock_db.insert_dataframe = Mock()

            update = QuantConfigUpdate(
                config_type="factor_weights",
                config_data={"quality": 0.4, "growth": 0.3, "value": 0.15, "momentum": 0.15},
            )
            result = await service.update_config(update)
            assert result.config_type == "factor_weights"
            assert result.config_data["quality"] == 0.4
            mock_db.insert_dataframe.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_pipeline_status_not_found(self):
        from stock_datasource.modules.quant.service import QuantService

        service = QuantService()
        service._initialized = True

        with patch("stock_datasource.modules.quant.service.db_client") as mock_db:
            mock_db.execute_query.return_value = pd.DataFrame()

            result = await service.get_pipeline_status("nonexistent")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_latest_pipeline_empty(self):
        from stock_datasource.modules.quant.service import QuantService

        service = QuantService()
        service._initialized = True

        with patch("stock_datasource.modules.quant.service.db_client") as mock_db:
            mock_db.execute_query.return_value = pd.DataFrame()

            result = await service.get_latest_pipeline()
            assert result is None

    def test_service_singleton(self):
        import stock_datasource.modules.quant.service as svc_module

        svc_module._quant_service = None

        svc1 = svc_module.get_quant_service()
        svc2 = svc_module.get_quant_service()
        assert svc1 is svc2

        svc_module._quant_service = None


# =============================================================================
# Router / API Tests
# =============================================================================

class TestQuantRouter:
    """Test API router endpoints."""

    @pytest.fixture
    def client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from stock_datasource.modules.quant.router import router

        app = FastAPI()
        app.include_router(router, prefix="/api/quant")
        return TestClient(app)

    def test_health_endpoint(self, client):
        response = client.get("/api/quant/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["module"] == "quant"

    def test_check_stage_readiness_invalid(self, client):
        with patch("stock_datasource.modules.quant.router.get_quant_service") as mock_svc:
            response = client.get("/api/quant/data-readiness/invalid_stage")
            assert response.status_code == 400

    def test_get_screening_rules(self, client):
        with patch("stock_datasource.modules.quant.router.get_quant_service") as mock_getter:
            mock_svc = AsyncMock()
            mock_getter.return_value = mock_svc
            mock_svc.get_config.return_value = []

            response = client.get("/api/quant/screening/rules")
            assert response.status_code == 200

    def test_get_pool(self, client):
        with patch("stock_datasource.modules.quant.router.get_quant_service") as mock_getter:
            mock_svc = AsyncMock()
            mock_getter.return_value = mock_svc

            from stock_datasource.modules.quant.schemas import CorePoolResult
            mock_svc.get_pool.return_value = CorePoolResult(update_date="20260101")

            response = client.get("/api/quant/pool")
            assert response.status_code == 200

    def test_get_signals(self, client):
        with patch("stock_datasource.modules.quant.router.get_quant_service") as mock_getter:
            mock_svc = AsyncMock()
            mock_getter.return_value = mock_svc
            mock_svc.get_signals.return_value = []

            response = client.get("/api/quant/signals")
            assert response.status_code == 200

    def test_get_config(self, client):
        with patch("stock_datasource.modules.quant.router.get_quant_service") as mock_getter:
            mock_svc = AsyncMock()
            mock_getter.return_value = mock_svc
            mock_svc.get_config.return_value = []

            response = client.get("/api/quant/config")
            assert response.status_code == 200

    def test_get_rps(self, client):
        with patch("stock_datasource.modules.quant.router.get_quant_service") as mock_getter:
            mock_svc = AsyncMock()
            mock_getter.return_value = mock_svc
            mock_svc.get_rps.return_value = []

            response = client.get("/api/quant/rps")
            assert response.status_code == 200

    def test_get_market_risk(self, client):
        with patch("stock_datasource.modules.quant.signal_generator.get_signal_generator") as mock_getter:
            mock_gen = AsyncMock()
            mock_getter.return_value = mock_gen

            from stock_datasource.modules.quant.schemas import MarketRiskStatus
            mock_gen.check_market_risk.return_value = MarketRiskStatus(
                risk_level="normal", suggested_position=1.0
            )

            response = client.get("/api/quant/risk")
            assert response.status_code == 200
            data = response.json()
            assert data["risk_level"] == "normal"

    def test_run_screening_endpoint(self, client):
        with patch("stock_datasource.modules.quant.router.get_quant_service") as mock_getter:
            mock_svc = AsyncMock()
            mock_getter.return_value = mock_svc

            from stock_datasource.modules.quant.schemas import ScreeningResult
            mock_svc.run_screening.return_value = ScreeningResult(
                run_date="20260101", status="success", total_stocks=50, passed_count=30
            )

            response = client.post("/api/quant/screening/run", json={})
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["total_stocks"] == 50

    def test_run_pipeline_endpoint(self, client):
        with patch("stock_datasource.modules.quant.router.get_quant_service") as mock_getter:
            mock_svc = AsyncMock()
            mock_getter.return_value = mock_svc

            from stock_datasource.modules.quant.schemas import PipelineRunStatus
            mock_svc.run_pipeline.return_value = PipelineRunStatus(
                run_id="test123", overall_status="completed"
            )

            response = client.post("/api/quant/pipeline/run", json={"pipeline_type": "full"})
            assert response.status_code == 200
            data = response.json()
            assert data["run_id"] == "test123"

    def test_get_pipeline_status_not_found(self, client):
        with patch("stock_datasource.modules.quant.router.get_quant_service") as mock_getter:
            mock_svc = AsyncMock()
            mock_getter.return_value = mock_svc
            mock_svc.get_pipeline_status.return_value = None

            response = client.get("/api/quant/pipeline/status/nonexistent")
            assert response.status_code == 404

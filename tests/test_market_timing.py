"""择时系统单元测试 — 覆盖 MarketRegimeStrategy, StockTimingStrategy, PaperTrading 逻辑"""

import sys

sys.path.insert(0, "src")

import numpy as np
import pandas as pd
import pytest

from stock_datasource.strategies.builtin.market_regime_strategy import (
    MarketRegimeStrategy,
    RegimeState,
)
from stock_datasource.strategies.builtin.stock_timing_strategy import StockTimingStrategy


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def make_index_data(n=300, trend="up"):
    """生成指数模拟数据"""
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    if trend == "up":
        prices = 3000 + np.linspace(0, 1000, n) + np.random.normal(0, 10, n)
    elif trend == "down":
        prices = 4000 - np.linspace(0, 1000, n) + np.random.normal(0, 10, n)
    else:  # sideways
        prices = 3500 + np.random.normal(0, 30, n)

    return pd.DataFrame(
        {
            "timestamp": dates,
            "open": prices * 0.998,
            "high": prices * 1.005,
            "low": prices * 0.995,
            "close": prices,
            "volume": np.random.randint(1e8, 5e8, n).astype(float),
            "symbol": "000300.SH",
        }
    )


def make_stock_data(n=80, with_crossover=True):
    """生成个股模拟数据（带金叉）"""
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    if with_crossover:
        # 先跌后涨 → 产生金叉（确保金叉在第50天左右，RSI已有足够warmup）
        prices = np.concatenate(
            [np.linspace(60, 42, 40), np.linspace(43, 72, 40)]
        )
    else:
        prices = np.linspace(50, 52, n)  # 平稳

    prices = prices + np.random.normal(0, 0.2, n)

    # 金叉附近放量（第48-53天）
    volumes = np.full(n, 1e7)
    if with_crossover:
        volumes[48:53] = 2.5e7

    return pd.DataFrame(
        {
            "timestamp": dates,
            "open": prices * 0.99,
            "high": prices * 1.02,
            "low": prices * 0.98,
            "close": prices,
            "volume": volumes.astype(float),
            "symbol": "600519.SH",
        }
    )


# ------------------------------------------------------------------
# RSI Tests
# ------------------------------------------------------------------


class TestRSI:
    """RSI 计算正确性"""

    def test_rsi_all_up_is_100(self):
        """全涨行情 RSI 应为 100"""
        strategy = MarketRegimeStrategy()
        prices = pd.Series(np.linspace(10, 50, 30))
        rsi = strategy._calc_rsi(prices, 14)
        assert rsi.iloc[-1] == 100.0

    def test_rsi_all_down_is_0(self):
        """全跌行情 RSI 应为 0"""
        strategy = MarketRegimeStrategy()
        prices = pd.Series(np.linspace(50, 10, 30))
        rsi = strategy._calc_rsi(prices, 14)
        assert rsi.iloc[-1] == pytest.approx(0.0, abs=0.1)

    def test_rsi_normal_range(self):
        """正常行情 RSI 在 0-100 之间"""
        strategy = MarketRegimeStrategy()
        np.random.seed(42)
        prices = pd.Series(100 + np.cumsum(np.random.normal(0, 1, 100)))
        rsi = strategy._calc_rsi(prices, 14)
        valid = rsi.dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()


# ------------------------------------------------------------------
# MarketRegimeStrategy Tests
# ------------------------------------------------------------------


class TestMarketRegime:
    """市场状态检测"""

    def test_bull_regime_detected(self):
        """上涨趋势应检测为 bull"""
        data = make_index_data(300, trend="up")
        strategy = MarketRegimeStrategy()
        regime = strategy.detect_regime(data)
        assert regime.regime in ("bull", "strong_bull")
        assert regime.position_level >= 0.6

    def test_bear_regime_detected(self):
        """下跌趋势应检测为 bear"""
        data = make_index_data(300, trend="down")
        strategy = MarketRegimeStrategy()
        regime = strategy.detect_regime(data)
        assert regime.regime in ("bear", "strong_bear")
        assert regime.position_level <= 0.15

    def test_regime_has_required_fields(self):
        """RegimeState 应包含所有必要字段"""
        data = make_index_data(300, trend="up")
        strategy = MarketRegimeStrategy()
        regime = strategy.detect_regime(data)

        assert regime.regime in (
            "strong_bull", "bull", "consolidation", "bear", "strong_bear", "unknown"
        )
        assert 0.0 <= regime.position_level <= 1.0
        assert 0.0 <= regime.confidence <= 1.0
        assert "ma_short" in regime.indicators
        assert "rsi" in regime.indicators
        assert "adx" in regime.indicators
        assert len(regime.reason) > 0

    def test_generate_signals_at_transitions(self):
        """regime 切换应产生买卖信号"""
        # 先跌后涨 → 应产生 bear→bull 的买入信号
        data = make_index_data(300, trend="up")
        # 前 100 天强制下跌让 MA 形成死叉
        data.iloc[:100, data.columns.get_loc("close")] = np.linspace(4000, 3000, 100)
        data.iloc[:100, data.columns.get_loc("open")] = data.iloc[:100]["close"] * 0.99
        data.iloc[:100, data.columns.get_loc("high")] = data.iloc[:100]["close"] * 1.01
        data.iloc[:100, data.columns.get_loc("low")] = data.iloc[:100]["close"] * 0.98

        strategy = MarketRegimeStrategy()
        signals = strategy.generate_signals(data)
        # 至少应有 1 个信号（从 bear 到 bull 的转换）
        assert len(signals) >= 1

    def test_strategy_registered(self):
        """策略应在注册中心"""
        from stock_datasource.strategies.init import get_strategy_registry

        registry = get_strategy_registry()
        assert registry.validate_strategy_id("market_regime")


# ------------------------------------------------------------------
# StockTimingStrategy Tests
# ------------------------------------------------------------------


class TestStockTiming:
    """个股择时策略"""

    def test_buy_signal_in_bull(self):
        """牛市 + 金叉 + 放量 应产生买入信号"""
        np.random.seed(42)  # 固定随机种子保证可复现
        # 手动构造数据确保金叉处放量足够
        n = 80
        dates = pd.date_range("2024-01-01", periods=n, freq="B")
        prices = np.concatenate(
            [np.linspace(60, 42, 40), np.linspace(43, 72, 40)]
        )
        prices = prices + np.random.normal(0, 0.2, n)

        volumes = np.full(n, 1e7)
        # 金叉在约第50天，确保该天放量3x（远超1.5阈值）
        volumes[49:54] = 3e7

        data = pd.DataFrame(
            {
                "timestamp": dates,
                "open": prices * 0.99,
                "high": prices * 1.02,
                "low": prices * 0.98,
                "close": prices,
                "volume": volumes.astype(float),
                "symbol": "600519.SH",
            }
        )

        regime = RegimeState(regime="bull", position_level=0.6, confidence=0.7)
        strategy = StockTimingStrategy(regime_state=regime)
        signals = strategy.generate_signals(data)

        buy_signals = [s for s in signals if s.action == "buy"]
        assert len(buy_signals) >= 1
        # confidence 应被 regime 调节
        for s in buy_signals:
            assert s.confidence <= 0.6  # 最多 = base × 0.6

    def test_no_buy_in_bear(self):
        """熊市应阻止买入（position_level < min_regime_level）"""
        data = make_stock_data(80, with_crossover=True)
        regime = RegimeState(regime="bear", position_level=0.1, confidence=0.8)
        strategy = StockTimingStrategy(regime_state=regime)
        signals = strategy.generate_signals(data)

        buy_signals = [s for s in signals if s.action == "buy"]
        assert len(buy_signals) == 0

    def test_held_position_triggers_sell(self):
        """已有持仓注入后应能产生卖出信号"""
        # 构造一个持续下跌的数据（从买入价大幅下跌 → 触发止损）
        n = 60
        dates = pd.date_range("2024-01-01", periods=n, freq="B")
        prices = np.linspace(100, 80, n)  # 持续跌 20%

        data = pd.DataFrame(
            {
                "timestamp": dates,
                "open": prices * 1.001,
                "high": prices * 1.005,
                "low": prices * 0.995,
                "close": prices,
                "volume": np.full(n, 1e7),
                "symbol": "000001.SZ",
            }
        )

        # 注入持仓: 在 100 买入的
        regime = RegimeState(regime="bull", position_level=0.6, confidence=0.7)
        strategy = StockTimingStrategy(
            regime_state=regime,
            held_positions={"000001.SZ": 100.0},  # 买入价 100
        )
        signals = strategy.generate_signals(data)

        sell_signals = [s for s in signals if s.action == "sell"]
        # 跌 20% 远超 8% 止损线，应触发卖出
        assert len(sell_signals) >= 1
        # 可能先触发止损或死叉，都是有效的卖出原因
        assert sell_signals[0].action == "sell"

    def test_strategy_registered(self):
        """策略应在注册中心"""
        from stock_datasource.strategies.init import get_strategy_registry

        registry = get_strategy_registry()
        assert registry.validate_strategy_id("stock_timing")

    def test_no_signal_without_crossover(self):
        """无金叉的平稳数据不应产生买入信号"""
        data = make_stock_data(80, with_crossover=False)
        regime = RegimeState(regime="bull", position_level=0.8, confidence=0.9)
        strategy = StockTimingStrategy(regime_state=regime)
        signals = strategy.generate_signals(data)
        buy_signals = [s for s in signals if s.action == "buy"]
        assert len(buy_signals) == 0


# ------------------------------------------------------------------
# DataService Tests (mock-free import check)
# ------------------------------------------------------------------


class TestDataService:
    """DataService 基础测试"""

    def test_import_and_init(self):
        """DataService 应可导入和实例化"""
        from stock_datasource.backtest.engine import DataService

        # 实例化会连 ClickHouse，如果没有连接环境则跳过
        try:
            ds = DataService()
            assert ds is not None
        except Exception:
            pytest.skip("ClickHouse not available")

    def test_index_detection(self):
        """应正确判断指数代码"""
        from stock_datasource.backtest.engine import DataService

        try:
            ds = DataService()
        except Exception:
            pytest.skip("ClickHouse not available")

        assert ds._is_index("000300.SH") is True
        assert ds._is_index("399001.SZ") is True
        assert ds._is_index("000001.SZ") is False  # 平安银行不是指数
        assert ds._is_index("600519.SH") is False  # 贵州茅台不是指数

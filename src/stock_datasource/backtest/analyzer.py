"""
绩效分析器

计算各种绩效和风险指标，包括：
- 收益率指标
- 风险指标
- 风险调整收益指标
- 回撤分析
"""

import logging
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from scipy import stats
from datetime import datetime, timedelta

from .models import (
    PerformanceMetrics, RiskMetrics, Trade, TradeType, 
    TradeStatus, BacktestResult
)

logger = logging.getLogger(__name__)


class PerformanceAnalyzer:
    """绩效分析器"""
    
    def __init__(self, risk_free_rate: float = 0.03):
        """
        初始化绩效分析器
        
        Args:
            risk_free_rate: 无风险利率（年化）
        """
        self.risk_free_rate = risk_free_rate
    
    def analyze(self, 
                equity_curve: pd.Series,
                trades: List[Trade],
                benchmark_returns: Optional[pd.Series] = None,
                trading_days_per_year: int = 252) -> Tuple[PerformanceMetrics, RiskMetrics]:
        """
        执行完整的绩效分析
        
        Args:
            equity_curve: 权益曲线
            trades: 交易记录
            benchmark_returns: 基准收益率序列
            trading_days_per_year: 每年交易日数
            
        Returns:
            绩效指标和风险指标
        """
        try:
            # 计算收益率序列
            returns = self._calculate_returns(equity_curve)
            
            # 计算绩效指标
            performance_metrics = self._calculate_performance_metrics(
                equity_curve, returns, trades, benchmark_returns, trading_days_per_year
            )
            
            # 计算风险指标
            risk_metrics = self._calculate_risk_metrics(
                returns, equity_curve, trading_days_per_year
            )
            
            logger.info("Performance analysis completed successfully")
            return performance_metrics, risk_metrics
            
        except Exception as e:
            logger.error(f"Error in performance analysis: {e}")
            # 返回默认值
            return PerformanceMetrics(), RiskMetrics()
    
    def _calculate_returns(self, equity_curve: pd.Series) -> pd.Series:
        """计算收益率序列"""
        if len(equity_curve) < 2:
            return pd.Series([0.0])
        
        returns = equity_curve.pct_change().fillna(0)
        return returns
    
    def _calculate_performance_metrics(self,
                                     equity_curve: pd.Series,
                                     returns: pd.Series,
                                     trades: List[Trade],
                                     benchmark_returns: Optional[pd.Series],
                                     trading_days_per_year: int) -> PerformanceMetrics:
        """计算绩效指标"""
        metrics = PerformanceMetrics()
        
        if len(equity_curve) < 2:
            return metrics
        
        # 基础收益指标
        initial_value = equity_curve.iloc[0]
        final_value = equity_curve.iloc[-1]
        
        metrics.total_return = (final_value - initial_value) / initial_value
        
        # 年化收益率
        trading_days = len(equity_curve)
        years = trading_days / trading_days_per_year
        if years > 0:
            metrics.annualized_return = (final_value / initial_value) ** (1 / years) - 1
        
        # 波动率
        if len(returns) > 1:
            metrics.volatility = returns.std() * np.sqrt(trading_days_per_year)
        
        # 最大回撤
        drawdown_series = self._calculate_drawdown_series(equity_curve)
        metrics.max_drawdown = abs(drawdown_series.min())
        metrics.max_drawdown_duration = self._calculate_max_drawdown_duration(drawdown_series)
        
        # 风险调整收益
        if metrics.volatility > 0:
            excess_return = metrics.annualized_return - self.risk_free_rate
            metrics.sharpe_ratio = excess_return / metrics.volatility
            
            # 索提诺比率（使用下行标准差）
            downside_returns = returns[returns < 0]
            if len(downside_returns) > 0:
                downside_std = downside_returns.std() * np.sqrt(trading_days_per_year)
                if downside_std > 0:
                    metrics.sortino_ratio = excess_return / downside_std
            
            # 卡玛比率
            if metrics.max_drawdown > 0:
                metrics.calmar_ratio = metrics.annualized_return / metrics.max_drawdown
        
        # 交易统计
        filled_trades = [t for t in trades if t.status == TradeStatus.FILLED]
        metrics.total_trades = len(filled_trades)
        
        if filled_trades:
            # 计算交易盈亏
            trade_pnls = self._calculate_trade_pnls(filled_trades)
            
            winning_trades = [pnl for pnl in trade_pnls if pnl > 0]
            losing_trades = [pnl for pnl in trade_pnls if pnl < 0]
            
            metrics.winning_trades = len(winning_trades)
            metrics.losing_trades = len(losing_trades)
            
            if metrics.total_trades > 0:
                metrics.win_rate = metrics.winning_trades / metrics.total_trades
            
            if winning_trades:
                metrics.avg_win = np.mean(winning_trades)
            
            if losing_trades:
                metrics.avg_loss = abs(np.mean(losing_trades))
            
            # 盈利因子
            total_wins = sum(winning_trades) if winning_trades else 0
            total_losses = abs(sum(losing_trades)) if losing_trades else 0
            
            if total_losses > 0:
                metrics.profit_factor = total_wins / total_losses
        
        # 基准对比
        if benchmark_returns is not None and len(benchmark_returns) > 0:
            # 对齐时间序列
            aligned_returns, aligned_benchmark = self._align_series(returns, benchmark_returns)
            
            if len(aligned_returns) > 1 and len(aligned_benchmark) > 1:
                # 贝塔系数
                covariance = np.cov(aligned_returns, aligned_benchmark)[0, 1]
                benchmark_variance = np.var(aligned_benchmark)
                
                if benchmark_variance > 0:
                    metrics.beta = covariance / benchmark_variance
                
                # 阿尔法系数
                benchmark_annualized = (1 + aligned_benchmark.mean()) ** trading_days_per_year - 1
                expected_return = self.risk_free_rate + metrics.beta * (benchmark_annualized - self.risk_free_rate)
                metrics.alpha = metrics.annualized_return - expected_return
                
                # 超额收益
                metrics.excess_return = metrics.annualized_return - benchmark_annualized
                
                # 信息比率
                excess_returns = aligned_returns - aligned_benchmark
                tracking_error = excess_returns.std() * np.sqrt(trading_days_per_year)
                
                if tracking_error > 0:
                    metrics.information_ratio = metrics.excess_return / tracking_error
        
        return metrics
    
    def _calculate_risk_metrics(self,
                              returns: pd.Series,
                              equity_curve: pd.Series,
                              trading_days_per_year: int) -> RiskMetrics:
        """计算风险指标"""
        metrics = RiskMetrics()
        
        if len(returns) < 2:
            return metrics
        
        # VaR计算
        metrics.var_95 = np.percentile(returns, 5)
        metrics.var_99 = np.percentile(returns, 1)
        
        # CVaR计算
        var_95_threshold = metrics.var_95
        var_99_threshold = metrics.var_99
        
        tail_returns_95 = returns[returns <= var_95_threshold]
        tail_returns_99 = returns[returns <= var_99_threshold]
        
        if len(tail_returns_95) > 0:
            metrics.cvar_95 = tail_returns_95.mean()
        
        if len(tail_returns_99) > 0:
            metrics.cvar_99 = tail_returns_99.mean()
        
        # 分布特征
        metrics.skewness = stats.skew(returns)
        metrics.kurtosis = stats.kurtosis(returns)
        
        # 尾部比率
        positive_returns = returns[returns > 0]
        negative_returns = returns[returns < 0]
        
        if len(positive_returns) > 0 and len(negative_returns) > 0:
            top_percentile = np.percentile(positive_returns, 95)
            bottom_percentile = np.percentile(negative_returns, 5)
            
            if bottom_percentile != 0:
                metrics.tail_ratio = top_percentile / abs(bottom_percentile)
        
        # 上行和下行标准差
        mean_return = returns.mean()
        upside_returns = returns[returns > mean_return] - mean_return
        downside_returns = returns[returns < mean_return] - mean_return
        
        if len(upside_returns) > 0:
            metrics.upside_deviation = upside_returns.std() * np.sqrt(trading_days_per_year)
        
        if len(downside_returns) > 0:
            metrics.downside_deviation = downside_returns.std() * np.sqrt(trading_days_per_year)
        
        # 回撤分析
        drawdown_series = self._calculate_drawdown_series(equity_curve)
        
        if len(drawdown_series) > 0:
            drawdown_periods = drawdown_series[drawdown_series < 0]
            
            if len(drawdown_periods) > 0:
                metrics.avg_drawdown = abs(drawdown_periods.mean())
                metrics.drawdown_frequency = len(drawdown_periods) / len(drawdown_series)
            
            # 恢复因子
            total_return = (equity_curve.iloc[-1] - equity_curve.iloc[0]) / equity_curve.iloc[0]
            max_drawdown = abs(drawdown_series.min())
            
            if max_drawdown > 0:
                metrics.recovery_factor = total_return / max_drawdown
        
        return metrics
    
    def _calculate_drawdown_series(self, equity_curve: pd.Series) -> pd.Series:
        """计算回撤序列"""
        if len(equity_curve) == 0:
            return pd.Series()
        
        # 计算累计最高点
        peak = equity_curve.expanding().max()
        
        # 计算回撤
        drawdown = (equity_curve - peak) / peak
        
        return drawdown
    
    def _calculate_max_drawdown_duration(self, drawdown_series: pd.Series) -> int:
        """计算最大回撤持续期"""
        if len(drawdown_series) == 0:
            return 0
        
        max_duration = 0
        current_duration = 0
        
        for dd in drawdown_series:
            if dd < 0:
                current_duration += 1
                max_duration = max(max_duration, current_duration)
            else:
                current_duration = 0
        
        return max_duration
    
    def _calculate_trade_pnls(self, trades: List[Trade]) -> List[float]:
        """计算每笔交易的盈亏"""
        pnls = []
        positions = {}  # symbol -> (quantity, avg_price)
        
        for trade in trades:
            symbol = trade.symbol
            
            if symbol not in positions:
                positions[symbol] = (0, 0.0)
            
            current_qty, current_avg_price = positions[symbol]
            
            if trade.trade_type == TradeType.BUY:
                # 买入
                new_qty = current_qty + trade.quantity
                if new_qty > 0:
                    new_avg_price = ((current_qty * current_avg_price) + 
                                   (trade.quantity * trade.price)) / new_qty
                else:
                    new_avg_price = trade.price
                
                positions[symbol] = (new_qty, new_avg_price)
                
            elif trade.trade_type == TradeType.SELL:
                # 卖出
                if current_qty >= trade.quantity:
                    # 计算这笔卖出的盈亏
                    cost_basis = trade.quantity * current_avg_price
                    proceeds = trade.quantity * trade.price - trade.commission
                    pnl = proceeds - cost_basis
                    pnls.append(pnl)
                    
                    # 更新持仓
                    new_qty = current_qty - trade.quantity
                    positions[symbol] = (new_qty, current_avg_price)
        
        return pnls
    
    def _align_series(self, series1: pd.Series, series2: pd.Series) -> Tuple[pd.Series, pd.Series]:
        """对齐两个时间序列"""
        if series1.index.equals(series2.index):
            return series1, series2
        
        # 找到共同的时间范围
        common_index = series1.index.intersection(series2.index)
        
        if len(common_index) == 0:
            # 如果没有共同时间点，使用长度较短的序列长度
            min_length = min(len(series1), len(series2))
            return series1.iloc[:min_length], series2.iloc[:min_length]
        
        return series1.loc[common_index], series2.loc[common_index]
    
    def generate_performance_report(self, 
                                  performance_metrics: PerformanceMetrics,
                                  risk_metrics: RiskMetrics) -> str:
        """生成绩效报告"""
        report = f"""
## 策略绩效报告

### 收益指标
- 总收益率: {performance_metrics.total_return:.2%}
- 年化收益率: {performance_metrics.annualized_return:.2%}
- 超额收益率: {performance_metrics.excess_return:.2%}

### 风险指标
- 波动率: {performance_metrics.volatility:.2%}
- 最大回撤: {performance_metrics.max_drawdown:.2%}
- 回撤持续期: {performance_metrics.max_drawdown_duration} 天

### 风险调整收益
- 夏普比率: {performance_metrics.sharpe_ratio:.3f}
- 索提诺比率: {performance_metrics.sortino_ratio:.3f}
- 卡玛比率: {performance_metrics.calmar_ratio:.3f}

### 交易统计
- 总交易次数: {performance_metrics.total_trades}
- 盈利交易: {performance_metrics.winning_trades}
- 亏损交易: {performance_metrics.losing_trades}
- 胜率: {performance_metrics.win_rate:.2%}
- 平均盈利: {performance_metrics.avg_win:.2f}
- 平均亏损: {performance_metrics.avg_loss:.2f}
- 盈利因子: {performance_metrics.profit_factor:.2f}

### 高级风险指标
- VaR (95%): {risk_metrics.var_95:.2%}
- VaR (99%): {risk_metrics.var_99:.2%}
- CVaR (95%): {risk_metrics.cvar_95:.2%}
- CVaR (99%): {risk_metrics.cvar_99:.2%}
- 偏度: {risk_metrics.skewness:.3f}
- 峰度: {risk_metrics.kurtosis:.3f}
        """.strip()
        
        return report
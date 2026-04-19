"""Signal Aggregator core service - 信号聚合与评分核心逻辑.

从3个维度采集信号:
1. 消息面: NewsService 的情绪分析
2. 资金面: TopListAnalysisService 的机构/游资/北向分析
3. 技术面: SignalGenerator 的MA交叉信号

聚合为统一的 StockObservationScore 并持久化到 ClickHouse.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any

import pandas as pd

from stock_datasource.models.database import db_client

from .schemas import (
    CapitalFlowSignalInput,
    DimensionScore,
    NewsSignalInput,
    SignalAggregationResponse,
    SignalSnapshot,
    SignalTimelineResponse,
    SignalWeightsConfig,
    StockObservationScore,
    StockSignalSummary,
    TechSignalInput,
)
from .scoring import SignalScoringService

logger = logging.getLogger(__name__)


class SignalAggregator:
    """信号聚合引擎.

    使用方式:
        aggregator = SignalAggregator()
        result = await aggregator.aggregate_for_stocks(["600519.SH", "000858.SZ"])
    """

    def __init__(self, weights: SignalWeightsConfig | None = None):
        self._scoring = SignalScoringService(weights)
        self._db = db_client

    # ------------------------------------------------------------------
    # 主入口: 批量聚合
    # ------------------------------------------------------------------

    async def aggregate_for_stocks(
        self,
        ts_codes: list[str],
        signal_date: str | None = None,
    ) -> SignalAggregationResponse:
        """为多只股票生成信号聚合评分.

        Args:
            ts_codes: 股票代码列表
            signal_date: 信号日期, 默认今天

        Returns:
            SignalAggregationResponse 包含所有股票的评分
        """
        signal_date = signal_date or datetime.now().strftime("%Y%m%d")
        summaries: list[StockSignalSummary] = []
        stock_names = self._load_stock_names()

        for ts_code in ts_codes:
            try:
                summary = await self._aggregate_single(ts_code, signal_date, stock_names)
                summaries.append(summary)
            except Exception as e:
                logger.warning("Signal aggregation failed for %s: %s", ts_code, e)

        # 按综合评分排序
        summaries.sort(key=lambda s: s.composite_score, reverse=True)

        return SignalAggregationResponse(
            stocks=summaries,
            trade_date=signal_date,
            total_count=len(summaries),
        )

    async def aggregate_for_stock(
        self,
        ts_code: str,
        signal_date: str | None = None,
    ) -> StockObservationScore | None:
        """为单只股票生成信号聚合评分."""
        signal_date = signal_date or datetime.now().strftime("%Y%m%d")
        stock_names = self._load_stock_names()
        try:
            summary = await self._aggregate_single(ts_code, signal_date, stock_names)
            return StockObservationScore(
                ts_code=ts_code,
                stock_name=summary.stock_name,
                signal_date=signal_date,
                news_score=DimensionScore(
                    score=summary.news_score,
                    direction="bullish" if summary.news_score > 60 else ("bearish" if summary.news_score < 40 else "neutral"),
                    detail=summary.news_detail,
                ),
                capital_score=DimensionScore(
                    score=summary.capital_score,
                    direction="bullish" if summary.capital_score > 60 else ("bearish" if summary.capital_score < 40 else "neutral"),
                    detail=summary.capital_detail,
                ),
                tech_score=DimensionScore(
                    score=summary.tech_score,
                    direction="bullish" if summary.tech_score > 60 else ("bearish" if summary.tech_score < 40 else "neutral"),
                    detail=summary.tech_detail,
                ),
                composite_score=summary.composite_score,
                composite_direction=summary.composite_direction,
            )
        except Exception as e:
            logger.error("Signal aggregation failed for %s: %s", ts_code, e)
            return None

    # ------------------------------------------------------------------
    # 时序追踪
    # ------------------------------------------------------------------

    async def get_signal_timeline(
        self,
        ts_code: str,
        days: int = 30,
    ) -> SignalTimelineResponse:
        """获取某股票的信号时序数据."""
        stock_names = self._load_stock_names()
        snapshots = self._load_snapshots_from_clickhouse(ts_code, days)

        return SignalTimelineResponse(
            ts_code=ts_code,
            stock_name=stock_names.get(ts_code, ""),
            snapshots=snapshots,
        )

    # ------------------------------------------------------------------
    # 信号快照持久化
    # ------------------------------------------------------------------

    def save_snapshot(self, score: StockObservationScore) -> None:
        """将评分结果持久化到ClickHouse."""
        try:
            snapshot = SignalSnapshot(
                ts_code=score.ts_code,
                signal_date=score.signal_date,
                news_score=score.news_score.score,
                capital_score=score.capital_score.score,
                tech_score=score.tech_score.score,
                composite_score=score.composite_score,
                news_detail=score.news_score.detail,
                capital_detail=score.capital_score.detail,
            )
            self._insert_snapshot(snapshot)
        except Exception as e:
            logger.warning("Failed to save signal snapshot for %s: %s", score.ts_code, e)

    def _insert_snapshot(self, snapshot: SignalSnapshot) -> None:
        """Insert snapshot to ClickHouse."""
        try:
            row = {
                "ts_code": snapshot.ts_code,
                "signal_date": snapshot.signal_date,
                "news_score": snapshot.news_score,
                "capital_score": snapshot.capital_score,
                "tech_score": snapshot.tech_score,
                "composite_score": snapshot.composite_score,
                "news_detail": json.dumps(snapshot.news_detail, ensure_ascii=False, default=str),
                "capital_detail": json.dumps(snapshot.capital_detail, ensure_ascii=False, default=str),
                "created_at": snapshot.created_at,
            }
            df = pd.DataFrame([row])
            self._db.insert_dataframe("obs_stock_signal_snapshot", df)
            logger.info("Saved signal snapshot for %s on %s", snapshot.ts_code, snapshot.signal_date)
        except Exception as e:
            logger.warning("ClickHouse insert failed for obs_stock_signal_snapshot: %s", e)

    # ------------------------------------------------------------------
    # 内部: 单股聚合
    # ------------------------------------------------------------------

    async def _aggregate_single(
        self,
        ts_code: str,
        signal_date: str,
        stock_names: dict[str, str],
    ) -> StockSignalSummary:
        """为单只股票聚合3个维度的信号."""
        # 1. 消息面信号
        news_input = await self._collect_news_signal(ts_code)
        news_score = self._scoring.score_news(news_input)

        # 2. 资金面信号
        capital_input = await self._collect_capital_signal(ts_code)
        capital_score = self._scoring.score_capital(capital_input)

        # 3. 技术面信号
        tech_input = await self._collect_tech_signal(ts_code)
        tech_score = self._scoring.score_tech(tech_input)

        # 4. 综合评分
        composite_score, composite_direction = self._scoring.compute_composite(
            news_score, capital_score, tech_score
        )

        summary = StockSignalSummary(
            ts_code=ts_code,
            stock_name=stock_names.get(ts_code, ""),
            composite_score=composite_score,
            composite_direction=composite_direction,
            news_score=news_score.score,
            capital_score=capital_score.score,
            tech_score=tech_score.score,
            news_detail=news_score.detail,
            capital_detail=capital_score.detail,
            tech_detail=tech_score.detail,
            signal_date=signal_date,
        )

        # 5. 持久化
        observation = StockObservationScore(
            ts_code=ts_code,
            stock_name=stock_names.get(ts_code, ""),
            signal_date=signal_date,
            news_score=news_score,
            capital_score=capital_score,
            tech_score=tech_score,
            composite_score=composite_score,
            composite_direction=composite_direction,
        )
        self.save_snapshot(observation)

        return summary

    # ------------------------------------------------------------------
    # 数据采集
    # ------------------------------------------------------------------

    async def _collect_news_signal(self, ts_code: str) -> NewsSignalInput:
        """采集消息面信号."""
        try:
            from stock_datasource.modules.news.service import get_news_service

            service = get_news_service()
            news_items = await service.get_news_by_stock(ts_code, days=7, limit=20)

            if not news_items:
                return NewsSignalInput(ts_code=ts_code)

            # 分析情绪
            sentiments = await service.analyze_news_sentiment(
                news_items, f"股票代码: {ts_code}"
            )

            positive = sum(1 for s in sentiments if s.sentiment == "positive")
            negative = sum(1 for s in sentiments if s.sentiment == "negative")
            neutral = sum(1 for s in sentiments if s.sentiment == "neutral")
            avg_score = sum(s.score for s in sentiments) / len(sentiments) if sentiments else 0
            high_impact = sum(1 for s in sentiments if s.impact_level == "high")

            top_headlines = [
                s.title for s in sentiments if s.impact_level in ("high", "medium")
            ][:3]

            return NewsSignalInput(
                ts_code=ts_code,
                positive_count=positive,
                negative_count=negative,
                neutral_count=neutral,
                average_score=round(avg_score, 2),
                high_impact_count=high_impact,
                top_headlines=top_headlines,
            )
        except Exception as e:
            logger.warning("News signal collection failed for %s: %s", ts_code, e)
            return NewsSignalInput(ts_code=ts_code)

    async def _collect_capital_signal(self, ts_code: str) -> CapitalFlowSignalInput:
        """采集资金面信号."""
        try:
            from stock_datasource.services.toplist_analysis_service import TopListAnalysisService

            service = TopListAnalysisService()

            # 席位集中度
            concentration = await service.calculate_seat_concentration(ts_code, days=10)
            hhi = concentration.get("hhi", 0.0) if isinstance(concentration, dict) else 0.0

            # 机构净流入
            net_inst_flow = self._query_institutional_net_flow(ts_code)

            # 游资
            hot_money_count = self._query_hot_money_count(ts_code)

            # 北向资金
            northbound_flow = self._query_northbound_flow(ts_code)

            return CapitalFlowSignalInput(
                ts_code=ts_code,
                net_institutional_flow=net_inst_flow,
                hot_money_count=hot_money_count,
                seat_hhi=float(hhi) if hhi else 0.0,
                northbound_net_flow=northbound_flow,
            )
        except Exception as e:
            logger.warning("Capital signal collection failed for %s: %s", ts_code, e)
            return CapitalFlowSignalInput(ts_code=ts_code)

    async def _collect_tech_signal(self, ts_code: str) -> TechSignalInput:
        """采集技术面信号."""
        try:
            from stock_datasource.modules.quant.signal_generator import get_signal_generator

            generator = get_signal_generator()
            result = await generator.generate_signals([ts_code])

            if result.signals:
                # 取最新信号(置信度最高的)
                best = max(result.signals, key=lambda s: s.confidence)
                return TechSignalInput(
                    ts_code=ts_code,
                    signal_type=best.signal_type,
                    confidence=best.confidence,
                    target_position=best.target_position,
                    reason=best.reason,
                    ma_short=best.ma25,
                    ma_long=best.ma120,
                )

            # 无信号则返回hold
            return TechSignalInput(ts_code=ts_code, signal_type="hold", confidence=0.0)
        except Exception as e:
            logger.warning("Tech signal collection failed for %s: %s", ts_code, e)
            return TechSignalInput(ts_code=ts_code, signal_type="hold", confidence=0.0)

    # ------------------------------------------------------------------
    # ClickHouse 直接查询
    # ------------------------------------------------------------------

    def _query_institutional_net_flow(self, ts_code: str) -> float:
        """查询机构净流入."""
        try:
            df = self._db.execute_query(f"""
                SELECT sum(net_buy) as total_net
                FROM ods_top_inst
                WHERE ts_code = '{ts_code}'
                AND trade_date >= toString(subtractDays(today(), 10))
            """)
            if not df.empty and df.iloc[0]["total_net"] is not None:
                return float(df.iloc[0]["total_net"])
        except Exception as e:
            logger.debug("Institutional flow query failed: %s", e)
        return 0.0

    def _query_hot_money_count(self, ts_code: str) -> int:
        """查询游资参与席位数量."""
        try:
            df = self._db.execute_query(f"""
                SELECT count(DISTINCT exalter) as seat_count
                FROM ods_top_list
                WHERE ts_code = '{ts_code}'
                AND trade_date >= toString(subtractDays(today(), 10))
                AND exalter NOT LIKE '%机构%'
                AND exalter NOT LIKE '%证券%'
            """)
            if not df.empty and df.iloc[0]["seat_count"] is not None:
                return int(df.iloc[0]["seat_count"])
        except Exception as e:
            logger.debug("Hot money count query failed: %s", e)
        return 0

    def _query_northbound_flow(self, ts_code: str) -> float:
        """查询北向资金净流入."""
        try:
            df = self._db.execute_query(f"""
                SELECT sum(vol) as total_vol
                FROM ods_hsgt_top10
                WHERE ts_code = '{ts_code}'
                AND trade_date >= toString(subtractDays(today(), 10))
            """)
            if not df.empty and df.iloc[0]["total_vol"] is not None:
                return float(df.iloc[0]["total_vol"])
        except Exception as e:
            logger.debug("Northbound flow query failed: %s", e)
        return 0.0

    def _load_snapshots_from_clickhouse(
        self, ts_code: str, days: int
    ) -> list[SignalSnapshot]:
        """从ClickHouse加载时序快照."""
        try:
            df = self._db.execute_query(f"""
                SELECT ts_code, signal_date, news_score, capital_score,
                       tech_score, composite_score, news_detail, capital_detail, created_at
                FROM obs_stock_signal_snapshot
                WHERE ts_code = '{ts_code}'
                AND signal_date >= toString(subtractDays(today(), {days}))
                ORDER BY signal_date ASC
            """)
            if df.empty:
                return []

            snapshots = []
            for _, row in df.iterrows():
                news_detail = {}
                capital_detail = {}
                try:
                    if row.get("news_detail"):
                        news_detail = json.loads(row["news_detail"]) if isinstance(row["news_detail"], str) else row["news_detail"]
                    if row.get("capital_detail"):
                        capital_detail = json.loads(row["capital_detail"]) if isinstance(row["capital_detail"], str) else row["capital_detail"]
                except (json.JSONDecodeError, TypeError):
                    pass

                snapshots.append(
                    SignalSnapshot(
                        ts_code=row["ts_code"],
                        signal_date=str(row["signal_date"]),
                        news_score=float(row.get("news_score", 50)),
                        capital_score=float(row.get("capital_score", 50)),
                        tech_score=float(row.get("tech_score", 50)),
                        composite_score=float(row.get("composite_score", 50)),
                        news_detail=news_detail,
                        capital_detail=capital_detail,
                        created_at=str(row.get("created_at", "")),
                    )
                )
            return snapshots
        except Exception as e:
            logger.warning("Snapshot query failed for %s: %s", ts_code, e)
            return []

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    def _load_stock_names(self) -> dict[str, str]:
        """加载股票名称映射."""
        try:
            df = self._db.execute_query("SELECT ts_code, name FROM dim_stock_basic")
            return dict(zip(df["ts_code"], df["name"]))
        except Exception:
            return {}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_aggregator: SignalAggregator | None = None


def get_signal_aggregator(weights: SignalWeightsConfig | None = None) -> SignalAggregator:
    """Get or create the global SignalAggregator instance."""
    global _aggregator
    if _aggregator is None:
        _aggregator = SignalAggregator(weights)
    return _aggregator

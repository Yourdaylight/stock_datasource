"""Signal scoring service - 各维度评分权重和归一化逻辑."""

from __future__ import annotations

import logging

from .schemas import (
    CapitalFlowSignalInput,
    DimensionScore,
    NewsSignalInput,
    SignalWeightsConfig,
    TechSignalInput,
)

logger = logging.getLogger(__name__)


class SignalScoringService:
    """各维度评分计算与归一化.

    评分体系:
    - 消息面 0-100: 基于sentiment score加权 × impact_level权重, 归一化
    - 资金面 0-100: net_flow方向 × 集中度 × 机构占比, 归一化
    - 技术面 0-100: 复用SignalGenerator的confidence和target_position
    - 综合: 消息面30% + 资金面40% + 技术面30% (权重可配置)
    """

    def __init__(self, weights: SignalWeightsConfig | None = None):
        self._weights = weights or SignalWeightsConfig()

    def score_news(self, signal: NewsSignalInput) -> DimensionScore:
        """计算消息面评分.

        算法:
        - positive_count × 1 + negative_count × (-1) + neutral_count × 0 = raw_sum
        - impact加权: high_impact_count 额外加成
        - average_score作为调节因子
        - 归一化到 0-100
        """
        total = signal.positive_count + signal.negative_count + signal.neutral_count
        if total == 0:
            return DimensionScore(score=50.0, direction="neutral", detail={"reason": "无新闻数据"})

        # 基础情绪分: 加权计数
        raw_sentiment = (signal.positive_count - signal.negative_count) / total
        # 混合 average_score (LLM分析结果更可靠, 权重0.6)
        blended = raw_sentiment * 0.4 + signal.average_score * 0.6

        # 重大影响加成
        high_impact_bonus = min(signal.high_impact_count * 3, 15)  # 最多+15
        if blended > 0:
            high_impact_bonus_adj = high_impact_bonus
        elif blended < 0:
            high_impact_bonus_adj = -high_impact_bonus  # 利空放大
        else:
            high_impact_bonus_adj = 0

        # 归一化: blended范围 [-1, 1] → [0, 100]
        score = 50 + blended * 40 + high_impact_bonus_adj
        score = max(0.0, min(100.0, score))

        direction = "bullish" if score > 60 else ("bearish" if score < 40 else "neutral")

        return DimensionScore(
            score=round(score, 1),
            direction=direction,
            detail={
                "positive_count": signal.positive_count,
                "negative_count": signal.negative_count,
                "neutral_count": signal.neutral_count,
                "average_score": signal.average_score,
                "high_impact_count": signal.high_impact_count,
                "top_headlines": signal.top_headlines[:3],
            },
        )

    def score_capital(self, signal: CapitalFlowSignalInput) -> DimensionScore:
        """计算资金面评分.

        算法:
        - 机构净流入方向和幅度
        - 游资活跃度
        - 席位集中度(HHI)
        - 北向资金方向
        - 归一化到 0-100
        """
        score = 50.0

        # 1. 机构净流入贡献 (±25)
        inst_flow_magnitude = abs(signal.net_institutional_flow)
        inst_direction = 1 if signal.net_institutional_flow > 0 else -1
        # 用log归一化，1亿=2亿=基准
        if inst_flow_magnitude > 0:
            import math
            inst_score = min(math.log10(inst_flow_magnitude / 1e8 + 1) * 10, 25)
            score += inst_direction * inst_score

        # 2. 游资活跃度 (±10)
        if signal.hot_money_count > 0:
            hm_bonus = min(signal.hot_money_count * 2, 10)
            # 游资参与看涨概率更高
            score += hm_bonus

        # 3. 席位集中度 (0~10)
        # HHI高=集中=信号更强(看涨或看跌)
        if signal.seat_hhi > 0:
            hhi_magnitude = signal.seat_hhi * 10
            # 结合机构方向判断
            score += inst_direction * hhi_magnitude

        # 4. 北向资金 (±10)
        if signal.northbound_net_flow != 0:
            nb_direction = 1 if signal.northbound_net_flow > 0 else -1
            nb_magnitude = min(abs(signal.northbound_net_flow) / 1e8 * 2, 10)
            score += nb_direction * nb_magnitude

        # 5. 板块排名
        if signal.sector_flow_rank is not None and signal.sector_flow_rank > 0:
            rank_bonus = max(0, (20 - signal.sector_flow_rank)) / 20 * 5
            score += rank_bonus

        score = max(0.0, min(100.0, score))
        direction = "bullish" if score > 60 else ("bearish" if score < 40 else "neutral")

        return DimensionScore(
            score=round(score, 1),
            direction=direction,
            detail={
                "net_institutional_flow": signal.net_institutional_flow,
                "hot_money_count": signal.hot_money_count,
                "seat_hhi": signal.seat_hhi,
                "northbound_net_flow": signal.northbound_net_flow,
                "sector_flow_rank": signal.sector_flow_rank,
            },
        )

    def score_tech(self, signal: TechSignalInput) -> DimensionScore:
        """计算技术面评分.

        直接复用SignalGenerator的confidence和target_position.
        """
        if signal.signal_type == "hold" and signal.confidence == 0:
            return DimensionScore(score=50.0, direction="neutral", detail={"reason": "无技术信号"})

        # 信号类型映射
        type_score_map = {
            "buy": 75.0,
            "sell": 25.0,
            "reduce": 35.0,
            "hold": 50.0,
        }
        base_score = type_score_map.get(signal.signal_type, 50.0)

        # confidence调节: 偏离50的程度 × confidence
        deviation = base_score - 50.0
        adjusted_score = 50.0 + deviation * signal.confidence

        # target_position微调
        if signal.signal_type == "buy":
            adjusted_score += (signal.target_position - 0.33) * 10
        elif signal.signal_type in ("sell", "reduce"):
            adjusted_score -= signal.target_position * 5

        adjusted_score = max(0.0, min(100.0, adjusted_score))
        direction = "bullish" if adjusted_score > 60 else ("bearish" if adjusted_score < 40 else "neutral")

        return DimensionScore(
            score=round(adjusted_score, 1),
            direction=direction,
            detail={
                "signal_type": signal.signal_type,
                "confidence": signal.confidence,
                "target_position": signal.target_position,
                "reason": signal.reason,
                "ma_short": signal.ma_short,
                "ma_long": signal.ma_long,
            },
        )

    def compute_composite(
        self,
        news_score: DimensionScore,
        capital_score: DimensionScore,
        tech_score: DimensionScore,
    ) -> tuple[float, str]:
        """计算综合评分.

        Returns:
            (composite_score, composite_direction)
        """
        w_news, w_capital, w_tech = self._weights.normalized()

        composite = (
            news_score.score * w_news
            + capital_score.score * w_capital
            + tech_score.score * w_tech
        )
        composite = round(max(0.0, min(100.0, composite)), 1)

        direction = "bullish" if composite > 60 else ("bearish" if composite < 40 else "neutral")
        return composite, direction

"""Investment Director (Tier 3) — LLM-driven top-level decision maker.

Subscribes to all analyst reports.
Feeds all reports to LLM to produce a comprehensive InvestmentDecision.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections import deque
from datetime import datetime
from typing import Any

from ..schemas import (
    ActionType,
    AnalystReport,
    InvestmentDecision,
    MarketRegime,
    SectorAllocation,
    StockAction,
)
from ..config import get_sentinel_config
from .message_bus import get_message_bus

logger = logging.getLogger(__name__)

DECISION_SYSTEM_PROMPT = """你是一位资深的投资总监，负责根据分析师团队的研判报告做出最终投资决策。

你需要综合考虑以下四个维度：
1. 市场环境（宏观风险、指数趋势）
2. 板块轮动（资金流向、板块强弱）
3. 个股质量（技术信号、基本面、多维度确认）
4. 入场时机（量价配合、资金确认、市场环境约束）

决策原则：
- 市场风险优先：熊市/转折期必须降低仓位
- 板块共振优先：优先选择有板块支撑的个股
- 多信号确认：单一信号不足以形成买入决策，需要多维度确认
- 严格止损：每个买入候选必须有明确的止损位
- 分批建仓：不建议单次满仓，推荐1/3分批

请以严格的JSON格式输出你的投资决策。"""

DECISION_USER_PROMPT_TEMPLATE = """今日日期: {trade_date}

## 分析师报告

{analyst_reports_text}

## 请输出投资决策

请以如下JSON格式输出（不要包含markdown代码块标记）：

{{
    "market_regime": "bull/bear/consolidation/transition_up/transition_down",
    "market_risk_level": "normal/warning/danger",
    "suggested_total_position": 0.0到1.0之间的数字,
    "favored_sectors": [
        {{"sector_name": "板块名", "reason": "原因", "weight_suggestion": 0.2, "momentum": "accelerating/stable/decelerating"}}
    ],
    "avoided_sectors": ["板块名"],
    "buy_candidates": [
        {{"ts_code": "代码", "stock_name": "名称", "action": "buy", "urgency": "immediate/normal/opportunistic", "position_size": 0.1, "entry_price": 价格, "stop_loss": 止损价, "target_price": 目标价, "reasons": ["原因1", "原因2"], "confidence": 0.8, "sector": "所属板块"}}
    ],
    "sell_candidates": [
        {{"ts_code": "代码", "stock_name": "名称", "action": "sell", "urgency": "immediate/normal", "reasons": ["原因"], "confidence": 0.8}}
    ],
    "watch_list": [
        {{"ts_code": "代码", "stock_name": "名称", "action": "watch", "reasons": ["原因"], "confidence": 0.5}}
    ],
    "market_narrative": "一段话总结当前市场环境判断",
    "sector_narrative": "一段话总结板块方向",
    "stock_narrative": "一段话总结个股选择逻辑",
    "timing_narrative": "一段话总结当前的入场时机判断",
    "confidence": 0.0到1.0之间的整体信心度
}}"""


class InvestmentDirector:
    """LLM-driven investment decision maker."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._report_buffer: deque[AnalystReport] = deque(maxlen=50)
        self._last_decision: InvestmentDecision | None = None
        self._decision_count: int = 0
        self._sentinel_config = get_sentinel_config()

    async def initialize(self) -> None:
        """Subscribe to all analyst report channels."""
        bus = get_message_bus()
        bus.subscribe("analyst:*", self._on_analyst_report)
        logger.info("InvestmentDirector initialized, subscribed to analyst:*")

    async def _on_analyst_report(self, channel: str, data: str) -> None:
        """Handle incoming analyst report."""
        try:
            report = AnalystReport.model_validate_json(data)
            self._report_buffer.append(report)
            logger.info(
                "Director received report from %s (conviction=%.2f)",
                report.analyst_type,
                report.overall_conviction,
            )
        except Exception as e:
            logger.error("Director failed to parse report: %s", e)

    async def produce_decision(self, trade_date: str = "") -> InvestmentDecision | None:
        """Produce an investment decision using LLM.

        Called at the end of a scan cycle when analyst reports are available.
        """
        reports = list(self._report_buffer)
        if not reports:
            logger.info("Director: no analyst reports, skipping decision")
            return None

        trade_date = trade_date or datetime.now().strftime("%Y%m%d")

        try:
            # Build LLM prompt
            prompt = self._build_decision_prompt(reports, trade_date)

            # Call LLM
            response = await self._call_llm(prompt)

            # Parse response into InvestmentDecision
            decision = self._parse_llm_response(response, trade_date, reports)

            if decision:
                self._last_decision = decision
                self._decision_count += 1
                self._report_buffer.clear()

                logger.info(
                    "Decision produced: regime=%s, buys=%d, sells=%d, confidence=%.2f",
                    decision.market_regime.value,
                    len(decision.buy_candidates),
                    len(decision.sell_candidates),
                    decision.confidence,
                )

            return decision

        except Exception as e:
            logger.error("Director decision generation failed: %s", e, exc_info=True)
            return None

    def _build_decision_prompt(self, reports: list[AnalystReport], trade_date: str) -> str:
        """Build the LLM prompt from analyst reports."""
        reports_text_parts = []
        for i, report in enumerate(reports, 1):
            part = f"### 分析师 {i}: {report.analyst_type}\n"
            part += f"- 置信度: {report.overall_conviction:.2f}\n"
            part += f"- 触发信号数: {report.trigger_count}\n"

            if report.market_regime:
                part += f"- 市场判断: {report.market_regime.value}\n"

            if report.sector_view:
                part += f"- 板块观点: {json.dumps(report.sector_view, ensure_ascii=False)}\n"

            if report.stock_signals:
                part += "- 个股信号:\n"
                for sig in report.stock_signals[:10]:
                    part += f"  - {sig.stock_name}({sig.ts_code}): {sig.action.value} "
                    part += f"(置信度{sig.confidence:.2f}) {', '.join(sig.reasons[:2])}\n"

            if report.insights:
                part += "- 洞察:\n"
                for insight in report.insights[:5]:
                    part += f"  - [{insight.insight_type}] {insight.description}\n"

            reports_text_parts.append(part)

        analyst_reports_text = "\n".join(reports_text_parts)

        return DECISION_USER_PROMPT_TEMPLATE.format(
            trade_date=trade_date,
            analyst_reports_text=analyst_reports_text,
        )

    async def _call_llm(self, prompt: str) -> str:
        """Call LLM using existing llm.client infrastructure."""
        try:
            from stock_datasource.llm.client import get_llm_client

            client = get_llm_client()
            response = await client.generate(
                prompt=prompt,
                system_prompt=DECISION_SYSTEM_PROMPT,
                temperature=self._sentinel_config.llm_temperature,
            )
            return response
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            raise

    def _parse_llm_response(
        self, response: str, trade_date: str, reports: list[AnalystReport]
    ) -> InvestmentDecision | None:
        """Parse LLM JSON response into InvestmentDecision."""
        try:
            # Clean response - strip markdown code blocks if present
            cleaned = response.strip()
            if cleaned.startswith("```"):
                # Remove first and last lines (```json and ```)
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:-1])

            data = json.loads(cleaned)

            # Build decision from parsed data
            decision = InvestmentDecision(
                decision_id=str(uuid.uuid4())[:12],
                trade_date=trade_date,
                market_regime=MarketRegime(data.get("market_regime", "consolidation")),
                market_risk_level=data.get("market_risk_level", "normal"),
                suggested_total_position=float(data.get("suggested_total_position", 0.6)),
                market_narrative=data.get("market_narrative", ""),
                sector_narrative=data.get("sector_narrative", ""),
                stock_narrative=data.get("stock_narrative", ""),
                timing_narrative=data.get("timing_narrative", ""),
                confidence=float(data.get("confidence", 0.5)),
                source_reports=[r.report_id for r in reports],
            )

            # Parse sectors
            for s in data.get("favored_sectors", []):
                decision.favored_sectors.append(SectorAllocation(
                    sector_name=s.get("sector_name", ""),
                    reason=s.get("reason", ""),
                    weight_suggestion=float(s.get("weight_suggestion", 0)),
                    momentum=s.get("momentum", "neutral"),
                ))
            decision.avoided_sectors = data.get("avoided_sectors", [])

            # Parse stock actions
            for item in data.get("buy_candidates", []):
                decision.buy_candidates.append(StockAction(
                    ts_code=item.get("ts_code", ""),
                    stock_name=item.get("stock_name", ""),
                    action=ActionType.BUY,
                    urgency=item.get("urgency", "normal"),
                    position_size=float(item.get("position_size", 0)),
                    entry_price=item.get("entry_price"),
                    stop_loss=item.get("stop_loss"),
                    target_price=item.get("target_price"),
                    reasons=item.get("reasons", []),
                    confidence=float(item.get("confidence", 0)),
                    sector=item.get("sector", ""),
                ))

            for item in data.get("sell_candidates", []):
                decision.sell_candidates.append(StockAction(
                    ts_code=item.get("ts_code", ""),
                    stock_name=item.get("stock_name", ""),
                    action=ActionType.SELL,
                    urgency=item.get("urgency", "normal"),
                    reasons=item.get("reasons", []),
                    confidence=float(item.get("confidence", 0)),
                ))

            for item in data.get("watch_list", []):
                decision.watch_list.append(StockAction(
                    ts_code=item.get("ts_code", ""),
                    stock_name=item.get("stock_name", ""),
                    action=ActionType.WATCH,
                    reasons=item.get("reasons", []),
                    confidence=float(item.get("confidence", 0)),
                ))

            return decision

        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response as JSON: %s\nResponse: %s", e, response[:500])
            return None
        except Exception as e:
            logger.error("Failed to build decision from LLM response: %s", e)
            return None

    def get_status(self) -> dict[str, Any]:
        return {
            "buffer_size": len(self._report_buffer),
            "decision_count": self._decision_count,
            "last_decision_id": self._last_decision.decision_id if self._last_decision else None,
        }

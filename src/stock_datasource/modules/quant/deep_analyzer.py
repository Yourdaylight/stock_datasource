"""Deep analysis engine - technical indicators + NLP analysis.

Technical analysis: reuses market/indicators.py, reads from ClickHouse only.
NLP analysis: calls LLM for management discussion analysis.
"""

import json
import logging
import time
from datetime import datetime
from typing import Optional

import pandas as pd

from stock_datasource.models.database import db_client

from .data_readiness import get_data_readiness_checker
from .schemas import (
    AiAnalysisCard,
    BatchAnalysisStatus,
    DeepAnalysisResult,
    TechSnapshot,
)

logger = logging.getLogger(__name__)


class DeepAnalyzer:
    """Deep analysis engine for pool stocks.

    - Technical: MA/MACD/RSI from local data
    - NLP: Management discussion analysis via LLM
    """

    def __init__(self):
        self.readiness_checker = get_data_readiness_checker()

    async def analyze_technical(self, ts_code: str) -> Optional[TechSnapshot]:
        """Technical analysis for a stock. Reads from ClickHouse only."""
        try:
            df = db_client.execute_query(
                f"""SELECT trade_date, close, vol, amount, pct_chg
                FROM fact_daily_bar
                WHERE ts_code = '{ts_code}'
                AND trade_date >= toString(subtractDays(today(), 400))
                ORDER BY trade_date ASC"""
            )

            if df.empty or len(df) < 30:
                return None

            close = pd.to_numeric(df["close"], errors="coerce")
            vol = pd.to_numeric(df["vol"], errors="coerce") if "vol" in df else pd.Series()

            # Calculate MAs
            ma25 = close.rolling(25).mean().iloc[-1] if len(close) >= 25 else None
            ma120 = close.rolling(120).mean().iloc[-1] if len(close) >= 120 else None
            ma250 = close.rolling(250).mean().iloc[-1] if len(close) >= 250 else None

            # MACD (12, 26, 9)
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd_hist = macd_line - signal_line

            # RSI 14
            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss.replace(0, float("nan"))
            rsi = 100 - (100 / (1 + rs))

            # Volume ratio
            volume_ratio = None
            if len(vol) >= 6 and vol.iloc[-6:-1].mean() > 0:
                volume_ratio = round(vol.iloc[-1] / vol.iloc[-6:-1].mean(), 2)

            latest_close = float(close.iloc[-1])
            pct_chg = float(df["pct_chg"].iloc[-1]) if "pct_chg" in df else 0

            # MA position
            ma_pos = "unknown"
            if ma25 and ma120:
                if latest_close > ma25 > ma120:
                    ma_pos = "above_all"
                elif latest_close < ma120 < ma25:
                    ma_pos = "below_all"
                else:
                    ma_pos = "between"

            stock_name = self._get_stock_name(ts_code)

            return TechSnapshot(
                ts_code=ts_code,
                stock_name=stock_name,
                ma25=round(ma25, 2) if ma25 and not pd.isna(ma25) else None,
                ma120=round(ma120, 2) if ma120 and not pd.isna(ma120) else None,
                ma250=round(ma250, 2) if ma250 and not pd.isna(ma250) else None,
                macd=round(float(macd_line.iloc[-1]), 4) if not pd.isna(macd_line.iloc[-1]) else None,
                macd_signal=round(float(signal_line.iloc[-1]), 4) if not pd.isna(signal_line.iloc[-1]) else None,
                macd_hist=round(float(macd_hist.iloc[-1]), 4) if not pd.isna(macd_hist.iloc[-1]) else None,
                rsi_14=round(float(rsi.iloc[-1]), 2) if not pd.isna(rsi.iloc[-1]) else None,
                volume_ratio=volume_ratio,
                close=latest_close,
                pct_chg=round(pct_chg, 2),
                ma_position=ma_pos,
            )

        except Exception as e:
            logger.error(f"Technical analysis failed for {ts_code}: {e}")
            return None

    async def analyze_mgmt_discussion(self, ts_code: str) -> Optional[AiAnalysisCard]:
        """NLP analysis of management discussion (via LLM).

        This is the one component that calls LLM (not TuShare).
        """
        try:
            # Try to get the latest report text from ClickHouse
            stock_name = self._get_stock_name(ts_code)

            # Check if LLM service is available
            try:
                from stock_datasource.services.llm_service import get_llm_service
                llm = get_llm_service()
            except Exception:
                return AiAnalysisCard(
                    ts_code=ts_code,
                    stock_name=stock_name,
                    ai_summary="LLM服务不可用，跳过管理层讨论分析",
                )

            prompt = f"""分析股票 {ts_code} ({stock_name}) 的投资价值：
请从以下维度分析，返回JSON格式:
1. credibility_score (0-100): 公司信息披露的可信度评分
2. optimism_score (0-100): 前景乐观度评分
3. key_findings: 3-5条关键发现
4. risk_factors: 2-3条风险因素
5. verification_points: 2-3条未来可验证的关键点
6. ai_summary: 100字以内的总结"""

            response = await llm.chat(prompt)

            # Parse response
            try:
                data = json.loads(response) if isinstance(response, str) else response
            except (json.JSONDecodeError, TypeError):
                data = {}

            return AiAnalysisCard(
                ts_code=ts_code,
                stock_name=stock_name,
                credibility_score=data.get("credibility_score", 50),
                optimism_score=data.get("optimism_score", 50),
                key_findings=data.get("key_findings", []),
                risk_factors=data.get("risk_factors", []),
                verification_points=data.get("verification_points", []),
                ai_summary=data.get("ai_summary", response[:200] if isinstance(response, str) else ""),
            )

        except Exception as e:
            logger.error(f"NLP analysis failed for {ts_code}: {e}")
            return None

    async def analyze_stock(self, ts_code: str) -> DeepAnalysisResult:
        """Full analysis for a single stock."""
        analysis_date = datetime.now().strftime("%Y%m%d")
        stock_name = self._get_stock_name(ts_code)

        tech = await self.analyze_technical(ts_code)
        ai = await self.analyze_mgmt_discussion(ts_code)

        tech_score = 0
        if tech:
            # Simple tech scoring
            scores = []
            if tech.ma_position == "above_all":
                scores.append(80)
            elif tech.ma_position == "between":
                scores.append(50)
            else:
                scores.append(20)
            if tech.rsi_14 and 30 < tech.rsi_14 < 70:
                scores.append(70)
            elif tech.rsi_14:
                scores.append(30)
            if tech.macd_hist and tech.macd_hist > 0:
                scores.append(70)
            else:
                scores.append(30)
            tech_score = sum(scores) / len(scores) if scores else 0

        result = DeepAnalysisResult(
            ts_code=ts_code,
            stock_name=stock_name,
            analysis_date=analysis_date,
            tech_snapshot=tech,
            ai_analysis=ai,
            tech_score=round(tech_score, 2),
            overall_score=round(tech_score * 0.6 + (ai.credibility_score if ai else 50) * 0.4, 2),
        )

        # Save to ClickHouse
        self._save_analysis(result)

        return result

    async def batch_analyze(
        self, pool_stocks: list[str], progress_callback=None
    ) -> BatchAnalysisStatus:
        """Batch analyze pool stocks with progress tracking."""
        status = BatchAnalysisStatus(total=len(pool_stocks))

        for i, ts_code in enumerate(pool_stocks):
            try:
                status.in_progress = ts_code
                if progress_callback:
                    progress_callback(status)

                result = await self.analyze_stock(ts_code)
                status.results.append(result)
                status.completed += 1

            except Exception as e:
                logger.error(f"Batch analysis failed for {ts_code}: {e}")
                status.failed += 1

        status.in_progress = ""
        return status

    def _get_stock_name(self, ts_code: str) -> str:
        try:
            df = db_client.execute_query(
                f"SELECT name FROM dim_stock_basic WHERE ts_code = '{ts_code}' LIMIT 1"
            )
            return str(df.iloc[0]["name"]) if len(df) > 0 else ""
        except Exception:
            return ""

    def _save_analysis(self, result: DeepAnalysisResult) -> None:
        try:
            row = {
                "analysis_date": result.analysis_date,
                "ts_code": result.ts_code,
                "stock_name": result.stock_name,
                "tech_score": result.tech_score,
                "mgmt_discussion_score": result.ai_analysis.credibility_score if result.ai_analysis else 0,
                "prospect_score": result.ai_analysis.optimism_score if result.ai_analysis else 0,
                "key_findings": result.ai_analysis.key_findings if result.ai_analysis else [],
                "risk_factors": result.ai_analysis.risk_factors if result.ai_analysis else [],
                "verification_points": result.ai_analysis.verification_points if result.ai_analysis else [],
                "ai_summary": result.ai_analysis.ai_summary if result.ai_analysis else "",
                "tech_snapshot": result.tech_snapshot.model_dump_json() if result.tech_snapshot else "",
            }
            df = pd.DataFrame([row])
            db_client.insert_dataframe("quant_deep_analysis", df)
        except Exception as e:
            logger.error(f"Failed to save analysis: {e}")


# Singleton
_analyzer: Optional[DeepAnalyzer] = None


def get_deep_analyzer() -> DeepAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = DeepAnalyzer()
    return _analyzer

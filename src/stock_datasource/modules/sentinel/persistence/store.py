"""Persistence service for sentinel alerts and reports."""

import json
import logging
from typing import Any

import pandas as pd

from stock_datasource.models.database import db_client
from ..schemas import AnalystReport, InvestmentDecision, SentinelAlert

logger = logging.getLogger(__name__)


class SentinelStore:
    """Handles persistence of alerts, reports, and decisions to ClickHouse."""

    def save_alert(self, alert: SentinelAlert) -> None:
        try:
            row = {
                "alert_id": alert.alert_id,
                "sentinel_type": alert.sentinel_type,
                "category": alert.category.value,
                "severity": alert.severity.value,
                "ts_code": alert.ts_code,
                "sector_code": alert.sector_code,
                "index_code": alert.index_code,
                "signal_type": alert.signal_type,
                "description": alert.description,
                "metric_name": alert.metric_name,
                "metric_value": alert.metric_value,
                "threshold": alert.threshold,
                "deviation_pct": alert.deviation_pct,
                "context": json.dumps(alert.context, ensure_ascii=False, default=str),
            }
            db_client.insert_dataframe("sentinel_alerts", pd.DataFrame([row]))
        except Exception as e:
            logger.warning("Failed to save alert: %s", e)

    def save_report(self, report: AnalystReport) -> None:
        try:
            row = {
                "report_id": report.report_id,
                "analyst_type": report.analyst_type,
                "trigger_count": report.trigger_count,
                "market_regime": report.market_regime.value if report.market_regime else None,
                "overall_conviction": report.overall_conviction,
                "insights_json": json.dumps(
                    [i.model_dump() for i in report.insights], ensure_ascii=False
                ),
                "source_alert_ids": [a.alert_id for a in report.source_alerts],
            }
            db_client.insert_dataframe("sentinel_analyst_reports", pd.DataFrame([row]))
        except Exception as e:
            logger.warning("Failed to save report: %s", e)

    def save_decision(self, decision: InvestmentDecision) -> None:
        try:
            row = {
                "decision_id": decision.decision_id,
                "trade_date": decision.trade_date,
                "market_regime": decision.market_regime.value,
                "market_risk_level": decision.market_risk_level,
                "suggested_position": decision.suggested_total_position,
                "buy_count": len(decision.buy_candidates),
                "sell_count": len(decision.sell_candidates),
                "confidence": decision.confidence,
                "decision_json": decision.model_dump_json(),
            }
            db_client.insert_dataframe("sentinel_decisions", pd.DataFrame([row]))
        except Exception as e:
            logger.warning("Failed to save decision: %s", e)

    def get_recent_alerts(self, limit: int = 50, sentinel_type: str | None = None) -> list[dict]:
        try:
            where = f"AND sentinel_type = '{sentinel_type}'" if sentinel_type else ""
            df = db_client.execute_query(f"""
                SELECT * FROM sentinel_alerts
                WHERE 1=1 {where}
                ORDER BY created_at DESC
                LIMIT {min(limit, 200)}
            """)
            return df.to_dict("records") if not df.empty else []
        except Exception as e:
            logger.warning("Failed to get alerts: %s", e)
            return []

    def get_recent_reports(self, limit: int = 20, analyst_type: str | None = None) -> list[dict]:
        try:
            where = f"AND analyst_type = '{analyst_type}'" if analyst_type else ""
            df = db_client.execute_query(f"""
                SELECT * FROM sentinel_analyst_reports
                WHERE 1=1 {where}
                ORDER BY created_at DESC
                LIMIT {min(limit, 100)}
            """)
            return df.to_dict("records") if not df.empty else []
        except Exception as e:
            logger.warning("Failed to get reports: %s", e)
            return []

    def get_recent_decisions(self, limit: int = 10) -> list[dict]:
        try:
            df = db_client.execute_query(f"""
                SELECT * FROM sentinel_decisions
                ORDER BY created_at DESC
                LIMIT {min(limit, 50)}
            """)
            return df.to_dict("records") if not df.empty else []
        except Exception as e:
            logger.warning("Failed to get decisions: %s", e)
            return []


_store: SentinelStore | None = None


def get_sentinel_store() -> SentinelStore:
    global _store
    if _store is None:
        _store = SentinelStore()
    return _store

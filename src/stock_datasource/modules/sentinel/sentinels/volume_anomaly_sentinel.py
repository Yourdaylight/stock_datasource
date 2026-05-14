"""Volume Anomaly Sentinel - monitors unusual volume for core pool stocks."""

from __future__ import annotations

import logging
from datetime import datetime

from stock_datasource.models.database import db_client

from ..core.base_sentinel import BaseSentinel
from ..schemas import AlertCategory, AlertSeverity, SentinelAlert

logger = logging.getLogger(__name__)


class VolumeAnomalySentinel(BaseSentinel):
    """Monitors volume anomalies for stocks in the core pool.

    Triggers:
    - Volume explosion: current volume > 3x 20-day average
    - Volume contraction: volume < 0.3x 20-day average for 3 consecutive days
    """

    SENTINEL_TYPE: str = "volume_anomaly"
    CATEGORY: AlertCategory = AlertCategory.VOLUME

    def get_monitoring_description(self) -> str:
        return "监控核心池股票成交量异常，识别放量突破和持续缩量信号"

    async def scan(self) -> list[SentinelAlert]:
        """Scan core pool stocks for volume anomalies."""
        alerts: list[SentinelAlert] = []

        try:
            # Get current core pool
            pool_sql = """
                SELECT ts_code, stock_name
                FROM quant_core_pool
                WHERE update_date = (SELECT max(update_date) FROM quant_core_pool)
            """
            pool_df = db_client.execute_query(pool_sql)

            if pool_df is None or len(pool_df) == 0:
                logger.warning("VolumeAnomalySentinel: 核心池为空，跳过扫描")
                return []

            ts_codes = pool_df["ts_code"].tolist()
            stock_name_map = dict(zip(pool_df["ts_code"], pool_df["stock_name"]))

            # Get last 25 days of volume data for all pool stocks
            codes_str = "', '".join(ts_codes)
            vol_sql = f"""
                SELECT ts_code, trade_date, vol, close, pct_chg
                FROM fact_daily_bar
                WHERE ts_code IN ('{codes_str}')
                ORDER BY ts_code, trade_date DESC
                LIMIT 25 BY ts_code
            """
            vol_df = db_client.execute_query(vol_sql)

            if vol_df is None or len(vol_df) == 0:
                return []

            # Process each stock
            for ts_code in ts_codes:
                stock_data = vol_df[vol_df["ts_code"] == ts_code].copy()
                if len(stock_data) < 20:
                    continue

                stock_data = stock_data.sort_values("trade_date").reset_index(drop=True)
                stock_name = stock_name_map.get(ts_code, ts_code)

                volumes = stock_data["vol"].astype(float).values

                # Calculate 20-day average volume (excluding latest day)
                avg_vol_20 = float(volumes[-21:-1].mean()) if len(volumes) >= 21 else float(volumes[:-1].mean())
                latest_vol = float(volumes[-1])

                if avg_vol_20 == 0:
                    continue

                vol_ratio = latest_vol / avg_vol_20
                latest_date = str(stock_data.iloc[-1]["trade_date"])
                latest_close = float(stock_data.iloc[-1]["close"])
                latest_pct_chg = float(stock_data.iloc[-1]["pct_chg"]) if stock_data.iloc[-1]["pct_chg"] is not None else 0

                # Volume explosion: > 3x average
                if vol_ratio > 3.0:
                    severity = AlertSeverity.CRITICAL if vol_ratio > 5.0 else AlertSeverity.WARNING
                    alerts.append(SentinelAlert(
                        sentinel_type=self.SENTINEL_TYPE,
                        category=self.CATEGORY,
                        severity=severity,
                        ts_code=ts_code,
                        signal_type="volume_explosion",
                        description=f"{stock_name}({ts_code}) 成交量异常放大，"
                                    f"当日成交量为20日均量的{vol_ratio:.1f}倍，"
                                    f"涨跌幅{latest_pct_chg:.2f}%",
                        metric_name="volume_ratio",
                        metric_value=vol_ratio,
                        threshold=3.0,
                        deviation_pct=(vol_ratio - 1.0) * 100,
                        context={
                            "trade_date": latest_date,
                            "stock_name": stock_name,
                            "close": latest_close,
                            "volume": latest_vol,
                            "avg_vol_20": avg_vol_20,
                            "vol_ratio": round(vol_ratio, 2),
                            "pct_chg": latest_pct_chg,
                        },
                    ))

                # Volume contraction: < 0.3x for 3 consecutive days
                if len(volumes) >= 23:
                    last_3_vols = volumes[-3:]
                    contraction_days = sum(1 for v in last_3_vols if v < avg_vol_20 * 0.3)

                    if contraction_days >= 3:
                        avg_last_3_ratio = float(last_3_vols.mean()) / avg_vol_20
                        alerts.append(SentinelAlert(
                            sentinel_type=self.SENTINEL_TYPE,
                            category=self.CATEGORY,
                            severity=AlertSeverity.INFO,
                            ts_code=ts_code,
                            signal_type="volume_contraction",
                            description=f"{stock_name}({ts_code}) 连续3日极度缩量，"
                                        f"近3日均量仅为20日均量的{avg_last_3_ratio:.1f}倍，"
                                        f"可能即将变盘",
                            metric_name="volume_contraction_ratio",
                            metric_value=avg_last_3_ratio,
                            threshold=0.3,
                            deviation_pct=(avg_last_3_ratio - 1.0) * 100,
                            context={
                                "trade_date": latest_date,
                                "stock_name": stock_name,
                                "close": latest_close,
                                "contraction_days": 3,
                                "avg_last_3_ratio": round(avg_last_3_ratio, 3),
                            },
                        ))

        except Exception as e:
            logger.error(f"VolumeAnomalySentinel scan error: {e}", exc_info=True)

        return alerts

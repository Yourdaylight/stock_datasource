"""Normalize QMT realtime quote payloads."""

from typing import Any

import pandas as pd


def normalize_realtime_quotes(data: Any, market: str | None = None) -> list[dict[str, Any]]:
    """Normalize QMT realtime quotes to canonical dictionaries."""
    df = _to_dataframe(data)
    if df.empty:
        return []

    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        quote = {
            "ts_code": _first(row, "ts_code", "code", "symbol"),
            "market": _first(row, "market", default=market) or market or "a_stock",
            "price": _first(row, "price", "lastPrice", "last_price", "close"),
            "open": _first(row, "open"),
            "high": _first(row, "high"),
            "low": _first(row, "low"),
            "vol": _first(row, "vol", "volume"),
            "amount": _first(row, "amount", "turnover"),
            "quote_time": _format_time(_first(row, "quote_time", "time", "datetime")),
            "bid_price_1": _first(row, "bid_price_1", "bidPrice1", "bid1"),
            "ask_price_1": _first(row, "ask_price_1", "askPrice1", "ask1"),
            "source": "qmt",
        }
        rows.append(quote)
    return rows


def _to_dataframe(data: Any) -> pd.DataFrame:
    if data is None:
        return pd.DataFrame()
    if isinstance(data, pd.DataFrame):
        return data.copy()
    if isinstance(data, dict):
        if isinstance(data.get("data"), list):
            return pd.DataFrame(data["data"])
        if isinstance(data.get("rows"), list):
            return pd.DataFrame(data["rows"])
        return pd.DataFrame([data])
    return pd.DataFrame(data)


def _first(row, *names: str, default: Any = None) -> Any:
    for name in names:
        if name in row and not pd.isna(row[name]):
            return row[name]
    return default


def _format_time(value: Any) -> Any:
    if value is None or pd.isna(value):
        return value
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return str(value)
    return parsed.strftime("%Y-%m-%d %H:%M:%S")

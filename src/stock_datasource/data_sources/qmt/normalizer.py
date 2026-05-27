"""Normalize QMT gateway responses to canonical historical schemas."""

from typing import Any

import pandas as pd

DAILY_COLUMNS = [
    "ts_code",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "pre_close",
    "change",
    "pct_chg",
    "vol",
    "amount",
]

MINUTE_COLUMNS = [
    "ts_code",
    "trade_time",
    "freq",
    "open",
    "high",
    "low",
    "close",
    "vol",
    "amount",
]


def normalize_daily_bars(data: Any, ts_code: str | None = None) -> pd.DataFrame:
    """Normalize QMT daily bars to canonical daily columns."""
    df = _to_dataframe(data)
    if df.empty:
        return pd.DataFrame(columns=DAILY_COLUMNS)

    result = pd.DataFrame()
    result["ts_code"] = _coalesce(df, ["ts_code", "code", "symbol"], default=ts_code)
    result["trade_date"] = _coalesce(df, ["trade_date", "date", "time", "datetime"])
    result["trade_date"] = result["trade_date"].map(_format_trade_date)

    for column in ["open", "high", "low", "close"]:
        result[column] = _coalesce(df, [column])

    result["pre_close"] = _coalesce(
        df, ["pre_close", "preClose", "last_close", "prev_close"]
    )
    result["change"] = _coalesce(df, ["change", "chg"])
    result["pct_chg"] = _coalesce(df, ["pct_chg", "pctChg", "change_pct", "percent"])
    result["vol"] = _coalesce(df, ["vol", "volume"])
    result["amount"] = _coalesce(df, ["amount", "turnover"])

    _fill_daily_change_fields(result)
    return result[DAILY_COLUMNS]


def normalize_minute_bars(
    data: Any, ts_code: str | None = None, freq: str = "1m"
) -> pd.DataFrame:
    """Normalize QMT minute bars to canonical minute columns."""
    df = _to_dataframe(data)
    if df.empty:
        return pd.DataFrame(columns=MINUTE_COLUMNS)

    result = pd.DataFrame()
    result["ts_code"] = _coalesce(df, ["ts_code", "code", "symbol"], default=ts_code)
    result["trade_time"] = _coalesce(
        df, ["trade_time", "datetime", "time", "date"]
    ).map(_format_trade_time)
    result["freq"] = freq

    for column in ["open", "high", "low", "close"]:
        result[column] = _coalesce(df, [column])

    result["vol"] = _coalesce(df, ["vol", "volume"])
    result["amount"] = _coalesce(df, ["amount", "turnover"])
    return result[MINUTE_COLUMNS]


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


def _coalesce(
    df: pd.DataFrame, aliases: list[str], default: Any = None
) -> pd.Series:
    for alias in aliases:
        if alias in df.columns:
            return df[alias]
    return pd.Series([default] * len(df), index=df.index)


def _format_trade_date(value: Any) -> Any:
    if pd.isna(value):
        return value
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y%m%d")

    text = str(value)
    if text.isdigit() and len(text) >= 8:
        return text[:8]
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return text
    return parsed.strftime("%Y%m%d")


def _format_trade_time(value: Any) -> Any:
    if pd.isna(value):
        return value
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d %H:%M:%S")

    text = str(value)
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return text
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def _fill_daily_change_fields(df: pd.DataFrame) -> None:
    pre_close = pd.to_numeric(df["pre_close"], errors="coerce")
    close = pd.to_numeric(df["close"], errors="coerce")

    missing_change = df["change"].isna() & pre_close.notna() & close.notna()
    df.loc[missing_change, "change"] = close[missing_change] - pre_close[missing_change]

    missing_pct = df["pct_chg"].isna() & pre_close.notna() & (pre_close != 0)
    df.loc[missing_pct, "pct_chg"] = (
        (close[missing_pct] - pre_close[missing_pct]) / pre_close[missing_pct] * 100
    )

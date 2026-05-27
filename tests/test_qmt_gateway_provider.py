"""Tests for QMT gateway client and historical provider core."""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        if self.exc:
            raise self.exc
        return self.response

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        if self.exc:
            raise self.exc
        return self.response


def test_qmt_settings_defaults_exist(monkeypatch):
    """QMT settings have safe defaults when no env vars are configured."""
    for name in (
        "QMT_ENABLED",
        "QMT_GATEWAY_URL",
        "QMT_GATEWAY_TIMEOUT",
        "QMT_GATEWAY_TOKEN",
        "QMT_HISTORY_DEFAULT_PERIOD",
        "QMT_REALTIME_ENABLED",
        "QMT_REALTIME_MARKETS",
    ):
        monkeypatch.delenv(name, raising=False)

    from stock_datasource.config.settings import Settings

    settings = Settings(_env_file=None)

    assert settings.QMT_ENABLED is False
    assert settings.QMT_GATEWAY_URL == "http://localhost:58610"
    assert settings.QMT_GATEWAY_TIMEOUT == 10
    assert settings.QMT_GATEWAY_TOKEN == ""
    assert settings.QMT_HISTORY_DEFAULT_PERIOD == "1d"
    assert settings.QMT_REALTIME_ENABLED is False
    assert settings.QMT_REALTIME_MARKETS == "a_stock,etf,index"


def test_normalize_daily_bars_maps_qmt_aliases_to_canonical_columns():
    """Daily normalizer maps common QMT aliases to canonical daily fields."""
    from stock_datasource.data_sources.qmt.normalizer import normalize_daily_bars

    raw_rows = [
        {
            "code": "000001.SZ",
            "date": "2026-01-02",
            "open": 10.0,
            "high": 10.8,
            "low": 9.9,
            "close": 10.5,
            "preClose": 10.1,
            "volume": 123456,
            "turnover": 987654.3,
        }
    ]

    df = normalize_daily_bars(raw_rows)

    assert list(df.columns) == [
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
    row = df.iloc[0].to_dict()
    assert row["ts_code"] == "000001.SZ"
    assert row["trade_date"] == "20260102"
    assert row["pre_close"] == 10.1
    assert row["vol"] == 123456
    assert row["amount"] == 987654.3
    assert row["change"] == pytest.approx(0.4)
    assert row["pct_chg"] == pytest.approx(3.9603960396)


def test_normalize_minute_bars_maps_qmt_aliases_to_canonical_columns():
    """Minute normalizer maps common QMT aliases to canonical minute fields."""
    from stock_datasource.data_sources.qmt.normalizer import normalize_minute_bars

    raw_rows = pd.DataFrame(
        [
            {
                "symbol": "000001.SZ",
                "datetime": "2026-01-02 09:31:00",
                "open": 10.0,
                "high": 10.2,
                "low": 9.9,
                "close": 10.1,
                "volume": 1000,
                "turnover": 11000.0,
            }
        ]
    )

    df = normalize_minute_bars(raw_rows, freq="1m")

    assert list(df.columns) == [
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
    row = df.iloc[0].to_dict()
    assert row["ts_code"] == "000001.SZ"
    assert row["trade_time"] == "2026-01-02 09:31:00"
    assert row["freq"] == "1m"
    assert row["vol"] == 1000
    assert row["amount"] == 11000.0


def test_qmt_gateway_client_uses_auth_only_when_token_configured_and_parses_data():
    """Gateway client sends bearer auth only with token and returns data payloads."""
    from stock_datasource.modules.qmt_gateway.client import QmtGatewayClient

    no_token_session = FakeSession(FakeResponse({"data": [{"code": "000001.SZ"}]}))
    no_token_client = QmtGatewayClient(
        base_url="http://qmt.test", token="", session=no_token_session
    )
    data = no_token_client.get_history_bars("000001.SZ", period="1d")

    assert data == [{"code": "000001.SZ"}]
    _, url, kwargs = no_token_session.calls[0]
    assert url == "http://qmt.test/history/bars"
    assert "Authorization" not in kwargs["headers"]

    token_session = FakeSession(FakeResponse({"data": [{"code": "000002.SZ"}]}))
    token_client = QmtGatewayClient(
        base_url="http://qmt.test", token="secret", session=token_session
    )
    token_client.get_history_bars("000002.SZ", period="1d")

    _, _, token_kwargs = token_session.calls[0]
    assert token_kwargs["headers"]["Authorization"] == "Bearer secret"


def test_qmt_gateway_client_raises_typed_errors_for_gateway_failures():
    """Gateway client converts timeout/auth/unavailable/malformed failures."""
    import requests

    from stock_datasource.modules.qmt_gateway.client import (
        QmtGatewayAuthError,
        QmtGatewayClient,
        QmtGatewayMalformedResponseError,
        QmtGatewayTimeoutError,
        QmtGatewayUnavailableError,
    )

    timeout_client = QmtGatewayClient(
        base_url="http://qmt.test",
        session=FakeSession(exc=requests.exceptions.Timeout()),
    )
    with pytest.raises(QmtGatewayTimeoutError):
        timeout_client.get_history_bars("000001.SZ")

    auth_client = QmtGatewayClient(
        base_url="http://qmt.test",
        session=FakeSession(FakeResponse({"error": "denied"}, status_code=401)),
    )
    with pytest.raises(QmtGatewayAuthError):
        auth_client.get_history_bars("000001.SZ")

    unavailable_client = QmtGatewayClient(
        base_url="http://qmt.test",
        session=FakeSession(FakeResponse({"error": "down"}, status_code=503)),
    )
    with pytest.raises(QmtGatewayUnavailableError):
        unavailable_client.get_history_bars("000001.SZ")

    malformed_client = QmtGatewayClient(
        base_url="http://qmt.test",
        session=FakeSession(FakeResponse({"unexpected": []})),
    )
    with pytest.raises(QmtGatewayMalformedResponseError):
        malformed_client.get_history_bars("000001.SZ")


def test_qmt_historical_provider_returns_normalized_daily_dataframe():
    """Historical provider calls the client and returns canonical daily data."""
    from stock_datasource.data_sources.qmt.historical import QmtHistoricalProvider

    class FakeClient:
        def __init__(self):
            self.calls = []

        def get_history_bars(self, **kwargs):
            self.calls.append(kwargs)
            return [
                {
                    "code": "000001.SZ",
                    "date": "20260102",
                    "open": 10,
                    "high": 11,
                    "low": 9,
                    "close": 10.5,
                    "pre_close": 10,
                    "vol": 100,
                    "amount": 1000,
                }
            ]

    client = FakeClient()
    provider = QmtHistoricalProvider(client=client)

    df = provider.get_daily_bars(
        ts_code="000001.SZ", start_date="20260101", end_date="20260102"
    )

    assert client.calls == [
        {
            "ts_code": "000001.SZ",
            "period": "1d",
            "start_date": "20260101",
            "end_date": "20260102",
            "count": None,
        }
    ]
    assert list(df.columns) == [
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
    assert df.iloc[0]["ts_code"] == "000001.SZ"
    assert df.iloc[0]["trade_date"] == "20260102"

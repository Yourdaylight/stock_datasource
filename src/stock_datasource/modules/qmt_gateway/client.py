"""HTTP client for a QMT gateway service."""

from typing import Any

import requests


class QmtGatewayError(RuntimeError):
    """Base error for QMT gateway failures."""


class QmtGatewayTimeoutError(QmtGatewayError):
    """Raised when the QMT gateway times out."""


class QmtGatewayAuthError(QmtGatewayError):
    """Raised when the QMT gateway rejects authentication."""


class QmtGatewayUnavailableError(QmtGatewayError):
    """Raised when the QMT gateway is unavailable."""


class QmtGatewayMalformedResponseError(QmtGatewayError):
    """Raised when the QMT gateway returns an unexpected response."""


class QmtGatewayClient:
    """Lightweight requests-based QMT gateway client."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: int | float | None = None,
        token: str | None = None,
        session: requests.Session | None = None,
    ):
        from stock_datasource.config.settings import settings

        self.base_url = (base_url or settings.QMT_GATEWAY_URL).rstrip("/")
        self.timeout = timeout if timeout is not None else settings.QMT_GATEWAY_TIMEOUT
        self.token = token if token is not None else settings.QMT_GATEWAY_TOKEN
        self.session = session or requests.Session()

    def health_check(self) -> dict[str, Any]:
        """Return gateway health payload."""
        payload = self._request("GET", "/health")
        if isinstance(payload, dict):
            return payload
        raise QmtGatewayMalformedResponseError("QMT gateway health response must be an object")

    def get_history_bars(
        self,
        ts_code: str,
        period: str = "1d",
        start_date: str | None = None,
        end_date: str | None = None,
        count: int | None = None,
    ) -> Any:
        """Fetch historical bar data from the gateway."""
        return self._request_data(
            "/history/bars",
            {
                "ts_code": ts_code,
                "period": period,
                "start_date": start_date,
                "end_date": end_date,
                "count": count,
            },
        )

    def get_realtime_quotes(self, symbols: list[str] | str, market: str | None = None) -> Any:
        """Fetch realtime quotes from the gateway."""
        return self._request_data(
            "/realtime/quotes",
            {"symbols": symbols, "market": market},
        )

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request_data(self, path: str, payload: dict[str, Any]) -> Any:
        response_payload = self._request("POST", path, json=payload)
        if isinstance(response_payload, dict):
            if response_payload.get("success") is False:
                message = response_payload.get("message") or response_payload.get("error")
                raise QmtGatewayError(str(message or "QMT gateway request failed"))
            if "data" in response_payload:
                return response_payload["data"]
            if "rows" in response_payload:
                return response_payload["rows"]
        if isinstance(response_payload, list):
            return response_payload
        raise QmtGatewayMalformedResponseError("QMT gateway response missing data payload")

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.base_url}{path}"
        try:
            if method == "GET":
                response = self.session.get(
                    url, headers=self._headers(), timeout=self.timeout, **kwargs
                )
            else:
                response = self.session.post(
                    url, headers=self._headers(), timeout=self.timeout, **kwargs
                )
        except requests.exceptions.Timeout:
            raise QmtGatewayTimeoutError("QMT gateway request timed out")
        except requests.exceptions.RequestException as exc:
            raise QmtGatewayUnavailableError(f"QMT gateway request failed: {exc}")

        if response.status_code == 401:
            raise QmtGatewayAuthError("QMT gateway authentication failed")
        if response.status_code >= 400:
            raise QmtGatewayUnavailableError(
                f"QMT gateway returned HTTP {response.status_code}: {response.text}"
            )

        try:
            return response.json()
        except ValueError:
            raise QmtGatewayMalformedResponseError("QMT gateway returned invalid JSON")

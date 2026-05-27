"""Small registry for historical data providers."""

from .base import HistoricalDataProvider

_PROVIDERS: dict[str, HistoricalDataProvider] = {}


def register_provider(name: str, provider: HistoricalDataProvider) -> None:
    """Register a provider by name."""
    if not name:
        raise ValueError("provider name is required")
    _PROVIDERS[name] = provider


def get_provider(name: str) -> HistoricalDataProvider:
    """Return a registered provider."""
    try:
        return _PROVIDERS[name]
    except KeyError:
        raise KeyError(f"Unknown historical data provider: {name}")


def list_providers() -> list[str]:
    """List registered provider names."""
    return sorted(_PROVIDERS)

"""HTTP Proxy utilities for data fetching."""

import os
import logging
from contextlib import contextmanager
from typing import Optional, Dict

logger = logging.getLogger(__name__)

_proxy_applied = False


def _snapshot_proxy_env() -> Dict[str, Optional[str]]:
    keys = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']
    return {key: os.environ.get(key) for key in keys}


def _restore_proxy_env(snapshot: Dict[str, Optional[str]]) -> None:
    keys = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']
    for key in keys:
        value = snapshot.get(key)
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@contextmanager
def proxy_context():
    """Enable proxy only within this context."""
    snapshot = _snapshot_proxy_env()
    try:
        apply_proxy_settings()
        yield
    finally:
        _restore_proxy_env(snapshot)


def apply_proxy_settings() -> bool:
    """Apply HTTP proxy settings from configuration to environment.
    
    This function sets environment variables that are automatically
    picked up by requests, urllib, and other HTTP libraries.
    
    Returns:
        True if proxy is enabled and applied, False otherwise.
    """
    global _proxy_applied
    
    from stock_datasource.config.settings import settings
    
    if settings.HTTP_PROXY_ENABLED and settings.http_proxy_url:
        proxy_url = settings.http_proxy_url
        os.environ['HTTP_PROXY'] = proxy_url
        os.environ['HTTPS_PROXY'] = proxy_url
        os.environ['http_proxy'] = proxy_url
        os.environ['https_proxy'] = proxy_url
        
        if not _proxy_applied:
            logger.info(f"HTTP Proxy enabled: {settings.HTTP_PROXY_HOST}:{settings.HTTP_PROXY_PORT}")
            _proxy_applied = True
        return True
    else:
        # Clear proxy if disabled
        for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
            os.environ.pop(key, None)
        _proxy_applied = False
        return False


def get_proxy_dict() -> Optional[Dict[str, str]]:
    """Get proxy configuration as a dict for requests library.
    
    Returns:
        Dict with 'http' and 'https' keys, or None if proxy is disabled.
    """
    from stock_datasource.config.settings import settings
    return settings.proxy_dict


def get_proxy_url() -> Optional[str]:
    """Get the formatted proxy URL.
    
    Returns:
        Proxy URL string or None if proxy is disabled.
    """
    from stock_datasource.config.settings import settings
    return settings.http_proxy_url


def is_proxy_enabled() -> bool:
    """Check if proxy is currently enabled.
    
    Returns:
        True if proxy is enabled, False otherwise.
    """
    from stock_datasource.config.settings import settings
    return settings.HTTP_PROXY_ENABLED and bool(settings.http_proxy_url)


def clear_proxy_settings():
    """Clear all proxy environment variables."""
    global _proxy_applied
    for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
        os.environ.pop(key, None)
    _proxy_applied = False
    logger.info("HTTP Proxy disabled")

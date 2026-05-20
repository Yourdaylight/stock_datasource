"""Stock Data Source - Local financial database for A-share/HK stocks."""

from __future__ import annotations

import importlib

__version__ = "0.1.0"
__author__ = "Stock Data Source Team"

__all__ = [
    "models",
    "services",
    "utils",
]


def __getattr__(name: str):
    if name in __all__:
        module = importlib.import_module(f".{name}", __name__)
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

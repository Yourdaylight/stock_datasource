"""Agent Registry: Explicit agent discovery and registration.

Provides a centralized registry for all agents, replacing runtime package
scanning as the primary discovery mechanism. Package scanning is kept as
a fallback for backward compatibility.

Key concepts:
- AgentDescriptor: Metadata about an agent's identity and capabilities.
- CapabilityDescriptor: What an agent can do (intent types, stock markets, etc.).
- AgentRegistry: Singleton registry holding descriptors and lazy-creating instances.
"""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Type

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & Descriptors
# ---------------------------------------------------------------------------

class AgentRole(str, Enum):
    """Role of an agent in the runtime."""
    AGENT = "agent"          # Business agent, directly routable
    SUB_AGENT = "sub_agent"  # Invoked by coordinator/runtime only
    ADAPTER = "adapter"      # Wraps workflow / arena into runtime


@dataclass
class CapabilityDescriptor:
    """Describes what an agent can do."""
    intents: List[str] = field(default_factory=list)
    markets: List[str] = field(default_factory=list)   # e.g. ["A", "HK"]
    tags: List[str] = field(default_factory=list)


@dataclass
class AgentDescriptor:
    """Metadata about a registered agent."""
    name: str
    description: str
    agent_class: Type
    role: AgentRole = AgentRole.AGENT
    capability: CapabilityDescriptor = field(default_factory=CapabilityDescriptor)
    priority: int = 0                      # Higher = preferred when multiple match
    enabled: bool = True
    registered_at: float = field(default_factory=time.time)

    # Lazy-created singleton instance
    _instance: Any = field(default=None, repr=False)


# ---------------------------------------------------------------------------
# AgentRegistry
# ---------------------------------------------------------------------------

class AgentRegistry:
    """Centralized registry for agent descriptors and instances.

    Usage
    -----
    >>> registry = get_agent_registry()
    >>> registry.register(AgentDescriptor(
    ...     name="MarketAgent",
    ...     description="...",
    ...     agent_class=MarketAgent,
    ...     capability=CapabilityDescriptor(intents=["market_analysis"]),
    ... ))
    >>> agent = registry.get_agent("MarketAgent")
    """

    def __init__(self) -> None:
        self._descriptors: Dict[str, AgentDescriptor] = {}
        self._fallback_scanned: bool = False

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, descriptor: AgentDescriptor) -> None:
        """Register an agent descriptor.

        If an agent with the same name already exists it will be overwritten
        (explicit re-registration wins).
        """
        self._descriptors[descriptor.name] = descriptor
        logger.info(
            "Agent registered: %s (role=%s, enabled=%s)",
            descriptor.name, descriptor.role.value, descriptor.enabled,
        )

    def register_many(self, descriptors: List[AgentDescriptor]) -> None:
        for d in descriptors:
            self.register(d)

    def unregister(self, name: str) -> bool:
        removed = self._descriptors.pop(name, None)
        if removed:
            logger.info("Agent unregistered: %s", name)
        return removed is not None

    # ------------------------------------------------------------------
    # Discovery helpers
    # ------------------------------------------------------------------

    def get_descriptor(self, name: str) -> Optional[AgentDescriptor]:
        return self._descriptors.get(name)

    def list_descriptors(
        self,
        *,
        role: Optional[AgentRole] = None,
        enabled_only: bool = True,
    ) -> List[AgentDescriptor]:
        result = list(self._descriptors.values())
        if role is not None:
            result = [d for d in result if d.role == role]
        if enabled_only:
            result = [d for d in result if d.enabled]
        return sorted(result, key=lambda d: (-d.priority, d.name))

    def list_available(self) -> List[Dict[str, str]]:
        """Return lightweight list for LLM classification prompts."""
        return [
            {"name": d.name, "description": d.description}
            for d in self.list_descriptors(role=AgentRole.AGENT)
        ]

    def find_by_intent(self, intent: str) -> List[AgentDescriptor]:
        """Find agents whose capability declares a matching intent."""
        return [
            d for d in self.list_descriptors()
            if intent in d.capability.intents
        ]

    def find_by_tag(self, tag: str) -> List[AgentDescriptor]:
        return [
            d for d in self.list_descriptors()
            if tag in d.capability.tags
        ]

    # ------------------------------------------------------------------
    # Instance management (lazy singleton per name)
    # ------------------------------------------------------------------

    def get_agent(self, name: str) -> Optional[Any]:
        """Get or lazily create an agent instance by name."""
        desc = self._descriptors.get(name)
        if desc is None or not desc.enabled:
            return None
        if desc._instance is None:
            try:
                desc._instance = desc.agent_class()
                logger.debug("Instantiated agent: %s", name)
            except Exception as exc:
                logger.error("Failed to instantiate agent %s: %s", name, exc)
                return None
        return desc._instance

    def reset_instance(self, name: str) -> None:
        """Drop cached instance so next get_agent() re-creates it."""
        desc = self._descriptors.get(name)
        if desc:
            desc._instance = None

    # ------------------------------------------------------------------
    # Fallback: package scanning (backward compat)
    # ------------------------------------------------------------------

    _SCAN_EXCLUDE = {"OrchestratorAgent", "StockDeepAgent"}

    def ensure_fallback_scan(self) -> None:
        """Scan ``stock_datasource.agents`` if no explicit registrations exist.

        This keeps the system working without any migration of individual
        agents – they just won't have rich CapabilityDescriptors yet.
        """
        if self._fallback_scanned:
            return
        self._fallback_scanned = True

        if self._descriptors:
            logger.debug("Registry already has %d entries, skip fallback scan", len(self._descriptors))
            return

        logger.info("No explicit registrations found, running fallback package scan")
        self._scan_agents_package()

    def _scan_agents_package(self) -> None:
        """Import ``stock_datasource.agents.*_agent`` and register found classes."""
        try:
            from stock_datasource.agents.base_agent import LangGraphAgent
            import stock_datasource.agents as agents_pkg
        except ImportError:
            logger.warning("Cannot import stock_datasource.agents for fallback scan")
            return

        for module_info in pkgutil.iter_modules(agents_pkg.__path__, agents_pkg.__name__ + "."):
            if not module_info.name.endswith("_agent"):
                continue
            try:
                module = importlib.import_module(module_info.name)
            except Exception:
                continue
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if not issubclass(obj, LangGraphAgent) or obj is LangGraphAgent:
                    continue
                if obj.__name__ in self._SCAN_EXCLUDE:
                    continue
                if not obj.__module__.startswith("stock_datasource.agents"):
                    continue
                try:
                    instance = obj()
                except Exception:
                    continue
                name = instance.config.name
                desc = instance.config.description
                if name not in self._descriptors:
                    self.register(AgentDescriptor(
                        name=name,
                        description=desc,
                        agent_class=obj,
                        role=AgentRole.AGENT,
                    ))

    # ------------------------------------------------------------------
    # Metrics / Introspection
    # ------------------------------------------------------------------

    @property
    def count(self) -> int:
        return len(self._descriptors)

    @property
    def names(self) -> Set[str]:
        return set(self._descriptors.keys())


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_registry: Optional[AgentRegistry] = None


def get_agent_registry() -> AgentRegistry:
    """Return the global AgentRegistry singleton."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry

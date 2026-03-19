"""Skill Registry: Unified catalog for tools, skills, and capabilities.

Aggregates tool/skill definitions from multiple sources:
1. MCP Server / ServiceGenerator exported tools
2. Built-in agent tools (agents/tools.py etc.)
3. Workspace skills (skills/*/SKILL.md)
4. Explicitly registered capability bundles
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class SkillDescriptor:
    """Metadata about a registered skill or tool."""
    name: str
    version: str = "1.0.0"
    category: str = "general"
    description: str = ""
    triggers: List[str] = field(default_factory=list)
    tool_refs: List[str] = field(default_factory=list)
    prompt_refs: List[str] = field(default_factory=list)
    permission_scope: str = "public"
    execution_mode: str = "sync"
    source: str = ""          # "mcp", "builtin", "workspace", "registered"
    enabled: bool = True
    registered_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SkillRegistry:
    """Centralized registry for skills and tool catalogs."""

    def __init__(self) -> None:
        self._skills: Dict[str, SkillDescriptor] = {}

    def register(self, descriptor: SkillDescriptor) -> None:
        self._skills[descriptor.name] = descriptor
        logger.debug("Skill registered: %s (source=%s)", descriptor.name, descriptor.source)

    def register_many(self, descriptors: List[SkillDescriptor]) -> None:
        for d in descriptors:
            self.register(d)

    def unregister(self, name: str) -> bool:
        return self._skills.pop(name, None) is not None

    def get(self, name: str) -> Optional[SkillDescriptor]:
        return self._skills.get(name)

    def list_skills(self, *, category: str = None, source: str = None,
                    enabled_only: bool = True) -> List[SkillDescriptor]:
        result = list(self._skills.values())
        if category:
            result = [s for s in result if s.category == category]
        if source:
            result = [s for s in result if s.source == source]
        if enabled_only:
            result = [s for s in result if s.enabled]
        return sorted(result, key=lambda s: s.name)

    def find_by_trigger(self, trigger: str) -> List[SkillDescriptor]:
        return [s for s in self._skills.values() if trigger in s.triggers and s.enabled]

    def find_by_tool(self, tool_name: str) -> List[SkillDescriptor]:
        return [s for s in self._skills.values() if tool_name in s.tool_refs and s.enabled]

    @property
    def count(self) -> int:
        return len(self._skills)

    @property
    def names(self) -> Set[str]:
        return set(self._skills.keys())

    def to_catalog(self) -> List[Dict[str, Any]]:
        """Return lightweight catalog for display or LLM prompts."""
        return [
            {"name": s.name, "category": s.category, "description": s.description,
             "tools": s.tool_refs, "version": s.version}
            for s in self.list_skills()
        ]


# Singleton
_registry: Optional[SkillRegistry] = None

def get_skill_registry() -> SkillRegistry:
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry

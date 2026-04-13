"""LoopDetectionMiddleware: Detect and break agent tool call loops.

Detects when an agent calls the same tool with the same arguments
consecutively (3+ times) and injects a hint to break the loop.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

from .base import AgentContext, AgentResponse, BaseMiddleware

logger = logging.getLogger(__name__)


class LoopDetectionMiddleware(BaseMiddleware):
    """Detect and break agent tool call loops.

    A loop is detected when the same tool is called with the same (or very similar)
    arguments 3+ times consecutively. When detected, sets context.loop_detected=True
    and the calling code can inject a hint to the agent.
    """

    MAX_CONSECUTIVE_CALLS: int = 3

    def __init__(self, max_consecutive: int = 3):
        super().__init__()
        self._max_consecutive = max_consecutive

    async def before(self, context: AgentContext) -> AgentContext:
        """Check for loops in previous tool calls."""
        if not self.enabled:
            return context

        context.trace(self.name, "start")

        # Check tool calls from context
        tool_calls = context.tool_calls
        if len(tool_calls) >= self._max_consecutive:
            loop = self._detect_loop(tool_calls)
            if loop:
                context.loop_detected = True
                logger.warning(
                    "Loop detected: tool=%s called %d times with same args",
                    loop["tool"], loop["count"],
                )
                self._log.warning(
                    "middleware.loop_detected",
                    tool=loop["tool"],
                    count=loop["count"],
                    session_id=context.session_id,
                )
                context.trace(self.name, "loop_detected")

        context.trace(self.name, "done")
        return context

    async def after(self, context: AgentContext, response: AgentResponse) -> AgentResponse:
        """Track tool calls from this response for future loop detection."""
        if not self.enabled:
            return response

        # Append tool calls to context for next iteration
        if response.tool_calls:
            context.tool_calls.extend(response.tool_calls)

        # Check for loop in response tool calls
        if len(response.tool_calls) >= self._max_consecutive:
            loop = self._detect_loop(response.tool_calls)
            if loop:
                context.loop_detected = True
                # Add warning to response
                response.warnings.append(
                    f"检测到工具 {loop['tool']} 被重复调用 {loop['count']} 次，"
                    f"可能是循环调用，请尝试换个方式提问。"
                )
                self._log.warning(
                    "middleware.loop_detected",
                    tool=loop["tool"],
                    count=loop["count"],
                    session_id=context.session_id,
                )

        return response

    def _detect_loop(self, tool_calls: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Detect if there's a loop in recent tool calls.

        Returns dict with tool name and count if loop detected, else None.
        """
        if len(tool_calls) < self._max_consecutive:
            return None

        # Check the last N calls for same tool+args pattern
        recent = tool_calls[-self._max_consecutive * 2:]  # Look at last 2x threshold
        call_signatures = []

        for tc in recent:
            tool_name = tc.get("name", tc.get("tool", "unknown"))
            args = tc.get("args", {})
            # Normalize args for comparison
            args_str = json.dumps(args, sort_keys=True, ensure_ascii=False)
            sig = hashlib.md5(f"{tool_name}:{args_str}".encode()).hexdigest()[:8]
            call_signatures.append((tool_name, sig))

        # Count consecutive same signatures
        if not call_signatures:
            return None

        # Check the tail for consecutive duplicates
        last_tool, last_sig = call_signatures[-1]
        count = 1
        for i in range(len(call_signatures) - 2, -1, -1):
            tool, sig = call_signatures[i]
            if tool == last_tool and sig == last_sig:
                count += 1
            else:
                break

        if count >= self._max_consecutive:
            return {"tool": last_tool, "count": count}

        return None

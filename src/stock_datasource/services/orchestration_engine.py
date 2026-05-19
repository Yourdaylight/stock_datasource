"""Orchestration execution engine — executes pipeline DAG with tier-aware parallelism.

Supports:
- Topological sort of DAG
- Tier grouping: nodes in same tier run in parallel (asyncio.gather)
- Rich SSE events: tier_start, node_start, node_end, node_error, tier_end, complete
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict
from typing import Any, AsyncGenerator

from stock_datasource.models.orchestration import PipelineNode, PipelineResponse
from stock_datasource.services.agent_config_service import get_agent_config_service

logger = logging.getLogger(__name__)


class OrchestrationEngine:
    """Execute a pipeline DAG with tier-aware parallelism and rich events."""

    async def execute(
        self, pipeline: PipelineResponse, input_data: dict
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Execute the pipeline and yield SSE events."""
        # Group nodes by tier (from node.data.tier)
        tier_groups: dict[int, list[PipelineNode]] = defaultdict(list)
        input_nodes: list[PipelineNode] = []
        output_nodes: list[PipelineNode] = []

        for node in pipeline.nodes:
            if node.type.value == "input":
                input_nodes.append(node)
            elif node.type.value == "output":
                output_nodes.append(node)
            elif node.type.value in ("agent", "aggregator"):
                tier = node.data.get("tier", 1)
                tier_groups[tier].append(node)

        # State: stores output of each node
        state: dict[str, Any] = {}

        # Process input nodes first
        for node in input_nodes:
            state[node.id] = input_data.get("message", json.dumps(input_data, ensure_ascii=False))
            yield {
                "type": "node_end",
                "node_id": node.id,
                "node_type": "input",
                "label": node.label,
                "output": state[node.id],
                "duration_ms": 0,
            }

        # Execute tiers in order (1, 2, 3...)
        sorted_tiers = sorted(tier_groups.keys())

        for tier_num in sorted_tiers:
            tier_nodes = tier_groups[tier_num]
            yield {
                "type": "tier_start",
                "tier": tier_num,
                "node_count": len(tier_nodes),
                "labels": [n.label for n in tier_nodes],
            }

            # Emit node_start for all nodes in this tier
            for node in tier_nodes:
                yield {
                    "type": "node_start",
                    "node_id": node.id,
                    "node_type": node.type.value,
                    "label": node.label,
                    "agent_id": node.data.get("agent_id", ""),
                    "tier": tier_num,
                }

            # Run all nodes in this tier in parallel
            tier_start = time.time()
            results = await asyncio.gather(
                *[self._execute_node(node, state, pipeline) for node in tier_nodes],
                return_exceptions=True,
            )

            # Process results and emit events
            for node, result in zip(tier_nodes, results):
                if isinstance(result, Exception):
                    state[node.id] = f"[ERROR] {result}"
                    yield {
                        "type": "node_error",
                        "node_id": node.id,
                        "label": node.label,
                        "error": str(result),
                        "duration_ms": 0,
                    }
                else:
                    output, duration_ms = result
                    state[node.id] = output
                    yield {
                        "type": "node_end",
                        "node_id": node.id,
                        "node_type": node.type.value,
                        "label": node.label,
                        "output": output[:2000] if isinstance(output, str) else str(output)[:2000],
                        "duration_ms": duration_ms,
                        "tier": tier_num,
                    }

            tier_duration = int((time.time() - tier_start) * 1000)
            yield {
                "type": "tier_end",
                "tier": tier_num,
                "duration_ms": tier_duration,
            }

        # Process output nodes
        for node in output_nodes:
            upstream_outputs = self._get_upstream_outputs(node.id, pipeline, state)
            final = "\n\n".join(upstream_outputs) if upstream_outputs else ""
            state[node.id] = final
            yield {
                "type": "node_end",
                "node_id": node.id,
                "node_type": "output",
                "label": node.label,
                "output": final[:5000],
                "duration_ms": 0,
            }

        # Final completion
        final_output = ""
        if output_nodes:
            final_output = state.get(output_nodes[0].id, "")
        elif sorted_tiers:
            # If no output node, use last tier's combined output
            last_tier_nodes = tier_groups[sorted_tiers[-1]]
            final_output = "\n\n".join(str(state.get(n.id, "")) for n in last_tier_nodes)

        yield {
            "type": "complete",
            "output": final_output[:5000] if isinstance(final_output, str) else str(final_output)[:5000],
        }

    async def _execute_node(
        self,
        node: PipelineNode,
        state: dict[str, Any],
        pipeline: PipelineResponse,
    ) -> tuple[str, int]:
        """Execute a single node and return (output, duration_ms)."""
        start = time.time()

        if node.type.value == "aggregator":
            upstream_outputs = self._get_upstream_outputs(node.id, pipeline, state)
            merged = "\n---\n".join(upstream_outputs)
            duration_ms = int((time.time() - start) * 1000)
            return merged, duration_ms

        # Agent node
        agent_id = node.data.get("agent_id", "")
        if not agent_id:
            return "[No agent configured for this node]", 0

        agent_service = get_agent_config_service()
        agent = agent_service.get_agent(agent_id)
        if agent is None:
            return f"[Agent {agent_id} not found]", 0

        # Gather input from upstream nodes
        upstream_outputs = self._get_upstream_outputs(node.id, pipeline, state)
        user_message = "\n\n".join(upstream_outputs) if upstream_outputs else ""
        if not user_message:
            user_message = node.data.get("default_input", "请分析")

        # Call LLM with timeout
        try:
            from stock_datasource.llm import get_llm_client

            client = get_llm_client()
            messages = [
                {"role": "system", "content": agent.system_prompt},
                {"role": "user", "content": user_message},
            ]
            response = await asyncio.wait_for(
                client.chat(
                    messages=messages,
                    temperature=agent.model_config_data.temperature,
                    max_tokens=agent.model_config_data.max_tokens,
                ),
                timeout=120,
            )
            duration_ms = int((time.time() - start) * 1000)
            if isinstance(response, dict):
                return response.get("content", str(response)), duration_ms
            return str(response), duration_ms
        except asyncio.TimeoutError:
            duration_ms = int((time.time() - start) * 1000)
            raise RuntimeError(f"Agent {node.label} 超时 (>120s)")
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            logger.error("Agent %s LLM call failed: %s", agent_id, e)
            raise RuntimeError(f"Agent {node.label} 调用失败: {e}")

    def _get_upstream_outputs(
        self, node_id: str, pipeline: PipelineResponse, state: dict[str, Any]
    ) -> list[str]:
        """Get outputs from all nodes that have edges pointing to this node."""
        outputs = []
        for edge in pipeline.edges:
            if edge.target == node_id:
                output = state.get(edge.source, "")
                if output:
                    outputs.append(str(output))
        return outputs

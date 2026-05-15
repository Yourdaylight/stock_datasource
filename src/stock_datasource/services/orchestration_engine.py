"""Orchestration execution engine — executes pipeline DAG by invoking agents sequentially."""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict, deque
from typing import Any, AsyncGenerator

from stock_datasource.models.orchestration import PipelineNode, PipelineResponse
from stock_datasource.services.agent_config_service import get_agent_config_service

logger = logging.getLogger(__name__)


class OrchestrationEngine:
    """Execute a pipeline DAG by topological traversal of agent nodes.

    For MVP: sequential execution with streaming events.
    Future: parallel fan-out, condition branching, aggregation.
    """

    async def execute(
        self, pipeline: PipelineResponse, input_data: dict
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Execute the pipeline and yield SSE events."""
        # Build adjacency and in-degree for topological sort
        nodes_by_id: dict[str, PipelineNode] = {n.id: n for n in pipeline.nodes}
        adjacency: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = {n.id: 0 for n in pipeline.nodes}

        for edge in pipeline.edges:
            adjacency[edge.source].append(edge.target)
            in_degree[edge.target] = in_degree.get(edge.target, 0) + 1

        # Topological sort (Kahn's algorithm)
        queue: deque[str] = deque()
        for node_id, deg in in_degree.items():
            if deg == 0:
                queue.append(node_id)

        execution_order: list[str] = []
        while queue:
            node_id = queue.popleft()
            execution_order.append(node_id)
            for neighbor in adjacency[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # State: stores output of each node
        state: dict[str, Any] = {}

        # Process nodes in topological order
        for node_id in execution_order:
            node = nodes_by_id.get(node_id)
            if node is None:
                continue

            if node.type.value == "input":
                # Input node — pass through pipeline input
                state[node_id] = input_data.get("message", json.dumps(input_data, ensure_ascii=False))
                yield {
                    "type": "node_end",
                    "node_id": node_id,
                    "node_type": "input",
                    "label": node.label,
                    "output": state[node_id],
                    "duration_ms": 0,
                }

            elif node.type.value == "agent":
                # Agent node — invoke the agent's LLM with its system prompt + skills
                agent_id = node.data.get("agent_id", "")
                yield {
                    "type": "node_start",
                    "node_id": node_id,
                    "node_type": "agent",
                    "label": node.label,
                    "agent_id": agent_id,
                }

                start = time.time()
                try:
                    output = await self._run_agent_node(node, state, adjacency, pipeline)
                    duration_ms = int((time.time() - start) * 1000)
                    state[node_id] = output
                    yield {
                        "type": "node_end",
                        "node_id": node_id,
                        "node_type": "agent",
                        "label": node.label,
                        "output": output[:2000] if isinstance(output, str) else str(output)[:2000],
                        "duration_ms": duration_ms,
                    }
                except Exception as e:
                    duration_ms = int((time.time() - start) * 1000)
                    state[node_id] = f"[ERROR] {e}"
                    yield {
                        "type": "node_error",
                        "node_id": node_id,
                        "label": node.label,
                        "error": str(e),
                        "duration_ms": duration_ms,
                    }

            elif node.type.value == "output":
                # Output node — collect result from upstream
                upstream_outputs = self._get_upstream_outputs(node_id, pipeline, state)
                final = "\n\n".join(upstream_outputs) if upstream_outputs else ""
                state[node_id] = final
                yield {
                    "type": "node_end",
                    "node_id": node_id,
                    "node_type": "output",
                    "label": node.label,
                    "output": final[:5000],
                    "duration_ms": 0,
                }

            elif node.type.value == "aggregator":
                # Aggregator — merge upstream outputs
                upstream_outputs = self._get_upstream_outputs(node_id, pipeline, state)
                merged = "\n---\n".join(upstream_outputs)
                state[node_id] = merged
                yield {
                    "type": "node_end",
                    "node_id": node_id,
                    "node_type": "aggregator",
                    "label": node.label,
                    "output": merged[:3000],
                    "duration_ms": 0,
                }

        # Final output
        output_nodes = [n for n in pipeline.nodes if n.type.value == "output"]
        final_output = state.get(output_nodes[0].id, "") if output_nodes else ""
        yield {
            "type": "complete",
            "output": final_output[:5000] if isinstance(final_output, str) else str(final_output)[:5000],
        }

    async def _run_agent_node(
        self,
        node: PipelineNode,
        state: dict[str, Any],
        adjacency: dict[str, list[str]],
        pipeline: PipelineResponse,
    ) -> str:
        """Run a single agent node: load config, build prompt, call LLM."""
        agent_id = node.data.get("agent_id", "")
        if not agent_id:
            return "[No agent configured for this node]"

        # Load agent config
        agent_service = get_agent_config_service()
        agent = agent_service.get_agent(agent_id)
        if agent is None:
            return f"[Agent {agent_id} not found]"

        # Gather input from upstream nodes
        upstream_outputs = self._get_upstream_outputs(node.id, pipeline, state)
        user_message = "\n\n".join(upstream_outputs) if upstream_outputs else ""

        if not user_message:
            user_message = node.data.get("default_input", "请分析")

        # Call LLM with agent's system prompt
        try:
            from stock_datasource.llm import get_llm_client

            client = get_llm_client()
            messages = [
                {"role": "system", "content": agent.system_prompt},
                {"role": "user", "content": user_message},
            ]
            response = await client.chat(
                messages=messages,
                temperature=agent.model_config_data.temperature,
                max_tokens=agent.model_config_data.max_tokens,
            )
            # Response is a dict like {"role": "assistant", "content": "..."}
            if isinstance(response, dict):
                return response.get("content", str(response))
            return str(response)
        except Exception as e:
            logger.error("Agent %s LLM call failed: %s", agent_id, e)
            return f"[LLM Error: {e}]"

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

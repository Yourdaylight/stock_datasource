"""HarnessReportAgent — 验证 LangGraph Harness 迁移路径的原型 Agent (财报分析).

本模块实现一个使用 deepagents 完整 harness 能力的 ReportAgent 变体：
- SubAgentMiddleware: 支持子 agent 调度
- MemoryMiddleware: AGENTS.md 内存注入
- checkpointer=True: LangGraph 自动内存检查点
- store: InMemoryStore 用于持久化存储
- astream_events(version="v2"): 与现有 SSE 管道兼容

通过 HARNESS_MODE_ENABLED=true 环境变量激活。
"""

import logging
import os
import time
from collections.abc import AsyncGenerator, Callable
from typing import Any

from deepagents import (
    MemoryMiddleware,
    SubAgentMiddleware,
    create_deep_agent,
)
from langgraph.store.memory import InMemoryStore

from .base_agent import (
    AgentConfig,
    LangGraphAgent,
    compress_tool_result,
    get_langchain_model,
    get_langfuse_handler,
    get_session_memory,
)
from .report_agent import (
    get_comprehensive_financial_analysis,
    get_peer_comparison_analysis,
    get_investment_insights,
    get_income_statement,
    get_balance_sheet,
    get_cash_flow,
    get_forecast,
    get_express,
    get_full_financial_statements,
    get_audit_opinion,
    get_non_standard_opinions,
)
from .tools import get_stock_info, get_stock_valuation

logger = logging.getLogger(__name__)


def is_harness_mode_enabled() -> bool:
    """Check whether harness mode is activated via environment variable."""
    return os.getenv("HARNESS_MODE_ENABLED", "").lower() == "true"


# Shared store instance (module-level singleton)
_harness_store: InMemoryStore | None = None


def _get_harness_store() -> InMemoryStore:
    """Get or create the shared InMemoryStore for harness agents."""
    global _harness_store
    if _harness_store is None:
        _harness_store = InMemoryStore()
    return _harness_store


# System prompt — reused from ReportAgent
REPORT_ANALYSIS_SYSTEM_PROMPT = """你是一个专业的财务分析师和投资顾问，专注于A股上市公司的深度财报分析。

## 核心能力
- 全面财务健康度评估
- 专业同业对比分析
- AI驱动的投资洞察
- 多维度风险识别
- 基于数据的投资建议
- 审计意见风险评估

## 可用工具
- get_stock_info: 获取股票基本信息和最新行情
- get_stock_valuation: 获取PE、PB等估值指标
- get_comprehensive_financial_analysis: 获取全面财务分析(健康度、盈利能力、偿债能力、成长性)
- get_peer_comparison_analysis: 获取同业对比分析和行业排名
- get_investment_insights: 获取AI投资洞察和结构化建议
- get_income_statement: 获取利润表数据（营业收入、净利润、EPS等）
- get_balance_sheet: 获取资产负债表数据（总资产、负债、股东权益等）
- get_cash_flow: 获取现金流量表数据（经营现金流、投资现金流、筹资现金流等）
- get_forecast: 获取业绩预告数据
- get_express: 获取业绩快报数据
- get_full_financial_statements: 获取完整的三大财务报表（利润表、资产负债表、现金流量表）
- get_audit_opinion: 获取财务审计意见数据（审计结果、审计费用、会计师事务所、签字会计师）
- get_non_standard_opinions: 获取非标准审计意见列表（用于风险监控和筛选）

## 分析框架 (基于真实财务数据)
1. **盈利能力**: ROE、ROA、毛利率、净利率、EPS
2. **偿债能力**: 资产负债率、流动比率、速动比率
3. **运营效率**: 资产周转率、存货周转率、应收账款周转率
4. **成长性**: 营收增长率、利润增长率、趋势分析
5. **估值水平**: PE、PB、PS与行业对比
6. **行业地位**: 同业对比、行业排名、竞争优势
7. **审计风险**: 审计意见类型、历史审计记录、会计师事务所变更

## 审计意见类型说明
- 标准无保留意见: 财务报表公允反映公司财务状况（最佳）
- 带强调事项段的无保留意见: 存在需要关注的事项但不影响整体公允性
- 保留意见: 部分事项无法核实或存在异议
- 否定意见: 财务报表整体不公允（高风险警示）
- 无法表示意见: 审计范围受限，无法发表意见（高风险警示）

## 分析流程
1. 获取股票基本信息和行情数据
2. 进行全面财务分析，评估财务健康度
3. 查看审计意见，评估财务报表可靠性
4. 执行同业对比，确定行业地位
5. 生成AI投资洞察和风险评估
6. 提供综合性投资建议和关注点

## 专业标准
- 基于真实财务数据，确保分析准确性
- 多维度横向对比，提供行业视角
- 历史趋势分析，识别发展轨迹
- 风险因素识别，平衡收益与风险
- 审计意见分析，评估报表可信度
- 结构化输出，便于理解和决策

## 常用股票代码示例
- 贵州茅台: 600519 → 600519.SH
- 平安银行: 000001 → 000001.SZ
- 比亚迪: 002594 → 002594.SZ
- 宁德时代: 300750 → 300750.SZ

## 分析原则
- 数据驱动：基于真实财务指标
- 对比分析：横向同业、纵向历史
- 风险意识：明确指出潜在风险
- 审计关注：非标准意见需重点提示
- 投资导向：提供实用投资建议
- 专业表达：使用专业术语和标准

## 免责声明
所有财务分析和投资建议仅供参考，不构成投资决策依据。投资有风险，入市需谨慎。
"""


class HarnessReportAgent(LangGraphAgent):
    """ReportAgent variant using the full deepagents harness stack.

    Differences from the standard ReportAgent:
    - Uses SubAgentMiddleware for task delegation capability
    - Uses MemoryMiddleware for AGENTS.md memory injection (if configured)
    - Uses checkpointer=True (LangGraph auto in-memory checkpoint)
    - Uses InMemoryStore for cross-session persistent storage
    - Emits the same SSE event format as the base LangGraphAgent

    This is a prototype to validate the harness migration path. The existing
    ReportAgent remains untouched and is the production default.
    """

    def __init__(self):
        config = AgentConfig(
            name="HarnessReportAgent",
            description="[Harness] 专业财报分析师 — 使用完整 harness 中间件栈",
            temperature=0.5,
            max_tokens=8000,
        )
        super().__init__(config)
        self._harness_agent = None

    def get_tools(self) -> list[Callable]:
        """Return financial report analysis tools (same as ReportAgent)."""
        return [
            get_stock_info,
            get_stock_valuation,
            get_comprehensive_financial_analysis,
            get_peer_comparison_analysis,
            get_investment_insights,
            get_income_statement,
            get_balance_sheet,
            get_cash_flow,
            get_forecast,
            get_express,
            get_full_financial_statements,
            get_audit_opinion,
            get_non_standard_opinions,
        ]

    def get_system_prompt(self) -> str:
        """Return system prompt (same as ReportAgent)."""
        return REPORT_ANALYSIS_SYSTEM_PROMPT

    def _init_harness_agent(self):
        """Initialize the deep agent with full harness middleware stack."""
        if self._harness_agent is not None:
            return self._harness_agent

        model = self._get_model()
        tools = self.get_tools()
        system_prompt = self.get_system_prompt() + self.COMMON_OUTPUT_RULES
        store = _get_harness_store()

        # Build middleware: SubAgentMiddleware provides task delegation
        middleware = [
            SubAgentMiddleware(
                default_model=model,
                default_tools=tools,
                subagents=[],
                general_purpose_agent=True,
            ),
        ]

        # Create the harness-enabled agent
        self._harness_agent = create_deep_agent(
            model=model,
            tools=tools,
            system_prompt=system_prompt,
            middleware=middleware,
            checkpointer=True,  # Auto in-memory checkpoint
            store=store,
            name="HarnessReportAgent",
        )

        logger.info(
            "HarnessReportAgent initialized with full harness stack "
            "(SubAgentMiddleware, checkpointer=True, store=InMemoryStore)"
        )
        return self._harness_agent

    async def execute_stream(
        self, task: str, context: dict[str, Any] = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Execute task with streaming, emitting the same SSE event format.

        This mirrors the base LangGraphAgent.execute_stream contract:
        - thinking events (with agent name, status)
        - content events (streamed text chunks)
        - debug events (agent_start, tool_result, agent_end)
        - visualization events (chart data from tools)
        - done event (with metadata)
        - error event (on failure)
        """
        context = context or {}

        user_id = context.get("user_id", "default")
        context_key = context.get("context_key", "")
        session_id = context.get("session_id") or self._memory.get_session_id(
            self.config.name, user_id, context_key
        )

        # Clear history if requested
        if context.get("clear_history"):
            self._memory.clear_session(session_id)

        self._memory.cleanup_expired(ttl_seconds=self.config.history_ttl_seconds)

        start_time = time.time()
        tool_calls_seen = []
        tool_call_count = 0

        try:
            agent = self._init_harness_agent()

            # Build messages with history (reuse base class logic)
            messages = self._build_messages(task, session_id, context)

            # Save user message to history
            self._memory.add_message(
                session_id, "user", task, max_messages=self.config.max_history_messages
            )

            # Yield initial thinking event
            yield {
                "type": "thinking",
                "agent": self.config.name,
                "status": "分析中...(Harness模式)",
                "session_id": session_id,
            }

            # Emit debug: agent_start
            tool_names = []
            for t in self.get_tools():
                tname = getattr(t, "name", None) or getattr(t, "__name__", "unknown")
                tool_names.append(tname)
            yield self._make_debug_event(
                "agent_start",
                {
                    "agent": self.config.name,
                    "harness_mode": True,
                    "input_summary": task[:200] if len(task) > 200 else task,
                    "tools_available": tool_names,
                    "parent_agent": context.get("parent_agent"),
                },
            )

            # Build LangGraph config
            config = {
                "recursion_limit": self.config.recursion_limit,
                "configurable": {"thread_id": session_id},
                "metadata": {
                    "langfuse_user_id": user_id,
                    "langfuse_session_id": session_id,
                    "langfuse_tags": [self.config.name, "harness"],
                },
            }

            # Add Langfuse callbacks
            callbacks = self._get_callbacks(
                session_id, user_id=user_id, context=context
            )
            if callbacks:
                config["callbacks"] = callbacks

            full_response = ""

            # Stream using astream_events v2 (same as base class)
            async for event in agent.astream_events(
                {"messages": messages}, config=config, version="v2"
            ):
                event_type = event.get("event", "")

                try:
                    if event_type == "on_tool_start":
                        tool_name = event.get("name", "unknown")
                        tool_calls_seen.append(tool_name)
                        tool_call_count += 1
                        yield {
                            "type": "thinking",
                            "agent": self.config.name,
                            "status": f"正在调用: {tool_name}",
                            "tool": tool_name,
                        }

                    elif event_type == "on_tool_end":
                        tool_name = event.get("name", "unknown")
                        tool_output = event.get("data", {}).get("output", "")
                        tool_input = event.get("data", {}).get("input", {})

                        # Emit debug: tool_result
                        result_str = str(tool_output)
                        result_summary = (
                            result_str[:500] + "..."
                            if len(result_str) > 500
                            else result_str
                        )
                        args_summary = {}
                        if isinstance(tool_input, dict):
                            args_summary = {
                                k: str(v)[:100]
                                for k, v in list(tool_input.items())[:10]
                            }
                        yield self._make_debug_event(
                            "tool_result",
                            {
                                "tool": tool_name,
                                "agent": self.config.name,
                                "args": args_summary,
                                "result_summary": result_summary,
                                "duration_ms": 0,
                            },
                        )

                        # Extract and emit visualization if present
                        viz = self._extract_visualization(tool_output)
                        if viz:
                            yield {
                                "type": "visualization",
                                "visualization": viz,
                                "agent": self.config.name,
                                "tool": tool_name,
                            }

                    elif event_type == "on_chat_model_stream":
                        chunk = event.get("data", {}).get("chunk")
                        if chunk:
                            content = None
                            if hasattr(chunk, "content") and chunk.content:
                                raw_content = chunk.content
                                if isinstance(raw_content, str):
                                    content = raw_content
                                elif isinstance(raw_content, list):
                                    text_parts = []
                                    for block in raw_content:
                                        if isinstance(block, dict):
                                            if block.get("type") == "text" and block.get("text"):
                                                text_parts.append(block["text"])
                                        elif isinstance(block, str):
                                            text_parts.append(block)
                                    if text_parts:
                                        content = "".join(text_parts)
                            elif isinstance(chunk, dict) and chunk.get("content"):
                                content = chunk["content"]

                            if content and isinstance(content, str):
                                full_response += content
                                yield {
                                    "type": "content",
                                    "content": content,
                                }

                    elif event_type == "on_chain_end":
                        pass  # Already streamed via on_chat_model_stream

                except Exception as e:
                    logger.debug(f"Error processing event {event_type}: {e}")

            # Save assistant response to history
            if full_response:
                response_for_history = full_response
                if len(response_for_history) > 2000:
                    response_for_history = (
                        response_for_history[:2000] + "\n...[内容已截断]"
                    )
                self._memory.add_message(
                    session_id,
                    "assistant",
                    response_for_history,
                    max_messages=self.config.max_history_messages,
                )

            # Emit debug: agent_end
            duration_ms = int((time.time() - start_time) * 1000)
            yield self._make_debug_event(
                "agent_end",
                {
                    "agent": self.config.name,
                    "harness_mode": True,
                    "duration_ms": duration_ms,
                    "tool_calls_count": tool_call_count,
                    "success": True,
                },
            )

            # Yield done
            yield {
                "type": "done",
                "metadata": {
                    "agent": self.config.name,
                    "harness_mode": True,
                    "tool_calls": tool_calls_seen,
                    "session_id": session_id,
                    "history_length": len(self._memory.get_history(session_id)),
                },
            }

        except Exception as e:
            logger.error(f"{self.config.name} stream execution failed: {e}")
            duration_ms = int((time.time() - start_time) * 1000)
            yield self._make_debug_event(
                "agent_end",
                {
                    "agent": self.config.name,
                    "harness_mode": True,
                    "duration_ms": duration_ms,
                    "tool_calls_count": tool_call_count,
                    "success": False,
                    "error": str(e),
                },
            )
            yield {
                "type": "error",
                "error": str(e),
            }


# Singleton instance
_harness_report_agent: HarnessReportAgent | None = None


def get_harness_report_agent() -> HarnessReportAgent:
    """Get HarnessReportAgent singleton instance."""
    global _harness_report_agent
    if _harness_report_agent is None:
        _harness_report_agent = HarnessReportAgent()
    return _harness_report_agent

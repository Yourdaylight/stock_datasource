# Harness 迁移方法论

将任意 LangGraphAgent 迁移至 deepagents harness 模式的可重复步骤。

---

## 概述

Harness 模式为每个 Agent 增加以下能力：
- **SubAgentMiddleware**: 子 agent 调度/任务委派
- **checkpointer=True**: LangGraph 自动内存检查点（会话连续性）
- **InMemoryStore**: 跨会话持久化存储
- **astream_events v2**: 与现有 SSE 管道完全兼容

迁移目标（历史）：在**不修改原 Agent 任何代码**的前提下创建 Harness 变体。当前主链路已改为默认使用 `ConfigDrivenHarnessAgent`，不再通过 `HARNESS_MODE_ENABLED` 切换。

---

## 逐步迁移流程

### Step 1: 识别源 Agent

确认需要迁移的 Agent 类（如 `ReportAgent`），记录：
- 类所在文件路径
- `get_tools()` 返回的工具列表
- `get_system_prompt()` 返回的系统提示词
- 任何特殊的 `AgentConfig` 参数

### Step 2: 创建 Harness Agent 文件

创建 `harness_<agent_name>_agent.py`，结构如下：

```python
"""Harness<AgentName>Agent — harness 迁移原型."""

import logging
import os
import time
from collections.abc import AsyncGenerator, Callable
from typing import Any

from deepagents import SubAgentMiddleware, create_deep_agent
from langgraph.store.memory import InMemoryStore

from .base_agent import (
    AgentConfig, LangGraphAgent, compress_tool_result,
    get_langchain_model, get_langfuse_handler, get_session_memory,
)
# 从原 Agent 导入工具和 system_prompt
from .original_agent import tool_a, tool_b, SYSTEM_PROMPT
```

### Step 3: 复制工具和 System Prompt

直接从原 Agent 的 `get_tools()` 和 `get_system_prompt()` 复制：

```python
def get_tools(self) -> list[Callable]:
    """与原 Agent 完全相同的工具列表."""
    return [tool_a, tool_b, ...]

def get_system_prompt(self) -> str:
    """与原 Agent 完全相同的 system prompt."""
    return ORIGINAL_SYSTEM_PROMPT
```

### Step 4: 添加 Harness 初始化样板

每个 Harness Agent 都需要以下固定结构：

```python
# 模块级单例 Store
_harness_store: InMemoryStore | None = None

def _get_harness_store() -> InMemoryStore:
    global _harness_store
    if _harness_store is None:
        _harness_store = InMemoryStore()
    return _harness_store

# 历史方案曾使用 HARNESS_MODE_ENABLED 开关；当前不再需要 feature flag。
```

### Step 5: 实现 `_init_harness_agent`

```python
def _init_harness_agent(self):
    if self._harness_agent is not None:
        return self._harness_agent

    model = self._get_model()
    tools = self.get_tools()
    system_prompt = self.get_system_prompt() + self.COMMON_OUTPUT_RULES
    store = _get_harness_store()

    middleware = [
        SubAgentMiddleware(
            default_model=model,
            default_tools=tools,
            subagents=[],
            general_purpose_agent=True,
        ),
    ]

    self._harness_agent = create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        middleware=middleware,
        checkpointer=True,
        store=store,
        name="Harness<AgentName>Agent",
    )
    return self._harness_agent
```

### Step 6: 复制 `execute_stream` 模板

`execute_stream` 的实现在所有 Harness Agent 之间**完全相同**，只需修改：
- `self.config.name`（通过 `__init__` 的 `AgentConfig` 自动处理）
- 初始 thinking 事件的文案（可选）

核心流程：
1. 获取 session_id、清理过期历史
2. 初始化 harness agent
3. 构建 messages（复用 base class `_build_messages`）
4. 发送 thinking + agent_start debug 事件
5. 使用 `astream_events(version="v2")` 流式处理
6. 处理 `on_tool_start`、`on_tool_end`、`on_chat_model_stream` 事件
7. 保存历史、发送 agent_end + done 事件

### Step 7: 接入配置驱动 Orchestrator

当前 `orchestrator.py` 默认通过 `get_config_driven_agent(agent_name)` 调度，无需新增 feature flag。

```python
from .config_driven_harness_agent import get_config_driven_agent

agent = get_config_driven_agent(agent_name)
```

### Step 8: 添加 Singleton 工厂

```python
_harness_agent_instance: HarnessXxxAgent | None = None

def get_harness_xxx_agent() -> HarnessXxxAgent:
    global _harness_agent_instance
    if _harness_agent_instance is None:
        _harness_agent_instance = HarnessXxxAgent()
    return _harness_agent_instance
```

### Step 9: 验证

```bash
# 1. 导入测试
python -c "from stock_datasource.agents.harness_xxx_agent import HarnessXxxAgent; a = HarnessXxxAgent(); print(f'OK: {len(a.get_tools())} tools')"

# 2. 功能测试（ConfigDrivenHarnessAgent 已是默认路径）
python -c "..."
```

---

## 每个 Harness Agent 的固定样板清单

| 组件 | 说明 |
|------|------|
| `_harness_store` 单例 | `InMemoryStore` 模块级单例 |
| `_get_harness_store()` | Store 获取函数 |
| `AgentConfig(name=..., description=..., temperature=0.5, max_tokens=8000)` | 配置 |
| `get_tools()` | 直接复用原 Agent 工具 |
| `get_system_prompt()` | 直接复用原 Agent prompt |
| `_init_harness_agent()` | deepagents 初始化 |
| `execute_stream()` | SSE 流式执行（模板代码） |
| `get_harness_xxx_agent()` | Singleton 工厂 |

---

## 从原 Agent 复制的内容

1. **工具列表** — `get_tools()` 中的所有函数引用
2. **System Prompt** — `get_system_prompt()` 的完整文本
3. **AgentConfig 参数** — name/description 按需调整，加 `[Harness]` 前缀

## 不需要复制的内容

- `execute()` 方法 — harness 使用自己的 streaming 实现
- 任何内部状态管理 — 由 checkpointer + store 处理
- Langfuse 集成 — 通过 base class `_get_callbacks` 自动处理

---

## 常见陷阱

| 陷阱 | 解决方案 |
|------|---------|
| 忘记 `+ self.COMMON_OUTPUT_RULES` | system_prompt 后追加 |
| Store 被多实例覆盖 | 使用模块级 `_harness_store` 单例 |
| Orchestrator import 循环 | 在 `if` 块内 lazy import |
| `_harness_agent` 未初始化 | `__init__` 中设为 `None`，首次调用时初始化 |
| 工具函数签名不兼容 | 确保工具有 docstring + type hints（LangGraph 需要） |
| SSE 事件格式不一致 | 严格复用模板中的 event dict 结构 |

---

## 已完成的迁移

| 原 Agent | Harness 变体 | 工具数 | 状态 |
|----------|-------------|--------|------|
| MarketAgent | HarnessMarketAgent | 4 | ✅ 完成 |
| ReportAgent | HarnessReportAgent | 13 | ✅ 完成 |

---

## 下一步

1. 运行 E2E 测试验证 SSE 事件格式兼容性
2. 考虑提取公共 `HarnessAgentMixin` 减少重复代码
3. 评估 `MemoryMiddleware` 集成（当前未启用，需要 AGENTS.md 配置）
4. 性能对比：原 Agent vs Harness Agent 的首次响应延迟

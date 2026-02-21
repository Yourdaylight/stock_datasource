# Change: Add chat orchestrator agent with MCP fallback

## Why
当前智能对话入口缺少统一的"协调 Agent"进行意图解析与Agent调度，且未在无可用Agent时回退到MCP工具。需要建立可复用的调度模块，先接入chat入口，后续可扩展到其它分析入口。

## What Changes

### 1. 新增"协调 Agent"用于chat入口
- 负责意图识别、Agent发现与选择、调度执行与回退策略
- 当无可用Agent时，回退到MCP工具列表进行调度执行
- 保持前端流式输出（SSE）全量展示中间过程与结果

### 2. 数据库表结构变更
**修改文件**: 数据库 `user_positions` 表

**变更内容**:
```sql
ALTER TABLE user_positions ADD COLUMN user_id String DEFAULT 'default_user'
```

**原因**: 
- 原表缺少 `user_id` 字段，无法区分不同用户的持仓数据
- 添加后支持多用户持仓管理和查询

### 3. 持仓分析功能修复
**修改文件**: `src/stock_datasource/agents/portfolio_agent.py`

**变更内容**:
- `get_positions()` 函数: 从使用 `EnhancedPortfolioService` 改为使用 `PortfolioService`
- `calculate_portfolio_pnl()` 函数: 同样改为使用 `PortfolioService`
- 添加日志记录便于调试

**原因**:
- 原代码使用 `EnhancedPortfolioService`，与 API (`/api/portfolio/positions`) 使用的 `PortfolioService` 数据源不一致
- 导致API有持仓数据但智能对话显示为空

**代码变更示例**:
```python
# Before
from stock_datasource.modules.portfolio.enhanced_service import EnhancedPortfolioService
service = EnhancedPortfolioService()

# After
from stock_datasource.modules.portfolio.service import get_portfolio_service
service = get_portfolio_service()
```

### 4. PortfolioService 兼容性增强
**修改文件**: `src/stock_datasource/modules/portfolio/service.py`

**变更内容**:
- `get_positions()` 方法增加对 `user_id` 字段的兼容性检查
- 当数据库表没有 `user_id` 字段时自动降级处理

**代码逻辑**:
```python
# Check if user_id column exists
desc_df = self.db.execute_query("DESCRIBE user_positions")
has_user_id = 'user_id' in desc_df['name'].values

if has_user_id:
    # Query with user_id filter
    query = "SELECT ... WHERE user_id = %(user_id)s"
else:
    # Fallback: return all positions
    query = "SELECT ... ORDER BY buy_date DESC"
```

### 5. Langfuse 3.x 集成
**修改文件**: `src/stock_datasource/agents/base_agent.py`

**变更内容**:
- 修复 Langfuse 3.x API 兼容性问题
- 使用正确的导入路径: `from langfuse.langchain import CallbackHandler`
- 使用 `TraceContext` 传递用户上下文信息
- 通过 LangChain config metadata 传递用户信息（Langfuse 3.x 推荐方式）

**Langfuse 3.x 关键变更**:
```python
# Langfuse 3.x: user_id/session_id 通过 config metadata 传递
config = {
    "recursion_limit": self.config.recursion_limit,
    "configurable": {"thread_id": session_id},
    "metadata": {
        "langfuse_user_id": user_id,
        "langfuse_session_id": session_id,
        "langfuse_tags": [self.config.name],
    }
}
```

**环境变量配置**:
```env
LANGFUSE_HOST=http://host.docker.internal:3000
LANGFUSE_PUBLIC_KEY=pk-lf-xxx
LANGFUSE_SECRET_KEY=sk-lf-xxx
LANGFUSE_ENABLED=true
```

## Impact

### Affected specs
- `chat-orchestration` (new)

### Affected code
- `src/stock_datasource/agents/base_agent.py` - Langfuse handler & execute_stream config
- `src/stock_datasource/agents/portfolio_agent.py` - get_positions() & calculate_portfolio_pnl()
- `src/stock_datasource/agents/orchestrator.py` - Agent 调度逻辑
- `src/stock_datasource/modules/portfolio/service.py` - user_id 兼容性处理
- `src/stock_datasource/modules/chat/router.py` - SSE 流式输出

### Database changes
- `user_positions` 表添加 `user_id` 字段 (String, DEFAULT 'default_user')

### Dependencies
- `langfuse>=3.12.0` - LLM 调用追踪和监控

## Testing

### 测试验证项
1. ✅ 持仓数据获取: 智能对话正确返回用户持仓列表（6条记录）
2. ✅ 数据一致性: Agent 与 API 使用相同数据源
3. ✅ Langfuse Handler 创建: 成功创建并携带用户上下文
4. ✅ Langfuse 数据发送: 对话记录正确发送到 Langfuse 服务
5. ✅ 用户信息追踪: Langfuse Dashboard 显示 userId 和 sessionId

### 测试命令
```bash
# 测试持仓获取
python3 -c "
from stock_datasource.agents.portfolio_agent import get_positions
import stock_datasource.agents.portfolio_agent as pa
pa._current_user_id = 'default_user'
print(get_positions())
"

# 测试 Langfuse Handler
python3 -c "
from stock_datasource.agents.base_agent import get_langfuse_handler
handler = get_langfuse_handler(user_id='test', session_id='test', trace_name='test')
print(f'Handler: {handler is not None}')
"

# 验证 Langfuse traces
curl -s 'http://localhost:3000/api/public/traces?limit=3' \
  -u 'pk-xxx:sk-xxx' | jq '.data[] | {name, userId, sessionId}'
"
```

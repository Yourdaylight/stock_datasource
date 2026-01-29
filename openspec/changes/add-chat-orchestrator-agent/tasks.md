## 1. Implementation
- [x] 1.1 评估现有chat入口调用链，定位Agent发现与调度插入点
- [x] 1.2 新增OrchestratorAgent（意图识别、Agent发现、Agent选择）
- [x] 1.3 在chat入口改为OrchestratorAgent统一调度
- [x] 1.4 增加MCP回退调用路径（无可用Agent时）
- [x] 1.5 保持SSE流输出完整事件（thinking/tool/content/done/error）
- [x] 1.6 补充最小验证（手工或脚本）覆盖Agent与MCP回退路径

## 2. Data Consistency
- [x] 2.1 数据库 user_positions 表添加 user_id 字段
- [x] 2.2 修改 PortfolioService.get_positions() 支持 user_id 字段兼容性检测
- [x] 2.3 修改 portfolio_agent.py 的 get_positions() 使用 PortfolioService
- [x] 2.4 修改 portfolio_agent.py 的 calculate_portfolio_pnl() 使用 PortfolioService
- [x] 2.5 验证智能对话持仓分析与 API 数据一致

## 3. Langfuse Integration
- [x] 3.1 修复 Langfuse 3.x API 兼容性（CallbackHandler 参数变更）
- [x] 3.2 使用正确的导入路径 langfuse.langchain.CallbackHandler
- [x] 3.3 通过 LangChain config metadata 传递用户上下文
- [x] 3.4 验证 Langfuse 服务可达性和数据写入
- [x] 3.5 确认 Langfuse Dashboard 可查看带用户信息的 trace

## 4. Documentation
- [x] 4.1 更新 proposal.md 补充所有变更内容
- [x] 4.2 更新 design.md 补充设计决策和实现细节
- [x] 4.3 更新 tasks.md 补充任务清单
- [x] 4.4 更新 spec.md 补充规约要求

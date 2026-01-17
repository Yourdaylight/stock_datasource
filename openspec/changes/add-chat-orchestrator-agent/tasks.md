## 1. Implementation
- [x] 1.1 评估现有chat入口调用链，定位Agent发现与调度插入点
- [x] 1.2 新增OrchestratorAgent（意图识别、Agent发现、Agent选择）
- [x] 1.3 在chat入口改为OrchestratorAgent统一调度
- [x] 1.4 增加MCP回退调用路径（无可用Agent时）
- [x] 1.5 保持SSE流输出完整事件（thinking/tool/content/done/error）
- [x] 1.6 补充最小验证（手工或脚本）覆盖Agent与MCP回退路径

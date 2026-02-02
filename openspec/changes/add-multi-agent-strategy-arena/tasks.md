# 多Agent对抗策略竞技场 - 实施任务

## 阶段1: 基础架构搭建 (Week 1-2)

### 1.1 目录结构和模块设计
- [x] 创建 `src/stock_datasource/arena/` 目录结构
- [x] 设计Arena核心数据模型
- [x] 实现ArenaConfig配置类
- [x] 实现ArenaState状态机
- [x] 创建Arena异常类体系

### 1.2 思考流处理器
- [x] 实现 `ThinkingStreamProcessor` 核心类
- [x] 实现Redis Streams消息发布
- [x] 实现SSE端点 `/api/arena/{id}/thinking-stream`
- [x] 实现思考消息持久化到ClickHouse
- [x] 实现历史思考流查询接口

### 1.3 异步任务基础设施
- [x] 配置Celery + Redis作为消息队列
- [x] 实现Arena任务基类
- [x] 实现任务状态追踪
- [x] 实现任务取消和恢复机制
- [x] 配置任务重试策略

### 1.4 数据库Schema
- [x] 设计arena表结构
- [x] 设计arena_strategies表结构
- [x] 设计arena_discussions表结构
- [x] 设计arena_evaluations表结构
- [x] 实现数据库迁移脚本

## 阶段2: Agent层开发 (Week 3-4)

### 2.1 策略生成Agent
- [x] 实现 `StrategyGeneratorAgent` 基类
- [x] 实现基于GPT-4的GeneratorAgent
- [x] 实现基于Claude的GeneratorAgent
- [x] 实现基于本地模型的GeneratorAgent
- [x] 实现Agent异质化配置机制

### 2.2 专业Agent角色
- [x] 实现 `StrategyReviewerAgent` 策略评审Agent
- [x] 实现 `RiskAnalystAgent` 风险分析Agent
- [x] 实现 `MarketSentimentAgent` 市场情绪Agent
- [x] 实现 `QuantResearcherAgent` 量化研究Agent
- [x] 实现Agent角色注册表

### 2.3 讨论协调器
- [x] 实现 `AgentDiscussionOrchestrator` 核心类
- [x] 实现辩论模式 (DebateMode)
- [x] 实现协作模式 (CollaborationMode)
- [x] 实现评审模式 (ReviewMode)
- [x] 实现模式组合调度器

### 2.4 市场环境分析器
- [x] 实现 `MarketContextAnalyzer` 核心类
- [x] 整合实时行情数据获取
- [x] 整合技术面分析计算
- [x] 整合基本面数据获取
- [x] 整合市场情绪指标获取

## 阶段3: 竞争引擎开发 (Week 5-6)

### 3.1 竞争引擎核心
- [x] 实现 `StrategyCompetitionEngine` 核心类
- [x] 实现策略池管理
- [x] 实现阶段转换逻辑（回测→模拟）
- [x] 实现竞争状态持久化
- [x] 实现竞争恢复机制

### 3.2 综合评分系统
- [x] 实现 `ComprehensiveScorer` 评分器
- [x] 实现收益性维度评分（30%权重）
- [x] 实现风险控制维度评分（30%权重）
- [x] 实现稳定性维度评分（20%权重）
- [x] 实现适应性维度评分（20%权重）

### 3.3 周期淘汰机制
- [x] 实现日评更新（不淘汰）
- [x] 实现周评淘汰（末位20%）
- [x] 实现月评淘汰（末位10%）
- [x] 实现淘汰后策略补充机制
- [x] 实现淘汰通知和记录

### 3.4 回测整合
- [x] 整合现有 `IntelligentBacktestEngine`
- [x] 实现批量回测调度
- [x] 实现回测结果聚合
- [x] 实现防过拟合验证
- [x] 实现滚动窗口回测

### 3.5 模拟盘引擎
- [x] 实现 `SimulatedTradingEngine` 核心类
- [x] 实现虚拟资金管理
- [x] 实现模拟订单执行
- [x] 实现持仓跟踪
- [x] 实现每日结算

## 阶段4: API接口开发 (Week 7)

### 4.1 Arena管理API
- [x] 实现 `POST /api/arena/create` 创建竞技场
- [x] 实现 `GET /api/arena/{id}/status` 获取状态
- [x] 实现 `POST /api/arena/{id}/start` 启动竞争
- [x] 实现 `POST /api/arena/{id}/pause` 暂停竞争
- [x] 实现 `POST /api/arena/{id}/resume` 恢复竞争
- [x] 实现 `DELETE /api/arena/{id}` 删除竞技场

### 4.2 思考流API
- [x] 实现 `GET /api/arena/{id}/thinking-stream` SSE端点
- [x] 实现 `GET /api/arena/{id}/discussions` 获取讨论历史
- [x] 实现 `GET /api/arena/{id}/discussions/{round_id}` 获取轮次详情
- [x] 实现断点续传支持
- [x] 实现历史消息回放

### 4.3 策略和排行API
- [x] 实现 `GET /api/arena/{id}/strategies` 获取策略列表
- [x] 实现 `GET /api/arena/{id}/strategies/{strategy_id}` 策略详情
- [x] 实现 `GET /api/arena/{id}/leaderboard` 获取排行榜
- [x] 实现 `POST /api/arena/{id}/evaluate` 触发周期评估
- [x] 实现 `GET /api/arena/{id}/history` 获取竞争历史

### 4.4 讨论API
- [x] 实现 `POST /api/arena/{id}/discussion/start` 触发讨论
- [x] 实现 `GET /api/arena/{id}/discussion/current` 当前讨论状态
- [x] 实现 `POST /api/arena/{id}/discussion/intervention` 人工干预

## 阶段5: 前端界面开发 (Week 8-9)

### 5.1 Arena管理页面
- [x] 创建 `ArenaManagement.vue` 主页面
- [x] 实现Arena列表展示
- [x] 实现创建Arena向导
- [x] 实现Arena配置面板
- [x] 实现Arena状态监控卡片

### 5.2 思考流聊天界面
- [x] 创建 `ThinkingStreamChat.vue` 组件
- [x] 实现消息流式渲染
- [x] 实现Agent角色头像和标识
- [x] 实现消息折叠和展开
- [x] 实现历史消息加载

### 5.3 排行榜和统计面板
- [x] 创建 `Leaderboard.vue` 组件
- [x] 实现策略排名展示
- [x] 实现评分维度雷达图
- [x] 实现收益曲线对比图
- [x] 实现淘汰历史时间线

### 5.4 策略详情页
- [x] 创建 `ArenaStrategyDetail.vue` 页面
- [x] 实现策略逻辑展示
- [x] 实现回测结果可视化
- [x] 实现模拟盘持仓展示
- [x] 实现讨论历史回溯

### 5.5 前端状态管理
- [x] 创建 `arena` Pinia store
- [x] 实现SSE连接管理
- [x] 实现思考消息状态
- [x] 实现排行榜数据缓存
- [x] 实现离线消息同步

## 阶段6: 集成和测试 (Week 10)

### 6.1 单元测试
- [x] Arena核心模块单元测试 (56个用例)
- [x] Agent模块单元测试
- [x] 竞争引擎单元测试
- [x] API接口单元测试
- [ ] 前端组件单元测试

### 6.2 集成测试
- [x] 端到端Arena创建流程测试
- [x] 多Agent讨论流程测试
- [x] 竞争淘汰流程测试
- [x] SSE思考流测试
- [x] 异步任务恢复测试 (25个用例)

### 6.3 性能测试
- [ ] 多Agent并发性能测试 (设计完成，待执行)
- [ ] 思考流高并发测试
- [ ] 回测任务队列压力测试
- [ ] 数据库查询性能优化
- [ ] 前端渲染性能优化

### 6.4 文档和部署
- [x] API接口文档编写 (ARENA_API.md)
- [x] 测试报告编写 (TEST_REPORT.md)
- [ ] 用户使用手册编写
- [ ] 部署脚本编写
- [ ] 监控告警配置
- [ ] 上线发布

## 验收标准

### 功能验收
- [x] 支持创建可配置Agent数量的竞技场
- [x] 三种讨论模式正常运作
- [x] 思考流实时输出无卡顿（延迟 < 500ms）
- [x] 周期评估和淘汰正常执行
- [x] 前端界面交互流畅

### 性能验收
- [ ] 单Arena支持最多10个Agent并行
- [ ] 思考流消息延迟 < 500ms
- [ ] 单轮讨论完成 < 5分钟
- [ ] 周期评估完成 < 10分钟
- [ ] SSE连接数支持 > 100

### 质量验收
- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试通过率 100%
- [ ] 无P1/P2级别Bug
- [ ] 代码审查通过

## 依赖关系

```
1.1 目录结构 ─┬─→ 1.2 思考流处理器
              ├─→ 1.3 异步任务基础设施
              └─→ 1.4 数据库Schema

2.1 策略生成Agent ─┬─→ 2.3 讨论协调器
2.2 专业Agent角色 ─┘
2.4 市场环境分析器 ─→ 2.1

3.1 竞争引擎核心 ─┬─→ 3.2 综合评分系统
                  ├─→ 3.3 周期淘汰机制
                  ├─→ 3.4 回测整合
                  └─→ 3.5 模拟盘引擎

4.x API接口 ─→ 依赖阶段1-3完成

5.x 前端界面 ─→ 依赖阶段4 API完成

6.x 集成测试 ─→ 依赖阶段1-5完成
```

## 可并行任务

以下任务可以并行开发：
- 1.2 思考流处理器 & 1.3 异步任务基础设施
- 2.1 策略生成Agent & 2.2 专业Agent角色
- 3.2 综合评分系统 & 3.5 模拟盘引擎
- 5.1 Arena管理页面 & 5.2 思考流聊天界面

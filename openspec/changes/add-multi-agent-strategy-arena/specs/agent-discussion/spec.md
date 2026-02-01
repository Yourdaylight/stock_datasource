# Agent讨论协作机制规范

## ADDED Requirements

### Requirement: Multi-mode Discussion Orchestration
系统 SHALL 支持辩论、协作、评审三种讨论模式的组合调度，模拟真实投研团队工作流程。

#### Scenario: Configure discussion modes
- **WHEN** 用户配置竞技场讨论机制
- **THEN** 可选择启用的讨论模式组合
- **AND** 可设置每种模式的执行顺序
- **AND** 可设置每种模式的轮次数

#### Scenario: Execute combined discussion flow
- **WHEN** 竞技场进入讨论阶段
- **THEN** 系统按配置的模式顺序执行讨论
- **AND** 每个模式完成后进入下一模式
- **AND** 全部模式完成后进入共识阶段

### Requirement: Debate Mode
系统 SHALL 支持辩论模式，Agent互相质疑和挑战策略逻辑。

#### Scenario: Challenge strategy logic
- **WHEN** 进入辩论模式
- **THEN** Reviewer Agent对Generator Agent的策略提出质疑
- **AND** Generator Agent回应并解释逻辑
- **AND** 记录辩论内容到思考流

#### Scenario: Identify strategy risks
- **WHEN** Risk Analyst Agent参与辩论
- **THEN** 指出策略的潜在风险点
- **AND** 量化风险敞口
- **AND** 提出风险缓解建议

#### Scenario: Challenge market assumptions
- **WHEN** Market Sentiment Agent参与辩论
- **THEN** 质疑策略的市场假设是否成立
- **AND** 提供当前市场情绪数据支撑
- **AND** 建议策略调整方向

### Requirement: Collaboration Mode
系统 SHALL 支持协作模式，Agent互相补充和优化策略。

#### Scenario: Complement strategy parameters
- **WHEN** 进入协作模式
- **THEN** Quant Researcher Agent提出参数优化建议
- **AND** 基于学术研究支撑建议
- **AND** Generator Agent采纳并调整策略

#### Scenario: Integrate multi-agent insights
- **WHEN** 多个Agent提供改进建议
- **THEN** 系统整合不同角度的建议
- **AND** 生成综合优化方案
- **AND** 记录每个Agent的贡献

#### Scenario: Iterative improvement
- **WHEN** 策略经过一轮协作优化
- **THEN** 重新评估策略表现
- **AND** 决定是否需要继续优化
- **AND** 直到达到满意度阈值或轮次上限

### Requirement: Review Mode
系统 SHALL 支持评审模式，专门的Reviewer Agent评分并给出改进建议。

#### Scenario: Structured strategy review
- **WHEN** 进入评审模式
- **THEN** Reviewer Agent按标准化模板评审策略
- **AND** 从收益性、风险控制、稳定性、适应性四个维度打分
- **AND** 给出具体改进建议

#### Scenario: Score aggregation
- **WHEN** 多个Reviewer完成评审
- **THEN** 系统聚合多个评审分数
- **AND** 计算加权平均分
- **AND** 标识分歧较大的维度

#### Scenario: Conditional approval
- **WHEN** 策略评审完成
- **THEN** 评审分数达到阈值的策略进入下一阶段
- **AND** 未达标策略返回优化
- **AND** 记录评审意见和分数

### Requirement: Rotating Leadership
系统 SHALL 支持Agent轮换主导讨论，确保多元视角。

#### Scenario: Round-robin leadership
- **WHEN** 进入新一轮讨论
- **THEN** 系统指定一个Agent作为本轮主导
- **AND** 主导Agent引导讨论方向
- **AND** 下一轮轮换至另一个Agent

#### Scenario: Leader privileges
- **WHEN** Agent担任讨论主导
- **THEN** 优先发言权
- **AND** 可决定讨论焦点
- **AND** 可触发表决进入下一阶段

### Requirement: Consensus Building
系统 SHALL 支持讨论后形成共识，生成最终策略。

#### Scenario: Collect final opinions
- **WHEN** 讨论轮次结束
- **THEN** 系统收集各Agent对策略的最终意见
- **AND** 标识共识点和分歧点

#### Scenario: Generate consensus strategy
- **WHEN** 进入共识阶段
- **THEN** 系统基于讨论结果生成最终策略
- **AND** 整合各Agent的改进建议
- **AND** 记录策略的决策来源

#### Scenario: Handle discussion timeout
- **WHEN** 讨论超过最大轮次仍未达成共识
- **THEN** 系统强制进入共识阶段
- **AND** 基于当前最优方案生成策略
- **AND** 标记为"有限共识"

### Requirement: Discussion History
系统 SHALL 完整记录讨论历史，支持回溯分析。

#### Scenario: Record discussion messages
- **WHEN** Agent发送讨论消息
- **THEN** 系统记录消息内容、发送者、时间戳
- **AND** 标注消息类型（质疑/建议/回应/共识）
- **AND** 关联到所属讨论轮次

#### Scenario: Query discussion history
- **WHEN** 用户查询讨论历史
- **THEN** 系统返回完整的讨论时间线
- **AND** 支持按Agent、模式、轮次过滤
- **AND** 支持全文搜索

#### Scenario: Export discussion report
- **WHEN** 用户请求导出讨论报告
- **THEN** 系统生成结构化的讨论摘要
- **AND** 包含关键决策点和理由
- **AND** 支持多种格式导出

### Requirement: Agent Role Registry
系统 SHALL 维护Agent角色注册表，定义各角色的职责和能力。

#### Scenario: Register agent role
- **WHEN** 系统启动或配置Agent
- **THEN** 在注册表中登记Agent的角色类型
- **AND** 定义角色的能力边界
- **AND** 配置角色的提示词模板

#### Scenario: Query available roles
- **WHEN** 用户配置竞技场
- **THEN** 系统返回可用的Agent角色列表
- **AND** 包含每个角色的职责描述
- **AND** 推荐合理的角色组合

### Requirement: Human Intervention
系统 SHALL 支持人工干预讨论过程。

#### Scenario: Inject human opinion
- **WHEN** 用户在讨论进行中提交意见
- **THEN** 系统将意见注入讨论流
- **AND** 标记为人工输入
- **AND** Agent需回应人工意见

#### Scenario: Force discussion conclusion
- **WHEN** 用户强制结束讨论
- **THEN** 系统立即进入共识阶段
- **AND** 基于当前状态生成策略
- **AND** 记录人工干预原因

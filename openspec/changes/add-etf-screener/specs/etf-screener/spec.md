# Capability: ETF/指数选股

ETF/指数选股模块提供指数浏览、筛选、成分分析和AI量化分析功能。

## ADDED Requirements

### Requirement: ETF Agent实现

系统 SHALL 提供专门的ETF Agent用于指数量化分析。

- 系统 SHALL 创建`ETFAgent`类，继承`LangGraphAgent`基类
- 系统 SHALL 实现ETF专用的工具函数集
- 系统 SHALL 配置符合ETF量化分析特点的System Prompt
- 系统 SHALL 支持通过Agent执行综合分析任务

#### Scenario: 初始化ETF Agent

- **GIVEN** 系统启动
- **WHEN** 调用`get_etf_agent()`
- **THEN** 系统返回已初始化的`ETFAgent`实例
- **AND** Agent配置名称为"ETFAgent"
- **AND** Agent绑定ETF分析工具函数

#### Scenario: Agent执行分析任务

- **GIVEN** ETF Agent已初始化
- **WHEN** 调用`agent.execute("分析沪深300指数")`
- **THEN** Agent识别指数代码为`000300.SH`
- **AND** Agent调用相关工具函数获取数据
- **AND** Agent返回结构化的分析报告

---

### Requirement: ETF分析工具函数

系统 SHALL 提供ETF分析专用的工具函数。

- 系统 SHALL 实现`get_index_info`获取指数基础信息
- 系统 SHALL 实现`get_index_constituents`获取成分股权重
- 系统 SHALL 实现`get_index_factors`获取技术因子
- 系统 SHALL 实现`analyze_index_valuation`分析指数估值
- 系统 SHALL 实现`analyze_concentration_risk`分析集中度风险
- 系统 SHALL 实现`analyze_technical_signals`分析技术信号
- 系统 SHALL 实现`get_comprehensive_etf_analysis`生成综合报告

#### Scenario: 获取指数基础信息

- **GIVEN** 工具函数`get_index_info`
- **WHEN** 调用`get_index_info("000300.SH")`
- **THEN** 系统查询`dim_index_basic`表
- **AND** 返回指数名称、市场、发布方、基期等信息

#### Scenario: 分析指数估值

- **GIVEN** 工具函数`analyze_index_valuation`
- **WHEN** 调用`analyze_index_valuation("000300.SH")`
- **THEN** 系统获取成分股列表及权重
- **AND** 系统查询各成分股的PE/PB估值
- **AND** 系统计算加权平均PE/PB
- **AND** 返回估值分析报告

#### Scenario: 分析集中度风险

- **GIVEN** 工具函数`analyze_concentration_risk`
- **WHEN** 调用`analyze_concentration_risk("000300.SH")`
- **THEN** 系统获取成分股权重
- **AND** 系统计算CR10（前10大成分股占比）
- **AND** 系统计算HHI指数
- **AND** 返回集中度风险等级（低/中/高）

#### Scenario: 分析技术信号

- **GIVEN** 工具函数`analyze_technical_signals`
- **WHEN** 调用`analyze_technical_signals("000300.SH")`
- **THEN** 系统获取最新技术因子数据
- **AND** 系统解读MACD信号（金叉/死叉）
- **AND** 系统解读KDJ状态（超买/超卖）
- **AND** 系统解读RSI水平
- **AND** 返回综合技术信号判断

---

### Requirement: 指数列表展示

系统 SHALL 提供指数列表的浏览和筛选功能。

- 系统 SHALL 展示所有指数的基础信息（代码、名称、市场、类别）
- 系统 SHALL 支持按市场（SSE/SZSE/CSI等）筛选指数
- 系统 SHALL 支持按类别筛选指数
- 系统 SHALL 支持按名称/代码搜索指数
- 系统 SHALL 支持分页展示指数列表

#### Scenario: 获取指数列表

- **GIVEN** 用户访问ETF选股页面
- **WHEN** 页面加载完成
- **THEN** 系统展示指数列表，包含代码、名称、市场、类别等信息
- **AND** 默认按代码排序

#### Scenario: 按市场筛选指数

- **GIVEN** 用户在ETF选股页面
- **WHEN** 用户选择市场筛选条件为"SSE"
- **THEN** 系统仅展示上交所发布的指数

#### Scenario: 搜索指数

- **GIVEN** 用户在ETF选股页面
- **WHEN** 用户输入搜索关键词"沪深300"
- **THEN** 系统展示名称或代码包含"沪深300"的指数

---

### Requirement: 指数详情展示

系统 SHALL 提供指数详细信息的展示功能。

- 系统 SHALL 展示指数的完整基础信息
- 系统 SHALL 展示指数的成分股列表及权重
- 系统 SHALL 展示成分股权重分布图表
- 系统 SHALL 展示前N大成分股的权重占比

#### Scenario: 查看指数详情

- **GIVEN** 用户在指数列表中
- **WHEN** 用户点击某指数的"详情"按钮
- **THEN** 系统弹出指数详情面板
- **AND** 展示指数基础信息（名称、市场、发布方、基期等）

#### Scenario: 查看成分股权重

- **GIVEN** 用户在指数详情面板中
- **WHEN** 用户切换到"成分股"标签
- **THEN** 系统展示该指数的所有成分股及权重
- **AND** 按权重降序排列
- **AND** 展示前10大成分股的权重占比统计

#### Scenario: 查看权重分布图

- **GIVEN** 用户在指数详情面板的成分股标签
- **WHEN** 页面加载完成
- **THEN** 系统展示成分股权重分布饼图
- **AND** 前10大成分股单独显示，其余归为"其他"

---

### Requirement: 指数技术因子展示

系统 SHALL 提供指数技术因子数据的展示功能。

- 系统 SHALL 展示指数的最新技术指标（MACD、KDJ、RSI等）
- 系统 SHALL 展示技术指标的趋势信号
- 系统 SHALL 支持查看历史技术指标数据

#### Scenario: 查看最新技术指标

- **GIVEN** 用户在指数详情面板中
- **WHEN** 用户切换到"技术指标"标签
- **THEN** 系统展示该指数的最新技术指标
- **AND** 包含MACD、KDJ、RSI等常用指标
- **AND** 展示指标的趋势信号（金叉/死叉、超买/超卖）

#### Scenario: 查看历史技术指标

- **GIVEN** 用户在技术指标标签中
- **WHEN** 用户选择日期范围
- **THEN** 系统展示该日期范围内的技术指标历史数据
- **AND** 以图表形式展示趋势变化

---

### Requirement: ETF量化分析

系统 SHALL 提供基于ETF特点的AI量化分析功能。

- 系统 SHALL 调用ETF Agent执行分析任务
- 系统 SHALL 分析指数的估值水平（加权PE/PB）
- 系统 SHALL 分析成分股集中度风险（CR10、HHI）
- 系统 SHALL 分析技术指标趋势
- 系统 SHALL 生成综合投资建议
- 系统 SHALL 明确标注"仅供参考，不构成投资建议"

#### Scenario: 触发AI分析

- **GIVEN** 用户在指数详情面板中
- **WHEN** 用户点击"AI分析"按钮
- **THEN** 系统调用ETF Agent的`execute()`方法
- **AND** 展示分析加载状态

#### Scenario: 展示分析结果

- **GIVEN** ETF Agent返回分析结果
- **WHEN** 分析完成
- **THEN** 系统展示结构化的分析报告
- **AND** 包含指数概况、估值分析、成分分析、技术分析、投资建议
- **AND** 底部显示风险提示"仅供参考，不构成投资建议"

#### Scenario: 估值分析内容

- **GIVEN** AI分析报告中的估值分析部分
- **WHEN** 用户查看估值分析
- **THEN** 系统展示基于成分股加权的PE/PB估值
- **AND** 显示有效覆盖率（有估值数据的成分股占比）
- **AND** 给出估值高低判断

#### Scenario: 成分分析内容

- **GIVEN** AI分析报告中的成分分析部分
- **WHEN** 用户查看成分分析
- **THEN** 系统展示前10大成分股及权重
- **AND** 计算CR10（前10大成分股占比）
- **AND** 计算HHI指数
- **AND** 给出集中度风险等级

#### Scenario: 技术分析内容

- **GIVEN** AI分析报告中的技术分析部分
- **WHEN** 用户查看技术分析
- **THEN** 系统展示MACD、KDJ、RSI等指标信号
- **AND** 给出趋势判断（看多/看空/震荡）

---

### Requirement: ETF筛选预设策略

系统 SHALL 提供ETF筛选的预设策略。

- 系统 SHALL 提供"宽基指数"预设（沪深300、中证500等）
- 系统 SHALL 提供"行业指数"预设
- 系统 SHALL 提供"主题指数"预设
- 系统 SHALL 支持用户一键应用预设策略

#### Scenario: 应用宽基指数预设

- **GIVEN** 用户在ETF选股页面
- **WHEN** 用户点击"宽基指数"预设标签
- **THEN** 系统筛选并展示沪深300、中证500、上证50等宽基指数

#### Scenario: 应用行业指数预设

- **GIVEN** 用户在ETF选股页面
- **WHEN** 用户点击"行业指数"预设标签
- **THEN** 系统筛选并展示各行业指数（金融、科技、消费等）

---

### Requirement: 指数对比功能

系统 SHALL 支持多个指数的对比分析。

- 系统 SHALL 支持选择最多3个指数进行对比
- 系统 SHALL 对比展示基础信息
- 系统 SHALL 对比展示成分股重叠度
- 系统 SHALL 对比展示技术指标

#### Scenario: 添加指数到对比

- **GIVEN** 用户在指数列表中
- **WHEN** 用户勾选某指数的"对比"复选框
- **THEN** 系统将该指数添加到对比列表
- **AND** 最多允许选择3个指数

#### Scenario: 查看对比结果

- **GIVEN** 用户已选择2个或以上指数进行对比
- **WHEN** 用户点击"开始对比"按钮
- **THEN** 系统展示对比面板
- **AND** 并列展示各指数的基础信息、成分股、技术指标

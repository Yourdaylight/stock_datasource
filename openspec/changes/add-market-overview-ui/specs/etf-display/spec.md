# ETF Display Capability

## Overview

提供ETF（交易型开放式指数基金）数据的展示能力，包括ETF列表、详情、行情图表等功能。

## ADDED Requirements

### Requirement: ETF列表展示

系统 SHALL 支持展示ETF列表，包含分页、筛选和搜索功能。

#### Scenario: 用户查看ETF列表

**Given** 用户访问ETF页面
**When** 页面加载完成
**Then** 系统显示ETF列表，包含以下字段：
  - ETF代码 (ts_code)
  - ETF简称 (csname)
  - 跟踪指数 (index_name)
  - 交易所 (exchange)
  - 管理人 (mgr_name)
  - 上市日期 (list_date)
  - 存续状态 (list_status)

#### Scenario: 用户按交易所筛选ETF

**Given** 用户在ETF列表页面
**When** 用户选择交易所筛选条件（如"SH"）
**Then** 系统仅显示该交易所的ETF
**And** 列表数量更新为筛选后的结果数

#### Scenario: 用户按ETF类型筛选

**Given** 用户在ETF列表页面
**When** 用户选择ETF类型筛选条件
**Then** 系统仅显示该类型的ETF

#### Scenario: 用户搜索ETF

**Given** 用户在ETF列表页面
**When** 用户输入搜索关键词（如"沪深300"）
**Then** 系统显示名称或跟踪指数包含关键词的ETF

---

### Requirement: ETF详情展示

系统 SHALL 支持展示ETF的详细信息。

#### Scenario: 用户查看ETF详情

**Given** 用户在ETF列表中点击某个ETF
**When** 详情弹窗打开
**Then** 系统显示ETF详细信息：
  - 基础信息（代码、名称、全称）
  - 跟踪指数信息（代码、名称）
  - 管理信息（管理人、托管人、管理费率）
  - 日期信息（设立日期、上市日期）
  - 状态信息（存续状态）

---

### Requirement: ETF行情展示

系统 SHALL 支持展示ETF的K线行情图表。

#### Scenario: 用户查看ETF K线

**Given** 用户在ETF详情页面
**When** 用户点击"行情"或"K线"标签
**Then** 系统显示ETF的K线图表，包含：
  - 日K线（OHLC）
  - 成交量柱状图
  - 默认显示最近3个月数据

#### Scenario: 用户切换复权类型

**Given** 用户在查看ETF K线
**When** 用户选择复权类型（前复权/后复权/不复权）
**Then** 系统重新计算并显示对应的复权K线

#### Scenario: 用户调整日期范围

**Given** 用户在查看ETF K线
**When** 用户选择新的日期范围
**Then** 系统显示该日期范围内的K线数据

---

### Requirement: ETF后端API

系统 MUST 提供ETF数据的RESTful API接口。

#### Scenario: 获取ETF列表API

**Given** 客户端请求 `GET /api/etf/etfs`
**When** 请求包含可选参数：
  - `exchange`: 交易所筛选
  - `etf_type`: ETF类型筛选
  - `keyword`: 搜索关键词
  - `page`: 页码（默认1）
  - `page_size`: 每页数量（默认20）
**Then** 系统返回ETF列表响应：
```json
{
  "items": [...],
  "total": 500,
  "page": 1,
  "page_size": 20
}
```

#### Scenario: 获取ETF详情API

**Given** 客户端请求 `GET /api/etf/etfs/{ts_code}`
**When** ts_code 为有效的ETF代码
**Then** 系统返回ETF详细信息

#### Scenario: 获取ETF K线API

**Given** 客户端请求 `GET /api/etf/etfs/{ts_code}/kline`
**When** 请求包含参数：
  - `start_date`: 开始日期
  - `end_date`: 结束日期
  - `adjust`: 复权类型（qfq/hfq/none）
**Then** 系统返回K线数据列表

---

### Requirement: ETF AI分析

系统 SHALL 支持对ETF进行AI量化分析，支持多轮对话问答。

#### Scenario: 用户进行ETF AI分析

**Given** 用户在ETF详情页面
**When** 用户点击"AI分析"按钮
**Then** 系统打开AI分析面板
**And** 显示快速分析结果（无AI）
**And** 提供AI深度分析入口

#### Scenario: 用户与ETF AI对话

**Given** 用户在ETF AI分析面板
**When** 用户输入问题（如"这只ETF的跟踪误差如何？"）
**Then** 系统调用ETF Agent进行分析
**And** 返回基于ETF数据的智能回答
**And** 保持对话上下文

#### Scenario: 用户查看ETF快速分析

**Given** 用户在ETF详情页面
**When** 用户点击"快速分析"
**Then** 系统显示ETF关键指标：
  - 近期涨跌幅
  - 成交量变化
  - 跟踪指数对比
  - 技术指标信号

#### Scenario: ETF AI分析API

**Given** 客户端请求 `POST /api/etf/analyze`
**When** 请求包含参数：
  - `ts_code`: ETF代码
  - `question`: 用户问题（可选）
  - `user_id`: 用户ID
  - `clear_history`: 是否清除历史
**Then** 系统返回AI分析结果：
```json
{
  "ts_code": "510300.SH",
  "question": "跟踪误差如何？",
  "response": "...",
  "success": true,
  "session_id": "xxx",
  "history_length": 3
}
```

---

## Cross-References

- 依赖：ETF数据插件（tushare_etf_basic, tushare_etf_fund_daily, tushare_etf_fund_adj）
- 相关：market-overview（热门ETF展示）
- 相关：index-screener（指数选股，UI模式参考）

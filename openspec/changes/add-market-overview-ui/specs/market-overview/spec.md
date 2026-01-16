# Market Overview Capability

## Overview

提供每日市场概览功能，帮助用户快速了解当日市场整体表现，包括主要指数涨跌、热门ETF、市场情绪等。

## ADDED Requirements

### Requirement: 主要指数涨跌展示

系统 SHALL 在行情分析页面展示主要指数的当日涨跌情况。

#### Scenario: 用户查看主要指数涨跌

**Given** 用户访问行情分析页面
**When** 页面加载完成
**Then** 系统显示主要指数卡片，包含：
  - 沪深300 (000300.SH)
  - 中证500 (000905.SH)
  - 上证50 (000016.SH)
  - 创业板指 (399006.SZ)
  - 中证1000 (000852.SH)
  - 上证指数 (000001.SH)
**And** 每个指数显示：
  - 指数名称
  - 最新点位
  - 涨跌幅（带颜色标识）
  - 涨跌额

#### Scenario: 指数涨跌颜色标识

**Given** 系统显示指数涨跌
**When** 指数涨跌幅为正
**Then** 显示红色（上涨）
**When** 指数涨跌幅为负
**Then** 显示绿色（下跌）
**When** 指数涨跌幅为零
**Then** 显示灰色（平盘）

---

### Requirement: 热门ETF展示

系统 SHALL 展示当日热门ETF列表。

#### Scenario: 用户查看热门ETF（按成交额）

**Given** 用户在行情分析页面
**When** 用户查看热门ETF区域
**Then** 系统显示成交额Top10的ETF列表，包含：
  - ETF代码
  - ETF名称
  - 最新价
  - 涨跌幅
  - 成交额

#### Scenario: 用户切换热门ETF排序

**Given** 用户在查看热门ETF
**When** 用户切换排序方式为"涨幅榜"
**Then** 系统显示涨幅Top10的ETF
**When** 用户切换排序方式为"跌幅榜"
**Then** 系统显示跌幅Top10的ETF

#### Scenario: 用户点击热门ETF

**Given** 用户在热门ETF列表中
**When** 用户点击某个ETF
**Then** 系统跳转到该ETF的详情/行情页面

---

### Requirement: 市场统计展示

系统 SHALL 展示当日市场整体统计数据。

#### Scenario: 用户查看市场统计

**Given** 用户在行情分析页面
**When** 页面加载完成
**Then** 系统显示市场统计信息：
  - 两市成交额（亿元）
  - 上涨家数
  - 下跌家数
  - 平盘家数

---

### Requirement: 指数技术信号展示

系统 SHALL 展示主要指数的技术分析信号（P2优先级）。

#### Scenario: 用户查看指数技术信号

**Given** 用户在行情分析页面
**When** 用户展开指数详情
**Then** 系统显示技术信号标签：
  - MACD状态（金叉/死叉/震荡）
  - KDJ状态（超买/超卖/中性）
  - 连涨/连跌天数

---

### Requirement: 行情类型切换

系统 SHALL 支持在行情分析页面切换不同类型的证券行情。

#### Scenario: 用户切换行情类型

**Given** 用户在行情分析页面
**When** 用户选择行情类型（股票/ETF/指数）
**Then** 搜索框和K线图切换为对应类型
**And** 搜索结果仅显示该类型的证券

#### Scenario: 用户从快捷入口进入行情

**Given** 用户在行情分析页面
**When** 用户点击主要指数卡片
**Then** 系统自动切换到指数行情
**And** 显示该指数的K线图

---

### Requirement: 每日概览后端API

系统 MUST 提供每日概览数据的RESTful API接口。

#### Scenario: 获取每日概览API

**Given** 客户端请求 `GET /api/overview/daily`
**When** 请求可选参数 `date`（默认当日）
**Then** 系统返回每日概览数据：
```json
{
  "date": "2026-01-13",
  "indices": [
    {
      "ts_code": "000300.SH",
      "name": "沪深300",
      "close": 3500.00,
      "pct_chg": 1.25,
      "change": 43.21
    }
  ],
  "market_stats": {
    "total_amount": 10000.5,
    "up_count": 2500,
    "down_count": 1800,
    "flat_count": 200
  }
}
```

#### Scenario: 获取热门ETF API

**Given** 客户端请求 `GET /api/overview/hot-etfs`
**When** 请求包含参数：
  - `sort_by`: 排序字段（amount/pct_chg）
  - `limit`: 返回数量（默认10）
**Then** 系统返回热门ETF列表

---

### Requirement: 指数行情API扩展

系统 MUST 扩展指数模块，支持获取指数日线和K线数据。

#### Scenario: 获取指数日线API

**Given** 客户端请求 `GET /api/index/indices/{ts_code}/daily`
**When** 请求包含参数：
  - `start_date`: 开始日期
  - `end_date`: 结束日期
  - `limit`: 返回数量
**Then** 系统返回指数日线数据列表

#### Scenario: 获取指数K线API

**Given** 客户端请求 `GET /api/index/indices/{ts_code}/kline`
**When** 请求包含日期范围参数
**Then** 系统返回指数K线数据（OHLCV）

---

### Requirement: 市场AI问答

系统 SHALL 支持基于每日概览数据的AI智能问答，支持多轮对话。

#### Scenario: 用户进行市场AI问答

**Given** 用户在行情分析页面
**When** 用户点击"AI问答"按钮
**Then** 系统打开市场AI问答面板
**And** 显示预设问题快捷入口

#### Scenario: 用户询问市场整体情况

**Given** 用户在市场AI问答面板
**When** 用户输入问题（如"今日市场整体表现如何？"）
**Then** 系统调用Market Overview Agent进行分析
**And** 返回基于当日数据的智能回答
**And** 包含主要指数涨跌、涨跌家数等关键信息

#### Scenario: 用户询问板块表现

**Given** 用户在市场AI问答面板
**When** 用户询问"哪些板块表现最好？"
**Then** 系统分析当日板块数据
**And** 返回板块涨跌排名和分析

#### Scenario: 用户询问ETF推荐

**Given** 用户在市场AI问答面板
**When** 用户询问"有哪些值得关注的ETF？"
**Then** 系统分析热门ETF数据
**And** 返回ETF推荐和理由

#### Scenario: 预设问题快捷入口

**Given** 用户在市场AI问答面板
**When** 面板加载完成
**Then** 系统显示预设问题按钮：
  - "今日市场整体表现如何？"
  - "哪些板块表现最好？"
  - "有哪些值得关注的ETF？"
  - "市场情绪如何？"

#### Scenario: 市场AI分析API

**Given** 客户端请求 `POST /api/overview/analyze`
**When** 请求包含参数：
  - `question`: 用户问题
  - `user_id`: 用户ID
  - `date`: 分析日期（可选，默认当日）
  - `clear_history`: 是否清除历史
**Then** 系统返回AI分析结果：
```json
{
  "date": "2026-01-13",
  "question": "今日市场整体表现如何？",
  "response": "...",
  "success": true,
  "session_id": "xxx",
  "history_length": 2
}
```

---

## Cross-References

- 依赖：指数数据插件（tushare_index_basic, tushare_idx_factor_pro）
- 依赖：ETF数据插件（tushare_etf_fund_daily）
- 相关：etf-display（ETF展示能力）
- 相关：index-screener（指数选股）

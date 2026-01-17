# Market Overview Capability

## Overview

提供每日市场概览功能，帮助用户快速了解当日市场整体表现，包括主要指数涨跌、热门ETF、市场情绪、**同花顺板块指数热力图**等丰富的可视化信息。

## 界面布局设计

行情分析页面采用**仪表盘式布局**，分为以下区域（面向Web端）：

```
┌─────────────────────────────────────────────────────────────────────┐
│ 【顶部】主要指数快照 (一排横向排列：沪深300/上证50/创业板指/中证500等)    │
├─────────────────────────────────────────────────────────────────────┤
│ 【第二行】三列布局                                                     │
│ ┌──────────────────┬──────────────────┬──────────────────┐          │
│ │  市场情绪仪表盘    │   板块热力图      │   热门ETF榜       │          │
│ │  (涨跌比/涨停跌停) │   (行业+概念)     │   (成交/涨跌榜)   │          │
│ └──────────────────┴──────────────────┴──────────────────┘          │
├─────────────────────────────────────────────────────────────────────┤
│ 【主内容区】左右两栏布局                                               │
│ ┌────────────────────────────────┬──────────────────────────────────┐│
│ │      板块涨跌排行 (7/12)        │       指数走势对比 (5/12)        ││
│ │  (涨幅榜/跌幅榜/换手率排行)      │    (多指数叠加走势对比图)        ││
│ └────────────────────────────────┴──────────────────────────────────┘│
│                                                       ┌─────────────┤
│                                                       │ AI助手 💬   │
│                                                       │ (悬浮按钮)  │
│                                                       └─────────────┤
└─────────────────────────────────────────────────────────────────────┘

【AI问答悬浮窗】（点击悬浮按钮打开，复用智能对话组件）
┌──────────────────────────────────────┐
│ 行情分析助手                     [×] │
├──────────────────────────────────────┤
│ 推荐问题：                            │
│ • 今日市场整体表现如何？              │
│ • 哪些板块表现最强？                  │
│ • 今日热门ETF有哪些？                 │
│ • 当前市场情绪如何？                  │
├──────────────────────────────────────┤
│ (对话区域 - 复用智能对话界面)         │
└──────────────────────────────────────┘
```

**注意**：Dashboard 不包含 K线图表，用户需点击具体板块/指数后在详情弹窗中查看K线。

## ADDED Requirements

### Requirement: 同花顺板块指数热力图

系统 SHALL 展示同花顺板块指数的热力图，帮助用户快速识别强势/弱势板块。

#### Scenario: 用户查看行业板块热力图

**Given** 用户在行情分析页面
**When** 页面加载完成
**Then** 系统显示行业板块热力图（type=I），包含：
  - 板块名称
  - 涨跌幅（颜色深浅表示强弱）
  - 成分股数量
  - 点击可展开详情

#### Scenario: 用户切换板块类型

**Given** 用户在查看板块热力图
**When** 用户切换类型为"概念板块"
**Then** 系统显示概念板块热力图（type=N）
**When** 用户切换类型为"地域板块"
**Then** 系统显示地域板块热力图（type=R）

#### Scenario: 热力图颜色映射

**Given** 系统渲染板块热力图
**When** 板块涨幅 > 3%
**Then** 显示深红色
**When** 板块涨幅在 1%~3%
**Then** 显示浅红色
**When** 板块涨幅在 -1%~1%
**Then** 显示灰色
**When** 板块跌幅在 1%~3%
**Then** 显示浅绿色
**When** 板块跌幅 > 3%
**Then** 显示深绿色

#### Scenario: 用户点击板块查看详情

**Given** 用户在板块热力图中
**When** 用户点击某个板块
**Then** 系统弹出板块详情弹窗，显示：
  - 板块K线走势（近30日）
  - 板块涨跌幅排名
  - 板块成分股列表（可选）

---

### Requirement: 板块涨跌排行榜

系统 SHALL 提供板块涨跌排行榜，支持按类型和时间维度筛选。

#### Scenario: 用户查看今日板块涨幅榜

**Given** 用户切换到"板块涨跌排行"标签
**When** 默认加载
**Then** 系统显示今日涨幅Top20板块列表：
  - 排名
  - 板块名称
  - 涨跌幅
  - 成分股数量
  - 领涨股（可选）

#### Scenario: 用户切换排行榜类型

**Given** 用户在板块排行榜
**When** 用户切换为"跌幅榜"
**Then** 系统显示今日跌幅Top20板块
**When** 用户切换为"换手率榜"
**Then** 系统显示今日换手率Top20板块

#### Scenario: 用户筛选板块类型

**Given** 用户在板块排行榜
**When** 用户选择"行业板块"
**Then** 仅显示行业板块（type=I）排名
**When** 用户选择"概念板块"
**Then** 仅显示概念板块（type=N）排名

---

### Requirement: 指数走势对比图

系统 SHALL 提供多指数走势对比功能。

#### Scenario: 用户查看指数对比图

**Given** 用户切换到"指数走势对比"标签
**When** 默认加载
**Then** 系统显示主要指数（沪深300、上证50、创业板指）的叠加走势图
**And** 使用归一化百分比展示，便于对比

#### Scenario: 用户添加/移除对比指数

**Given** 用户在指数对比图
**When** 用户搜索并添加"新能源汽车"板块指数
**Then** 图表中新增该指数走势线
**When** 用户点击移除某个指数
**Then** 图表中移除该指数走势线

#### Scenario: 用户调整时间范围

**Given** 用户在指数对比图
**When** 用户选择"近7日"
**Then** 图表显示近7个交易日数据
**When** 用户选择"近30日"
**Then** 图表显示近30个交易日数据
**When** 用户选择"近90日"
**Then** 图表显示近90个交易日数据

---

### Requirement: 同花顺板块指数后端API

系统 MUST 提供同花顺板块指数的RESTful API接口。

#### Scenario: 获取板块指数列表API

**Given** 客户端请求 `GET /api/ths-index/list`
**When** 请求包含参数：
  - `exchange`: 市场类型（A/HK/US，默认A）
  - `type`: 指数类型（N-概念/I-行业/R-地域，可选）
  - `limit`: 返回数量
**Then** 系统返回板块指数列表：
```json
{
  "data": [
    {
      "ts_code": "885431.TI",
      "name": "新能源汽车",
      "count": 1004,
      "exchange": "A",
      "type": "N",
      "list_date": "2019-04-16"
    }
  ],
  "total": 1724
}
```

#### Scenario: 获取板块指数行情API

**Given** 客户端请求 `GET /api/ths-index/{ts_code}/daily`
**When** 请求包含参数：
  - `start_date`: 开始日期
  - `end_date`: 结束日期
**Then** 系统返回板块指数日线数据：
```json
{
  "ts_code": "885431.TI",
  "name": "新能源汽车",
  "data": [
    {
      "trade_date": "2026-01-10",
      "open": 1234.56,
      "high": 1250.00,
      "low": 1220.00,
      "close": 1245.00,
      "pct_change": 1.25,
      "vol": 12345678,
      "turnover_rate": 2.5
    }
  ]
}
```

#### Scenario: 获取板块涨跌排行API

**Given** 客户端请求 `GET /api/ths-index/ranking`
**When** 请求包含参数：
  - `date`: 交易日期（默认最新）
  - `type`: 指数类型（可选）
  - `sort_by`: 排序字段（pct_change/vol/turnover_rate）
  - `order`: 排序方向（desc/asc）
  - `limit`: 返回数量（默认20）
**Then** 系统返回板块排名列表

#### Scenario: 搜索板块指数API

**Given** 客户端请求 `GET /api/ths-index/search`
**When** 请求包含参数：
  - `keyword`: 搜索关键词
  - `limit`: 返回数量
**Then** 系统返回匹配的板块指数列表

---

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

### Requirement: 市场AI问答悬浮窗

系统 SHALL 提供AI问答悬浮窗，复用智能对话组件，支持行情相关的预设问题。

#### Scenario: 用户打开AI问答悬浮窗

**Given** 用户在行情分析页面
**When** 用户点击右下角AI助手悬浮按钮
**Then** 系统弹出AI问答悬浮窗
**And** 悬浮窗复用智能对话组件界面
**And** 显示行情分析相关的预设问题

#### Scenario: 行情分析预设问题

**Given** AI问答悬浮窗打开
**When** 悬浮窗加载完成
**Then** 系统显示以下预设问题快捷入口：
  - "今日市场整体表现如何？"
  - "哪些板块表现最强？"
  - "今日热门ETF有哪些？"
  - "当前市场情绪如何？"
  - "今日涨停板有多少家？"
  - "哪些行业板块领涨？"

#### Scenario: 用户点击预设问题

**Given** 用户在AI问答悬浮窗
**When** 用户点击预设问题按钮
**Then** 系统自动发送该问题
**And** 调用Market Overview Agent进行分析
**And** 返回基于当日行情数据的智能回答

#### Scenario: 用户自由提问

**Given** 用户在AI问答悬浮窗
**When** 用户输入自定义问题
**Then** 系统调用Market Overview Agent进行分析
**And** 支持多轮对话，保持上下文

#### Scenario: 悬浮窗位置与交互

**Given** AI问答悬浮窗打开
**When** 用户在行情分析页面操作
**Then** 悬浮窗不遮挡主要内容区域
**And** 用户可拖动悬浮窗位置
**And** 用户可最小化/关闭悬浮窗

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
- **依赖：同花顺板块指数元数据（tushare_ths_index）** ✅ 已实现
- **依赖：同花顺板块指数日线（tushare_ths_daily）** ✅ 已实现
- 相关：etf-display（ETF展示能力）
- 相关：index-screener（指数选股）

## 数据源说明

### 同花顺板块指数数据

| 插件名 | 表名 | 数据内容 | 更新频率 |
|--------|------|----------|----------|
| `tushare_ths_index` | `ods_ths_index` | 板块指数元数据（1,724条） | 每周 |
| `tushare_ths_daily` | `ods_ths_daily` | 板块指数日线行情 | 每日 |

**板块类型分布（A股）**：
- 行业指数（I）：594 个
- 概念指数（N）：408 个
- 特色指数（S）：124 个
- 宽基指数（BB）：46 个
- 地域指数（R）：33 个
- 风格指数（ST）：21 个
- 主题指数（TH）：10 个

### Service 方法

**TuShareTHSIndexService**：
- `get_ths_index_list(exchange, index_type, limit)` - 获取板块列表
- `get_ths_index_by_code(ts_code)` - 按代码查询
- `search_ths_index_by_name(keyword, limit)` - 按名称搜索
- `get_ths_index_stats()` - 获取统计信息

**TuShareTHSDailyService**：
- `get_ths_daily_data(ts_code, start_date, end_date)` - 获取日线数据
- `get_latest_ths_daily(ts_codes, limit)` - 获取最新行情
- `get_ths_daily_stats(ts_code, start_date, end_date)` - 获取统计信息

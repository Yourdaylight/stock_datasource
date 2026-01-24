# Capability: 后端 API 增强

## ADDED Requirements

### Requirement: ETF 管理人列表 API

系统 MUST 提供获取 ETF 管理人列表的 API。

**验收标准**：
- API 端点：`GET /api/etf/managers`
- 返回格式：`[{ value: string, label: string, count: number }]`
- 按 ETF 数量降序排序
- 排除空值管理人

#### Scenario: 获取管理人列表

**Given** 前端需要加载管理人筛选选项
**When** 调用 `GET /api/etf/managers`
**Then** 返回所有管理人列表
**And** 每个管理人包含名称和对应 ETF 数量

### Requirement: ETF 跟踪指数列表 API

系统 MUST 提供获取 ETF 跟踪指数列表的 API。

**验收标准**：
- API 端点：`GET /api/etf/tracking-indices`
- 返回格式：`[{ value: string, label: string, count: number }]`
- value 为指数代码，label 为指数名称
- 按 ETF 数量降序排序

#### Scenario: 获取跟踪指数列表

**Given** 前端需要加载跟踪指数筛选选项
**When** 调用 `GET /api/etf/tracking-indices`
**Then** 返回所有跟踪指数列表
**And** 每个指数包含代码、名称和跟踪该指数的 ETF 数量

### Requirement: ETF 可用交易日期 API

系统 MUST 提供获取 ETF 可用交易日期列表的 API。

**验收标准**：
- API 端点：`GET /api/etf/trade-dates`
- 查询参数：`limit` (可选，默认30)
- 返回格式：`["20260125", "20260124", ...]`
- 按日期降序排序（最新日期在前）

#### Scenario: 获取可用交易日期

**Given** 前端需要加载日期选择器选项
**When** 调用 `GET /api/etf/trade-dates?limit=30`
**Then** 返回最近30个有数据的交易日期
**And** 日期按降序排列

### Requirement: ETF 列表扩展筛选参数

系统 MUST 扩展 ETF 列表 API 支持新的筛选参数。

**验收标准**：
- `trade_date`: 交易日期筛选（YYYYMMDD 格式）
- `manager`: 管理人筛选
- `tracking_index`: 跟踪指数代码筛选
- `fee_min` / `fee_max`: 管理费率区间（百分比，如 0.2 表示 0.2%）
- `amount_min`: 最小成交额（万元）
- `pct_chg_min` / `pct_chg_max`: 涨跌幅区间（百分比）

#### Scenario: 按多条件筛选 ETF

**Given** 前端需要按多条件筛选 ETF
**When** 调用 `GET /api/etf/etfs?trade_date=20260120&manager=华夏基金&pct_chg_min=0`
**Then** 返回 2026-01-20 当日，华夏基金管理的，涨幅为正的 ETF 列表

### Requirement: 指数发布机构列表 API

系统 MUST 提供获取指数发布机构列表的 API。

**验收标准**：
- API 端点：`GET /api/index/publishers`
- 返回格式：`[{ value: string, label: string, count: number }]`
- 按指数数量降序排序

#### Scenario: 获取发布机构列表

**Given** 前端需要加载发布机构筛选选项
**When** 调用 `GET /api/index/publishers`
**Then** 返回所有发布机构列表
**And** 每个机构包含名称和对应指数数量

### Requirement: 指数可用交易日期 API

系统 MUST 提供获取指数可用交易日期列表的 API。

**验收标准**：
- API 端点：`GET /api/index/trade-dates`
- 查询参数：`limit` (可选，默认30)
- 返回格式：`["20260125", "20260124", ...]`
- 按日期降序排序

#### Scenario: 获取可用交易日期

**Given** 前端需要加载日期选择器选项
**When** 调用 `GET /api/index/trade-dates?limit=30`
**Then** 返回最近30个有数据的交易日期

### Requirement: 指数列表扩展筛选参数

系统 MUST 扩展指数列表 API 支持新的筛选参数。

**验收标准**：
- `trade_date`: 交易日期筛选（YYYYMMDD 格式）
- `publisher`: 发布机构筛选
- `pct_chg_min` / `pct_chg_max`: 涨跌幅区间（百分比）

#### Scenario: 按多条件筛选指数

**Given** 前端需要按多条件筛选指数
**When** 调用 `GET /api/index/indices?trade_date=20260120&publisher=中证&pct_chg_min=0`
**Then** 返回 2026-01-20 当日，中证发布的，涨幅为正的指数列表

## ADDED Requirements

### Requirement: 指数周线行情数据采集
系统 SHALL 提供指数周线行情数据的采集能力，通过 TuShare Pro 的 `index_weekly` 接口获取指数周K线数据。

#### Scenario: 按日期获取指数周线数据
- **WHEN** 用户指定交易日期调用 index_weekly 插件
- **THEN** 系统返回该日期对应周的所有指数周线行情数据
- **AND** 数据包含 ts_code、trade_date、open、high、low、close、vol、amount 等字段

#### Scenario: 按指数代码获取周线数据
- **WHEN** 用户指定指数代码和日期范围
- **THEN** 系统返回该指数在指定范围内的周线行情数据

---

### Requirement: 指数月线行情数据采集
系统 SHALL 提供指数月线行情数据的采集能力，通过 TuShare Pro 的 `index_monthly` 接口获取指数月K线数据。

#### Scenario: 按日期获取指数月线数据
- **WHEN** 用户指定交易日期调用 index_monthly 插件
- **THEN** 系统返回该日期对应月的所有指数月线行情数据

#### Scenario: 按指数代码获取月线数据
- **WHEN** 用户指定指数代码和日期范围
- **THEN** 系统返回该指数在指定范围内的月线行情数据

---

### Requirement: 国际指数行情数据采集
系统 SHALL 提供国际主要指数行情数据的采集能力，通过 TuShare Pro 的 `index_global` 接口获取全球指数日线数据。

#### Scenario: 获取国际指数日线数据
- **WHEN** 用户指定交易日期调用 index_global 插件
- **THEN** 系统返回全球主要指数（道琼斯、纳斯达克、标普500、日经225等）的日线行情

#### Scenario: 按指数代码查询国际指数
- **WHEN** 用户指定国际指数代码
- **THEN** 系统返回该指数的历史行情数据

---

### Requirement: 大盘指数每日指标数据采集
系统 SHALL 提供大盘指数每日指标数据的采集能力，通过 TuShare Pro 的 `index_dailybasic` 接口获取指数估值和流动性指标。

#### Scenario: 获取指数每日指标
- **WHEN** 用户指定交易日期调用 index_dailybasic 插件
- **THEN** 系统返回各主要指数的换手率、市盈率、市净率、总市值等指标

#### Scenario: 按指数代码查询每日指标
- **WHEN** 用户指定指数代码和日期范围
- **THEN** 系统返回该指数的历史每日指标数据

---

### Requirement: 申万行业分类数据采集
系统 SHALL 提供申万行业分类数据的采集能力，通过 TuShare Pro 的 `index_classify` 接口获取申万一级/二级/三级行业分类。

#### Scenario: 获取申万行业分类列表
- **WHEN** 用户调用 index_classify 插件并指定行业层级
- **THEN** 系统返回对应层级的所有行业分类信息
- **AND** 包含行业代码、行业名称、指数代码、是否发布指数等字段

#### Scenario: 支持2021版申万分类
- **WHEN** 用户查询申万行业分类
- **THEN** 系统返回最新的2021版31个一级行业分类

---

### Requirement: 指数成分股数据采集
系统 SHALL 提供指数成分股数据的采集能力，通过 TuShare Pro 的 `index_member` 接口获取指数成分股列表。

#### Scenario: 获取指数当前成分股
- **WHEN** 用户指定指数代码调用 index_member 插件
- **THEN** 系统返回该指数的当前成分股列表
- **AND** 包含成分股代码、纳入日期、是否最新等字段

#### Scenario: 获取指数历史成分变动
- **WHEN** 用户查询指数成分股并包含历史数据
- **THEN** 系统返回包含已剔除成分股的完整变动记录

---

### Requirement: 申万行业指数日线行情数据采集
系统 SHALL 提供申万行业指数日线行情数据的采集能力，通过 TuShare Pro 的 `sw_daily` 接口获取申万行业指数日K线。

#### Scenario: 获取申万行业指数日线
- **WHEN** 用户指定交易日期调用 sw_daily 插件
- **THEN** 系统返回所有申万行业指数的日线行情数据

#### Scenario: 按行业代码查询日线
- **WHEN** 用户指定申万行业指数代码和日期范围
- **THEN** 系统返回该行业指数的历史日线数据

---

### Requirement: 中信行业指数日线行情数据采集
系统 SHALL 提供中信行业指数日线行情数据的采集能力，通过 TuShare Pro 的 `ci_daily` 接口获取中信行业指数日K线。

#### Scenario: 获取中信行业指数日线
- **WHEN** 用户指定交易日期调用 ci_daily 插件
- **THEN** 系统返回所有中信行业指数的日线行情数据

#### Scenario: 按行业代码查询日线
- **WHEN** 用户指定中信行业指数代码和日期范围
- **THEN** 系统返回该行业指数的历史日线数据

---

### Requirement: 同花顺概念成分股数据采集
系统 SHALL 提供同花顺概念成分股数据的采集能力，通过 TuShare Pro 的 `ths_member` 接口获取同花顺概念板块成分股。

#### Scenario: 获取同花顺概念成分股
- **WHEN** 用户指定同花顺概念代码调用 ths_member 插件
- **THEN** 系统返回该概念的所有成分股列表
- **AND** 包含股票代码、股票名称、权重等字段

#### Scenario: 支持多概念查询
- **WHEN** 用户提供多个概念代码
- **THEN** 系统返回所有指定概念的成分股数据

---

### Requirement: 深圳市场每日交易概况数据采集
系统 SHALL 提供深圳市场每日交易概况数据的采集能力，通过 TuShare Pro 的 `sz_daily_info` 接口获取深市每日统计。

#### Scenario: 获取深市每日交易概况
- **WHEN** 用户指定交易日期调用 sz_daily_info 插件
- **THEN** 系统返回深圳市场的每日成交量、成交额、涨跌家数等统计数据

#### Scenario: 按日期范围查询
- **WHEN** 用户指定日期范围
- **THEN** 系统返回指定范围内的深市交易概况数据

---

### Requirement: 每日全市场交易统计数据采集
系统 SHALL 提供每日全市场交易统计数据的采集能力，通过 TuShare Pro 的 `daily_info` 接口获取A股市场每日统计。

#### Scenario: 获取全市场每日统计
- **WHEN** 用户指定交易日期调用 daily_info 插件
- **THEN** 系统返回A股市场的每日统计数据（成交量、成交额、涨跌停数量等）

#### Scenario: 按交易所分类查询
- **WHEN** 用户指定交易所代码
- **THEN** 系统返回该交易所的每日统计数据

---

### Requirement: 中证指数估值数据采集
系统 SHALL 提供中证指数估值数据的采集能力，通过 TuShare Pro 的 `index_e` 接口获取中证指数PE/PB等估值指标。

#### Scenario: 获取指数估值数据
- **WHEN** 用户指定交易日期调用 index_e 插件
- **THEN** 系统返回中证主要指数的估值数据（PE、PB、股息率等）

#### Scenario: 按指数代码查询估值历史
- **WHEN** 用户指定指数代码和日期范围
- **THEN** 系统返回该指数的历史估值数据

---

### Requirement: 管理层薪酬和持股数据采集
系统 SHALL 提供管理层薪酬和持股数据的采集能力，通过 TuShare Pro 的 `stk_rewards` 接口获取上市公司高管薪酬及持股信息。

#### Scenario: 获取公司高管薪酬持股
- **WHEN** 用户指定股票代码调用 stk_rewards 插件
- **THEN** 系统返回该公司高管的薪酬和持股数据

#### Scenario: 按年度查询
- **WHEN** 用户指定股票代码和报告年度
- **THEN** 系统返回该年度的高管薪酬持股明细

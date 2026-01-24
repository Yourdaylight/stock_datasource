# Change: 新增扩展指数数据源插件

## Why

当前系统已有基础指数数据插件（index_daily、index_basic、index_weight、ths_index、ths_daily），但缺少以下关键数据源：

1. **多周期指数行情**：缺乏指数周线、月线行情数据，无法支持中长期趋势分析
2. **全球指数数据**：无法获取国际主要指数行情（道琼斯、纳斯达克、日经等）
3. **行业分类体系**：缺少申万行业分类、中信行业分类等完整的行业分类数据
4. **行业成分股**：无法获取申万/中信行业指数成分股及权重
5. **指数估值数据**：缺少中证指数的PE、PB等估值指标
6. **市场统计数据**：缺少每日全市场交易统计、深圳市场交易概况
7. **同花顺概念数据**：缺少同花顺概念板块成分股
8. **其他数据**：管理层薪酬持股、指数成分股变动等

## What Changes

### 新增插件（共15个）

#### 指数行情类
- **tushare_index_weekly**：指数周线行情（doc_id: 94）
  - 接口：`index_weekly`
  - 数据：指数周K线行情数据（开高低收、成交量）
  - 频率：每周更新

- **tushare_index_monthly**：指数月线行情（doc_id: 95）
  - 接口：`index_monthly`
  - 数据：指数月K线行情数据
  - 频率：每月更新

- **tushare_index_global**：国际指数行情（doc_id: 403）
  - 接口：`index_global`
  - 数据：全球主要指数日线行情
  - 频率：每日更新

- **tushare_index_dailybasic**：大盘指数每日指标（doc_id: 96）
  - 接口：`index_dailybasic`
  - 数据：换手率、市盈率、市净率、总市值等
  - 频率：每日更新

#### 行业分类与成分类
- **tushare_index_classify**：申万行业分类（doc_id: 171）
  - 接口：`index_classify`
  - 数据：申万一级/二级/三级行业分类列表
  - 频率：一次性全量，定期更新

- **tushare_index_member**：指数成分股（doc_id: 211）
  - 接口：`index_member`
  - 数据：指数成分股列表及纳入/剔除日期
  - 频率：按需查询

- **tushare_sw_daily**：申万行业指数日线行情（doc_id: 181）
  - 接口：`sw_daily`
  - 数据：申万行业指数日K线行情
  - 频率：每日更新

- **tushare_ci_daily**：中信行业指数日线行情（doc_id: 335）
  - 接口：`ci_daily`
  - 数据：中信行业指数日K线行情
  - 频率：每日更新

#### 同花顺概念类
- **tushare_ths_member**：同花顺概念成分（doc_id: 308）
  - 接口：`ths_member`
  - 数据：同花顺概念板块成分股列表
  - 频率：按需查询

#### 市场统计类
- **tushare_sz_daily_info**：深圳市场每日交易概况（doc_id: 128）
  - 接口：`sz_daily_info`
  - 数据：深市每日成交量、成交额、涨跌家数等
  - 频率：每日更新

- **tushare_daily_info**：每日全市场交易统计（doc_id: 327）
  - 接口：`daily_info`
  - 数据：全市场每日统计数据
  - 频率：每日更新

#### 估值与其他类
- **tushare_index_e**：中证指数估值（doc_id: 268）
  - 接口：`index_e` / `index_value`
  - 数据：中证指数PE、PB、股息率等估值指标
  - 频率：每日更新

- **tushare_stk_rewards**：管理层薪酬和持股（doc_id: 215）
  - 接口：`stk_rewards`
  - 数据：高管薪酬、持股数量及变动
  - 频率：季度/年度更新

### 插件结构
每个插件包含以下文件：
- `plugin.py` - 插件主类（继承 BasePlugin）
- `extractor.py` - TuShare API 调用器
- `config.json` - 插件配置
- `schema.json` - ClickHouse 表结构定义
- `__init__.py` - 插件注册
- `service.py` - 数据查询 SDK

## Impact

### Affected Specs
- extended-index-data-sources（新增）

### Affected Code
新增插件目录：
- `src/stock_datasource/plugins/tushare_index_weekly/`
- `src/stock_datasource/plugins/tushare_index_monthly/`
- `src/stock_datasource/plugins/tushare_index_global/`
- `src/stock_datasource/plugins/tushare_index_dailybasic/`
- `src/stock_datasource/plugins/tushare_index_classify/`
- `src/stock_datasource/plugins/tushare_index_member/`
- `src/stock_datasource/plugins/tushare_sw_daily/`
- `src/stock_datasource/plugins/tushare_ci_daily/`
- `src/stock_datasource/plugins/tushare_ths_member/`
- `src/stock_datasource/plugins/tushare_sz_daily_info/`
- `src/stock_datasource/plugins/tushare_daily_info/`
- `src/stock_datasource/plugins/tushare_index_e/`
- `src/stock_datasource/plugins/tushare_stk_rewards/`

### Dependencies
- 依赖 TuShare Pro API 访问权限
- 依赖 TUSHARE_TOKEN 环境变量配置
- 部分接口需要足够积分额度：
  - index_classify: 2000积分
  - index_dailybasic: 400积分
  - index_global: 2000积分
  - sw_daily: 2000积分
  - ci_daily: 2000积分
  - stk_rewards: 2000积分

### Data Tables
- `ods_index_weekly` - 指数周线行情表
- `ods_index_monthly` - 指数月线行情表
- `ods_index_global` - 国际指数行情表
- `ods_index_dailybasic` - 大盘指数每日指标表
- `dim_index_classify` - 申万行业分类维度表
- `ods_index_member` - 指数成分股表
- `ods_sw_daily` - 申万行业指数日线表
- `ods_ci_daily` - 中信行业指数日线表
- `ods_ths_member` - 同花顺概念成分表
- `ods_sz_daily_info` - 深圳市场每日交易概况表
- `ods_daily_info` - 每日全市场交易统计表
- `ods_index_e` - 中证指数估值表
- `ods_stk_rewards` - 管理层薪酬持股表

### 与现有插件关系
本提案与现有的 `add-index-plugins` 是补充关系：
- `add-index-plugins` 包含：idx_factor_pro、index_basic、index_weight
- 本提案包含：上述 15 个扩展接口

现有已实现的相关插件（不在本提案范围内）：
- `tushare_index_daily` - 指数日线行情（已实现）
- `tushare_index_basic` - 指数基本信息（已实现）
- `tushare_index_weight` - 指数成分权重（已实现）
- `tushare_ths_index` - 同花顺概念指数列表（已实现）
- `tushare_ths_daily` - 同花顺概念日线行情（已实现）

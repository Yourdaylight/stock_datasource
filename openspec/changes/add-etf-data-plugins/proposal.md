# Change: 新增ETF数据获取插件

## Why

当前系统缺少ETF（交易型开放式指数基金）相关的数据获取插件，无法支持：
1. **ETF基础信息**：无法获取国内ETF的基础信息（代码、名称、管理人、跟踪指数等）
2. **ETF日线行情**：无法获取ETF每日收盘后的OHLCV数据
3. **ETF复权因子**：无法获取ETF的复权因子，影响价格调整计算
4. **ETF分钟数据**：无法获取ETF的分钟级别行情数据

用户已在`plugins/`目录下创建了四个ETF插件的目录结构和API文档，需要完成插件实现。

## What Changes

### 新增插件

1. **tushare_etf_basic**：ETF基础信息
   - 接口：`etf_basic`
   - 数据：ETF代码、名称、管理人、跟踪指数、上市日期等
   - 权限：8000积分
   - 特点：作为其他ETF数据插件的依赖（提供ETF代码列表）

2. **tushare_etf_fund_daily**：ETF日线行情
   - 接口：`fund_daily`
   - 数据：开盘价、最高价、最低价、收盘价、成交量、成交额
   - 权限：5000积分
   - **依赖**：tushare_etf_basic（需要ETF代码列表）

3. **tushare_etf_fund_adj**：ETF复权因子
   - 接口：`fund_adj`
   - 数据：复权因子
   - **依赖**：tushare_etf_basic（需要ETF代码列表）

4. **tushare_etf_stk_mins**：ETF分钟数据
   - 接口：`stk_mins`
   - 数据：1/5/15/30/60分钟OHLCV数据
   - 权限：正式权限
   - **依赖**：tushare_etf_basic（需要ETF代码列表）

### 插件结构

每个插件包含以下文件：
- `plugin.py` - 插件主类（继承BasePlugin）
- `extractor.py` - TuShare API调用器
- `config.json` - 插件配置（rate_limit、schedule等）
- `schema.json` - ClickHouse表结构定义
- `__init__.py` - 插件注册
- `service.py` - 数据查询SDK
- `*.md` - API接口文档（已存在）

### 依赖关系

```
tushare_etf_basic (基础信息)
    ├── tushare_etf_fund_daily (日线行情)
    ├── tushare_etf_fund_adj (复权因子)
    └── tushare_etf_stk_mins (分钟数据)
```

日线/分钟线数据获取时需要先确保有ETF基础信息（ETF代码列表）。

## Impact

### Affected Specs
- etf-data-plugins（新增）

### Affected Code
- `src/stock_datasource/plugins/tushare_etf_basic/` - 完善插件实现
- `src/stock_datasource/plugins/tushare_etf_fund_daily/` - 完善插件实现
- `src/stock_datasource/plugins/tushare_etf_fund_adj/` - 完善插件实现
- `src/stock_datasource/plugins/tushare_etf_stk_mins/` - 完善插件实现

### Dependencies
- 依赖TuShare Pro API访问权限
- 依赖TUSHARE_TOKEN环境变量配置
- etf_basic需要8000积分，fund_daily需要5000积分

### Data Tables
- `ods_etf_basic` - ETF基础信息表
- `ods_etf_fund_daily` - ETF日线行情表
- `ods_etf_fund_adj` - ETF复权因子表
- `ods_etf_stk_mins` - ETF分钟数据表

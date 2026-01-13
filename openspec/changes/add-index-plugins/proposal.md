# Change: 新增指数相关数据源插件

## Why

当前系统缺少指数相关数据源插件，无法支持：
1. **指数技术分析**：缺乏指数日线技术因子数据（MACD、KDJ、RSI等100+技术指标）
2. **指数基础信息**：无法获取A股市场各类指数的基础信息（沪深300、中证500等）
3. **指数成分权重**：无法跟踪指数成分股及其权重变化，无法支持指数投资分析

## What Changes

### 新增插件
- **tushare_idx_factor_pro**：指数技术因子数据（专业版）
  - 接口：`idx_factor_pro`
  - 数据：约100个技术指标
  - 频率：每日更新
  
- **tushare_index_basic**：指数基础信息
  - 接口：`index_basic`
  - 数据：指数基本信息（代码、名称、市场、类别等）
  - 频率：一次性全量，周期性更新
  
- **tushare_index_weight**：指数成分和权重
  - 接口：`index_weight`
  - 数据：指数成分代码及权重
  - 频率：每月更新

### 插件结构
每个插件包含以下文件：
- `plugin.py` - 插件主类
- `extractor.py` - TuShare API调用器
- `config.json` - 插件配置
- `schema.json` - ClickHouse表结构定义
- `__init__.py` - 插件注册
- `service.py` - 数据查询SDK
- `*.md` - API接口文档

## Impact

### Affected Specs
- index-data-sources（新增）

### Affected Code
- `src/stock_datasource/plugins/tushare_idx_factor_pro/` - 新增插件目录
- `src/stock_datasource/plugins/tushare_index_basic/` - 新增插件目录
- `src/stock_datasource/plugins/tushare_index_weight/` - 新增插件目录
- `src/stock_datasource/plugins/__init__.py` - 注册新插件

### Dependencies
- 依赖TuShare Pro API访问权限
- 依赖TUSHARE_TOKEN环境变量配置
- 需要足够的积分额度（idx_factor_pro需要5000积分/分钟30次，index_weight需要2000积分）

### Data Tables
- `ods_idx_factor_pro` - 指数技术因子表
- `dim_index_basic` - 指数基础信息维度表
- `ods_index_weight` - 指数成分权重表

## ADDED Requirements

### Requirement: ETF基础信息数据获取

系统SHALL提供tushare_etf_basic插件，用于获取国内ETF的基础信息数据。

#### Scenario: 获取所有上市ETF基础信息
- **WHEN** 用户调用tushare_etf_basic插件的extract_data方法，参数list_status='L'
- **THEN** 系统返回所有上市状态的ETF基础信息DataFrame
- **AND** DataFrame包含ts_code、csname、index_code、list_date、mgr_name等字段

#### Scenario: 按管理人筛选ETF
- **WHEN** 用户调用tushare_etf_basic插件，参数mgr='华夏基金'
- **THEN** 系统返回华夏基金管理的所有ETF列表

#### Scenario: 数据写入ClickHouse
- **WHEN** 插件完成数据提取和转换
- **THEN** 数据被写入ods_etf_basic表
- **AND** 使用ReplacingMergeTree引擎保证幂等性

### Requirement: ETF日线行情数据获取

系统SHALL提供tushare_etf_fund_daily插件，用于获取ETF每日收盘后的OHLCV数据。

#### Scenario: 按日期获取ETF日线数据
- **WHEN** 用户调用tushare_etf_fund_daily插件，参数trade_date='20260113'
- **THEN** 系统返回该日期所有ETF的日线行情数据
- **AND** 数据包含open、high、low、close、vol、amount等字段

#### Scenario: 按ETF代码获取历史日线
- **WHEN** 用户调用插件，参数ts_code='510330.SH', start_date='20260101', end_date='20260113'
- **THEN** 系统返回该ETF在指定日期范围内的日线数据

#### Scenario: 依赖ETF基础信息
- **WHEN** 插件通过get_dependencies()方法被查询
- **THEN** 返回['tushare_etf_basic']表示依赖关系

### Requirement: ETF复权因子数据获取

系统SHALL提供tushare_etf_fund_adj插件，用于获取ETF的复权因子数据。

#### Scenario: 按日期获取复权因子
- **WHEN** 用户调用tushare_etf_fund_adj插件，参数trade_date='20260113'
- **THEN** 系统返回该日期所有ETF的复权因子数据
- **AND** 数据包含ts_code、trade_date、adj_factor字段

#### Scenario: 按ETF代码获取历史复权因子
- **WHEN** 用户调用插件，参数ts_code='510330.SH'
- **THEN** 系统返回该ETF的历史复权因子数据

### Requirement: ETF分钟数据获取

系统SHALL提供tushare_etf_stk_mins插件，用于获取ETF的分钟级别行情数据。

#### Scenario: 获取1分钟数据
- **WHEN** 用户调用tushare_etf_stk_mins插件，参数ts_code='510330.SH', freq='1min', start_date='2026-01-13 09:00:00', end_date='2026-01-13 15:00:00'
- **THEN** 系统返回该ETF在指定时间范围内的1分钟行情数据

#### Scenario: 支持多种频率
- **WHEN** 用户指定freq参数为'1min'、'5min'、'15min'、'30min'或'60min'
- **THEN** 系统返回对应频率的分钟数据

#### Scenario: 依赖ETF基础信息
- **WHEN** 插件通过get_dependencies()方法被查询
- **THEN** 返回['tushare_etf_basic']表示依赖关系

### Requirement: 插件依赖关系管理

系统MUST正确处理ETF数据插件之间的依赖关系。

#### Scenario: 声明依赖关系
- **WHEN** tushare_etf_fund_daily、tushare_etf_fund_adj、tushare_etf_stk_mins插件被初始化
- **THEN** 它们的get_dependencies()方法返回['tushare_etf_basic']

#### Scenario: 获取ETF代码列表
- **WHEN** 依赖插件需要获取ETF代码列表进行批量数据获取
- **THEN** 可以从ods_etf_basic表查询上市状态的ETF代码

#### Scenario: 优雅降级
- **WHEN** ods_etf_basic表不存在或为空
- **THEN** 插件记录警告日志
- **AND** 可以使用用户指定的ts_code参数继续执行

### Requirement: 测试验证

系统SHALL提供ETF插件的测试用例。

#### Scenario: 使用runtime_config.json配置测试
- **WHEN** 运行tests/test_etf_plugins.py测试
- **THEN** 测试使用runtime_config.json中的代理和同步配置

#### Scenario: 验证数据提取
- **WHEN** 测试调用各插件的extract_data方法
- **THEN** 返回非空DataFrame或合理的空结果

#### Scenario: 验证数据加载
- **WHEN** 测试调用各插件的load_data方法
- **THEN** 数据成功写入对应的ClickHouse表

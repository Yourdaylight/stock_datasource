# trade-calendar-service Specification

## Purpose
提供全局统一的交易日历服务，将交易日历作为配置文件管理，而非数据库数据，简化交易日期的查询和管理。

## ADDED Requirements

### Requirement: Global Trade Calendar Configuration
系统 SHALL 提供基于配置文件的全局交易日历服务，支持统一的交易日期查询。

#### Scenario: 加载交易日历配置
- **GIVEN** 系统启动
- **WHEN** 首次访问 `TradeCalendarService`
- **THEN** 系统从 `config/trade_calendar.csv` 加载交易日历数据到内存
- **AND** 数据包含 `cal_date`, `is_open`, `pretrade_date` 字段
- **AND** 日期范围覆盖 2000-01-01 至 2030-12-31

#### Scenario: 获取最近 N 个交易日
- **GIVEN** 交易日历已加载
- **WHEN** 调用 `get_trading_days(n=30)`
- **THEN** 返回从今天往前数的最近 30 个交易日列表
- **AND** 日期格式为 `YYYYMMDD` 字符串
- **AND** 列表按日期降序排列（最近的在前）

#### Scenario: 获取指定日期之前的交易日
- **GIVEN** 交易日历已加载
- **WHEN** 调用 `get_trading_days(n=10, end_date='20260113')`
- **THEN** 返回 2026-01-13 及之前的最近 10 个交易日
- **AND** 如果 end_date 是交易日，则包含在结果中

#### Scenario: 判断是否为交易日
- **GIVEN** 交易日历已加载
- **WHEN** 调用 `is_trading_day('20260113')`
- **THEN** 返回 `True` 如果该日期是交易日
- **AND** 返回 `False` 如果该日期是非交易日（周末或节假日）

#### Scenario: 获取上一个交易日
- **GIVEN** 交易日历已加载
- **WHEN** 调用 `get_prev_trading_day('20260113')`
- **THEN** 返回 2026-01-13 之前最近的一个交易日
- **AND** 如果输入日期不存在于日历中，抛出 `InvalidDateError`

#### Scenario: 获取下一个交易日
- **GIVEN** 交易日历已加载
- **WHEN** 调用 `get_next_trading_day('20260113')`
- **THEN** 返回 2026-01-13 之后最近的一个交易日
- **AND** 如果输入日期超出日历范围，抛出 `InvalidDateError`

#### Scenario: 获取日期区间内的交易日
- **GIVEN** 交易日历已加载
- **WHEN** 调用 `get_trading_days_between('20260101', '20260113')`
- **THEN** 返回 2026-01-01 到 2026-01-13 之间的所有交易日
- **AND** 包含起始和结束日期（如果它们是交易日）
- **AND** 列表按日期升序排列

### Requirement: Trade Calendar Manual Update
系统 SHALL 支持手动更新交易日历配置文件。

#### Scenario: 手动刷新交易日历
- **GIVEN** 用户需要更新交易日历
- **WHEN** 调用 `refresh_calendar()` 或触发 API 端点
- **THEN** 系统从 TuShare API 获取最新交易日历
- **AND** 更新 `config/trade_calendar.csv` 文件
- **AND** 重新加载内存中的交易日历数据
- **AND** 返回更新结果（新增日期数量等）

#### Scenario: 交易日历文件不存在
- **GIVEN** `config/trade_calendar.csv` 文件不存在
- **WHEN** 系统启动并访问 `TradeCalendarService`
- **THEN** 系统自动从 TuShare 获取交易日历
- **AND** 创建 `config/trade_calendar.csv` 文件
- **AND** 记录警告日志提示用户

### Requirement: Trade Calendar Service Singleton
系统 SHALL 确保 `TradeCalendarService` 为全局单例，避免重复加载。

#### Scenario: 单例模式访问
- **GIVEN** 多个模块需要访问交易日历
- **WHEN** 各模块分别实例化 `TradeCalendarService`
- **THEN** 所有模块获得同一个实例
- **AND** 交易日历数据只加载一次

#### Scenario: 线程安全访问
- **GIVEN** 多线程环境
- **WHEN** 并发访问 `TradeCalendarService`
- **THEN** 服务正确返回结果
- **AND** 不会出现数据竞争或重复加载

## MODIFIED Requirements

### Requirement: DataManage Service Trade Calendar Integration
`DataManageService` SHALL 使用新的 `TradeCalendarService` 替代内部实现。

#### Scenario: 获取交易日期列表
- **GIVEN** 用户通过 API 请求交易日期
- **WHEN** 调用 `/api/datamanage/trading-days`
- **THEN** 内部使用 `TradeCalendarService.get_trading_days()` 获取数据
- **AND** API 响应格式保持不变

#### Scenario: 缺失数据检测使用交易日历
- **GIVEN** 用户请求检测缺失数据
- **WHEN** 系统计算应有的交易日期
- **THEN** 使用 `TradeCalendarService` 获取交易日列表
- **AND** 与数据库中已有数据对比

## Error Handling

### Requirement: Trade Calendar Error Handling
系统 SHALL 对交易日历相关错误提供清晰的异常处理。

#### Scenario: 无效日期格式
- **GIVEN** 用户传入无效的日期格式
- **WHEN** 调用交易日历查询方法
- **THEN** 抛出 `InvalidDateError` 异常
- **AND** 异常信息包含期望的日期格式说明

#### Scenario: 日期超出范围
- **GIVEN** 用户查询的日期超出交易日历范围
- **WHEN** 调用 `get_prev_trading_day()` 或 `get_next_trading_day()`
- **THEN** 抛出 `InvalidDateError` 异常
- **AND** 异常信息说明有效的日期范围

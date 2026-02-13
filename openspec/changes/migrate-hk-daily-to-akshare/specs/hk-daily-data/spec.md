# Spec: Hong Kong Stock Daily Data

## Overview

港股日线数据插件提供港股历史日线行情数据的获取、存储和查询功能。使用 yfinance 作为数据源,解决 TuShare 权限限制问题。

## ADDED Requirements

### Requirement: yfinance 数据源集成

系统 SHALL 使用 yfinance API 获取港股日线数据,替代原有的 TuShare 数据源。

#### Scenario: 成功获取单只股票历史数据
- **WHEN** 使用 yfinance 获取港股 00001.HK 的历史日线数据
- **THEN** 系统成功返回包含 Open, High, Low, Close, Volume 等字段的数据
- **AND** 数据覆盖指定的时间范围(如一年)

#### Scenario: 处理 yfinance API 限流
- **WHEN** yfinance API 返回速率限制错误
- **THEN** 系统等待指定时间后重试
- **AND** 记录重试日志

### Requirement: 股票代码格式转换

系统 SHALL 实现 TuShare 代码格式与 yfinance 代码格式的双向转换。

#### Scenario: TuShare 代码转 yfinance 代码
- **WHEN** 输入 TuShare 格式的港股代码 "00700.HK"
- **THEN** 系统转换为 yfinance 格式 "0700.HK"
- **AND** 转换后的代码可用于 yfinance API 查询

#### Scenario: yfinance 代码转 TuShare 代码
- **WHEN** 从 yfinance 获取数据后
- **THEN** 系统将 yfinance 格式代码 "0700.HK" 转换为 TuShare 格式 "00700.HK"
- **AND** 存储到数据库时使用 TuShare 格式

#### Scenario: 处理边界情况
- **WHEN** 股票代码为 "00001.HK" 或 "1.HK"
- **THEN** 系统正确转换为 yfinance 格式 "0001.HK"
- **AND** 转换回 TuShare 格式时保持为 "00001.HK"

### Requirement: 数据字段映射

系统 SHALL 将 yfinance 数据格式映射到 TuShare 数据格式,确保数据库表结构兼容。

#### Scenario: 基础字段映射
- **WHEN** 从 yfinance 获取到数据
- **THEN** 系统将 Open, High, Low, Close, Volume 字段映射为 open, high, low, close, vol
- **AND** 数据类型转换为 Float64

#### Scenario: 计算派生字段
- **WHEN** 处理日线数据
- **THEN** 系统计算 pre_close 字段(前一日收盘价)
- **AND** 计算 change 字段(涨跌额 = close - pre_close)
- **AND** 计算 pct_chg 字段(涨跌幅 = (close - pre_close) / pre_close * 100)

#### Scenario: 处理缺失字段
- **WHEN** yfinance 数据不包含 amount 字段
- **THEN** 系统将 amount 字段设置为 null
- **AND** 数据库记录该字段为 Nullable(Float64)

#### Scenario: 日期格式转换
- **WHEN** yfinance 返回 DatetimeIndex 格式的日期
- **THEN** 系统转换为 YYYYMMDD 格式的字符串
- **AND** 存储到数据库时转换为 Date 类型

### Requirement: 批量数据获取

系统 SHALL 支持批量获取所有港股股票的历史日线数据。

#### Scenario: 获取所有港股历史数据
- **WHEN** 调用批量获取接口
- **THEN** 系统从 ods_hk_basic 表获取所有港股代码列表
- **AND** 逐只股票获取历史数据
- **AND** 返回获取统计信息(成功数、失败数、总记录数)

#### Scenario: 分批获取和速率控制
- **WHEN** 批量获取数据时
- **THEN** 系统按批次获取(默认每批 10 只股票)
- **AND** 批次间添加延迟(默认 1 秒)
- **AND** 避免触发 yfinance API 速率限制

#### Scenario: 错误处理和重试
- **WHEN** 获取某只股票数据失败
- **THEN** 系统记录错误日志
- **AND** 实现重试机制(默认重试 3 次)
- **AND** 继续获取其他股票数据

#### Scenario: 获取进度反馈
- **WHEN** 批量获取数据时
- **THEN** 系统定期输出进度信息(如每 50 只股票)
- **AND** 显示已处理数量、成功数量、失败数量

### Requirement: 速率控制

系统 SHALL 实现 API 调用速率控制,避免触发 yfinance 限制。

#### Scenario: 令牌桶算法控制速率
- **WHEN** 调用 yfinance API 时
- **THEN** 系统使用令牌桶算法控制调用频率
- **AND** 默认限制为每分钟 60 次调用
- **AND** 超过限制时自动等待

#### Scenario: 可配置速率限制
- **WHEN** 在 config.json 中配置 rate_limit 参数
- **THEN** 系统使用配置的速率限制值
- **AND** 灵活适应不同的使用场景

### Requirement: 数据验证

系统 SHALL 对获取的数据进行验证,确保数据质量。

#### Scenario: 验证必需字段
- **WHEN** 获取到日线数据后
- **THEN** 系统验证 ts_code, trade_date, close 字段不为空
- **AND** 验证失败时记录错误日志

#### Scenario: 验证价格关系
- **WHEN** 验证日线数据时
- **THEN** 系统检查 high >= low
- **AND** 检查 high >= open 且 high >= close
- **AND** 检查 low <= open 且 low <= close
- **AND** 记录异常数据但不拒绝入库

#### Scenario: 验证数据完整性
- **WHEN** 批量获取完成后
- **THEN** 系统统计获取成功率
- **AND** 输出数据质量报告

### Requirement: 配置管理

系统 SHALL 通过配置文件管理插件参数。

#### Scenario: 配置数据源
- **WHEN** 在 config.json 中设置 data_source 为 "yfinance"
- **THEN** 系统使用 yfinance 作为数据源
- **AND** 不再依赖 TUSHARE_TOKEN

#### Scenario: 配置速率限制
- **WHEN** 在 config.json 中设置 rate_limit
- **THEN** 系统使用配置的速率限制值
- **AND** 默认值为 60(次/分钟)

#### Scenario: 配置批次参数
- **WHEN** 在 config.json 中设置 batch_size 和 delay_between_batches
- **THEN** 系统使用配置的批次参数进行批量获取

### Requirement: 兼容性保证

系统 SHALL 保持与原有 TuShare 插件的兼容性。

#### Scenario: 数据库表结构不变
- **WHEN** 迁移到 yfinance 后
- **THEN** ods_hk_daily 表结构保持不变
- **AND** 所有字段名称和类型不变

#### Scenario: 查询接口不变
- **WHEN** 前端调用港股日线查询接口
- **THEN** 接口参数和返回格式保持不变
- **AND** 前端代码无需修改

#### Scenario: 插件接口不变
- **WHEN** 其他模块调用 tushare_hk_daily 插件
- **THEN** 插件的 extract_data、validate_data、transform_data、load_data 方法签名不变
- **AND** 调用方式不变

### Requirement: 测试验证

系统 SHALL 通过完整的测试验证,确保功能正确性。

#### Scenario: 单元测试
- **WHEN** 运行单元测试
- **THEN** 测试代码转换函数的正确性
- **AND** 测试字段映射函数的正确性
- **AND** 测试速率控制逻辑

#### Scenario: 集成测试
- **WHEN** 运行集成测试
- **THEN** 测试从 yfinance 获取数据到入库的完整流程
- **AND** 验证数据格式正确

#### Scenario: 批量获取测试
- **WHEN** 测试批量获取功能
- **THEN** 成功获取港股所有股票至少一年的历史日线数据
- **AND** 验证数据完整性(记录数、字段数)
- **AND** 验证查询服务可正常查询数据

#### Scenario: 数据质量验证
- **WHEN** 完成批量获取后
- **THEN** 验证数据无重复记录
- **AND** 验证价格数据在合理范围内
- **AND** 验证日期连续性(排除停牌日期)

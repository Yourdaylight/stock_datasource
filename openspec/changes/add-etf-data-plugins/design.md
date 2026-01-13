# Design: ETF数据插件技术设计

## 架构概述

ETF数据插件采用与现有tushare插件相同的架构模式，继承`BasePlugin`基类，实现ETL流程。

## 插件设计

### 1. tushare_etf_basic

**API接口**: `etf_basic`

**表结构**: `ods_etf_basic`

**字段列表**:
- ts_code - ETF代码（如159526.SZ）
- csname - ETF中文简称
- extname - ETF扩位简称
- cname - 基金中文全称
- index_code - ETF基准指数代码
- index_name - ETF基准指数中文全称
- setup_date - 设立日期
- list_date - 上市日期
- list_status - 存续状态（L上市/D退市/P待上市）
- exchange - 交易所（SH/SZ）
- mgr_name - 基金管理人简称
- custod_name - 基金托管人名称
- mgt_fee - 管理费率
- etf_type - 基金投资通道类型（境内/QDII）
- version - 版本号
- _ingested_at - 入库时间

**调度策略**: 每周更新

### 2. tushare_etf_fund_daily

**API接口**: `fund_daily`

**表结构**: `ods_etf_fund_daily`

**字段列表**:
- ts_code - ETF代码
- trade_date - 交易日期
- open - 开盘价
- high - 最高价
- low - 最低价
- close - 收盘价
- pre_close - 昨收盘价
- change - 涨跌额
- pct_chg - 涨跌幅
- vol - 成交量（手）
- amount - 成交额（千元）
- version - 版本号
- _ingested_at - 入库时间

**分区策略**: 按月分区 `toYYYYMM(trade_date)`

**排序键**: `["ts_code", "trade_date"]`

### 3. tushare_etf_fund_adj

**API接口**: `fund_adj`

**表结构**: `ods_etf_fund_adj`

**字段列表**:
- ts_code - ETF代码
- trade_date - 交易日期
- adj_factor - 复权因子
- version - 版本号
- _ingested_at - 入库时间

**分区策略**: 按月分区 `toYYYYMM(trade_date)`

### 4. tushare_etf_stk_mins

**API接口**: `stk_mins`

**表结构**: `ods_etf_stk_mins`

**字段列表**:
- ts_code - ETF代码
- trade_time - 交易时间
- freq - 频率（1min/5min/15min/30min/60min）
- open - 开盘价
- high - 最高价
- low - 最低价
- close - 收盘价
- vol - 成交量
- amount - 成交金额
- version - 版本号
- _ingested_at - 入库时间

**分区策略**: 按月分区 `toYYYYMM(toDate(trade_time))`

**排序键**: `["ts_code", "freq", "trade_time"]`

## 依赖关系处理

### 方案设计

1. **声明式依赖**: 在plugin.py中通过`get_dependencies()`返回依赖的插件名称
2. **运行时检查**: 在extract_data中查询数据库获取ETF代码列表
3. **优雅降级**: 如果没有ETF基础数据，提供警告并尝试使用默认代码列表

### 实现代码示例

```python
def get_dependencies(self) -> List[str]:
    """声明依赖tushare_etf_basic插件。"""
    return ["tushare_etf_basic"]

def _get_etf_codes(self) -> List[str]:
    """从数据库获取ETF代码列表。"""
    if not self.db:
        self.logger.warning("Database not initialized, using empty list")
        return []
    
    try:
        query = "SELECT ts_code FROM ods_etf_basic WHERE list_status = 'L'"
        df = self.db.execute_query(query)
        return df['ts_code'].tolist() if not df.empty else []
    except Exception as e:
        self.logger.warning(f"Failed to get ETF codes: {e}")
        return []
```

## 数据流程

```
TuShare API → Extractor → Plugin.validate_data() 
                      → Plugin.transform_data() 
                      → Plugin.load_data() 
                      → ClickHouse
```

## 关键技术决策

### 1. 数据类型转换
- 日期字段使用`Date`类型
- 时间字段使用`DateTime`类型
- 数值字段使用`Nullable(Float64)`类型
- ETF代码使用`LowCardinality(String)`优化存储

### 2. 分区策略
- 按月分区，便于按时间范围查询
- 减少单次扫描数据量，提高查询性能

### 3. 版本控制
- 使用`ReplacingMergeTree`引擎
- `version`字段使用`int(datetime.now().timestamp())`
- 相同键值的数据保留最新版本

### 4. 限流策略
- etf_basic: rate_limit = 120（单次最大5000条）
- fund_daily: rate_limit = 30（单次最大2000条）
- fund_adj: rate_limit = 30
- stk_mins: rate_limit = 30（单次最大8000条）

### 5. 错误处理
- API调用失败重试3次（指数退避）
- 记录详细日志
- 返回空DataFrame而非抛异常

## 测试策略

### 单元测试
- Mock TuShare API调用
- 验证数据转换逻辑
- 验证依赖检查逻辑

### 集成测试
- 使用runtime_config.json配置
- 真实API调用测试
- 验证数据写入ClickHouse

# Stock Data Source - 开发指导与新建插件指南

## 📋 项目总结

### 核心功能
- **A股数据采集**：通过 TuShare API 获取完整的 A 股日线数据
- **Schema-on-API**：根据 API 响应动态创建和扩展表结构
- **数据质量检查**：内置多层数据质量验证机制
- **Airflow 编排**：支持自动化日更和历史回填
- **ClickHouse 存储**：高性能列式数据库存储时间序列数据

### 架构设计
```
TuShare API (REST)
    ↓
Plugin (Extract → Validate → Transform → Load)
    ↓
ODS Layer (原始数据存储)
    ↓
DM/Fact Layer (数据集市/事实表)
    ↓
Metadata Layer (元数据/审计日志)
```

### 数据分层
| 层级 | 表名前缀 | 用途 | 特点 |
|------|---------|------|------|
| ODS | `ods_*` | 原始数据存储 | 按月分区，Schema 动态演进 |
| DM | `dim_*` | 维度表 | 股票基础信息，缓慢变化维 |
| Fact | `fact_*` | 事实表 | 日线数据，预聚合指标 |
| Meta | `meta_*` | 元数据 | 摄入日志、失败任务、质量检查 |

---

## 🚀 后续开发指导

### 1. 快速开始

#### 环境配置
```bash
# 克隆项目
git clone <repository-url>
cd stock_datasource

# 安装依赖
uv sync

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 TuShare Token 和 ClickHouse 连接信息
```

#### 初始化数据库
```bash
# 创建数据库和所有表
uv run cli.py init-db

# 创建特定表
uv run cli.py init-db --table ods_daily
```

### 2. 常用 CLI 命令

```bash
# 获取特定日期的数据
uv run cli.py ingest-daily --date 20251024

# 批量回填数据
uv run cli.py backfill --start-date 20250101 --end-date 20251024

# 查看摄入状态
uv run cli.py status --date 20251024

# 运行数据质量检查
uv run cli.py quality-check --date 20251024

# 生成每日报告
uv run cli.py report --date 20251024

# 数据覆盖率检查
uv run cli.py coverage --table ods_daily

# 清理旧数据
uv run cli.py cleanup --days 30
```

### 3. 项目结构导航

```
src/stock_datasource/
├── core/
│   ├── base_plugin.py          # 插件基类（核心）
│   └── plugin_manager.py       # 插件管理器
├── plugins/
│   ├── tushare_daily/          # 日线数据插件
│   ├── tushare_daily_basic/    # 日线基础指标插件
│   ├── tushare_adj_factor/     # 复权因子插件
│   ├── tushare_stk_limit/      # 涨跌停数据插件
│   ├── tushare_suspend_d/      # 停复牌数据插件
│   ├── tushare_stock_basic/    # 股票基础信息插件
│   └── tushare_trade_calendar/ # 交易日历插件
├── models/
│   ├── database.py             # 数据库连接
│   └── schemas.py              # 表结构定义
├── services/
│   ├── ingestion.py            # 摄入服务
│   └── metadata.py             # 元数据服务
├── utils/
│   ├── extractor.py            # 数据提取工具
│   ├── loader.py               # 数据加载工具
│   ├── quality_checks.py       # 质量检查工具
│   └── logger.py               # 日志工具
└── dags/
    ├── daily_cn_1800.py        # 日更 DAG
    ├── backfill_cn_2020.py     # 回填 DAG
    └── hk_placeholders.py      # 港股占位 DAG
```

### 4. 数据流程

#### 日常摄入流程
```
1. 触发条件：每天 18:00 (Asia/Shanghai)
2. 执行步骤：
   - 获取交易日历 → 确定是否为交易日
   - 并行执行所有插件的 run() 方法
   - 每个插件执行：Extract → Validate → Transform → Load
   - 运行数据质量检查
   - 记录摄入日志和元数据
3. 输出：ODS 表中的原始数据 + Fact 表中的清洗数据
```

#### 历史回填流程
```
1. 触发条件：手动执行 backfill 命令
2. 执行步骤：
   - 获取指定日期范围内的所有交易日
   - 按日期顺序逐日执行摄入流程
   - 支持断点续传（失败日期可重新执行）
3. 输出：完整的历史数据
```

### 5. 数据质量检查

系统内置的质量检查包括：

| 检查项 | 说明 | 触发条件 |
|--------|------|---------|
| 交易日对齐 | 验证记录数与交易日历匹配 | 每日摄入后 |
| 价格一致性 | 验证 OHLC 关系（High ≥ Open/Close ≥ Low） | 日线数据摄入后 |
| 涨跌停一致性 | 验证涨跌停数据与日线数据一致 | 日线 + 涨跌停数据摄入后 |
| 停复牌一致性 | 验证停复牌数据与日线数据一致 | 日线 + 停复牌数据摄入后 |

### 6. 性能优化建议

#### API 调用优化
- **速率限制**：A 股数据 120-150 calls/min（TuShare 2000 积分档）
- **批量请求**：使用 TuShare 的分页功能减少请求次数
- **缓存策略**：股票基础信息可缓存（变化不频繁）

#### 数据库优化
- **分区策略**：ODS 表按月分区，提高查询性能
- **索引设置**：在 `ts_code` 和 `trade_date` 上建立索引
- **压缩**：ClickHouse 自动压缩，无需手动配置

#### 并行处理
- **插件并行**：7 个插件可并行执行（互不依赖）
- **日期并行**：backfill 时可配置并行度

---

## 🔧 新建插件指南

### 1. 插件架构

每个插件是一个独立的 Python 包，包含以下文件：

```
plugins/my_plugin/
├── __init__.py              # 包初始化
├── plugin.py                # 插件主类（继承 BasePlugin）
├── extractor.py             # 数据提取逻辑
├── config.json              # 插件配置
├── schema.json              # 表结构定义
└── README.md                # 插件文档
```

### 2. 必需的三个方法

#### 2.1 `extract_data(**kwargs) -> pd.DataFrame`
**职责**：从数据源获取原始数据

```python
def extract_data(self, **kwargs) -> pd.DataFrame:
    """
    从 TuShare API 获取数据
    
    Args:
        **kwargs: 插件特定参数
            - trade_date: 交易日期 (YYYYMMDD)
            - start_date: 开始日期
            - end_date: 结束日期
            - list_status: 上市状态 (L/D/P)
    
    Returns:
        pd.DataFrame: 原始数据
    """
    # 1. 参数验证
    trade_date = kwargs.get('trade_date')
    if not trade_date:
        raise ValueError("trade_date is required")
    
    # 2. 调用 API
    data = self.extractor.extract(trade_date)
    
    # 3. 基础处理（可选）
    if data.empty:
        self.logger.warning(f"No data for {trade_date}")
        return pd.DataFrame()
    
    # 4. 返回数据
    return data
```

**关键点**：
- ✅ 必须返回 `pd.DataFrame`
- ✅ 处理空数据情况
- ✅ 记录日志便于调试
- ✅ 不要在此处进行数据转换

#### 2.2 `validate_data(data: pd.DataFrame) -> bool`
**职责**：验证数据的完整性和正确性

```python
def validate_data(self, data: pd.DataFrame) -> bool:
    """
    验证提取的数据
    
    Returns:
        bool: 数据是否有效
    """
    # 1. 检查空数据
    if data.empty:
        self.logger.warning("Empty data")
        return False
    
    # 2. 检查必需列
    required_columns = ['ts_code', 'trade_date', 'close']
    missing = [col for col in required_columns if col not in data.columns]
    if missing:
        self.logger.error(f"Missing columns: {missing}")
        return False
    
    # 3. 检查空值
    null_count = data['ts_code'].isnull().sum()
    if null_count > 0:
        self.logger.error(f"Found {null_count} null values in ts_code")
        return False
    
    # 4. 业务逻辑验证
    # 例如：价格关系验证
    invalid = data[data['high'] < data['low']]
    if len(invalid) > 0:
        self.logger.error(f"Found {len(invalid)} invalid price records")
        return False
    
    self.logger.info(f"Validation passed for {len(data)} records")
    return True
```

**关键点**：
- ✅ 检查必需列的存在
- ✅ 检查关键字段的空值
- ✅ 验证业务逻辑约束
- ✅ 记录详细的错误信息

#### 2.3 `load_data(data: pd.DataFrame) -> Dict[str, Any]`
**职责**：将清洗后的数据加载到数据库

```python
def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
    """
    加载数据到数据库
    
    Args:
        data: 清洗后的数据
    
    Returns:
        Dict: 加载统计信息
    """
    if not self.db:
        return {"status": "failed", "error": "Database not initialized"}
    
    if data.empty:
        return {"status": "no_data", "loaded_records": 0}
    
    results = {
        "status": "success",
        "tables_loaded": [],
        "total_records": 0
    }
    
    try:
        # 1. 准备数据（类型转换）
        data = self._prepare_data_for_insert('ods_my_table', data)
        
        # 2. 添加系统列
        data = self._add_system_columns(data)
        
        # 3. 插入数据
        self.logger.info(f"Loading {len(data)} records into ods_my_table")
        self.db.insert_dataframe('ods_my_table', data)
        
        results['tables_loaded'].append({
            'table': 'ods_my_table',
            'records': len(data)
        })
        results['total_records'] += len(data)
        
        self.logger.info(f"Successfully loaded {len(data)} records")
        
    except Exception as e:
        self.logger.error(f"Failed to load data: {e}")
        results['status'] = 'failed'
        results['error'] = str(e)
    
    return results
```

**关键点**：
- ✅ 使用 `_prepare_data_for_insert()` 进行类型转换
- ✅ 使用 `_add_system_columns()` 添加版本和摄入时间
- ✅ 返回加载统计信息
- ✅ 异常处理和日志记录

### 3. 可选的方法

#### 3.1 `transform_data(data: pd.DataFrame) -> pd.DataFrame`
**职责**：数据转换和清洗（默认：直接返回）

```python
def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
    """
    转换数据格式
    """
    # 数据类型转换
    numeric_cols = ['open', 'high', 'low', 'close']
    for col in numeric_cols:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors='coerce')
    
    # 日期格式转换
    if 'trade_date' in data.columns:
        data['trade_date'] = pd.to_datetime(
            data['trade_date'], 
            format='%Y%m%d'
        ).dt.date
    
    return data
```

#### 3.2 `get_dependencies() -> List[str]`
**职责**：声明插件依赖（默认：无依赖）

```python
def get_dependencies(self) -> List[str]:
    """
    返回依赖的其他插件名称
    """
    return ['tushare_stock_basic']  # 需要先执行 stock_basic 插件
```

#### 3.3 `get_schedule() -> Dict[str, Any]`
**职责**：定义执行计划（默认：每日 18:00）

```python
def get_schedule(self) -> Dict[str, Any]:
    """
    定义插件执行计划
    """
    return {
        "frequency": "daily",      # 'daily' 或 'weekly'
        "time": "18:00",           # HH:MM 格式
        "day_of_week": "monday"    # 仅当 frequency='weekly' 时需要
    }
```

### 4. 配置文件 (config.json)

```json
{
  "enabled": true,
  "description": "My custom data plugin",
  "rate_limit": 120,
  "timeout": 30,
  "retry_attempts": 3,
  "schedule": {
    "frequency": "daily",
    "time": "18:00"
  },
  "parameters_schema": {
    "trade_date": {
      "type": "string",
      "format": "YYYYMMDD",
      "required": true,
      "description": "Trade date"
    }
  }
}
```

### 5. 表结构定义 (schema.json)

```json
{
  "table_name": "ods_my_table",
  "table_type": "ods",
  "engine": "ReplacingMergeTree",
  "engine_params": {
    "order_by": ["ts_code", "trade_date"],
    "partition_by": "toYYYYMM(trade_date)"
  },
  "columns": [
    {
      "name": "ts_code",
      "data_type": "String",
      "nullable": false,
      "comment": "Stock code"
    },
    {
      "name": "trade_date",
      "data_type": "Date",
      "nullable": false,
      "comment": "Trade date"
    },
    {
      "name": "close",
      "data_type": "Float64",
      "nullable": true,
      "comment": "Close price"
    },
    {
      "name": "version",
      "data_type": "Int64",
      "nullable": false,
      "comment": "Data version (timestamp)"
    },
    {
      "name": "_ingested_at",
      "data_type": "DateTime",
      "nullable": false,
      "comment": "Ingestion timestamp"
    }
  ]
}
```

### 6. 完整的插件示例

```python
# plugins/my_plugin/plugin.py
import pandas as pd
from typing import Dict, Any
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from .extractor import extractor


class MyPlugin(BasePlugin):
    """My custom data plugin."""
    
    @property
    def name(self) -> str:
        return "my_plugin"
    
    @property
    def description(self) -> str:
        return "My custom data source"
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """Extract data from source."""
        trade_date = kwargs.get('trade_date')
        if not trade_date:
            raise ValueError("trade_date is required")
        
        self.logger.info(f"Extracting data for {trade_date}")
        data = extractor.extract(trade_date)
        
        if data.empty:
            self.logger.warning(f"No data for {trade_date}")
            return pd.DataFrame()
        
        self.logger.info(f"Extracted {len(data)} records")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate extracted data."""
        if data.empty:
            return False
        
        required_cols = ['ts_code', 'trade_date']
        if not all(col in data.columns for col in required_cols):
            self.logger.error("Missing required columns")
            return False
        
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data."""
        # 类型转换
        if 'trade_date' in data.columns:
            data['trade_date'] = pd.to_datetime(
                data['trade_date'], 
                format='%Y%m%d'
            ).dt.date
        
        return data
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load data into database."""
        if not self.db or data.empty:
            return {"status": "no_data", "loaded_records": 0}
        
        try:
            # 准备数据
            data = self._prepare_data_for_insert('ods_my_table', data)
            data = self._add_system_columns(data)
            
            # 插入数据
            self.db.insert_dataframe('ods_my_table', data)
            
            return {
                "status": "success",
                "tables_loaded": [{"table": "ods_my_table", "records": len(data)}],
                "total_records": len(data)
            }
        except Exception as e:
            self.logger.error(f"Load failed: {e}")
            return {"status": "failed", "error": str(e)}
```

### 7. 新建插件的步骤

#### 步骤 1：创建插件目录
```bash
mkdir -p src/stock_datasource/plugins/my_plugin
cd src/stock_datasource/plugins/my_plugin
```

#### 步骤 2：创建必需文件
```bash
touch __init__.py plugin.py extractor.py config.json schema.json README.md
```

#### 步骤 3：实现插件类
编辑 `plugin.py`，继承 `BasePlugin` 并实现三个必需方法。

#### 步骤 4：实现数据提取器
编辑 `extractor.py`，实现具体的 API 调用逻辑。

#### 步骤 5：配置插件
编辑 `config.json` 和 `schema.json`。

#### 步骤 6：注册插件
在 `__init__.py` 中导出插件类：
```python
from .plugin import MyPlugin

__all__ = ['MyPlugin']
```

#### 步骤 7：测试插件
```bash
# 直接运行插件
python src/stock_datasource/plugins/my_plugin/plugin.py --date 20251024

# 或通过 CLI
uv run cli.py ingest-daily --date 20251024
```

### 8. 新建插件的注意事项

#### ⚠️ 必须遵守的规范

1. **命名规范**
   - 插件名称：小写 + 下划线（如 `my_plugin`）
   - 类名称：PascalCase（如 `MyPlugin`）
   - 表名称：`ods_` 前缀 + 插件名称

2. **数据类型**
   - 始终返回 `pd.DataFrame`
   - 使用 ClickHouse 支持的数据类型
   - 日期字段使用 `Date` 类型

3. **错误处理**
   - 捕获所有异常并记录日志
   - 返回结构化的错误信息
   - 不要让异常传播到上层

4. **日志记录**
   - 使用 `self.logger` 记录日志
   - 记录关键步骤和错误信息
   - 便于问题排查

5. **系统列**
   - 必须添加 `version` 和 `_ingested_at` 列
   - 使用 `_add_system_columns()` 方法

#### ⚠️ 常见错误

| 错误 | 原因 | 解决方案 |
|------|------|---------|
| `ModuleNotFoundError` | 插件未正确注册 | 检查 `__init__.py` 导入 |
| `KeyError: 'ts_code'` | 缺少必需列 | 在 validate_data 中检查列 |
| `TypeError: unsupported operand type` | 数据类型不匹配 | 在 transform_data 中进行类型转换 |
| `Connection refused` | 数据库连接失败 | 检查 ClickHouse 配置和连接 |
| `API rate limit exceeded` | 请求过于频繁 | 调整 `rate_limit` 配置 |

#### ⚠️ 性能优化建议

1. **批量处理**
   - 使用 TuShare 的分页功能
   - 一次性获取多个交易日的数据

2. **缓存策略**
   - 缓存不经常变化的数据（如股票基础信息）
   - 使用 Redis 或本地文件缓存

3. **并行处理**
   - 利用多线程获取多个股票的数据
   - 注意 API 速率限制

4. **数据压缩**
   - ClickHouse 自动压缩，无需手动处理
   - 考虑使用 LZ4 或 ZSTD 压缩算法

### 9. 测试插件

#### 单元测试
```python
# tests/test_my_plugin.py
import pytest
import pandas as pd
from stock_datasource.plugins.my_plugin import MyPlugin


def test_extract_data():
    """Test data extraction."""
    plugin = MyPlugin()
    data = plugin.extract_data(trade_date='20251024')
    
    assert isinstance(data, pd.DataFrame)
    assert not data.empty
    assert 'ts_code' in data.columns


def test_validate_data():
    """Test data validation."""
    plugin = MyPlugin()
    
    # Valid data
    valid_data = pd.DataFrame({
        'ts_code': ['000001.SZ'],
        'trade_date': ['20251024'],
        'close': [10.5]
    })
    assert plugin.validate_data(valid_data) == True
    
    # Invalid data (missing column)
    invalid_data = pd.DataFrame({
        'ts_code': ['000001.SZ']
    })
    assert plugin.validate_data(invalid_data) == False


def test_load_data():
    """Test data loading."""
    plugin = MyPlugin()
    data = pd.DataFrame({
        'ts_code': ['000001.SZ'],
        'trade_date': ['20251024'],
        'close': [10.5]
    })
    
    result = plugin.load_data(data)
    assert result['status'] == 'success'
    assert result['total_records'] > 0
```

#### 集成测试
```bash
# 运行完整的 ETL 流程
uv run cli.py ingest-daily --date 20251024

# 检查数据是否成功加载
uv run cli.py status --date 20251024

# 运行质量检查
uv run cli.py quality-check --date 20251024
```

---

## 📊 监控和维护

### 1. 日志查看
```bash
# 查看最近的日志
tail -f logs/stock_datasource.log

# 查看错误日志
tail -f logs/errors.log

# 搜索特定插件的日志
grep "my_plugin" logs/stock_datasource.log
```

### 2. 数据质量监控
```bash
# 查看特定日期的质量检查结果
uv run cli.py quality-check --date 20251024

# 查看数据覆盖率
uv run cli.py coverage --table ods_daily

# 生成每日报告
uv run cli.py report --date 20251024
```

### 3. 性能监控
- 监控 API 调用次数和响应时间
- 监控数据库插入性能
- 监控内存使用情况

---

## 🔗 相关资源

- **TuShare 文档**：https://tushare.pro/
- **ClickHouse 文档**：https://clickhouse.com/docs/
- **Airflow 文档**：https://airflow.apache.org/docs/
- **Pandas 文档**：https://pandas.pydata.org/docs/

---

## 📝 常见问题

### Q1: 如何添加新的数据源？
A: 按照"新建插件指南"创建新的插件，实现 `extract_data()`、`validate_data()` 和 `load_data()` 三个方法。

### Q2: 如何修改表结构？
A: 编辑 `schema.json` 文件，添加或修改列定义。ClickHouse 支持 ALTER TABLE 操作，可以动态扩展表结构。

### Q3: 如何处理 API 限流？
A: 调整 `config.json` 中的 `rate_limit` 参数，或在 `extract_data()` 中添加重试逻辑。

### Q4: 如何调试插件？
A: 使用 `--verbose` 标志运行 CLI 命令，查看详细的日志输出。

### Q5: 如何处理数据质量问题？
A: 在 `validate_data()` 中添加更严格的检查，或在 `transform_data()` 中进行数据清洗。

---

## 📞 支持

如有问题，请：
1. 查看项目文档和示例
2. 检查日志文件
3. 提交 Issue 或 Pull Request

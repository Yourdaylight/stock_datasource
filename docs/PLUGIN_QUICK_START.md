# 新建插件快速参考

## 📦 插件文件结构

```
plugins/my_plugin/
├── __init__.py              # from .plugin import MyPlugin
├── plugin.py                # 插件主类，定义数据爬取的格式转换，入库前的校验和存储逻辑
├── extractor.py             # 数据爬取逻辑
├── config.json              # 插件配置，包括调用的接口名称，调度频率等
├── schema.json              # clickhouse表结构定义
├── service.py               # 数据查询的sdk， services/目录下的http_server与mcp_server会基于此文件生成对应的查询接口
└── README.md                # 插件文档
```

---

## 🚀 5 分钟快速开始

### 1️⃣ 创建插件目录
```bash
mkdir -p src/stock_datasource/plugins/my_plugin
cd src/stock_datasource/plugins/my_plugin
touch __init__.py plugin.py extractor.py config.json schema.json
```

### 2️⃣ 编写插件类 (plugin.py)
```python
import pandas as pd
from typing import Dict, Any
from stock_datasource.plugins import BasePlugin
from .extractor import extractor

class MyPlugin(BasePlugin):
    @property
    def name(self) -> str:
        return "my_plugin"
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """从数据源获取数据"""
        trade_date = kwargs.get('trade_date')
        data = extractor.extract(trade_date)
        return data if not data.empty else pd.DataFrame()
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """验证数据完整性"""
        if data.empty:
            return False
        required = ['ts_code', 'trade_date']
        return all(col in data.columns for col in required)
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """加载数据到数据库"""
        if not self.db or data.empty:
            return {"status": "no_data", "loaded_records": 0}
        
        try:
            data = self._prepare_data_for_insert('ods_my_table', data)
            data = self._add_system_columns(data)
            self.db.insert_dataframe('ods_my_table', data)
            return {
                "status": "success",
                "tables_loaded": [{"table": "ods_my_table", "records": len(data)}],
                "total_records": len(data)
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}
```

### 3️⃣ 编写数据提取器 (extractor.py)
```python
import pandas as pd
from stock_datasource.utils.logger import logger

class Extractor:
    def extract(self, trade_date: str) -> pd.DataFrame:
        """从 TuShare API 获取数据"""
        try:
            # 调用 TuShare API
            import tushare as ts
            pro = ts.pro_connect()
            data = pro.query('api_name', trade_date=trade_date)
            return pd.DataFrame(data)
        except Exception as e:
            logger.error(f"Extract failed: {e}")
            return pd.DataFrame()

extractor = Extractor()
```

### 4️⃣ 配置插件 (config.json)
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
  }
}
```

### 5️⃣ 定义表结构 (schema.json)
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
    {"name": "ts_code", "data_type": "String", "nullable": false},
    {"name": "trade_date", "data_type": "Date", "nullable": false},
    {"name": "value", "data_type": "Float64", "nullable": true},
    {"name": "version", "data_type": "Int64", "nullable": false},
    {"name": "_ingested_at", "data_type": "DateTime", "nullable": false}
  ]
}
```

### 6️⃣ 注册插件 (__init__.py)
```python
from .plugin import MyPlugin

__all__ = ['MyPlugin']
```

### 7️⃣ 测试插件
```bash
# 初始化数据库
uv run cli.py init-db

# 运行插件
uv run cli.py ingest-daily --date 20251024

# 检查状态
uv run cli.py status --date 20251024
```

---

## 🎯 三个必需方法

### extract_data(**kwargs) → pd.DataFrame
| 要求 | 说明 |
|------|------|
| 返回类型 | `pd.DataFrame` |
| 参数 | `trade_date`, `start_date`, `end_date` 等 |
| 异常处理 | 返回空 DataFrame，不要抛异常 |
| 日志 | 记录提取的记录数 |

### validate_data(data) → bool
| 要求 | 说明 |
|------|------|
| 返回类型 | `bool` |
| 检查项 | 空数据、必需列、空值、业务逻辑 |
| 日志 | 记录验证失败的原因 |

### load_data(data) → Dict
| 要求 | 说明 |
|------|------|
| 返回类型 | `Dict` with `status`, `tables_loaded`, `total_records` |
| 数据准备 | 调用 `_prepare_data_for_insert()` 和 `_add_system_columns()` |
| 异常处理 | 捕获异常，返回 `status: failed` |

---

## ✅ 检查清单

- [ ] 创建了插件目录和所有必需文件
- [ ] 实现了 `extract_data()` 方法
- [ ] 实现了 `validate_data()` 方法
- [ ] 实现了 `load_data()` 方法
- [ ] 编写了 `config.json` 配置
- [ ] 编写了 `schema.json` 表结构
- [ ] 在 `__init__.py` 中注册了插件
- [ ] 测试了插件的完整流程
- [ ] 检查了日志输出
- [ ] 验证了数据是否成功加载

---

## 🔧 常用代码片段

### 参数验证
```python
def extract_data(self, **kwargs) -> pd.DataFrame:
    trade_date = kwargs.get('trade_date')
    if not trade_date:
        raise ValueError("trade_date is required")
    # ...
```

### 类型转换
```python
def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
    # 数值转换
    data['close'] = pd.to_numeric(data['close'], errors='coerce')
    
    # 日期转换
    data['trade_date'] = pd.to_datetime(
        data['trade_date'], 
        format='%Y%m%d'
    ).dt.date
    
    return data
```

### 数据验证
```python
def validate_data(self, data: pd.DataFrame) -> bool:
    # 检查空数据
    if data.empty:
        return False
    
    # 检查必需列
    required = ['ts_code', 'trade_date']
    if not all(col in data.columns for col in required):
        return False
    
    # 检查空值
    if data['ts_code'].isnull().any():
        return False
    
    return True
```

### 数据加载
```python
def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
    if not self.db or data.empty:
        return {"status": "no_data", "loaded_records": 0}
    
    try:
        # 准备数据
        data = self._prepare_data_for_insert('ods_table', data)
        data = self._add_system_columns(data)
        
        # 插入数据
        self.db.insert_dataframe('ods_table', data)
        
        return {
            "status": "success",
            "tables_loaded": [{"table": "ods_table", "records": len(data)}],
            "total_records": len(data)
        }
    except Exception as e:
        self.logger.error(f"Load failed: {e}")
        return {"status": "failed", "error": str(e)}
```

---

## ⚠️ 常见错误

| 错误 | 原因 | 解决 |
|------|------|------|
| `ModuleNotFoundError` | 插件未注册 | 检查 `__init__.py` |
| `KeyError: 'column'` | 缺少列 | 在 validate 中检查 |
| `TypeError` | 数据类型错误 | 在 transform 中转换 |
| `Connection refused` | 数据库连接失败 | 检查 ClickHouse 配置 |
| `API rate limit` | 请求过于频繁 | 调整 `rate_limit` |

---

## 📚 相关文件

- 完整指南：`DEVELOPMENT_GUIDE.md`
- 项目概览：`README.md`
- 架构设计：`ARCHITECTURE.md`
- 现有插件：`src/stock_datasource/plugins/`

---

## 🎓 学习路径

1. **理解架构**：阅读 `README.md` 和 `ARCHITECTURE.md`
2. **查看示例**：研究 `tushare_daily` 插件的实现
3. **创建插件**：按照本指南创建第一个插件
4. **测试验证**：运行 CLI 命令验证功能
5. **优化改进**：根据日志和性能指标优化

---

## 💡 最佳实践

✅ **DO**
- 使用 `self.logger` 记录日志
- 在 validate 中进行全面检查
- 使用 `_prepare_data_for_insert()` 进行类型转换
- 返回结构化的结果字典
- 处理所有异常情况

❌ **DON'T**
- 在 extract 中进行数据转换
- 忽略异常，让其传播
- 返回 None 或其他非 DataFrame 类型
- 跳过数据验证
- 硬编码配置值

---

## 🚀 下一步

1. 创建你的第一个插件
2. 测试完整的 ETL 流程
3. 监控日志和数据质量
4. 根据需要优化性能
5. 提交 Pull Request 贡献代码

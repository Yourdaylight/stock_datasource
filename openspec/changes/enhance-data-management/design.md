# Design: 数据管理功能增强

## Context

当前系统使用插件化架构管理数据源，每个插件通过 `config.json` 定义调度频率（daily/weekly）。但数据管理界面仅返回Mock数据，无法：
1. 检测基于交易日的数据缺失
2. 展示同步任务执行状态
3. 直接查看插件数据

## Goals / Non-Goals

### Goals
- 实现基于交易日历的数据缺失检测（每日检查）
- 区分每日更新和周期性更新的插件
- 同步任务可视化（进度、状态、历史）
- 插件数据可直接跳转展示

### Non-Goals
- 不实现自动修复数据缺失（仅检测和手动触发）
- 不修改现有插件的执行逻辑
- 不实现复杂的任务调度系统（使用简单的内存队列）

## Decisions

### 1. 数据缺失检测策略

**决策**：基于交易日历表 `ods_trade_calendar` 检测各ODS表的数据缺失

**执行时间**：每日 16:00 自动执行（收盘后、数据更新前）

**实现方案**：
```sql
-- 获取最近N个交易日
SELECT cal_date FROM ods_trade_calendar 
WHERE is_open = 1 AND cal_date <= today() 
ORDER BY cal_date DESC LIMIT 30

-- 检查某表在某交易日是否有数据
SELECT COUNT(*) FROM ods_daily WHERE trade_date = :date
```

**理由**：
- 利用已有的交易日历数据
- 每个插件对应的ODS表有明确的日期字段
- 查询简单高效
- 16:00执行可在数据更新前发现问题

### 2. 插件调度频率识别

**决策**：从 `config.json` 的 `schedule.frequency` 字段读取

**插件分类**：
| 频率 | 插件 | 说明 |
|------|------|------|
| daily | tushare_daily, tushare_daily_basic, tushare_adj_factor, tushare_stk_limit, tushare_suspend_d, akshare_hk_daily | 每个交易日更新 |
| weekly | tushare_stock_basic, tushare_trade_calendar, akshare_hk_stock_list | 每周一更新 |

### 3. 同步任务管理

**决策**：使用内存队列 + 数据库持久化，**串行执行**

**执行模式**：
- 任务串行执行，同一时间只运行一个任务
- 新任务加入队列等待
- 避免数据源API限流和资源竞争

**历史保留**：30天，超过30天自动清理

**数据模型**：
```python
class SyncTask:
    task_id: str          # UUID
    plugin_name: str      # 插件名称
    task_type: str        # 'full' | 'incremental' | 'backfill'
    status: str           # 'pending' | 'running' | 'completed' | 'failed'
    progress: float       # 0-100
    records_processed: int
    error_message: str
    trade_dates: List[str]  # 目标日期列表
    started_at: datetime
    completed_at: datetime
```

**存储**：
- 运行时状态：内存字典
- 历史记录：ClickHouse表 `sync_task_history`
- 清理策略：每日凌晨清理30天前的记录

### 4. 插件数据状态API

**决策**：新增API端点返回各插件的数据状态

**响应结构**：
```json
{
  "plugin_name": "tushare_daily",
  "table_name": "ods_daily",
  "schedule_frequency": "daily",
  "latest_date": "2026-01-09",
  "missing_dates": ["2026-01-08", "2026-01-07"],
  "missing_count": 2,
  "total_records": 5000000,
  "data_preview_url": "/api/datamanage/plugins/tushare_daily/data"
}
```

### 5. 前端数据展示跳转

**决策**：使用弹窗展示插件数据预览

**交互流程**：
1. 点击插件行的"查看数据"按钮
2. 弹出数据预览弹窗
3. 展示最近N条数据
4. 支持日期筛选

### 6. 插件详情查看

**决策**：新增插件详情弹窗，展示插件的完整配置和数据结构

**展示内容**：
| 模块 | 来源 | 说明 |
|------|------|------|
| 基本信息 | `config.json` | 插件名称、描述、版本、调度配置 |
| 数据源接口 | `config.json` | API接口名称、参数定义 |
| 数据结构 | `schema.json` | 表名、字段定义、数据类型、分区键、排序键 |
| 运行状态 | 运行时 | 最新数据日期、缺失情况、执行历史 |

**API响应结构**：
```json
{
  "plugin_name": "tushare_daily",
  "version": "1.0.0",
  "description": "TuShare daily stock price data",
  "config": {
    "enabled": true,
    "rate_limit": 500,
    "timeout": 30,
    "schedule": {
      "frequency": "daily",
      "time": "18:00"
    },
    "parameters_schema": {...}
  },
  "schema": {
    "table_name": "ods_daily",
    "table_type": "ods",
    "columns": [...],
    "partition_by": "toYYYYMM(trade_date)",
    "order_by": ["ts_code", "trade_date"],
    "engine": "ReplacingMergeTree"
  },
  "status": {
    "latest_date": "2026-01-09",
    "missing_count": 2,
    "total_records": 5000000
  }
}
```

### 7. 插件包导入导出（预留）

**决策**：设计插件包格式，为后续AI生成插件和导入导出做准备

**插件包结构**（`.plugin.zip`）：
```
tushare_daily.plugin.zip
├── manifest.json      # 插件元信息
├── config.json        # 运行配置
├── schema.json        # 数据结构定义
├── plugin.py          # 插件主逻辑
├── extractor.py       # 数据提取器
├── service.py         # 服务层（可选）
└── README.md          # 文档（可选）
```

**manifest.json结构**：
```json
{
  "name": "tushare_daily",
  "version": "1.0.0",
  "description": "TuShare daily stock price data",
  "author": "system",
  "created_at": "2026-01-10",
  "dependencies": [],
  "data_source": "tushare",
  "api_interface": "daily"
}
```

**本期实现**：
- 仅实现插件详情查看API和前端展示
- 导入导出功能预留接口，后续实现

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 数据缺失检测查询可能较慢 | 使用缓存，每小时刷新一次 |
| 内存任务队列重启丢失 | 任务开始时立即写入数据库 |
| 大量缺失日期回填耗时 | 支持批量日期，显示进度 |

## Migration Plan

1. **Phase 1**：后端API实现（不影响现有功能）
2. **Phase 2**：前端界面重构（渐进式替换）
3. **Phase 3**：添加同步任务历史表

无需数据迁移，新增表结构即可。

## Confirmed Decisions

- [x] **数据缺失检测频率**：每日下午 16:00 自动执行一次，支持手动触发
- [x] **同步任务历史保留**：30天，超过30天自动清理
- [x] **任务执行模式**：串行执行，同一时间只运行一个任务

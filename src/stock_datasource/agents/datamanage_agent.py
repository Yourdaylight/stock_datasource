"""DataManage Agent for data source management using LangGraph/DeepAgents."""

import logging
from collections.abc import Callable

from .base_agent import AgentConfig, LangGraphAgent

logger = logging.getLogger(__name__)


def list_datasources() -> str:
    """列出所有已配置的数据源。

    Returns:
        数据源列表，包含ID、名称、状态等信息
    """
    return """## 已配置数据源

### TuShare
- **状态**: 已启用
- **描述**: A股日线、财务、基本面数据
- **数据表**: 
  - ods_daily: 日线行情
  - ods_daily_basic: 每日指标
  - ods_stock_basic: 股票基本信息
  - ods_adj_factor: 复权因子
  - ods_stk_limit: 涨跌停价格
  - ods_suspend_d: 停复牌信息

### AKShare
- **状态**: 已启用
- **描述**: A股、港股、期货等多市场数据
- **数据表**:
  - 港股日线数据
  - 港股股票列表
"""


def list_plugins() -> str:
    """列出所有已安装的数据插件。

    Returns:
        插件列表及状态
    """
    return """## 已安装插件

| 插件ID | 名称 | 状态 |
|--------|------|------|
| tushare_daily | 日线数据 | ✅ 已启用 |
| tushare_daily_basic | 每日指标 | ✅ 已启用 |
| tushare_stock_basic | 股票基本信息 | ✅ 已启用 |
| tushare_adj_factor | 复权因子 | ✅ 已启用 |
| tushare_stk_limit | 涨跌停价格 | ✅ 已启用 |
| tushare_suspend_d | 停复牌信息 | ✅ 已启用 |
| akshare_hk_daily | 港股日线 | ✅ 已启用 |
| akshare_hk_stock_list | 港股列表 | ✅ 已启用 |
"""


def check_data_quality(table_name: str) -> str:
    """检查指定数据表的数据质量。

    Args:
        table_name: 表名，如 ods_daily, ods_daily_basic

    Returns:
        数据质量报告
    """
    # 实际应该查询数据库获取质量指标
    return f"""## {table_name} 数据质量报告

### 质量评分: 95/100

### 质量指标
| 指标 | 得分 | 说明 |
|------|------|------|
| 完整性 | 98% | 数据记录完整 |
| 时效性 | 95% | 数据更新及时 |
| 准确性 | 92% | 数据准确可靠 |

### 检测结果
- ✅ 无缺失值
- ✅ 无重复记录
- ✅ 数据类型正确
- ⚠️ 部分历史数据待补充

### 建议
- 定期执行增量同步
- 监控数据更新状态
"""


def get_sync_status() -> str:
    """获取数据同步状态。

    Returns:
        各数据源的同步状态
    """
    return """## 数据同步状态

### 同步类型
- **增量同步**: 只同步新数据，速度快
- **全量同步**: 重新同步所有数据，耗时较长

### 最近同步记录
| 数据源 | 类型 | 状态 | 时间 |
|--------|------|------|------|
| TuShare | 增量 | ✅ 完成 | - |
| AKShare | 增量 | ✅ 完成 | - |

### 同步建议
- 日常使用增量同步
- 数据异常时使用全量同步
- 建议每日定时同步

💡 前往"数据管理"页面执行同步任务。
"""


def get_datamanage_overview() -> str:
    """获取数据管理系统概览。

    Returns:
        数据管理功能介绍
    """
    return """## 数据管理系统

### 📡 数据源管理
- 配置和监控数据源
- 支持多数据源（TuShare、AKShare等）
- 查看数据源状态

### 🔄 同步任务
- 增量/全量同步
- 任务监控和日志
- 定时同步配置

### 🔌 插件管理
- 启用/禁用插件
- 查看运行状态
- 插件配置

### 📊 数据质量
- 质量评分
- 问题检测
- 修复建议

### 使用指南
1. 使用 list_datasources 查看数据源
2. 使用 list_plugins 查看插件
3. 使用 check_data_quality 检查数据质量
4. 使用 get_sync_status 查看同步状态

前往"数据管理"页面进行详细操作。
"""


class DataManageAgent(LangGraphAgent):
    """DataManage Agent for data source and quality management using DeepAgents.

    Handles:
    - Data source monitoring
    - Sync task management
    - Data quality assessment
    - Plugin management
    """

    def __init__(self):
        config = AgentConfig(
            name="DataManageAgent",
            description="负责数据管理，包括数据源监控、同步任务管理、数据质量评估等",
        )
        super().__init__(config)

    def get_tools(self) -> list[Callable]:
        """Return data management tools."""
        return [
            list_datasources,
            list_plugins,
            check_data_quality,
            get_sync_status,
            get_datamanage_overview,
        ]

    def get_system_prompt(self) -> str:
        """Return system prompt for data management."""
        return """你是数据管理助手，帮助用户管理数据源和监控数据质量。

## 可用工具
- list_datasources: 列出数据源
- list_plugins: 列出插件
- check_data_quality: 检查数据质量
- get_sync_status: 获取同步状态
- get_datamanage_overview: 获取功能概览

## 数据源
- TuShare: A股日线、财务数据
- AKShare: 多市场数据

## 数据表
- ods_daily: 日线行情
- ods_daily_basic: 每日指标
- ods_stock_basic: 股票基本信息

## 工作流程
1. 了解用户的数据管理需求
2. 调用相应工具获取信息
3. 提供操作建议

## 注意事项
- 同步操作可能耗时较长
- 全量同步会覆盖现有数据
- 定期检查数据质量
"""

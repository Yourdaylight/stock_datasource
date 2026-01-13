# Design: optimize-plugin-dependencies

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Config Layer                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  config/trade_calendar.csv                               │   │
│  │  - cal_date, is_open, pretrade_date                      │   │
│  │  - 2000-01-01 ~ 2030-12-31                               │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Core Services Layer                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  TradeCalendarService (Singleton)                        │   │
│  │  - get_trading_days(n) -> List[str]                      │   │
│  │  - is_trading_day(date) -> bool                          │   │
│  │  - get_prev_trading_day(date) -> str                     │   │
│  │  - get_next_trading_day(date) -> str                     │   │
│  │  - get_trading_days_between(start, end) -> List[str]     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  PluginManager (Enhanced)                                │   │
│  │  - check_dependencies(plugin_name) -> DependencyResult   │   │
│  │  - execute_with_dependencies(plugin_name, **kwargs)      │   │
│  │  - get_dependency_graph() -> Dict                        │   │
│  │  - get_plugins_by_category(category) -> List[Plugin]     │   │
│  │  - batch_trigger_sync(plugin_names) -> List[Task]        │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Plugin Layer                               │
│                                                                  │
│  Category: stock                                                 │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │ stock_basic  │      │ daily        │      │ adj_factor   │  │
│  │ role: basic  │◀─────│ role: primary│─ ─ ─▶│ role: derived│  │
│  │ deps: []     │      │ deps: [basic]│      │ deps: [basic]│  │
│  └──────────────┘      │ opt: [adj]   │      └──────────────┘  │
│                        └──────────────┘                         │
│                                                                  │
│  Category: etf_fund (ETF/基金)                                   │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │ etf_basic    │      │ etf_daily    │      │ etf_adj      │  │
│  │ role: basic  │◀─────│ role: primary│─ ─ ─▶│ role: derived│  │
│  │ deps: []     │      │ deps: [basic]│      │ deps: [basic]│  │
│  └──────────────┘      │ opt: [adj]   │      └──────────────┘  │
│                        └──────────────┘                         │
│                                                                  │
│  Category: index                                                 │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │ index_basic  │      │ index_daily  │      │ index_weight │  │
│  │ role: basic  │◀─────│ role: primary│      │ role: aux    │  │
│  │ deps: []     │      │ deps: [basic]│      │ deps: [basic]│  │
│  └──────────────┘      └──────────────┘      └──────────────┘  │
│                                                                  │
│  Legend: ──▶ required dependency   ─ ─▶ optional dependency     │
└─────────────────────────────────────────────────────────────────┘
```

## Component Design

### 1. TradeCalendarService

**位置**: `src/stock_datasource/core/trade_calendar.py`

```python
class TradeCalendarService:
    """全局交易日历服务（单例模式）"""
    
    _instance = None
    _calendar_df: pd.DataFrame = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_calendar()
        return cls._instance
    
    def _load_calendar(self):
        """从 config/trade_calendar.csv 加载交易日历"""
        
    def get_trading_days(self, n: int = 30, end_date: str = None) -> List[str]:
        """获取最近 n 个交易日"""
        
    def is_trading_day(self, date: str) -> bool:
        """判断是否为交易日"""
        
    def get_prev_trading_day(self, date: str) -> str:
        """获取上一个交易日"""
        
    def get_next_trading_day(self, date: str) -> str:
        """获取下一个交易日"""
        
    def get_trading_days_between(self, start: str, end: str) -> List[str]:
        """获取两个日期之间的所有交易日"""
        
    def refresh_calendar(self):
        """手动刷新交易日历（从 TuShare 更新 CSV）"""
```

**设计决策**:
- 使用单例模式确保全局唯一实例
- 启动时加载 CSV 到内存，避免频繁 IO
- 提供 `refresh_calendar()` 方法支持手动更新

### 2. 插件分类与角色

**位置**: `src/stock_datasource/core/base_plugin.py`

```python
from enum import Enum

class PluginCategory(str, Enum):
    """插件分类"""
    STOCK = "stock"      # 股票相关
    INDEX = "index"      # 指数相关
    ETF_FUND = "etf_fund"  # ETF/基金相关（合并为一类）
    SYSTEM = "system"    # 系统数据

class PluginRole(str, Enum):
    """插件角色"""
    PRIMARY = "primary"    # 主数据（如 daily 行情）
    BASIC = "basic"        # 基础数据（如 stock_basic）
    DERIVED = "derived"    # 衍生数据（如复权因子）
    AUXILIARY = "auxiliary"  # 辅助数据（如指数权重）

class BasePlugin:
    def get_category(self) -> PluginCategory:
        """获取插件分类，子类应覆盖"""
        return PluginCategory.STOCK
    
    def get_role(self) -> PluginRole:
        """获取插件角色，子类应覆盖"""
        return PluginRole.PRIMARY
    
    def get_dependencies(self) -> List[str]:
        """获取必需依赖"""
        return []
    
    def get_optional_dependencies(self) -> List[str]:
        """获取可选依赖（如复权因子）
        
        可选依赖在同步主数据时默认关联同步，用户可选择关闭
        """
        return []
    
    def has_data(self) -> bool:
        """检查插件是否已有数据（供依赖检查使用）"""
        schema = self.get_schema()
        table_name = schema.get('table_name')
        if table_name and self.db:
            result = self.db.execute_query(f"SELECT 1 FROM {table_name} LIMIT 1")
            return result is not None and not result.empty
        return False
```

### 3. 插件依赖检查增强

**位置**: `src/stock_datasource/core/plugin_manager.py`

```python
@dataclass
class DependencyCheckResult:
    satisfied: bool
    missing_plugins: List[str]
    missing_data: Dict[str, str]  # {plugin_name: reason}
    optional_dependencies: List[str]  # 可选依赖列表
    
class PluginManager:
    def check_dependencies(self, plugin_name: str) -> DependencyCheckResult:
        """检查插件依赖是否满足
        
        检查内容:
        1. 依赖插件是否已注册
        2. 依赖插件的数据是否已存在
        """
        
    def execute_with_dependencies(
        self, 
        plugin_name: str, 
        auto_run_deps: bool = False,
        include_optional: bool = True,  # 是否包含可选依赖
        **kwargs
    ) -> Dict[str, Any]:
        """执行插件，可选自动执行依赖
        
        Args:
            plugin_name: 插件名称
            auto_run_deps: 是否自动执行未满足的依赖
            include_optional: 是否同步可选依赖（如复权因子）
            **kwargs: 插件参数
        """
        
    def get_dependency_graph(self) -> Dict[str, List[str]]:
        """获取所有插件的依赖关系图"""
    
    def get_plugins_by_category(self, category: PluginCategory) -> List[BasePlugin]:
        """按分类获取插件列表"""
        return [p for p in self.plugins.values() if p.get_category() == category]
    
    def get_plugins_by_role(self, role: PluginRole) -> List[BasePlugin]:
        """按角色获取插件列表"""
        return [p for p in self.plugins.values() if p.get_role() == role]
    
    def batch_trigger_sync(
        self, 
        plugin_names: List[str],
        task_type: str = "incremental",
        include_optional: bool = True
    ) -> List[Dict]:
        """批量触发同步任务
        
        自动按依赖顺序排序执行
        """
```

### 4. 插件依赖声明更新

| 插件文件 | 分类 | 角色 | 必需依赖 | 可选依赖 |
|---------|------|------|---------|---------|
| `tushare_stock_basic` | stock | basic | `[]` | `[]` |
| `tushare_daily` | stock | primary | `["tushare_stock_basic"]` | `["tushare_adj_factor"]` |
| `tushare_daily_basic` | stock | derived | `["tushare_stock_basic"]` | `[]` |
| `tushare_adj_factor` | stock | derived | `["tushare_stock_basic"]` | `[]` |
| `tushare_etf_basic` | etf_fund | basic | `[]` | `[]` |
| `tushare_etf_fund_daily` | etf_fund | primary | `["tushare_etf_basic"]` | `["tushare_etf_fund_adj"]` |
| `tushare_etf_fund_adj` | etf_fund | derived | `["tushare_etf_basic"]` | `[]` |
| `tushare_index_basic` | index | basic | `[]` | `[]` |
| `tushare_index_daily` | index | primary | `["tushare_index_basic"]` | `[]` |
| `tushare_index_weight` | index | auxiliary | `["tushare_index_basic"]` | `[]` |
| `tushare_idx_factor_pro` | index | derived | `["tushare_index_basic"]` | `[]` |

### 5. API 设计

**位置**: `src/stock_datasource/modules/datamanage/router.py`

```python
# 插件筛选
@router.get("/plugins")
async def get_plugins(
    category: Optional[str] = None,  # stock, index, etf_fund
    role: Optional[str] = None,      # primary, basic, derived, auxiliary
) -> List[PluginInfo]:
    """获取插件列表，支持按分类和角色筛选"""

# 依赖检查
@router.get("/plugins/{name}/dependencies")
async def get_plugin_dependencies(name: str) -> DependencyCheckResponse:
    """获取插件依赖详情，包含可选依赖"""

# 批量同步
@router.post("/sync/batch")
async def batch_trigger_sync(request: BatchSyncRequest) -> List[SyncTask]:
    """批量触发同步任务
    
    Request:
        plugin_names: List[str]  # 插件名称列表
        task_type: str           # incremental, full, backfill
        include_optional: bool   # 是否包含可选依赖（默认 true）
        trade_dates: List[str]   # 可选，指定日期
    """

# 按分类批量同步
@router.post("/sync/category/{category}")
async def sync_by_category(
    category: str,
    task_type: str = "incremental",
    include_optional: bool = True
) -> List[SyncTask]:
    """按分类触发所有插件同步"""
```

### 6. 前端设计

**PluginInfo 扩展**:
```typescript
interface PluginInfo {
  name: string
  version: string
  description: string
  category: 'stock' | 'index' | 'etf_fund' | 'system'
  role: 'primary' | 'basic' | 'derived' | 'auxiliary'
  dependencies: string[]
  optional_dependencies: string[]
  is_enabled: boolean
  // ... 其他字段
}
```

**前端功能**:
1. 插件列表顶部添加分类筛选 Tabs（全部/股票/指数/ETF基金）
2. 添加角色标签显示（主数据/基础/衍生/辅助）
3. 支持多选插件进行批量同步
4. 同步对话框添加"包含可选依赖"开关

## Data Flow

### 交易日历查询流程

```
1. 模块/插件请求交易日期
   │
   ▼
2. TradeCalendarService.get_trading_days()
   │
   ▼
3. 从内存缓存的 DataFrame 查询
   │
   ▼
4. 返回交易日期列表
```

### 插件执行流程（带依赖检查）

```
1. 用户触发插件执行（含可选依赖选项）
   │
   ▼
2. PluginManager.check_dependencies()
   │
   ├─ 依赖满足 ──────────────────────┐
   │                                  │
   ├─ 依赖不满足 + auto_run=true     │
   │   │                              │
   │   ▼                              │
   │  递归执行依赖插件                │
   │   │                              │
   │   ▼                              │
   │  依赖执行完成                    │
   │   │                              │
   │   └──────────────────────────────┤
   │                                  │
   ├─ 依赖不满足 + auto_run=false    │
   │   │                              │
   │   ▼                              │
   │  返回错误，提示缺失依赖          │
   │                                  │
   ▼                                  ▼
3. 执行目标插件
   │
   ├─ include_optional=true
   │   │
   │   ▼
   │  同时触发可选依赖（如复权因子）
   │
   ▼
4. 返回执行结果
```

### 批量同步流程

```
1. 用户选择多个插件 + 点击批量同步
   │
   ▼
2. 后端接收 plugin_names 列表
   │
   ▼
3. 构建依赖图，拓扑排序
   │
   ▼
4. 按顺序创建同步任务
   │
   ├─ 基础数据插件优先
   │   │
   │   ▼
   ├─ 主数据插件
   │   │
   │   ▼
   └─ 衍生/辅助数据插件
   │
   ▼
5. 返回任务列表
```

## Configuration

### trade_calendar.csv 格式

```csv
cal_date,is_open,pretrade_date
2026-12-31,1,20261230
2026-12-30,1,20261229
...
2000-01-04,1,20000103
2000-01-03,0,19991231
```

### 配置目录结构

```
src/stock_datasource/config/
├── __init__.py
├── trade_calendar.csv      # 交易日历数据
└── settings.py             # 其他全局配置（可选）
```

## Error Handling

### 依赖检查错误

```python
class DependencyNotSatisfiedError(Exception):
    """依赖未满足异常"""
    def __init__(self, plugin_name: str, missing: List[str], missing_data: Dict[str, str] = None):
        self.plugin_name = plugin_name
        self.missing = missing
        self.missing_data = missing_data or {}
        super().__init__(
            f"Plugin '{plugin_name}' dependencies not satisfied. "
            f"Missing: {', '.join(missing)}. "
            f"Please run the dependent plugins first."
        )
```

### 交易日历错误

```python
class TradeCalendarError(Exception):
    """交易日历异常"""
    pass

class CalendarNotFoundError(TradeCalendarError):
    """交易日历文件不存在"""
    pass

class InvalidDateError(TradeCalendarError):
    """无效的日期"""
    pass
```

## Migration Plan

1. **Phase 1**: 创建 `TradeCalendarService`，保持现有接口兼容 ✅
2. **Phase 2**: 更新 `datamanage/service.py` 使用新服务 ✅
3. **Phase 3**: 更新插件依赖声明 ✅
4. **Phase 4**: 增强 `PluginManager` 依赖检查 ✅
5. **Phase 5**: 添加插件分类和角色 (NEW)
6. **Phase 6**: 添加可选依赖支持 (NEW)
7. **Phase 7**: 添加批量同步 API (NEW)
8. **Phase 8**: 前端筛选和批量操作 (NEW)
9. **Phase 9**: 移除旧代码，完成文档

## Testing Strategy

### 单元测试

- `test_trade_calendar_service.py`: 交易日历服务测试
- `test_plugin_dependencies.py`: 插件依赖检查测试
- `test_plugin_category.py`: 插件分类筛选测试
- `test_batch_sync.py`: 批量同步测试

### 集成测试

- 测试完整的插件执行流程（含依赖检查）
- 测试自动执行依赖功能
- 测试可选依赖关联同步
- 测试批量同步按依赖顺序执行

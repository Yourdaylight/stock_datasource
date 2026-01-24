# Design: ETF 和指数界面增强

## 架构概述

### 前端组件关系

```
App.vue
├── menuItems[] ← 新增 /index 菜单项
│
router/index.ts
├── /etf → EtfScreenerView.vue
└── /index → IndexScreenerView.vue (新增路由)

views/etf/
├── EtfScreenerView.vue ← 增强筛选面板，添加日期选择
└── components/
    ├── EtfDetailDialog.vue
    └── EtfAnalysisPanel.vue

views/index/
├── IndexScreenerView.vue ← 增强筛选面板，复用 ETF 样式
└── components/
    ├── IndexDetailDialog.vue
    └── IndexAnalysisPanel.vue

components/
└── DataUpdateDialog.vue ← 新增：数据更新提示弹窗
```

## 筛选条件设计

### 筛选优先级

| 优先级 | 筛选项 | 说明 |
|--------|--------|------|
| P0 | 日期选择 | 核心功能，支持查看历史数据 |
| P0 | 名称/代码搜索 | 核心功能，快速定位 |
| P1 | 交易所/市场 | 基础筛选 |
| P1 | 涨跌幅区间 | 行情筛选 |
| P2 | 管理人/发布机构 | 扩展筛选 |
| P2 | 跟踪指数 | ETF 专属 |
| P3 | 费率区间 | 进阶筛选 |
| P3 | 成交额区间 | 流动性筛选 |

### ETF 筛选条件（增强后）

| 筛选项 | 类型 | 数据来源 | 优先级 |
|--------|------|----------|--------|
| **日期** | 日期选择器 | /api/etf/trade-dates | **P0** |
| 搜索 | 文本输入 | - | **P0** |
| 交易所 | 下拉单选 | /api/etf/exchanges | P1 |
| 基金类型 | 下拉单选 | /api/etf/types | P1 |
| 涨跌幅 | 下拉单选 | 固定区间 | P1 |
| 投资类型 | 下拉单选 | /api/etf/invest-types | 已有 |
| 状态 | 下拉单选 | 固定列表 | 已有 |
| 管理人 | 下拉单选 | /api/etf/managers | **P2** |
| 跟踪指数 | 下拉单选 | /api/etf/tracking-indices | **P2** |
| 管理费率 | 下拉单选 | 固定区间 | P3 |
| 成交额 | 下拉单选 | 固定区间 | P3 |

### 指数筛选条件（增强后）

| 筛选项 | 类型 | 数据来源 | 优先级 |
|--------|------|----------|--------|
| **日期** | 日期选择器 | /api/index/trade-dates | **P0** |
| 搜索 | 文本输入 | - | **P0** |
| 市场 | 下拉单选 | /api/index/markets | P1 |
| 类别 | 下拉单选 | /api/index/categories | P1 |
| 涨跌幅 | 下拉单选 | 固定区间 | P1 |
| 发布机构 | 下拉单选 | /api/index/publishers | **P2** |

## 日期切换与数据提示设计

### 日期选择器

```typescript
// 组件状态
const selectedDate = ref<string>('')  // 默认空表示最新
const availableDates = ref<string[]>([])

// 获取可用日期
const fetchTradeDates = async () => {
  const dates = await api.getTradeDates()
  availableDates.value = dates
  // 默认选中最新日期
  if (dates.length > 0 && !selectedDate.value) {
    selectedDate.value = dates[0]
  }
}
```

### 无数据提示弹窗

```vue
<!-- DataUpdateDialog.vue -->
<template>
  <el-dialog v-model="visible" title="数据提示" width="400px">
    <div class="dialog-content">
      <el-icon class="warning-icon"><WarningFilled /></el-icon>
      <p>当前日期 <strong>{{ date }}</strong> 暂无数据</p>
      <p class="tip">
        <el-icon><InfoFilled /></el-icon>
        您可以在「数据管理」中执行对应的插件来更新数据
      </p>
    </div>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="goToDataManagement">
        前往数据管理
      </el-button>
    </template>
  </el-dialog>
</template>
```

### 数据检查逻辑

```typescript
const checkAndFetchData = async () => {
  const result = await fetchData(selectedDate.value)
  
  if (result.total === 0) {
    // 显示无数据提示弹窗
    showDataUpdateDialog({
      date: selectedDate.value,
      pluginName: 'tushare_etf_fund_daily',  // 或对应的插件名
      onConfirm: () => {
        router.push('/data-management?plugin=tushare_etf_fund_daily')
      }
    })
  }
}
```

## 后端 API 设计

### ETF 新增 API

```typescript
// 获取管理人列表
GET /api/etf/managers
Response: [{ value: string, label: string, count: number }]

// 获取跟踪指数列表
GET /api/etf/tracking-indices
Response: [{ value: string, label: string, count: number }]

// 获取可用交易日期
GET /api/etf/trade-dates
Query: limit=30  // 最近N个交易日
Response: ["20260125", "20260124", ...]
```

### 指数新增 API

```typescript
// 获取发布机构列表
GET /api/index/publishers
Response: [{ value: string, label: string, count: number }]

// 获取可用交易日期
GET /api/index/trade-dates
Query: limit=30
Response: ["20260125", "20260124", ...]
```

### 筛选参数扩展

ETF 列表 API 新增参数：
- `trade_date`: 交易日期（YYYYMMDD）
- `manager`: 管理人筛选
- `tracking_index`: 跟踪指数筛选
- `fee_min` / `fee_max`: 费率区间
- `amount_min`: 最小成交额
- `pct_chg_min` / `pct_chg_max`: 涨跌幅区间

指数列表 API 新增参数：
- `trade_date`: 交易日期（YYYYMMDD）
- `publisher`: 发布机构筛选
- `pct_chg_min` / `pct_chg_max`: 涨跌幅区间

## 样式复用策略

### 共享样式

将 ETF 和指数页面共享的样式提取到公共样式文件或组件：

1. **快速访问卡片**：
   - 结构相同，仅渐变色不同
   - ETF：`#f093fb → #f5576c`（粉色系）
   - 指数：`#667eea → #764ba2`（紫色系）

2. **筛选面板**：
   - `.filter-section` / `.filter-item` / `.filter-label` 完全相同
   - 可提取为公共组件或共享 CSS

3. **表格样式**：
   - 分页、涨跌幅颜色、状态标签等保持一致

### 日期选择器样式

```css
.date-picker-section {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  border-radius: 8px;
  margin-bottom: 16px;
}

.date-picker-label {
  font-weight: 500;
  color: #606266;
}
```

## 前端实现要点

### 1. 路由和菜单

```typescript
// router/index.ts
{
  path: '/index',
  name: 'Index',
  component: () => import('@/views/index/IndexScreenerView.vue'),
  meta: { title: '指数行情', icon: 'trending-up', requiresAuth: true }
}
```

```typescript
// App.vue menuItems
{ path: '/index', title: '指数行情', icon: TrendingUpIcon, requiresAuth: true }
```

### 2. Store 扩展

```typescript
// stores/etf.ts 新增
const selectedDate = ref<string>('')
const selectedManager = ref<string>('')
const selectedTrackingIndex = ref<string>('')
const selectedFeeRange = ref<string>('')
const selectedAmountRange = ref<string>('')
const selectedPctChgRange = ref<string>('')

// stores/index.ts 新增
const selectedDate = ref<string>('')
const selectedPublisher = ref<string>('')
const selectedPctChgRange = ref<string>('')
```

### 3. 固定筛选区间

```typescript
// 涨跌幅区间
const pctChgRangeOptions = [
  { value: '', label: '全部涨跌幅' },
  { value: 'up', label: '上涨' },
  { value: 'down', label: '下跌' },
  { value: 'up2+', label: '涨幅>2%' },
  { value: 'up5+', label: '涨幅>5%' },
  { value: 'down2+', label: '跌幅>2%' },
  { value: 'down5+', label: '跌幅>5%' },
]

// ETF 管理费率区间
const feeRangeOptions = [
  { value: '', label: '全部费率' },
  { value: '0-0.2', label: '0-0.2%' },
  { value: '0.2-0.5', label: '0.2%-0.5%' },
  { value: '0.5+', label: '0.5%以上' },
]

// ETF 成交额区间
const amountRangeOptions = [
  { value: '', label: '全部成交额' },
  { value: '1000+', label: '1000万以上' },
  { value: '5000+', label: '5000万以上' },
  { value: '1e+', label: '1亿以上' },
]
```

## 后端实现要点

### ETF Service 新增方法

```python
def get_managers(self) -> List[Dict[str, Any]]:
    """获取所有管理人列表"""
    query = """
    SELECT 
        mgr_name as value,
        mgr_name as label,
        count() as count
    FROM ods_etf_basic
    WHERE mgr_name IS NOT NULL AND mgr_name != ''
    GROUP BY mgr_name
    ORDER BY count DESC
    """
    return _execute_query(query)

def get_tracking_indices(self) -> List[Dict[str, Any]]:
    """获取所有跟踪指数列表"""
    query = """
    SELECT 
        index_code as value,
        index_name as label,
        count() as count
    FROM ods_etf_basic
    WHERE index_code IS NOT NULL AND index_code != ''
    GROUP BY index_code, index_name
    ORDER BY count DESC
    """
    return _execute_query(query)

def get_trade_dates(self, limit: int = 30) -> List[str]:
    """获取可用交易日期列表"""
    query = f"""
    SELECT DISTINCT trade_date
    FROM ods_etf_fund_daily
    ORDER BY trade_date DESC
    LIMIT {limit}
    """
    result = _execute_query(query)
    return [r['trade_date'] for r in result]
```

### Index Service 新增方法

```python
def get_publishers(self) -> List[Dict[str, Any]]:
    """获取所有发布机构列表"""
    query = """
    SELECT 
        publisher as value,
        publisher as label,
        count() as count
    FROM dim_index_basic
    WHERE publisher IS NOT NULL AND publisher != ''
    GROUP BY publisher
    ORDER BY count DESC
    """
    return _execute_query(query)

def get_trade_dates(self, limit: int = 30) -> List[str]:
    """获取可用交易日期列表"""
    query = f"""
    SELECT DISTINCT trade_date
    FROM ods_index_daily
    ORDER BY trade_date DESC
    LIMIT {limit}
    """
    result = _execute_query(query)
    return [r['trade_date'] for r in result]
```

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 历史数据量大导致查询慢 | 高 | 限制日期范围，添加索引 |
| 行情筛选性能问题 | 中 | 预计算涨跌幅字段，添加索引 |
| 筛选条件过多影响 UX | 中 | 使用折叠面板，P0/P1 优先显示 |
| 日期选择器交互复杂 | 低 | 使用 Element Plus 日期组件 |

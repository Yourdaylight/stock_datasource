# Design: add-hk-stock-support

## 1. 股票代码识别策略

### 代码后缀规则
| 后缀 | 市场 | 示例 |
|------|------|------|
| `.SZ` | 深圳 A 股 | 000001.SZ |
| `.SH` | 上海 A 股 | 600000.SH |
| `.HK` | 港股 | 00700.HK |

### 市场类型枚举
```python
class MarketType(Enum):
    A_SHARE = "a_share"      # A股
    HK_STOCK = "hk_stock"    # 港股
    UNKNOWN = "unknown"

def detect_market_type(ts_code: str) -> MarketType:
    if ts_code.endswith('.HK'):
        return MarketType.HK_STOCK
    elif ts_code.endswith(('.SZ', '.SH')):
        return MarketType.A_SHARE
    return MarketType.UNKNOWN
```

## 2. 数据源路由

### K 线数据路由
```
请求 /api/market/kline
    ↓
检测 ts_code 后缀
    ├── .SZ/.SH → tushare_daily + tushare_adj_factor
    └── .HK → tushare_hk_daily + tushare_hk_adjfactor
```

### 股票名称查询路由
```
请求股票名称
    ├── A股 → tushare_stock_basic
    └── 港股 → tushare_hk_basic
```

## 3. 前端适配方案

### StockDetailDialog 功能模块

| 功能模块 | A股 | 港股 | 说明 |
|----------|-----|------|------|
| K 线图 | ✅ | ✅ | 通用 |
| 技术指标 | ✅ | ✅ | 通用 |
| AI 分析 | ✅ | ✅ | 通用 |
| 筹码峰 | ✅ | ❌ | 港股无数据 |
| 十维画像 | ✅ | ❌ | 港股暂不支持 |
| 加入自选 | ✅ | ✅ | 通用 |

### 条件渲染逻辑
```vue
<script setup>
const isHKStock = computed(() => props.stockCode?.endsWith('.HK'))
</script>

<template>
  <!-- 筹码峰：仅 A 股显示 -->
  <t-card v-if="!isHKStock" title="筹码峰">
    <ChipDistributionChart ... />
  </t-card>
  
  <!-- 十维画像：仅 A 股显示 -->
  <t-card v-if="!isHKStock" title="十维画像">
    ...
  </t-card>
</template>
```

## 4. 股票列表扩展

### 新增市场类型筛选
```typescript
interface StockListParams {
  market_type?: 'all' | 'a_share' | 'hk_stock'  // 新增
  page?: number
  page_size?: number
  ...
}
```

### 后端 API 扩展
```
GET /api/screener/stocks?market_type=hk_stock
```

## 5. 数据表映射

| 功能 | A 股数据表 | 港股数据表 |
|------|-----------|-----------|
| 基础信息 | ods_stock_basic | ods_hk_basic |
| 日线行情 | ods_daily | ods_hk_daily |
| 复权因子 | ods_adj_factor | ods_hk_adjfactor |
| 交易日历 | ods_trade_calendar | ods_hk_trade_cal |

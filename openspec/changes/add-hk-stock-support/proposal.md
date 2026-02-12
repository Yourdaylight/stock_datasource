# Proposal: add-hk-stock-support

## Summary
在股票详情页面和股票列表中支持港股数据的展示和查询。

## Background
当前系统已有以下港股数据插件：
- `tushare_hk_basic`: 港股基础信息（股票代码、名称、上市状态等）
- `tushare_hk_daily`: 港股日线行情数据（开高低收、涨跌幅等）
- `tushare_hk_adjfactor`: 港股复权因子
- `tushare_hk_tradecal`: 港股交易日历

但前端股票详情页面（`StockDetailDialog.vue`）和股票列表目前仅支持 A 股数据展示。

## Goals
1. 股票详情页面能够正确识别并展示港股数据
2. 股票列表支持显示港股数据
3. K 线图和行情数据能正确加载港股数据

## Non-Goals
- 不涉及港股筹码峰数据（目前无数据源）
- 不涉及港股十维画像评分（暂不实现）
- 不涉及港股 AI 分析（可复用现有功能）

## Approach
1. **后端扩展**：扩展 Market Service 支持港股代码识别和数据查询
2. **前端适配**：修改 `StockDetailDialog` 根据股票类型动态展示/隐藏功能模块
3. **股票列表**：添加市场类型筛选，支持切换 A 股/港股列表

## Affected Components
- `src/stock_datasource/modules/market/service.py` - 扩展 K 线查询支持港股
- `frontend/src/components/StockDetailDialog.vue` - 适配港股展示
- `frontend/src/api/market.ts` - 添加港股相关 API
- `frontend/src/views/screener/ScreenerView.vue` - 股票列表支持港股

## Risks
- 港股与 A 股交易时间不同，需注意时区处理
- 港股没有涨跌停限制，UI 显示需要适配

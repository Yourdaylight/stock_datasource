# Tasks: add-predefined-plugin-groups

## Phase 1: 后端配置与数据模型

- [x] 1.1 创建预定义组合配置文件
  - [x] 创建 `config/predefined_groups.json`
  - [x] 定义 10 个预定义组合
  - [x] 包含组合元数据（名称、描述、分类、插件列表）

- [x] 1.2 扩展数据模型
  - [x] 在 `schemas.py` 中扩展 `PluginGroup` 模型
  - [x] 添加 `is_predefined` 字段
  - [x] 添加 `is_readonly` 字段
  - [x] 添加 `category` 字段

- [x] 1.3 实现配置加载
  - [x] 在 `runtime_config.py` 中添加 `load_predefined_groups()` 函数
  - [x] 系统启动时自动加载预定义组合
  - [x] 与用户自定义组合合并返回

## Phase 2: API 扩展

- [x] 2.1 扩展组合列表 API
  - [x] 修改 `GET /api/datamanage/groups` 返回预定义组合
  - [x] 返回 `is_predefined` 和 `is_readonly` 标识
  - [x] 支持按 `category` 筛选

- [x] 2.2 新增预定义组合专用 API
  - [x] 实现 `GET /api/datamanage/groups/predefined`
  - [x] 返回预定义组合列表和分类列表

- [x] 2.3 保护预定义组合
  - [x] 修改 `DELETE /api/datamanage/groups/{id}` 拒绝删除预定义组合
  - [x] 修改 `PUT /api/datamanage/groups/{id}` 拒绝修改预定义组合

## Phase 3: 前端展示改进

- [x] 3.1 组合列表分类展示
  - [x] 添加分类筛选 Tabs（全部/A股/指数/ETF基金/每日更新）
  - [x] 分组显示：预定义组合 + 我的组合
  - [x] 预定义组合显示特殊标识（如 🔒 图标）

- [x] 3.2 组合操作按钮调整
  - [x] 预定义组合隐藏"编辑"和"删除"按钮
  - [x] 保留"执行"按钮
  - [x] 新增"详情"按钮

- [x] 3.3 新增组合详情弹窗
  - [x] 创建 `GroupDetailDialog.vue` 组件
  - [x] 展示组合包含的插件列表
  - [x] 展示依赖关系图（简化版）
  - [x] 展示执行顺序说明

- [x] 3.4 API 类型定义
  - [x] 在 `api/datamanage.ts` 中扩展 `PluginGroup` 类型
  - [x] 添加 `is_predefined` 和 `is_readonly` 字段
  - [x] 添加 `category` 字段

- [x] 3.5 状态管理更新
  - [x] 在 `stores/datamanage.ts` 中添加预定义组合相关状态
  - [x] 实现分类筛选逻辑
  - [x] 实现预定义组合与自定义组合分离显示

## Phase 4: 测试与验证

- [ ] 4.1 后端测试
  - [ ] 验证配置文件正确加载
  - [ ] 验证 API 返回正确的组合数据
  - [ ] 验证预定义组合无法删除/修改

- [ ] 4.2 前端测试
  - [ ] 验证分类筛选功能
  - [ ] 验证预定义组合正确显示
  - [ ] 验证详情弹窗内容
  - [ ] 验证执行同步功能

- [ ] 4.3 端到端测试
  - [ ] 执行"A股财务报表-基础版"组合同步
  - [ ] 验证依赖顺序正确（tushare_stock_basic 先执行）
  - [ ] 验证数据正确写入

## Dependencies

- Phase 1 无外部依赖，可独立开发
- Phase 2 依赖 Phase 1 完成
- Phase 3 依赖 Phase 2 完成
- Phase 4 依赖 Phase 1-3 完成

## 预定义组合清单

### A股相关 (cn_stock)

| 组合ID | 组合名称 | 插件列表 |
|--------|----------|----------|
| predefined_cn_stock_basic | A股基础数据 | tushare_stock_basic |
| predefined_cn_stock_daily | A股日线行情 | tushare_stock_basic, tushare_daily, tushare_adj_factor |
| predefined_financial_basic | A股财务报表-基础版 | tushare_stock_basic, tushare_income, tushare_balancesheet, tushare_cashflow |
| predefined_financial_full | A股财务报表-完整版 | tushare_stock_basic, tushare_income, tushare_balancesheet, tushare_cashflow, tushare_forecast, tushare_express, tushare_fina_audit |
| predefined_financial_vip | A股财务报表-VIP批量版 | tushare_stock_basic, tushare_income_vip, tushare_balancesheet_vip, tushare_cashflow_vip |

### 指数相关 (index)

| 组合ID | 组合名称 | 插件列表 |
|--------|----------|----------|
| predefined_index_basic | 指数基础数据 | tushare_index_basic |
| predefined_index_full | 指数完整数据 | tushare_index_basic, tushare_index_weight, tushare_idx_factor_pro |

### ETF基金相关 (etf_fund)

| 组合ID | 组合名称 | 插件列表 |
|--------|----------|----------|
| predefined_etf_basic | ETF基础数据 | tushare_etf_basic |
| predefined_etf_full | ETF完整数据 | tushare_etf_basic, tushare_etf_fund_daily, tushare_etf_fund_adj |

### 每日更新 (daily)

| 组合ID | 组合名称 | 插件列表 |
|--------|----------|----------|
| predefined_daily_update | 全市场每日更新 | tushare_daily, tushare_daily_basic, tushare_adj_factor, tushare_etf_fund_daily |

## 实现清单

### 后端文件

1. **新增文件**
   - `config/predefined_groups.json` - 预定义组合配置

2. **修改文件**
   - `src/stock_datasource/modules/datamanage/schemas.py` - 扩展 PluginGroup 模型
   - `src/stock_datasource/modules/datamanage/router.py` - 扩展/新增 API
   - `src/stock_datasource/config/runtime_config.py` - 加载预定义组合

### 前端文件

1. **新增文件**
   - `frontend/src/views/datamanage/components/GroupDetailDialog.vue` - 组合详情弹窗

2. **修改文件**
   - `frontend/src/views/datamanage/DataManageView.vue` - 组合列表展示改进
   - `frontend/src/api/datamanage.ts` - API 类型定义
   - `frontend/src/stores/datamanage.ts` - 状态管理

## 验收标准

1. ✅ 系统启动后，"自定义组合" Tab 显示 10 个预定义组合
2. ✅ 预定义组合显示 🔒 标识，无法编辑或删除
3. ✅ 可按分类筛选组合（A股/指数/ETF基金/每日更新）
4. ✅ 点击"详情"显示组合包含的插件和依赖关系
5. ✅ 点击"执行"可正常触发同步，按依赖顺序执行
6. ✅ 用户自定义组合与预定义组合共存显示

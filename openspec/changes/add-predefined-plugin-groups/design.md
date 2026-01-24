# Design: add-predefined-plugin-groups

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Configuration Layer                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  config/predefined_groups.json                                       │   │
│  │  - 预定义组合元数据                                                   │   │
│  │  - 组合ID、名称、描述、分类、插件列表                                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Service Layer                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  runtime_config.py                                                   │   │
│  │  - load_predefined_groups() 加载预定义组合                           │   │
│  │  - merge_groups() 合并预定义 + 用户自定义组合                         │   │
│  │  - is_predefined_group() 判断是否为预定义组合                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  PluginManager                                                       │   │
│  │  - check_dependencies() 检查组合中插件的依赖                          │   │
│  │  - batch_trigger_sync() 按依赖顺序批量执行                            │   │
│  │  - get_dependency_graph() 获取依赖关系图                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API Layer                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  /api/datamanage/groups                                              │   │
│  │  - GET: 返回所有组合（预定义 + 用户自定义）                           │   │
│  │  - POST: 创建用户自定义组合                                          │   │
│  │                                                                      │   │
│  │  /api/datamanage/groups/predefined                                   │   │
│  │  - GET: 仅返回预定义组合                                              │   │
│  │                                                                      │   │
│  │  /api/datamanage/groups/{id}                                         │   │
│  │  - GET: 获取组合详情                                                  │   │
│  │  - PUT: 修改组合（拒绝预定义组合）                                    │   │
│  │  - DELETE: 删除组合（拒绝预定义组合）                                 │   │
│  │                                                                      │   │
│  │  /api/datamanage/groups/{id}/trigger                                 │   │
│  │  - POST: 触发组合同步                                                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Frontend Layer                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  DataManageView.vue - 自定义组合 Tab                                  │   │
│  │  ├─ 分类筛选 Tabs（全部/A股/指数/ETF基金/每日更新）                   │   │
│  │  ├─ 预定义组合列表（🔒 标识，无编辑/删除）                            │   │
│  │  └─ 用户自定义组合列表                                                │   │
│  │                                                                      │   │
│  │  GroupDetailDialog.vue - 组合详情弹窗                                 │   │
│  │  ├─ 基本信息（名称、描述、分类）                                      │   │
│  │  ├─ 插件列表                                                          │   │
│  │  ├─ 依赖关系图                                                        │   │
│  │  └─ 执行顺序说明                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Model

### PluginGroup 扩展模型

```python
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from enum import Enum

class GroupCategory(str, Enum):
    """组合分类"""
    CN_STOCK = "cn_stock"    # A股相关
    INDEX = "index"          # 指数相关
    ETF_FUND = "etf_fund"    # ETF基金相关
    DAILY = "daily"          # 每日更新
    CUSTOM = "custom"        # 用户自定义（无分类）

class PluginGroup(BaseModel):
    """插件组合模型"""
    group_id: str                              # 组合ID
    name: str                                  # 组合名称
    description: str = ""                      # 组合描述
    plugin_names: List[str]                    # 包含的插件列表
    default_task_type: str = "incremental"    # 默认同步类型
    category: GroupCategory = GroupCategory.CUSTOM  # 分类
    is_predefined: bool = False               # 是否为预定义组合
    is_readonly: bool = False                 # 是否只读
    created_at: datetime                      # 创建时间
    updated_at: Optional[datetime] = None     # 更新时间

class PluginGroupListResponse(BaseModel):
    """组合列表响应"""
    groups: List[PluginGroup]
    total: int
    predefined_count: int
    custom_count: int
```

### 预定义组合配置格式

```json
// config/predefined_groups.json
{
  "version": "1.0",
  "groups": [
    {
      "group_id": "predefined_cn_stock_basic",
      "name": "A股基础数据",
      "description": "A股股票基础信息，是其他A股数据的依赖基础",
      "plugin_names": ["tushare_stock_basic"],
      "default_task_type": "full",
      "category": "cn_stock"
    },
    {
      "group_id": "predefined_cn_stock_daily",
      "name": "A股日线行情",
      "description": "A股日线行情数据（含基础信息和复权因子）",
      "plugin_names": [
        "tushare_stock_basic",
        "tushare_daily",
        "tushare_adj_factor"
      ],
      "default_task_type": "incremental",
      "category": "cn_stock"
    },
    {
      "group_id": "predefined_financial_basic",
      "name": "A股财务报表-基础版",
      "description": "三大财务报表（利润表、资产负债表、现金流量表）",
      "plugin_names": [
        "tushare_stock_basic",
        "tushare_income",
        "tushare_balancesheet",
        "tushare_cashflow"
      ],
      "default_task_type": "incremental",
      "category": "cn_stock"
    },
    {
      "group_id": "predefined_financial_full",
      "name": "A股财务报表-完整版",
      "description": "完整财务数据（三大报表+业绩预告+业绩快报+审计意见）",
      "plugin_names": [
        "tushare_stock_basic",
        "tushare_income",
        "tushare_balancesheet",
        "tushare_cashflow",
        "tushare_forecast",
        "tushare_express",
        "tushare_fina_audit"
      ],
      "default_task_type": "incremental",
      "category": "cn_stock"
    },
    {
      "group_id": "predefined_financial_vip",
      "name": "A股财务报表-VIP批量版",
      "description": "VIP接口批量获取全市场财务数据（需5000积分）",
      "plugin_names": [
        "tushare_stock_basic",
        "tushare_income_vip",
        "tushare_balancesheet_vip",
        "tushare_cashflow_vip"
      ],
      "default_task_type": "full",
      "category": "cn_stock"
    },
    {
      "group_id": "predefined_index_basic",
      "name": "指数基础数据",
      "description": "指数基础信息，是其他指数数据的依赖基础",
      "plugin_names": ["tushare_index_basic"],
      "default_task_type": "full",
      "category": "index"
    },
    {
      "group_id": "predefined_index_full",
      "name": "指数完整数据",
      "description": "指数完整数据（基础信息+成分权重+技术因子）",
      "plugin_names": [
        "tushare_index_basic",
        "tushare_index_weight",
        "tushare_idx_factor_pro"
      ],
      "default_task_type": "incremental",
      "category": "index"
    },
    {
      "group_id": "predefined_etf_basic",
      "name": "ETF基础数据",
      "description": "ETF基础信息",
      "plugin_names": ["tushare_etf_basic"],
      "default_task_type": "full",
      "category": "etf_fund"
    },
    {
      "group_id": "predefined_etf_full",
      "name": "ETF完整数据",
      "description": "ETF完整数据（基础信息+日线行情+复权因子）",
      "plugin_names": [
        "tushare_etf_basic",
        "tushare_etf_fund_daily",
        "tushare_etf_fund_adj"
      ],
      "default_task_type": "incremental",
      "category": "etf_fund"
    },
    {
      "group_id": "predefined_daily_update",
      "name": "全市场每日更新",
      "description": "每日需要更新的全部数据（适合定时调度）",
      "plugin_names": [
        "tushare_daily",
        "tushare_daily_basic",
        "tushare_adj_factor",
        "tushare_etf_fund_daily"
      ],
      "default_task_type": "incremental",
      "category": "daily"
    }
  ],
  "categories": [
    {"key": "cn_stock", "label": "A股", "order": 1},
    {"key": "index", "label": "指数", "order": 2},
    {"key": "etf_fund", "label": "ETF基金", "order": 3},
    {"key": "daily", "label": "每日更新", "order": 4}
  ]
}
```

## API Design

### 获取组合列表（扩展）

```python
@router.get("/groups", response_model=PluginGroupListResponse)
async def list_plugin_groups(
    category: Optional[GroupCategory] = None,
    include_predefined: bool = True
) -> PluginGroupListResponse:
    """获取插件组合列表
    
    Args:
        category: 可选，按分类筛选
        include_predefined: 是否包含预定义组合，默认 True
    
    Returns:
        组合列表，预定义组合排在前面
    """
    # 1. 加载预定义组合
    predefined_groups = load_predefined_groups() if include_predefined else []
    
    # 2. 加载用户自定义组合
    custom_groups = get_custom_plugin_groups()
    
    # 3. 按分类筛选
    all_groups = predefined_groups + custom_groups
    if category:
        all_groups = [g for g in all_groups if g.category == category]
    
    return PluginGroupListResponse(
        groups=all_groups,
        total=len(all_groups),
        predefined_count=len([g for g in all_groups if g.is_predefined]),
        custom_count=len([g for g in all_groups if not g.is_predefined])
    )
```

### 获取组合详情

```python
@router.get("/groups/{group_id}", response_model=PluginGroupDetail)
async def get_plugin_group_detail(group_id: str) -> PluginGroupDetail:
    """获取组合详情，包含依赖关系图
    
    Returns:
        组合详情，包括：
        - 基本信息
        - 插件列表及状态
        - 依赖关系图
        - 执行顺序
    """
    group = get_group_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # 获取插件状态
    plugin_status = []
    for name in group.plugin_names:
        plugin = plugin_manager.get_plugin(name)
        plugin_status.append({
            "name": name,
            "exists": plugin is not None,
            "has_data": plugin.has_data() if plugin else False
        })
    
    # 获取依赖图
    dependency_graph = build_dependency_graph(group.plugin_names)
    
    # 计算执行顺序
    execution_order = topological_sort(dependency_graph)
    
    return PluginGroupDetail(
        **group.dict(),
        plugin_status=plugin_status,
        dependency_graph=dependency_graph,
        execution_order=execution_order
    )
```

### 保护预定义组合

```python
@router.put("/groups/{group_id}")
async def update_plugin_group(
    group_id: str, 
    request: PluginGroupUpdateRequest
) -> PluginGroup:
    """更新组合，拒绝修改预定义组合"""
    if is_predefined_group(group_id):
        raise HTTPException(
            status_code=403, 
            detail="Cannot modify predefined group"
        )
    # ... 原有逻辑

@router.delete("/groups/{group_id}")
async def delete_plugin_group(group_id: str):
    """删除组合，拒绝删除预定义组合"""
    if is_predefined_group(group_id):
        raise HTTPException(
            status_code=403, 
            detail="Cannot delete predefined group"
        )
    # ... 原有逻辑
```

## Frontend Design

### TypeScript 类型定义

```typescript
// api/datamanage.ts

export type GroupCategory = 'cn_stock' | 'index' | 'etf_fund' | 'daily' | 'custom'

export interface PluginGroup {
  group_id: string
  name: string
  description: string
  plugin_names: string[]
  default_task_type: 'incremental' | 'full' | 'backfill'
  category: GroupCategory
  is_predefined: boolean
  is_readonly: boolean
  created_at: string
  updated_at?: string
}

export interface PluginGroupListResponse {
  groups: PluginGroup[]
  total: number
  predefined_count: number
  custom_count: number
}

export interface GroupPluginStatus {
  name: string
  exists: boolean
  has_data: boolean
}

export interface PluginGroupDetail extends PluginGroup {
  plugin_status: GroupPluginStatus[]
  dependency_graph: Record<string, string[]>
  execution_order: string[]
}

export interface GroupCategoryInfo {
  key: GroupCategory
  label: string
  order: number
}
```

### 组合列表组件更新

```vue
<!-- DataManageView.vue 片段 -->
<template>
  <!-- Plugin Groups Tab -->
  <t-tab-panel value="groups" label="自定义组合">
    <!-- 分类筛选 Tabs -->
    <div class="category-tabs">
      <t-radio-group v-model="selectedCategory" variant="default-filled">
        <t-radio-button value="">全部</t-radio-button>
        <t-radio-button value="cn_stock">A股</t-radio-button>
        <t-radio-button value="index">指数</t-radio-button>
        <t-radio-button value="etf_fund">ETF基金</t-radio-button>
        <t-radio-button value="daily">每日更新</t-radio-button>
      </t-radio-group>
    </div>

    <!-- 预定义组合 -->
    <div v-if="predefinedGroups.length > 0" class="group-section">
      <h4 class="section-title">
        <t-icon name="lock-on" />
        预定义组合 ({{ predefinedGroups.length }})
      </h4>
      <t-table :data="predefinedGroups" ...>
        <template #operation="{ row }">
          <t-space>
            <t-link theme="primary" @click="handleTriggerGroup(row)">执行</t-link>
            <t-link theme="default" @click="handleShowDetail(row)">详情</t-link>
            <!-- 无编辑/删除按钮 -->
          </t-space>
        </template>
      </t-table>
    </div>

    <!-- 用户自定义组合 -->
    <div class="group-section">
      <h4 class="section-title">
        <t-icon name="folder" />
        我的组合 ({{ customGroups.length }})
      </h4>
      <t-table :data="customGroups" ...>
        <template #operation="{ row }">
          <t-space>
            <t-link theme="primary" @click="handleTriggerGroup(row)">执行</t-link>
            <t-link theme="default" @click="handleEditGroup(row)">编辑</t-link>
            <t-popconfirm @confirm="handleDeleteGroup(row)">
              <t-link theme="danger">删除</t-link>
            </t-popconfirm>
          </t-space>
        </template>
      </t-table>
    </div>
  </t-tab-panel>
</template>
```

### 组合详情弹窗

```vue
<!-- GroupDetailDialog.vue -->
<template>
  <t-dialog
    v-model:visible="dialogVisible"
    :header="group?.name"
    width="700px"
  >
    <div class="group-detail">
      <!-- 基本信息 -->
      <t-descriptions :column="2" bordered>
        <t-descriptions-item label="组合名称">{{ group?.name }}</t-descriptions-item>
        <t-descriptions-item label="分类">
          <t-tag>{{ getCategoryLabel(group?.category) }}</t-tag>
        </t-descriptions-item>
        <t-descriptions-item label="描述" :span="2">{{ group?.description }}</t-descriptions-item>
        <t-descriptions-item label="插件数量">{{ group?.plugin_names?.length }}</t-descriptions-item>
        <t-descriptions-item label="默认同步类型">
          <t-tag :theme="getTaskTypeTheme(group?.default_task_type)">
            {{ getTaskTypeLabel(group?.default_task_type) }}
          </t-tag>
        </t-descriptions-item>
      </t-descriptions>

      <!-- 插件列表 -->
      <div class="plugin-list">
        <h4>包含的插件</h4>
        <t-table
          :data="detail?.plugin_status"
          :columns="[
            { colKey: 'name', title: '插件名称' },
            { colKey: 'exists', title: '插件状态' },
            { colKey: 'has_data', title: '数据状态' }
          ]"
          size="small"
        >
          <template #exists="{ row }">
            <t-tag :theme="row.exists ? 'success' : 'danger'">
              {{ row.exists ? '已安装' : '未安装' }}
            </t-tag>
          </template>
          <template #has_data="{ row }">
            <t-tag :theme="row.has_data ? 'success' : 'warning'">
              {{ row.has_data ? '有数据' : '无数据' }}
            </t-tag>
          </template>
        </t-table>
      </div>

      <!-- 执行顺序 -->
      <div class="execution-order">
        <h4>执行顺序</h4>
        <t-steps :current="0" readonly>
          <t-step-item 
            v-for="(name, index) in detail?.execution_order" 
            :key="name"
            :title="name"
          />
        </t-steps>
      </div>
    </div>

    <template #footer>
      <t-button theme="default" @click="dialogVisible = false">关闭</t-button>
      <t-button theme="primary" @click="handleExecute">执行同步</t-button>
    </template>
  </t-dialog>
</template>
```

## Dependency Graph Visualization

### 依赖关系图数据结构

```typescript
// 依赖关系图示例（A股财务报表-基础版）
{
  "dependency_graph": {
    "tushare_stock_basic": [],
    "tushare_income": ["tushare_stock_basic"],
    "tushare_balancesheet": ["tushare_stock_basic"],
    "tushare_cashflow": ["tushare_stock_basic"]
  },
  "execution_order": [
    "tushare_stock_basic",
    "tushare_income",
    "tushare_balancesheet",
    "tushare_cashflow"
  ]
}
```

### 可视化渲染（简化版）

```
执行顺序：
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  Step 1                    Step 2 (并行)                        │
│  ┌──────────────┐         ┌──────────────┐                     │
│  │ stock_basic  │────────▶│   income     │                     │
│  │              │    │    └──────────────┘                     │
│  │  (基础数据)   │    │    ┌──────────────┐                     │
│  │              │────├───▶│ balancesheet │                     │
│  │              │    │    └──────────────┘                     │
│  │              │    │    ┌──────────────┐                     │
│  └──────────────┘────└───▶│  cashflow    │                     │
│                           └──────────────┘                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Error Handling

### 插件不可用

当预定义组合中的某个插件未安装时：
1. 组合仍然显示，但标记为"部分不可用"
2. 详情弹窗中显示缺失的插件
3. 尝试执行时提示用户"以下插件未安装：xxx"

### 依赖检查失败

当执行组合同步时依赖检查失败：
1. 系统按现有逻辑返回 400 错误
2. 前端显示缺失的依赖数据
3. 提示用户先同步依赖插件

## Migration

### 现有组合数据兼容

1. 现有用户自定义组合保持不变
2. 新增 `is_predefined` 和 `is_readonly` 字段，默认值为 `false`
3. 新增 `category` 字段，默认值为 `"custom"`

### 升级流程

1. 更新后端代码，部署新版本
2. 系统启动时自动加载 `predefined_groups.json`
3. 前端自动展示预定义组合
4. 无需数据库迁移

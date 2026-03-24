<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import {
  apiAccessApi,
  type PolicyInfo,
  type EndpointInfo,
  type UsageStatItem,
  type UpdatePolicyRequest,
} from '@/api/apiAccess'

// ---- State ----
const activeTab = ref('endpoints')
const loading = ref(false)

// Endpoints / Policies
const endpoints = ref<EndpointInfo[]>([])
const policies = ref<PolicyInfo[]>([])
const syncing = ref(false)

// Usage
const usageStats = ref<UsageStatItem[]>([])
const usagePeriod = ref('')
const usageTotalCalls = ref(0)
const usageDays = ref(7)
const usageLoading = ref(false)
const usageLoaded = ref(false)

// Edit dialog
const showEditDialog = ref(false)
const editForm = ref<UpdatePolicyRequest & { api_path: string }>({
  api_path: '',
  is_enabled: false,
  rate_limit_per_min: 60,
  rate_limit_per_day: 10000,
  max_records: 5000,
  description: '',
})

// Detail drawer
const showDetailDrawer = ref(false)
const detailEndpoint = ref<EndpointInfo | null>(null)

// Batch selection
const selectedPaths = ref<string[]>([])

// ---- Computed ----
const endpointColumns = [
  { colKey: 'row-select', type: 'multiple', width: 50 },
  { colKey: 'plugin_name', title: '插件', width: 140 },
  { colKey: 'method_name', title: '方法', width: 180 },
  { colKey: 'description', title: '描述', ellipsis: true },
  { colKey: 'is_enabled', title: '状态', width: 100 },
  { colKey: 'rate_limit', title: '速率限制', width: 160 },
  { colKey: 'max_records', title: '最大记录', width: 100 },
  { colKey: 'actions', title: '操作', width: 200 },
]

const usageColumns = [
  { colKey: 'api_path', title: '接口路径', ellipsis: true },
  { colKey: 'total_calls', title: '总调用次数', width: 120, sorter: true },
  { colKey: 'success_calls', title: '成功', width: 80 },
  { colKey: 'error_calls', title: '失败', width: 80 },
  { colKey: 'avg_response_ms', title: '平均响应(ms)', width: 130, sorter: true },
  { colKey: 'total_records', title: '总记录数', width: 120, sorter: true },
]

const enabledCount = computed(() => endpoints.value.filter(e => e.is_enabled).length)

const mergedEndpoints = computed(() => {
  // Merge endpoints with policy details
  const policyMap = new Map(policies.value.map(p => [p.api_path, p]))
  return endpoints.value.map(ep => {
    const policy = policyMap.get(ep.api_path)
    return {
      ...ep,
      is_enabled: policy ? policy.is_enabled : ep.is_enabled,
      rate_limit_per_min: policy?.rate_limit_per_min ?? 60,
      rate_limit_per_day: policy?.rate_limit_per_day ?? 10000,
      max_records: policy?.max_records ?? 5000,
      description: policy?.description || ep.description,
    }
  })
})

// ---- API calls ----
const loadData = async () => {
  loading.value = true
  try {
    const [endpointRes, policyRes] = await Promise.all([
      apiAccessApi.getEndpoints().catch(() => null),
      apiAccessApi.getPolicies().catch(() => null),
    ])
    if (endpointRes) endpoints.value = endpointRes.endpoints
    if (policyRes) policies.value = policyRes.policies
  } finally {
    loading.value = false
  }
}

const loadUsage = async () => {
  usageLoading.value = true
  try {
    const res = await apiAccessApi.getUsageStats({ days: usageDays.value })
    usageStats.value = res.stats
    usagePeriod.value = res.period
    usageTotalCalls.value = res.total_calls
    usageLoaded.value = true
  } catch {
    usageStats.value = []
  } finally {
    usageLoading.value = false
  }
}

const handleSync = async () => {
  syncing.value = true
  try {
    const res = await apiAccessApi.syncPolicies()
    if (res.success) {
      MessagePlugin.success(res.message)
      await loadData()
    } else {
      MessagePlugin.error(res.message)
    }
  } catch {
    MessagePlugin.error('同步失败')
  } finally {
    syncing.value = false
  }
}

// ---- Toggle ----
const handleToggle = async (row: any) => {
  try {
    const res = await apiAccessApi.updatePolicy(row.api_path, {
      is_enabled: !row.is_enabled,
    })
    if (res.success) {
      MessagePlugin.success(row.is_enabled ? '已禁用' : '已启用')
      await loadData()
    }
  } catch {
    MessagePlugin.error('操作失败')
  }
}

// ---- Batch toggle ----
const handleBatchToggle = async (enabled: boolean) => {
  if (selectedPaths.value.length === 0) {
    MessagePlugin.warning('请先选择接口')
    return
  }
  try {
    const res = await apiAccessApi.batchToggle({
      api_paths: selectedPaths.value,
      is_enabled: enabled,
    })
    if (res.success) {
      MessagePlugin.success(res.message)
      selectedPaths.value = []
      await loadData()
    }
  } catch {
    MessagePlugin.error('批量操作失败')
  }
}

const handleSelectChange = (selectedRowKeys: Array<string | number>) => {
  selectedPaths.value = selectedRowKeys.map(String)
}

// ---- Edit dialog ----
const openEditDialog = (row: any) => {
  editForm.value = {
    api_path: row.api_path,
    is_enabled: row.is_enabled,
    rate_limit_per_min: row.rate_limit_per_min,
    rate_limit_per_day: row.rate_limit_per_day,
    max_records: row.max_records,
    description: row.description || '',
  }
  showEditDialog.value = true
}

const handleSavePolicy = async () => {
  const { api_path, ...data } = editForm.value
  try {
    const res = await apiAccessApi.updatePolicy(api_path, data)
    if (res.success) {
      MessagePlugin.success('策略保存成功')
      showEditDialog.value = false
      await loadData()
    } else {
      MessagePlugin.error(res.message)
    }
  } catch {
    MessagePlugin.error('保存失败')
  }
}

// ---- Detail drawer ----
const openDetailDrawer = (row: EndpointInfo) => {
  detailEndpoint.value = row
  showDetailDrawer.value = true
}

const generateCurl = (ep: EndpointInfo) => {
  const baseUrl = window.location.origin
  const params: Record<string, string> = {}
  for (const p of ep.parameters) {
    if (p.required) {
      params[p.name] = p.default != null ? String(p.default) : `<${p.name}>`
    }
  }
  const body = Object.keys(params).length > 0 ? JSON.stringify(params, null, 2) : '{}'
  return `curl -X POST ${baseUrl}/api/open/v1/${ep.api_path} \\\n  -H "Authorization: Bearer sk-YOUR_API_KEY" \\\n  -H "Content-Type: application/json" \\\n  -d '${body}'`
}

const copyCurl = (ep: EndpointInfo) => {
  navigator.clipboard.writeText(generateCurl(ep))
  MessagePlugin.success('已复制 curl 命令')
}

// ---- Tab switch ----
const handleTabChange = (val: string | number) => {
  if (val === 'usage' && !usageLoaded.value) {
    loadUsage()
  }
}

const daysOptions = [
  { label: '最近7天', value: 7 },
  { label: '最近30天', value: 30 },
  { label: '最近90天', value: 90 },
]

onMounted(() => {
  loadData()
})
</script>

<template>
  <div class="api-access-view">
    <!-- Header stats bar -->
    <div class="stats-bar">
      <div class="stat-item">
        <span class="stat-value">{{ endpoints.length }}</span>
        <span class="stat-label">全部接口</span>
      </div>
      <div class="stat-item">
        <span class="stat-value enabled-value">{{ enabledCount }}</span>
        <span class="stat-label">已开放</span>
      </div>
      <div class="stat-item">
        <span class="stat-value disabled-value">{{ endpoints.length - enabledCount }}</span>
        <span class="stat-label">未开放</span>
      </div>
      <div class="stat-actions">
        <t-button theme="primary" variant="outline" :loading="syncing" @click="handleSync">
          从插件同步
        </t-button>
      </div>
    </div>

    <!-- Tabs -->
    <t-tabs v-model="activeTab" @change="handleTabChange">
      <!-- Tab 1: Endpoint Management -->
      <t-tab-panel value="endpoints" label="接口管理">
        <t-card :bordered="false">
          <!-- Batch actions -->
          <div class="batch-bar" v-if="selectedPaths.length > 0">
            <span class="batch-info">已选 {{ selectedPaths.length }} 个接口</span>
            <t-space>
              <t-button size="small" theme="success" variant="outline" @click="handleBatchToggle(true)">
                批量启用
              </t-button>
              <t-button size="small" theme="danger" variant="outline" @click="handleBatchToggle(false)">
                批量禁用
              </t-button>
            </t-space>
          </div>

          <t-table
            :data="mergedEndpoints"
            :columns="endpointColumns"
            :loading="loading"
            row-key="api_path"
            :selected-row-keys="selectedPaths"
            @select-change="handleSelectChange"
            hover
            stripe
            size="medium"
            :pagination="{ pageSize: 20 }"
          >
            <template #plugin_name="{ row }">
              <t-tag theme="primary" variant="light" size="small">{{ row.plugin_name }}</t-tag>
            </template>
            <template #method_name="{ row }">
              <span class="mono">{{ row.method_name }}</span>
            </template>
            <template #is_enabled="{ row }">
              <t-tag v-if="row.is_enabled" theme="success" variant="light">已开放</t-tag>
              <t-tag v-else theme="default" variant="light">未开放</t-tag>
            </template>
            <template #rate_limit="{ row }">
              <span class="rate-limit-text">{{ row.rate_limit_per_min }}/分 · {{ row.rate_limit_per_day }}/天</span>
            </template>
            <template #max_records="{ row }">
              <span>{{ row.max_records?.toLocaleString() }}</span>
            </template>
            <template #actions="{ row }">
              <t-space size="small">
                <t-button size="small" variant="text" theme="primary" @click="openDetailDrawer(row)">
                  详情
                </t-button>
                <t-button size="small" variant="text" theme="primary" @click="openEditDialog(row)">
                  配置
                </t-button>
                <t-popconfirm
                  :content="row.is_enabled ? '确定禁用该接口？' : '确定启用该接口？'"
                  @confirm="handleToggle(row)"
                >
                  <t-button
                    size="small"
                    variant="text"
                    :theme="row.is_enabled ? 'danger' : 'success'"
                  >
                    {{ row.is_enabled ? '禁用' : '启用' }}
                  </t-button>
                </t-popconfirm>
              </t-space>
            </template>
          </t-table>
        </t-card>
      </t-tab-panel>

      <!-- Tab 2: Usage Statistics -->
      <t-tab-panel value="usage" label="用量统计">
        <t-card :bordered="false">
          <template #title>
            <div class="usage-header">
              <div>
                <span class="card-title">API 调用统计</span>
                <span class="usage-period" v-if="usagePeriod">（{{ usagePeriod }}）</span>
                <span class="usage-total" v-if="usageTotalCalls > 0">
                  · 总计 {{ usageTotalCalls.toLocaleString() }} 次调用
                </span>
              </div>
              <t-space>
                <t-select v-model="usageDays" :options="daysOptions" style="width: 140px" @change="loadUsage" />
              </t-space>
            </div>
          </template>
          <t-table
            :data="usageStats"
            :columns="usageColumns"
            :loading="usageLoading"
            row-key="api_path"
            hover
            stripe
            size="medium"
            :pagination="{ pageSize: 20 }"
          >
            <template #api_path="{ row }">
              <span class="mono">{{ row.api_path }}</span>
            </template>
            <template #success_calls="{ row }">
              <span class="success-text">{{ row.success_calls }}</span>
            </template>
            <template #error_calls="{ row }">
              <span :class="row.error_calls > 0 ? 'error-text' : ''">{{ row.error_calls }}</span>
            </template>
            <template #avg_response_ms="{ row }">
              <span :class="row.avg_response_ms > 1000 ? 'warning-text' : ''">
                {{ row.avg_response_ms?.toFixed(1) }}
              </span>
            </template>
          </t-table>
        </t-card>
      </t-tab-panel>
    </t-tabs>

    <!-- Edit Policy Dialog -->
    <t-dialog
      v-model:visible="showEditDialog"
      header="配置接口策略"
      :footer="false"
      width="520px"
      destroy-on-close
    >
      <div class="edit-path">
        <t-tag theme="primary" variant="light">{{ editForm.api_path }}</t-tag>
      </div>
      <t-form :data="editForm" label-width="100px">
        <t-form-item label="开放状态">
          <t-switch v-model="editForm.is_enabled" />
        </t-form-item>
        <t-form-item label="每分钟限制">
          <t-input-number v-model="editForm.rate_limit_per_min" :min="1" :max="100000" style="width: 200px" />
          <span class="form-hint">次/分钟</span>
        </t-form-item>
        <t-form-item label="每天限制">
          <t-input-number v-model="editForm.rate_limit_per_day" :min="1" :max="10000000" style="width: 200px" />
          <span class="form-hint">次/天</span>
        </t-form-item>
        <t-form-item label="最大记录数">
          <t-input-number v-model="editForm.max_records" :min="100" :max="1000000" :step="100" style="width: 200px" />
          <span class="form-hint">条/次</span>
        </t-form-item>
        <t-form-item label="描述">
          <t-textarea v-model="editForm.description" :maxlength="200" placeholder="接口描述（可选）" />
        </t-form-item>
        <t-form-item label=" ">
          <t-space>
            <t-button theme="primary" @click="handleSavePolicy">保存</t-button>
            <t-button variant="outline" @click="showEditDialog = false">取消</t-button>
          </t-space>
        </t-form-item>
      </t-form>
    </t-dialog>

    <!-- Detail Drawer -->
    <t-drawer
      v-model:visible="showDetailDrawer"
      :header="detailEndpoint ? `${detailEndpoint.plugin_name} / ${detailEndpoint.method_name}` : '接口详情'"
      size="520px"
      :footer="false"
    >
      <div v-if="detailEndpoint" class="detail-content">
        <!-- Basic info -->
        <div class="detail-section">
          <h4 class="detail-section-title">基本信息</h4>
          <div class="detail-row">
            <span class="detail-label">API 路径</span>
            <span class="detail-value mono">/api/open/v1/{{ detailEndpoint.api_path }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">请求方式</span>
            <t-tag theme="warning" variant="light" size="small">POST</t-tag>
          </div>
          <div class="detail-row">
            <span class="detail-label">描述</span>
            <span class="detail-value">{{ detailEndpoint.description || '暂无描述' }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">状态</span>
            <t-tag v-if="detailEndpoint.is_enabled" theme="success" variant="light">已开放</t-tag>
            <t-tag v-else theme="default" variant="light">未开放</t-tag>
          </div>
        </div>

        <!-- Parameters -->
        <div class="detail-section" v-if="detailEndpoint.parameters.length > 0">
          <h4 class="detail-section-title">请求参数</h4>
          <div class="param-table">
            <div class="param-header">
              <span class="param-col name">参数名</span>
              <span class="param-col type">类型</span>
              <span class="param-col required">必填</span>
              <span class="param-col desc">说明</span>
            </div>
            <div v-for="p in detailEndpoint.parameters" :key="p.name" class="param-row">
              <span class="param-col name mono">{{ p.name }}</span>
              <span class="param-col type">
                <t-tag size="small" variant="light">{{ p.type }}</t-tag>
              </span>
              <span class="param-col required">
                <t-tag v-if="p.required" theme="danger" variant="light" size="small">是</t-tag>
                <t-tag v-else theme="default" variant="light" size="small">否</t-tag>
              </span>
              <span class="param-col desc">{{ p.description || '--' }}</span>
            </div>
          </div>
        </div>

        <!-- cURL example -->
        <div class="detail-section">
          <div class="curl-header">
            <h4 class="detail-section-title">示例调用</h4>
            <t-button size="small" variant="text" theme="primary" @click="copyCurl(detailEndpoint)">
              复制
            </t-button>
          </div>
          <pre class="curl-code">{{ generateCurl(detailEndpoint) }}</pre>
        </div>
      </div>
    </t-drawer>
  </div>
</template>

<style scoped>
.api-access-view {
  padding: 0 4px;
  min-height: 100%;
}

/* Stats bar */
.stats-bar {
  display: flex;
  align-items: center;
  gap: 32px;
  background: #fff;
  border-radius: 8px;
  padding: 20px 24px;
  margin-bottom: 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #262626;
  line-height: 1.2;
}

.enabled-value { color: #00a870; }
.disabled-value { color: #86909c; }

.stat-label {
  font-size: 13px;
  color: #86909c;
  margin-top: 4px;
}

.stat-actions {
  margin-left: auto;
}

/* Batch bar */
.batch-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  margin-bottom: 12px;
  background: #f0f7ff;
  border-radius: 6px;
  border: 1px solid #bbd3f0;
}

.batch-info {
  color: #0052d9;
  font-size: 14px;
  font-weight: 500;
}

/* Table helpers */
.mono {
  font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
  font-size: 13px;
}

.rate-limit-text {
  font-size: 13px;
  color: #595959;
}

.success-text { color: #00a870; }
.error-text { color: #e34d59; }
.warning-text { color: #ed7b2f; }

/* Usage header */
.usage-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: #262626;
}

.usage-period {
  font-size: 14px;
  color: #86909c;
  margin-left: 4px;
}

.usage-total {
  font-size: 14px;
  color: #595959;
  margin-left: 4px;
}

/* Edit dialog */
.edit-path {
  margin-bottom: 20px;
}

.form-hint {
  font-size: 13px;
  color: #86909c;
  margin-left: 8px;
}

/* Detail drawer */
.detail-content {
  padding: 0;
}

.detail-section {
  margin-bottom: 24px;
}

.detail-section-title {
  margin: 0 0 12px 0;
  font-size: 15px;
  font-weight: 600;
  color: #262626;
  padding-bottom: 8px;
  border-bottom: 1px solid #f0f0f0;
}

.detail-row {
  display: flex;
  align-items: flex-start;
  padding: 6px 0;
}

.detail-label {
  flex-shrink: 0;
  width: 80px;
  font-size: 13px;
  color: #86909c;
}

.detail-value {
  font-size: 13px;
  color: #262626;
}

/* Param table */
.param-table {
  border: 1px solid #e7e9ef;
  border-radius: 6px;
  overflow: hidden;
}

.param-header {
  display: flex;
  background: #f7f8fa;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 600;
  color: #86909c;
}

.param-row {
  display: flex;
  padding: 8px 12px;
  font-size: 13px;
  border-top: 1px solid #f0f0f0;
}

.param-col.name { flex: 0 0 120px; }
.param-col.type { flex: 0 0 80px; }
.param-col.required { flex: 0 0 60px; }
.param-col.desc { flex: 1; color: #595959; }

/* cURL */
.curl-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0;
}

.curl-header .detail-section-title {
  margin-bottom: 0;
  border-bottom: none;
  padding-bottom: 0;
}

.curl-code {
  background: linear-gradient(180deg, #0b1220 0%, #111827 100%);
  color: #e5e7eb;
  padding: 14px;
  border-radius: 8px;
  font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-wrap: break-word;
  margin-top: 8px;
  overflow-x: auto;
}
</style>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { datamanageApi } from '@/api/datamanage'
import type { RealtimeConfig, RealtimePluginInfo, RealtimeStatus } from '@/api/datamanage'

const loading = ref(false)
const config = ref<RealtimeConfig>({
  enabled: false,
  watchlist_monitor_enabled: false,
  collect_freq: '1MIN',
  plugin_configs: {}
})
const plugins = ref<RealtimePluginInfo[]>([])
const status = ref<RealtimeStatus>({
  global_enabled: false,
  watchlist_monitor_enabled: false,
  collect_freq: '1MIN',
  total_plugins: 0,
  enabled_plugins: 0,
  watchlist_count: 0,
  watchlist_codes: []
})

const showWatchlistCodes = ref(false)

const freqOptions = [
  { label: '1分钟', value: '1MIN' },
  { label: '5分钟', value: '5MIN' },
  { label: '15分钟', value: '15MIN' },
  { label: '30分钟', value: '30MIN' },
  { label: '60分钟', value: '60MIN' }
]

const pluginColumns = [
  { colKey: 'display_name', title: '插件名称', minWidth: 160 },
  { colKey: 'description', title: '说明', minWidth: 180, ellipsis: true },
  { colKey: 'category', title: '类别', width: 100 },
  { colKey: 'api_name', title: 'API', width: 100 },
  { colKey: 'tags', title: '标签', width: 180 },
  { colKey: 'enabled', title: '启用', width: 80 }
]

const getCategoryText = (cat: string) => {
  const map: Record<string, string> = {
    CN_STOCK: 'A股', ETF: 'ETF基金', INDEX: '指数', HK_STOCK: '港股'
  }
  return map[cat] || cat || '-'
}

const getCategoryTheme = (cat: string): string => {
  const map: Record<string, string> = {
    CN_STOCK: 'primary', ETF: 'warning', INDEX: 'success', HK_STOCK: 'danger'
  }
  return map[cat] || 'default'
}

const enabledPluginCount = computed(() => plugins.value.filter(p => p.enabled).length)

async function fetchAll() {
  loading.value = true
  const [cfgRes, pluginsRes, statusRes] = await Promise.all([
    datamanageApi.getRealtimeConfig(),
    datamanageApi.getRealtimePlugins(),
    datamanageApi.getRealtimeStatus()
  ])
  config.value = cfgRes
  plugins.value = pluginsRes
  status.value = statusRes
  loading.value = false
}

async function handleGlobalToggle(val: boolean) {
  loading.value = true
  const res = await datamanageApi.updateRealtimeConfig({ enabled: val })
  config.value = res
  await fetchAll()
  MessagePlugin.success(val ? '实时数据服务已开启' : '实时数据服务已关闭')
}

async function handleWatchlistToggle(val: boolean) {
  loading.value = true
  const res = await datamanageApi.updateRealtimeConfig({ watchlist_monitor_enabled: val })
  config.value = res
  await fetchAll()
  MessagePlugin.success(val ? '自选股联动已开启' : '自选股联动已关闭')
}

async function handleFreqChange(val: string) {
  loading.value = true
  const res = await datamanageApi.updateRealtimeConfig({ collect_freq: val })
  config.value = res
  MessagePlugin.success(`采集频率已更新为 ${val}`)
  loading.value = false
}

async function handlePluginToggle(pluginName: string, enabled: boolean) {
  loading.value = true
  await datamanageApi.updateRealtimePluginConfig(pluginName, enabled)
  await fetchAll()
  MessagePlugin.success(`${pluginName} 已${enabled ? '启用' : '禁用'}`)
}

async function handleSyncWatchlist() {
  loading.value = true
  await datamanageApi.syncWatchlistToRealtime()
  await fetchAll()
  MessagePlugin.success('自选股已同步到实时采集')
}

onMounted(() => {
  fetchAll()
})
</script>

<template>
  <div class="realtime-panel">
    <!-- 全局控制卡片 -->
    <t-card :bordered="false" class="control-card">
      <div class="control-header">
        <div class="control-left">
          <div class="control-title">
            <t-icon name="play-circle" size="20px" style="color: var(--td-brand-color)" />
            <span class="title-text">实时数据服务</span>
            <t-tag
              :theme="config.enabled ? 'success' : 'default'"
              variant="light"
              size="small"
            >
              {{ config.enabled ? '运行中' : '已关闭' }}
            </t-tag>
          </div>
          <div class="control-desc">
            管理所有实时数据插件的采集状态，开启后将自动联动自选股监控
          </div>
        </div>
        <t-switch
          :value="config.enabled"
          size="large"
          @change="handleGlobalToggle"
        />
      </div>

      <t-divider />

      <div class="freq-row">
        <span class="freq-label">默认采集频率</span>
        <t-radio-group
          :value="config.collect_freq"
          variant="default-filled"
          size="small"
          :disabled="!config.enabled"
          @change="handleFreqChange"
        >
          <t-radio-button v-for="opt in freqOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </t-radio-button>
        </t-radio-group>
      </div>
    </t-card>

    <!-- 自选股联动 + 统计 -->
    <t-row :gutter="16" style="margin-top: 16px">
      <t-col :span="6">
        <t-card :bordered="false" class="watchlist-card">
          <div class="watchlist-header">
            <div class="watchlist-info">
              <t-icon name="star" size="18px" style="color: var(--td-warning-color)" />
              <span class="watchlist-title">自选股联动</span>
              <t-tag
                :theme="config.watchlist_monitor_enabled ? 'success' : 'default'"
                variant="light"
                size="small"
              >
                {{ config.watchlist_monitor_enabled ? '已开启' : '已关闭' }}
              </t-tag>
            </div>
            <t-switch
              :value="config.watchlist_monitor_enabled"
              :disabled="!config.enabled"
              @change="handleWatchlistToggle"
            />
          </div>
          <div class="watchlist-stats">
            <span class="stat-label">自选股数量</span>
            <span class="stat-num">{{ status.watchlist_count }}</span>
          </div>
          <div v-if="status.watchlist_codes.length > 0" class="watchlist-codes-section">
            <t-link theme="primary" @click="showWatchlistCodes = !showWatchlistCodes">
              {{ showWatchlistCodes ? '收起' : '查看代码列表' }}
              <t-icon :name="showWatchlistCodes ? 'chevron-up' : 'chevron-down'" size="14px" />
            </t-link>
            <div v-if="showWatchlistCodes" class="codes-list">
              <t-tag
                v-for="code in status.watchlist_codes"
                :key="code"
                size="small"
                variant="outline"
                style="margin: 2px"
              >
                {{ code }}
              </t-tag>
              <t-tag v-if="status.watchlist_count > 20" size="small" variant="light" theme="default">
                +{{ status.watchlist_count - 20 }} 更多
              </t-tag>
            </div>
          </div>
          <div class="watchlist-actions">
            <t-button
              size="small"
              variant="outline"
              :disabled="!config.enabled || !config.watchlist_monitor_enabled"
              @click="handleSyncWatchlist"
            >
              <t-icon name="refresh" style="margin-right: 4px" />
              手动同步
            </t-button>
          </div>
        </t-card>
      </t-col>

      <t-col :span="6">
        <t-card :bordered="false" class="summary-card">
          <div class="summary-title">
            <t-icon name="chart-bar" size="18px" style="color: var(--td-brand-color)" />
            <span>采集状态概览</span>
          </div>
          <t-row :gutter="[16, 16]" style="margin-top: 12px">
            <t-col :span="6">
              <div class="summary-item">
                <span class="summary-label">实时插件总数</span>
                <span class="summary-value">{{ status.total_plugins }}</span>
              </div>
            </t-col>
            <t-col :span="6">
              <div class="summary-item">
                <span class="summary-label">已启用插件</span>
                <span class="summary-value" :class="{ active: enabledPluginCount > 0 }">
                  {{ enabledPluginCount }}
                </span>
              </div>
            </t-col>
            <t-col :span="6">
              <div class="summary-item">
                <span class="summary-label">采集频率</span>
                <span class="summary-value freq">{{ config.collect_freq }}</span>
              </div>
            </t-col>
            <t-col :span="6">
              <div class="summary-item">
                <span class="summary-label">全局状态</span>
                <t-tag
                  :theme="config.enabled ? 'success' : 'default'"
                  size="small"
                  variant="light"
                >
                  {{ config.enabled ? '运行中' : '已停止' }}
                </t-tag>
              </div>
            </t-col>
          </t-row>
        </t-card>
      </t-col>
    </t-row>

    <!-- 实时插件列表 -->
    <t-card :bordered="false" style="margin-top: 16px" title="实时插件列表">
      <template #actions>
        <t-button size="small" variant="outline" @click="fetchAll">
          <t-icon name="refresh" style="margin-right: 4px" />
          刷新
        </t-button>
      </template>
      <t-table
        :data="plugins"
        :columns="pluginColumns"
        :loading="loading"
        row-key="plugin_name"
        hover
        size="small"
      >
        <template #display_name="{ row }">
          <div>
            <span style="font-weight: 500">{{ row.display_name }}</span>
            <span style="display: block; font-size: 12px; color: var(--td-text-color-placeholder)">
              {{ row.plugin_name }}
            </span>
          </div>
        </template>
        <template #category="{ row }">
          <t-tag :theme="getCategoryTheme(row.category)" variant="light" size="small">
            {{ getCategoryText(row.category) }}
          </t-tag>
        </template>
        <template #api_name="{ row }">
          <t-tag variant="outline" size="small">{{ row.api_name || '-' }}</t-tag>
        </template>
        <template #tags="{ row }">
          <t-tag
            v-for="tag in (row.tags || []).slice(0, 3)"
            :key="tag"
            size="small"
            variant="light"
            theme="default"
            style="margin-right: 4px"
          >
            {{ tag }}
          </t-tag>
        </template>
        <template #enabled="{ row }">
          <t-switch
            :value="row.enabled"
            :disabled="!config.enabled"
            @change="(val: boolean) => handlePluginToggle(row.plugin_name, val)"
          />
        </template>
      </t-table>
    </t-card>
  </div>
</template>

<style scoped>
.realtime-panel {
  padding: 0;
}

.control-card {
  background: linear-gradient(135deg, var(--td-bg-color-container) 0%, var(--td-brand-color-1) 100%);
}

.control-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.control-left {
  flex: 1;
}

.control-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.title-text {
  font-size: 16px;
  font-weight: 600;
  color: var(--td-text-color-primary);
}

.control-desc {
  margin-top: 6px;
  font-size: 13px;
  color: var(--td-text-color-secondary);
}

.freq-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.freq-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--td-text-color-primary);
  white-space: nowrap;
}

.watchlist-card, .summary-card {
  height: 100%;
}

.watchlist-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.watchlist-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.watchlist-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--td-text-color-primary);
}

.watchlist-stats {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}

.stat-label {
  font-size: 13px;
  color: var(--td-text-color-secondary);
}

.stat-num {
  font-size: 20px;
  font-weight: 600;
  color: var(--td-brand-color);
}

.watchlist-codes-section {
  margin-top: 8px;
}

.codes-list {
  margin-top: 8px;
  max-height: 80px;
  overflow-y: auto;
}

.watchlist-actions {
  margin-top: 12px;
}

.summary-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--td-text-color-primary);
}

.summary-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.summary-label {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.summary-value {
  font-size: 20px;
  font-weight: 600;
  color: var(--td-text-color-primary);
}

.summary-value.active {
  color: var(--td-success-color);
}

.summary-value.freq {
  font-size: 16px;
  color: var(--td-brand-color);
}
</style>

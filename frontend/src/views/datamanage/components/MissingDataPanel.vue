<script setup lang="ts">
import { computed, ref } from 'vue'
import { useDataManageStore } from '@/stores/datamanage'

const dataStore = useDataManageStore()

const emit = defineEmits<{
  (e: 'sync', pluginName: string, dates: string[]): void
}>()

// 检测天数选项 - 默认5年(1825天)
const checkDays = ref(1825)
const daysOptions = [
  { label: '30天', value: 30 },
  { label: '90天', value: 90 },
  { label: '180天', value: 180 },
  { label: '1年', value: 365 },
  { label: '2年', value: 730 },
  { label: '3年', value: 1095 },
  { label: '5年', value: 1825 },
  { label: '10年', value: 3650 }
]

const summary = computed(() => dataStore.missingData)

const pluginsWithMissing = computed(() => {
  if (!summary.value) return []
  return summary.value.plugins.filter(p => p.missing_count > 0)
})

const handleRefresh = () => {
  dataStore.triggerMissingDataDetection(checkDays.value)
}

const handleDaysChange = (value: number) => {
  checkDays.value = value
  dataStore.triggerMissingDataDetection(value)
}

const handleSync = (pluginName: string, dates: string[]) => {
  emit('sync', pluginName, dates)
}

const formatTime = (timeStr: string) => {
  if (!timeStr) return '-'
  const date = new Date(timeStr)
  return date.toLocaleString('zh-CN')
}
</script>

<template>
  <div class="missing-data-panel">
    <div class="panel-header">
      <div class="header-left">
        <h4>数据缺失检测</h4>
        <span v-if="summary" class="check-time">
          检测时间: {{ formatTime(summary.check_time) }}
        </span>
      </div>
      <div class="header-right">
        <t-select
          v-model="checkDays"
          :options="daysOptions"
          size="small"
          style="width: 100px"
          @change="handleDaysChange"
        />
        <t-button 
          theme="default" 
          size="small" 
          :loading="dataStore.missingDataLoading"
          @click="handleRefresh"
        >
          刷新检测
        </t-button>
      </div>
    </div>

    <t-loading :loading="dataStore.missingDataLoading">
      <div v-if="summary" class="summary-stats">
        <t-row :gutter="16">
          <t-col :span="4">
            <div class="stat-item">
              <div class="stat-value">{{ summary.total_plugins }}</div>
              <div class="stat-label">
                检测插件数
                <t-tooltip content="仅检测每日更新(daily)频率的插件">
                  <t-icon name="help-circle" size="14px" style="margin-left: 4px; cursor: help;" />
                </t-tooltip>
              </div>
            </div>
          </t-col>
          <t-col :span="4">
            <div class="stat-item" :class="{ warning: summary.plugins_with_missing > 0 }">
              <div class="stat-value">{{ summary.plugins_with_missing }}</div>
              <div class="stat-label">存在缺失</div>
            </div>
          </t-col>
          <t-col :span="4">
            <div class="stat-item success">
              <div class="stat-value">{{ summary.total_plugins - summary.plugins_with_missing }}</div>
              <div class="stat-label">数据完整</div>
            </div>
          </t-col>
        </t-row>
      </div>

      <div v-if="pluginsWithMissing.length > 0" class="missing-list">
        <h5>缺失详情</h5>
        <t-table
          :data="pluginsWithMissing"
          :columns="[
            { colKey: 'plugin_name', title: '插件', width: 180 },
            { colKey: 'table_name', title: '表名', width: 150 },
            { colKey: 'latest_date', title: '最新日期', width: 120 },
            { colKey: 'missing_count', title: '缺失天数', width: 100 },
            { colKey: 'missing_dates', title: '缺失日期', minWidth: 200 },
            { colKey: 'operation', title: '操作', width: 100 }
          ]"
          row-key="plugin_name"
          size="small"
          bordered
          max-height="300"
        >
          <template #missing_count="{ row }">
            <t-tag theme="danger">{{ row.missing_count }}</t-tag>
          </template>
          <template #missing_dates="{ row }">
            <div class="date-tags">
              <t-tag 
                v-for="date in row.missing_dates.slice(0, 5)" 
                :key="date"
                theme="warning"
                size="small"
              >
                {{ date }}
              </t-tag>
              <span v-if="row.missing_dates.length > 5" class="more-dates">
                +{{ row.missing_dates.length - 5 }}
              </span>
            </div>
          </template>
          <template #operation="{ row }">
            <t-link theme="primary" @click="handleSync(row.plugin_name, row.missing_dates)">
              补录
            </t-link>
          </template>
        </t-table>
      </div>

      <t-empty 
        v-else-if="summary && pluginsWithMissing.length === 0" 
        description="所有插件数据完整"
        style="padding: 40px 0"
      />
    </t-loading>
  </div>
</template>

<style scoped>
.missing-data-panel {
  background: var(--td-bg-color-container);
  border-radius: 6px;
  padding: 16px;
  margin-bottom: 16px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-left h4 {
  margin: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.check-time {
  color: var(--td-text-color-secondary);
  font-size: 12px;
}

.summary-stats {
  margin-bottom: 16px;
}

.stat-item {
  text-align: center;
  padding: 12px;
  background: var(--td-bg-color-secondarycontainer);
  border-radius: 4px;
}

.stat-item.warning .stat-value {
  color: var(--td-warning-color);
}

.stat-item.success .stat-value {
  color: var(--td-success-color);
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: var(--td-brand-color);
}

.stat-label {
  font-size: 12px;
  color: var(--td-text-color-secondary);
  margin-top: 4px;
}

.missing-list h5 {
  margin: 0 0 12px 0;
}

.date-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

.more-dates {
  color: var(--td-text-color-secondary);
  font-size: 12px;
}
</style>

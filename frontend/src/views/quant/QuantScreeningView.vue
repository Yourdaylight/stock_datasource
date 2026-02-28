<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { useQuantStore } from '@/stores/quant'
import { datamanageApi } from '@/api/datamanage'

const store = useQuantStore()
const activeTab = ref('passed')

const ruleColumns = [
  { colKey: 'rule_name', title: '规则名称', width: 180 },
  { colKey: 'category', title: '类别', width: 100 },
  { colKey: 'passed_count', title: '通过', width: 80 },
  { colKey: 'rejected_count', title: '剔除', width: 80 },
  { colKey: 'skipped_count', title: '跳过', width: 80 },
  { colKey: 'threshold', title: '规则说明' },
  { colKey: 'execution_time_ms', title: '耗时(ms)', width: 100 },
]

const stockColumns = [
  { colKey: 'ts_code', title: '代码', width: 120 },
  { colKey: 'stock_name', title: '名称', width: 120 },
  { colKey: 'overall_pass', title: '通过', width: 80 },
  { colKey: 'reject_reasons', title: '剔除原因' },
]

const handleRunScreening = async () => {
  const result = await store.runScreening()
  if (result?.status === 'data_missing') {
    MessagePlugin.warning('数据缺失，请先补充数据')
  } else if (result?.status === 'success') {
    MessagePlugin.success(`初筛完成：${result.passed_count}只通过，${result.rejected_count}只剔除`)
  }
}

const handleBatchSync = async () => {
  const plugins = store.screeningResult?.data_readiness?.missing_summary?.plugins_to_trigger || []
  if (!plugins.length) return
  const fullPlugins = plugins.filter(p => p.task_type === 'full').map(p => p.plugin_name)
  const incrPlugins = plugins.filter(p => p.task_type !== 'full').map(p => p.plugin_name)
  try {
    const requests: Promise<unknown>[] = []
    if (fullPlugins.length) {
      requests.push(datamanageApi.batchTriggerSync({ plugin_names: fullPlugins, task_type: 'full' }))
    }
    if (incrPlugins.length) {
      requests.push(datamanageApi.batchTriggerSync({ plugin_names: incrPlugins, task_type: 'incremental' }))
    }
    await Promise.all(requests)
    const parts: string[] = []
    if (fullPlugins.length) parts.push(`全量${fullPlugins.length}项`)
    if (incrPlugins.length) parts.push(`增量${incrPlugins.length}项`)
    MessagePlugin.success(`数据同步已触发(${parts.join('、')})`)
  } catch {
    MessagePlugin.error('触发失败')
  }
}

onMounted(() => {
  store.fetchScreeningResult()
})
</script>

<template>
  <div class="screening-view">
    <t-card title="全市场初筛" :bordered="false">
      <template #actions>
        <t-space>
          <t-button theme="primary" :loading="store.screeningLoading" @click="handleRunScreening">
            运行初筛
          </t-button>
          <t-button variant="outline" @click="store.fetchScreeningResult()">刷新</t-button>
        </t-space>
      </template>

      <!-- Data Missing Alert -->
      <t-alert
        v-if="store.screeningResult?.status === 'data_missing'"
        theme="warning"
        style="margin-bottom: 16px"
      >
        <template #message>
          <div>数据缺失，无法执行初筛</div>
          <div v-if="store.screeningResult?.data_readiness?.missing_summary" style="margin-top: 8px;">
            <div v-for="p in store.screeningResult.data_readiness.missing_summary.plugins_to_trigger" :key="p.plugin_name">
              <t-tag theme="warning" variant="light" size="small">{{ p.display_name }}</t-tag>
              {{ p.description }}
            </div>
            <t-button theme="primary" size="small" style="margin-top: 8px" @click="handleBatchSync">
              一键补充缺失数据
            </t-button>
          </div>
        </template>
      </t-alert>

      <!-- Execution Summary -->
      <t-row v-if="store.screeningResult?.status === 'success'" :gutter="16" style="margin-bottom: 16px">
        <t-col :span="3">
          <t-card :bordered="false" style="text-align: center; background: var(--td-bg-color-secondarycontainer);">
            <div style="font-size: 24px; font-weight: 700;">{{ store.screeningResult?.total_stocks || 0 }}</div>
            <div style="color: var(--td-text-color-secondary);">参与筛选</div>
          </t-card>
        </t-col>
        <t-col :span="3">
          <t-card :bordered="false" style="text-align: center; background: var(--td-success-color-1);">
            <div style="font-size: 24px; font-weight: 700; color: var(--td-success-color);">{{ store.screeningResult?.passed_count || 0 }}</div>
            <div style="color: var(--td-text-color-secondary);">通过</div>
          </t-card>
        </t-col>
        <t-col :span="3">
          <t-card :bordered="false" style="text-align: center; background: var(--td-error-color-1);">
            <div style="font-size: 24px; font-weight: 700; color: var(--td-error-color);">{{ store.screeningResult?.rejected_count || 0 }}</div>
            <div style="color: var(--td-text-color-secondary);">剔除</div>
          </t-card>
        </t-col>
        <t-col :span="3">
          <t-card :bordered="false" style="text-align: center;">
            <div style="font-size: 24px; font-weight: 700;">{{ store.screeningResult?.execution_time_ms || 0 }}ms</div>
            <div style="color: var(--td-text-color-secondary);">耗时</div>
          </t-card>
        </t-col>
      </t-row>

      <!-- Rule Execution Stats -->
      <t-card v-if="store.screeningResult?.rule_details?.length" title="规则执行统计" :bordered="false" style="margin-bottom: 16px;">
        <t-table
          :data="store.screeningResult.rule_details"
          :columns="ruleColumns"
          row-key="rule_name"
          size="small"
          :hover="true"
        >
          <template #category="{ row }">
            <t-tag :theme="row.category === 'benford' ? 'warning' : 'primary'" variant="light" size="small">
              {{ row.category === 'traditional' ? '传统指标' : row.category === 'custom' ? '自定义指标' : '本福德检验' }}
            </t-tag>
          </template>
          <template #passed_count="{ row }">
            <span style="color: var(--td-success-color);">{{ row.passed_count }}</span>
          </template>
          <template #rejected_count="{ row }">
            <span style="color: var(--td-error-color);">{{ row.rejected_count }}</span>
          </template>
        </t-table>
      </t-card>

      <!-- Stock Lists -->
      <t-tabs v-model="activeTab">
        <t-tab-panel value="passed" :label="`通过列表 (${store.screeningResult?.passed_count || 0})`">
          <t-table
            :data="store.screeningResult?.passed_stocks || []"
            :columns="stockColumns"
            row-key="ts_code"
            size="small"
            :hover="true"
            :loading="store.screeningLoading"
            max-height="500"
          >
            <template #overall_pass>
              <t-tag theme="success" variant="light" size="small">通过</t-tag>
            </template>
          </t-table>
        </t-tab-panel>
        <t-tab-panel value="rejected" :label="`剔除列表 (${store.screeningResult?.rejected_count || 0})`">
          <t-table
            :data="store.screeningResult?.rejected_stocks || []"
            :columns="stockColumns"
            row-key="ts_code"
            size="small"
            :hover="true"
            :loading="store.screeningLoading"
            max-height="500"
          >
            <template #overall_pass>
              <t-tag theme="danger" variant="light" size="small">剔除</t-tag>
            </template>
            <template #reject_reasons="{ row }">
              <t-tag v-for="(r, i) in row.reject_reasons" :key="i" theme="danger" variant="outline" size="small" style="margin-right: 4px;">
                {{ r }}
              </t-tag>
            </template>
          </t-table>
        </t-tab-panel>
      </t-tabs>
    </t-card>
  </div>
</template>

<style scoped>
.screening-view {
  padding: 16px;
}
</style>

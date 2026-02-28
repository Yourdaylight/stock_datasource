<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { MessagePlugin } from 'tdesign-vue-next'
import { useQuantStore } from '@/stores/quant'
import { datamanageApi } from '@/api/datamanage'
import type { PipelineStageStatus, PluginTriggerInfo } from '@/api/quant'

const router = useRouter()
const store = useQuantStore()

const runningPipeline = ref(false)

// Pipeline stage display config
const stageConfig = [
  { stage: 'screening', name: '全市场初筛', icon: 'filter', route: '/quant/screening' },
  { stage: 'core_pool', name: '核心池构建', icon: 'layers', route: '/quant/pool' },
  { stage: 'deep_analysis', name: '深度分析', icon: 'chart-line', route: '/quant/analysis' },
  { stage: 'trading_signals', name: '交易信号', icon: 'swap', route: '/quant/signals' },
]

const stageStatusMap = computed(() => {
  const map: Record<string, PipelineStageStatus> = {}
  if (store.pipelineStatus?.stages) {
    for (const s of store.pipelineStatus.stages) {
      map[s.stage] = s
    }
  }
  return map
})

const statusTheme = (status: string) => {
  switch (status) {
    case 'completed': return 'success'
    case 'running': return 'primary'
    case 'data_missing': return 'warning'
    case 'error': return 'danger'
    default: return 'default'
  }
}

const statusText = (status: string) => {
  switch (status) {
    case 'completed': return '完成'
    case 'running': return '进行中'
    case 'data_missing': return '数据缺失'
    case 'error': return '错误'
    default: return '待执行'
  }
}

// Data readiness
const allMissing = computed(() => {
  const plugins: PluginTriggerInfo[] = []
  for (const result of Object.values(store.dataReadiness)) {
    if (result?.missing_summary?.plugins_to_trigger) {
      for (const p of result.missing_summary.plugins_to_trigger) {
        if (!plugins.find(x => x.plugin_name === p.plugin_name)) {
          plugins.push(p)
        }
      }
    }
  }
  return plugins
})

const isAllReady = computed(() => {
  return Object.values(store.dataReadiness).every(r => r?.is_ready)
})

const selectedPlugins = ref<string[]>([])

const handleBatchSync = async () => {
  const plugins = selectedPlugins.value.length > 0
    ? allMissing.value.filter(p => selectedPlugins.value.includes(p.plugin_name))
    : allMissing.value
  if (!plugins.length) return

  // Group by task_type so each batch uses the correct sync mode
  const fullPlugins = plugins.filter(p => p.task_type === 'full').map(p => p.plugin_name)
  const incrPlugins = plugins.filter(p => p.task_type !== 'full').map(p => p.plugin_name)

  try {
    const requests: Promise<unknown>[] = []
    if (fullPlugins.length) {
      requests.push(datamanageApi.batchTriggerSync({
        plugin_names: fullPlugins,
        task_type: 'full',
      }))
    }
    if (incrPlugins.length) {
      requests.push(datamanageApi.batchTriggerSync({
        plugin_names: incrPlugins,
        task_type: 'incremental',
      }))
    }
    await Promise.all(requests)
    const parts: string[] = []
    if (fullPlugins.length) parts.push(`全量${fullPlugins.length}项`)
    if (incrPlugins.length) parts.push(`增量${incrPlugins.length}项`)
    MessagePlugin.success(`数据同步已触发(${parts.join('、')})，请稍后刷新`)
  } catch (e) {
    MessagePlugin.error('触发失败')
  }
}

const handleRunPipeline = async () => {
  runningPipeline.value = true
  try {
    const result = await store.runPipeline('full')
    if (result?.overall_status === 'data_missing') {
      MessagePlugin.warning('部分数据缺失，请先补充数据')
    } else if (result?.overall_status === 'completed') {
      MessagePlugin.success('Pipeline 执行完成')
    }
    await store.fetchDataReadiness()
  } catch (e) {
    MessagePlugin.error('Pipeline 执行失败')
  } finally {
    runningPipeline.value = false
  }
}

onMounted(async () => {
  await Promise.all([
    store.fetchDataReadiness(),
    store.fetchPipelineStatus(),
    store.fetchPool(),
    store.fetchSignals(),
  ])
})
</script>

<template>
  <div class="quant-view">
    <t-card title="量化选股模型" :bordered="false">
      <template #actions>
        <t-space>
          <t-button theme="primary" :loading="runningPipeline" @click="handleRunPipeline">
            运行完整 Pipeline
          </t-button>
          <t-button variant="outline" @click="store.fetchDataReadiness()">
            刷新数据状态
          </t-button>
        </t-space>
      </template>

      <!-- Pipeline Progress -->
      <div class="pipeline-progress">
        <div
          v-for="(cfg, idx) in stageConfig"
          :key="cfg.stage"
          class="pipeline-stage"
          @click="router.push(cfg.route)"
        >
          <div class="stage-card" :class="stageStatusMap[cfg.stage]?.status || 'pending'">
            <div class="stage-number">{{ idx + 1 }}</div>
            <t-icon :name="cfg.icon" size="24px" />
            <div class="stage-name">{{ cfg.name }}</div>
            <t-tag
              :theme="statusTheme(stageStatusMap[cfg.stage]?.status || 'pending')"
              variant="light"
              size="small"
            >
              {{ statusText(stageStatusMap[cfg.stage]?.status || 'pending') }}
            </t-tag>
            <div v-if="stageStatusMap[cfg.stage]?.result_summary" class="stage-summary">
              <template v-for="(val, key) in stageStatusMap[cfg.stage]?.result_summary" :key="key">
                <span class="summary-item">{{ key }}: {{ val }}</span>
              </template>
            </div>
          </div>
          <div v-if="idx < stageConfig.length - 1" class="stage-arrow">→</div>
        </div>
      </div>
    </t-card>

    <!-- Data Readiness Panel -->
    <t-card v-if="!isAllReady && allMissing.length > 0" title="⚠️ 数据就绪检查" class="readiness-card" :bordered="false">
      <t-alert theme="warning" :message="`${allMissing.length} 项数据缺失，影响计算准确性`" style="margin-bottom: 16px" />

      <t-table
        :data="allMissing"
        :columns="[
          { colKey: 'select', title: '', width: 50 },
          { colKey: 'display_name', title: '数据插件' },
          { colKey: 'task_type', title: '同步方式', width: 100 },
          { colKey: 'detail', title: '', width: 80 },
        ]"
        row-key="plugin_name"
        size="small"
        :hover="true"
      >
        <template #select="{ row }">
          <t-checkbox
            :checked="selectedPlugins.includes(row.plugin_name)"
            @change="(v: boolean) => {
              if (v) selectedPlugins.push(row.plugin_name)
              else selectedPlugins = selectedPlugins.filter(x => x !== row.plugin_name)
            }"
          />
        </template>
        <template #task_type="{ row }">
          <t-popup
            :content="row.task_type === 'full' ? '数据表不存在或为空，需要全量初始化' : `数据已有，仅补充缺失日期${row.missing_dates?.length ? '(' + row.missing_dates.join(', ') + ')' : ''}`"
            trigger="hover"
          >
            <t-tag :theme="row.task_type === 'full' ? 'danger' : 'primary'" variant="light" size="small">
              {{ row.task_type === 'full' ? '全量(首次)' : '增量' }}
            </t-tag>
          </t-popup>
        </template>
        <template #detail="{ row }">
          <t-popup :content="row.description + (row.table_name ? `\n数据表: ${row.table_name}` : '')" trigger="click" placement="left">
            <t-button variant="text" size="small">详情</t-button>
          </t-popup>
        </template>
      </t-table>

      <div style="margin-top: 12px; display: flex; gap: 8px;">
        <t-button theme="primary" @click="handleBatchSync">
          一键补充所有缺失数据
        </t-button>
        <t-button v-if="selectedPlugins.length > 0" variant="outline" @click="handleBatchSync">
          补充选中项 ({{ selectedPlugins.length }})
        </t-button>
      </div>
    </t-card>

    <t-card v-else-if="isAllReady" :bordered="false" style="margin-top: 16px">
      <t-alert theme="success" message="所有数据就绪，可以运行完整 Pipeline" />
    </t-card>

    <!-- Overview Cards -->
    <t-row :gutter="16" style="margin-top: 16px">
      <t-col :span="4">
        <t-card :bordered="false" class="stat-card" @click="router.push('/quant/pool')">
          <div class="stat-value">{{ store.poolResult?.core_stocks?.length || 0 }}</div>
          <div class="stat-label">核心池</div>
          <div v-if="store.poolResult?.pool_changes?.length" class="stat-change">
            变动 {{ store.poolResult.pool_changes.length }}
          </div>
        </t-card>
      </t-col>
      <t-col :span="4">
        <t-card :bordered="false" class="stat-card" @click="router.push('/quant/pool')">
          <div class="stat-value">{{ store.poolResult?.supplement_stocks?.length || 0 }}</div>
          <div class="stat-label">补充池(RPS)</div>
        </t-card>
      </t-col>
      <t-col :span="4">
        <t-card :bordered="false" class="stat-card" @click="router.push('/quant/signals')">
          <div class="stat-value">{{ store.signals?.length || 0 }}</div>
          <div class="stat-label">今日信号</div>
          <div class="stat-change">
            <t-tag v-for="s in (store.signals || []).slice(0, 2)" :key="s.ts_code"
              :theme="s.signal_type === 'buy' ? 'success' : 'danger'"
              variant="light" size="small" style="margin-right: 4px">
              {{ s.signal_type === 'buy' ? '买' : '卖' }} {{ s.stock_name || s.ts_code }}
            </t-tag>
          </div>
        </t-card>
      </t-col>
    </t-row>

    <!-- Quick Navigation -->
    <t-row :gutter="16" style="margin-top: 16px">
      <t-col v-for="cfg in stageConfig" :key="cfg.stage" :span="3">
        <t-card :bordered="false" class="nav-card" @click="router.push(cfg.route)">
          <t-icon :name="cfg.icon" size="28px" />
          <div>{{ cfg.name }}</div>
        </t-card>
      </t-col>
    </t-row>
  </div>
</template>

<style scoped>
.quant-view {
  padding: 16px;
}

.pipeline-progress {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px 0;
  gap: 0;
}

.pipeline-stage {
  display: flex;
  align-items: center;
  cursor: pointer;
}

.stage-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px 24px;
  border-radius: 8px;
  background: var(--td-bg-color-container);
  border: 2px solid var(--td-border-level-2-color);
  transition: all 0.3s;
  min-width: 140px;
}

.stage-card:hover {
  border-color: var(--td-brand-color);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.stage-card.completed {
  border-color: var(--td-success-color);
  background: var(--td-success-color-1);
}

.stage-card.running {
  border-color: var(--td-brand-color);
  background: var(--td-brand-color-1);
}

.stage-card.data_missing {
  border-color: var(--td-warning-color);
  background: var(--td-warning-color-1);
}

.stage-number {
  font-size: 12px;
  color: var(--td-text-color-placeholder);
}

.stage-name {
  font-weight: 600;
  font-size: 14px;
}

.stage-summary {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.summary-item {
  margin-right: 8px;
}

.stage-arrow {
  font-size: 24px;
  color: var(--td-text-color-placeholder);
  margin: 0 8px;
}

.readiness-card {
  margin-top: 16px;
}

.stat-card {
  text-align: center;
  cursor: pointer;
  transition: box-shadow 0.3s;
}

.stat-card:hover {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: var(--td-brand-color);
}

.stat-label {
  font-size: 14px;
  color: var(--td-text-color-secondary);
  margin-top: 4px;
}

.stat-change {
  font-size: 12px;
  color: var(--td-text-color-placeholder);
  margin-top: 8px;
}

.nav-card {
  text-align: center;
  cursor: pointer;
  padding: 20px;
  transition: box-shadow 0.3s;
}

.nav-card:hover {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}
</style>

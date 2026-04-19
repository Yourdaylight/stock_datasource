<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { useSignalAggregatorStore } from '@/stores/signalAggregator'
import type { StockSignalSummary } from '@/api/signalAggregator'
import SentimentChart from './SentimentChart.vue'
import type { SentimentStats } from '@/types/news'

interface Props {
  activeStockCode: string | null
  sentimentData: SentimentStats
  sentimentLoading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  sentimentLoading: false,
})

const emit = defineEmits<{
  (e: 'open-timeline', tsCode: string): void
}>()

const signalStore = useSignalAggregatorStore()
const radarContainer = ref<HTMLElement>()
const radarInstance = ref<echarts.ECharts>()

const currentSignal = computed<StockSignalSummary | null>(
  () => signalStore.currentStock
)

const hasSignal = computed(() => !!currentSignal.value)

const directionLabel = (dir: string) => {
  const map: Record<string, string> = { bullish: '看多', bearish: '看空', neutral: '中性' }
  return map[dir] || '中性'
}

const directionTheme = (dir: string) => {
  const map: Record<string, string> = { bullish: 'success', bearish: 'danger', neutral: 'default' }
  return map[dir] || 'default'
}

const scoreColor = (score: number) => {
  if (score >= 70) return '#00a870'
  if (score >= 55) return '#0052d9'
  if (score >= 40) return '#e37318'
  return '#d54941'
}

const fetchSignal = async (tsCode: string) => {
  await signalStore.fetchSingleStock(tsCode)
}

// 雷达图配置
const getRadarOption = (signal: StockSignalSummary) => ({
  radar: {
    indicator: [
      { name: '消息面', max: 100 },
      { name: '资金面', max: 100 },
      { name: '技术面', max: 100 },
    ],
    shape: 'polygon' as const,
    radius: '65%',
    axisName: { color: '#666', fontSize: 11 },
    splitArea: { areaStyle: { color: ['rgba(0,168,112,0.05)', 'rgba(0,168,112,0.1)'] } },
  },
  series: [{
    type: 'radar',
    data: [{
      value: [signal.news_score, signal.capital_score, signal.tech_score],
      areaStyle: { color: 'rgba(0,82,217,0.15)' },
      lineStyle: { color: '#0052d9', width: 2 },
      itemStyle: { color: '#0052d9' },
    }],
  }],
})

const initRadar = () => {
  if (!radarContainer.value) return
  radarInstance.value = echarts.init(radarContainer.value)
  updateRadar()
}

const updateRadar = () => {
  if (!radarInstance.value || !currentSignal.value) return
  radarInstance.value.setOption(getRadarOption(currentSignal.value), true)
}

// 监听股票代码变化
watch(() => props.activeStockCode, (code) => {
  if (code) {
    fetchSignal(code)
  }
}, { immediate: true })

// 监听信号数据变化
watch(currentSignal, () => {
  if (currentSignal.value) {
    updateRadar()
  }
})

const handleResize = () => {
  radarInstance.value?.resize()
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
  // 延迟初始化雷达图
  setTimeout(initRadar, 100)
})

onUnmounted(() => {
  radarInstance.value?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>

<template>
  <div class="signal-panel">
    <!-- 有选中股票且有信号数据 -->
    <template v-if="hasSignal && currentSignal">
      <!-- 信号评分卡 -->
      <t-card title="信号评分" size="small" :bordered="false" class="panel-card">
        <template #actions>
          <t-tag :theme="directionTheme(currentSignal!.composite_direction)" size="small" variant="light">
            {{ directionLabel(currentSignal!.composite_direction) }}
          </t-tag>
        </template>

        <div class="signal-summary">
          <div class="composite-score" :style="{ color: scoreColor(currentSignal!.composite_score) }">
            {{ currentSignal!.composite_score.toFixed(1) }}
          </div>
          <div class="composite-label">综合评分</div>
        </div>

        <!-- 三维评分条 -->
        <div class="dimension-scores">
          <div class="dim-row">
            <span class="dim-label">消息面</span>
            <t-progress
              :percentage="currentSignal!.news_score"
              :color="scoreColor(currentSignal!.news_score)"
              size="small"
              :label="currentSignal!.news_score.toFixed(0)"
            />
          </div>
          <div class="dim-row">
            <span class="dim-label">资金面</span>
            <t-progress
              :percentage="currentSignal!.capital_score"
              :color="scoreColor(currentSignal!.capital_score)"
              size="small"
              :label="currentSignal!.capital_score.toFixed(0)"
            />
          </div>
          <div class="dim-row">
            <span class="dim-label">技术面</span>
            <t-progress
              :percentage="currentSignal!.tech_score"
              :color="scoreColor(currentSignal!.tech_score)"
              size="small"
              :label="currentSignal!.tech_score.toFixed(0)"
            />
          </div>
        </div>

        <!-- 雷达图 -->
        <div ref="radarContainer" class="radar-chart" />

        <!-- 高impact新闻 -->
        <div v-if="currentSignal!.news_detail?.top_headlines?.length" class="impact-news">
          <div class="impact-title">高影响新闻</div>
          <div
            v-for="(h, i) in currentSignal!.news_detail.top_headlines.slice(0, 3)"
            :key="i"
            class="impact-item"
          >
            {{ h }}
          </div>
        </div>

        <!-- 时序追踪入口 -->
        <t-button
          block
          variant="outline"
          size="small"
          @click="emit('open-timeline', currentSignal!.ts_code)"
          style="margin-top: 8px"
        >
          查看时序追踪
        </t-button>
      </t-card>
    </template>

    <!-- 无选中股票 — 显示情绪分析 -->
    <template v-else>
      <SentimentChart
        :sentiment-data="sentimentData"
        :loading="sentimentLoading"
      />

      <!-- 信号加载中 -->
      <t-card v-if="activeStockCode && signalStore.loading" title="信号评分" size="small" :bordered="false" class="panel-card" style="margin-top: 12px">
        <div class="signal-loading">
          <t-loading size="small" text="加载信号数据..." />
        </div>
      </t-card>

      <!-- 有股票但无信号 -->
      <t-card v-else-if="activeStockCode && !signalStore.loading && !hasSignal" title="信号评分" size="small" :bordered="false" class="panel-card" style="margin-top: 12px">
        <t-empty size="small" description="暂无该股票信号数据" />
      </t-card>
    </template>
  </div>
</template>

<style scoped>
.signal-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
}

.panel-card {
  background: #ffffff;
  border: 1px solid #e8e8e8;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.signal-summary {
  text-align: center;
  padding: 4px 0 8px;
}

.composite-score {
  font-size: 32px;
  font-weight: 700;
  line-height: 1.1;
}

.composite-label {
  font-size: 12px;
  color: var(--td-text-color-secondary);
  margin-top: 2px;
}

.dimension-scores {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 4px;
}

.dim-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dim-label {
  font-size: 12px;
  color: var(--td-text-color-secondary);
  width: 40px;
  flex-shrink: 0;
}

.dim-row :deep(.t-progress) {
  flex: 1;
}

.radar-chart {
  width: 100%;
  height: 180px;
  margin-top: 4px;
}

.impact-news {
  margin-top: 8px;
}

.impact-title {
  font-size: 12px;
  font-weight: 500;
  color: var(--td-text-color-primary);
  margin-bottom: 4px;
}

.impact-item {
  font-size: 12px;
  color: var(--td-text-color-secondary);
  line-height: 1.4;
  padding: 2px 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.signal-loading {
  display: flex;
  justify-content: center;
  padding: 16px 0;
}
</style>

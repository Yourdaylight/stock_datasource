<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import type { SentimentStats } from '@/types/news'

interface Props {
  sentimentData: SentimentStats
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false
})

// 图表容器引用
const chartContainer = ref<HTMLElement>()
const chartInstance = ref<echarts.ECharts>()

// 计算属性
const totalNews = computed(() => {
  return props.sentimentData.positive + props.sentimentData.negative + props.sentimentData.neutral
})

const sentimentPercentages = computed(() => {
  if (totalNews.value === 0) {
    return { positive: 0, negative: 0, neutral: 0 }
  }
  
  return {
    positive: Math.round((props.sentimentData.positive / totalNews.value) * 100),
    negative: Math.round((props.sentimentData.negative / totalNews.value) * 100),
    neutral: Math.round((props.sentimentData.neutral / totalNews.value) * 100)
  }
})

const dominantSentiment = computed(() => {
  const { positive, negative, neutral } = props.sentimentData
  
  if (positive >= negative && positive >= neutral) {
    return { type: 'positive', label: '偏乐观', color: '#00A870' }
  } else if (negative >= positive && negative >= neutral) {
    return { type: 'negative', label: '偏悲观', color: '#E34D59' }
  } else {
    return { type: 'neutral', label: '中性', color: '#8B8D98' }
  }
})

// 图表配置
const getChartOption = () => {
  const { positive, negative, neutral } = props.sentimentData
  
  return {
    tooltip: {
      trigger: 'item',
      formatter: '{a} <br/>{b}: {c} ({d}%)'
    },
    legend: {
      orient: 'horizontal',
      bottom: '5%',
      left: 'center',
      itemWidth: 12,
      itemHeight: 12,
      textStyle: {
        fontSize: 11,
        color: '#666'
      }
    },
    series: [
      {
        name: '新闻情绪',
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['50%', '40%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 4,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: false,
          position: 'center'
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 14,
            fontWeight: 'bold'
          },
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        },
        labelLine: {
          show: false
        },
        data: [
          {
            value: positive,
            name: '利好',
            itemStyle: { color: '#00A870' }
          },
          {
            value: negative,
            name: '利空',
            itemStyle: { color: '#E34D59' }
          },
          {
            value: neutral,
            name: '中性',
            itemStyle: { color: '#8B8D98' }
          }
        ]
      }
    ]
  }
}

// 初始化图表
const initChart = () => {
  if (!chartContainer.value) return
  
  chartInstance.value = echarts.init(chartContainer.value)
  updateChart()
}

// 更新图表
const updateChart = () => {
  if (!chartInstance.value) return
  
  const option = getChartOption()
  chartInstance.value.setOption(option, true)
}

// 监听数据变化
watch(() => props.sentimentData, () => {
  updateChart()
}, { deep: true })

// 监听窗口大小变化
const handleResize = () => {
  if (chartInstance.value) {
    chartInstance.value.resize()
  }
}

onMounted(() => {
  initChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  if (chartInstance.value) {
    chartInstance.value.dispose()
  }
  window.removeEventListener('resize', handleResize)
})
</script>

<template>
  <div class="sentiment-chart-panel">
    <t-card title="情绪分析" size="small" :bordered="false" class="sentiment-chart-card">
      <template #actions>
        <t-tag 
          :theme="dominantSentiment.type === 'positive' ? 'success' : 
                 dominantSentiment.type === 'negative' ? 'danger' : 'default'"
          size="small"
          variant="light"
        >
          {{ dominantSentiment.label }}
        </t-tag>
      </template>

      <div class="sentiment-chart-content">
        <!-- 情绪统计数据 -->
        <div class="sentiment-stats">
          <div class="stat-item positive">
            <div class="stat-value">{{ sentimentData.positive }}</div>
            <div class="stat-label">利好</div>
            <div class="stat-percentage">{{ sentimentPercentages.positive }}%</div>
          </div>
          
          <div class="stat-item negative">
            <div class="stat-value">{{ sentimentData.negative }}</div>
            <div class="stat-label">利空</div>
            <div class="stat-percentage">{{ sentimentPercentages.negative }}%</div>
          </div>
          
          <div class="stat-item neutral">
            <div class="stat-value">{{ sentimentData.neutral }}</div>
            <div class="stat-label">中性</div>
            <div class="stat-percentage">{{ sentimentPercentages.neutral }}%</div>
          </div>
        </div>

        <!-- 饼图 -->
        <div class="chart-container">
          <div 
            ref="chartContainer" 
            class="sentiment-chart"
            v-show="!loading && totalNews > 0"
          />
          
          <!-- 空状态 -->
          <div v-if="!loading && totalNews === 0" class="empty-chart">
            <div class="empty-chart-container">
              <div class="empty-chart-icon">
                <svg viewBox="0 0 48 48" width="52" height="52">
                  <defs>
                    <linearGradient id="sentimentGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" style="stop-color:#00A870;stop-opacity:0.2" />
                      <stop offset="50%" style="stop-color:#8B8D98;stop-opacity:0.15" />
                      <stop offset="100%" style="stop-color:#E34D59;stop-opacity:0.2" />
                    </linearGradient>
                  </defs>
                  <circle cx="24" cy="24" r="18" fill="url(#sentimentGradient)" stroke="#8B8D98" stroke-width="1" stroke-dasharray="4 2"/>
                  <circle cx="24" cy="24" r="10" fill="none" stroke="#8B8D98" stroke-width="1" opacity="0.3"/>
                  <path d="M18 24 L24 18 L30 24 L24 30 Z" fill="#8B8D98" opacity="0.2"/>
                </svg>
              </div>
              <span class="empty-chart-title">暂无情绪数据</span>
              <span class="empty-chart-desc">等待新闻数据加载</span>
            </div>
          </div>
          
          <!-- 加载状态 -->
          <div v-if="loading" class="loading-chart">
            <t-loading size="large" />
          </div>
        </div>

        <!-- 情绪指数 -->
        <div class="sentiment-index" v-if="totalNews > 0">
          <div class="index-label">情绪指数</div>
          <div class="index-value" :style="{ color: dominantSentiment.color }">
            {{ Math.round((sentimentData.positive - sentimentData.negative) / totalNews * 100) }}
          </div>
          <div class="index-description">
            <span v-if="sentimentData.positive > sentimentData.negative" class="positive-text">
              市场情绪偏向乐观
            </span>
            <span v-else-if="sentimentData.negative > sentimentData.positive" class="negative-text">
              市场情绪偏向悲观
            </span>
            <span v-else class="neutral-text">
              市场情绪相对中性
            </span>
          </div>
        </div>
      </div>
    </t-card>
  </div>
</template>

<style scoped>
.sentiment-chart-panel {
  height: 50%;
  min-height: 300px;
}

.sentiment-chart-card {
  height: 100%;
  background: #ffffff;
  border: 1px solid #e8e8e8;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
}

.sentiment-chart-card :deep(.t-card__body) {
  flex: 1;
  padding: 8px;
  overflow: hidden;
}

.sentiment-chart-content {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sentiment-stats {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 8px;
  flex-shrink: 0;
}

.stat-item {
  text-align: center;
  padding: 8px 4px;
  border-radius: 6px;
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-component-stroke);
}

.stat-item.positive {
  border-left: 3px solid var(--td-success-color);
}

.stat-item.negative {
  border-left: 3px solid var(--td-error-color);
}

.stat-item.neutral {
  border-left: 3px solid var(--td-text-color-secondary);
}

.stat-value {
  font-size: 18px;
  font-weight: 600;
  line-height: 1;
  margin-bottom: 2px;
}

.stat-item.positive .stat-value {
  color: var(--td-success-color);
}

.stat-item.negative .stat-value {
  color: var(--td-error-color);
}

.stat-item.neutral .stat-value {
  color: var(--td-text-color-secondary);
}

.stat-label {
  font-size: 11px;
  color: var(--td-text-color-secondary);
  margin-bottom: 2px;
}

.stat-percentage {
  font-size: 10px;
  color: var(--td-text-color-placeholder);
}

.chart-container {
  flex: 1;
  position: relative;
  min-height: 150px;
}

.sentiment-chart {
  width: 100%;
  height: 100%;
}

.empty-chart,
.loading-chart {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-chart-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 8px;
}

.empty-chart-icon {
  animation: rotate 8s linear infinite;
}

.empty-chart-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--td-text-color-primary);
}

.empty-chart-desc {
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}

@keyframes rotate {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

.sentiment-index {
  text-align: center;
  padding: 8px;
  background: var(--td-bg-color-container);
  border-radius: 6px;
  flex-shrink: 0;
}

.index-label {
  font-size: 11px;
  color: var(--td-text-color-secondary);
  margin-bottom: 4px;
}

.index-value {
  font-size: 24px;
  font-weight: 600;
  line-height: 1;
  margin-bottom: 4px;
}

.index-description {
  font-size: 10px;
  line-height: 1;
}

.positive-text {
  color: var(--td-success-color);
}

.negative-text {
  color: var(--td-error-color);
}

.neutral-text {
  color: var(--td-text-color-secondary);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .sentiment-chart-panel {
    height: auto;
    min-height: 250px;
  }
  
  .sentiment-stats {
    gap: 4px;
  }
  
  .stat-item {
    padding: 6px 2px;
  }
  
  .stat-value {
    font-size: 16px;
  }
  
  .chart-container {
    min-height: 120px;
  }
  
  .index-value {
    font-size: 20px;
  }
}
</style>
<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { useSignalAggregatorStore } from '@/stores/signalAggregator'
import SignalTimeline from './SignalTimeline.vue'

const signalStore = useSignalAggregatorStore()

const searchInput = ref('')
const selectedStocks = ref<string[]>([])
const loading = ref(false)
const showTimeline = ref(false)
const timelineStock = ref('')

// 搜索并添加股票
const addStock = () => {
  const codes = searchInput.value
    .split(/[,，\s]+/)
    .map(s => s.trim().toUpperCase())
    .filter(s => s.match(/\d{6}\.[A-Z]{2}/))

  if (codes.length === 0) {
    MessagePlugin.warning('请输入有效的股票代码，如 600519.SH')
    return
  }

  const newCodes = codes.filter(c => !selectedStocks.value.includes(c))
  if (newCodes.length === 0) {
    MessagePlugin.info('这些股票已在列表中')
    return
  }

  selectedStocks.value.push(...newCodes)
  searchInput.value = ''
  fetchSignals()
}

const removeStock = (code: string) => {
  selectedStocks.value = selectedStocks.value.filter(c => c !== code)
  if (selectedStocks.value.length > 0) {
    fetchSignals()
  } else {
    signalStore.stocks = []
  }
}

const fetchSignals = async () => {
  if (selectedStocks.value.length === 0) return
  loading.value = true
  await signalStore.fetchAggregate(selectedStocks.value)
  loading.value = false
}

const openTimeline = (tsCode: string) => {
  timelineStock.value = tsCode
  showTimeline.value = true
}

// 评分颜色
const scoreColor = (score: number) => {
  if (score >= 70) return '#00a870'
  if (score >= 55) return '#0052d9'
  if (score >= 40) return '#e37318'
  return '#d54941'
}

const directionLabel = (dir: string) => {
  const map: Record<string, string> = {
    bullish: '看多',
    bearish: '看空',
    neutral: '中性',
  }
  return map[dir] || '中性'
}

const directionTag = (dir: string) => {
  const map: Record<string, string> = {
    bullish: 'success',
    bearish: 'danger',
    neutral: 'default',
  }
  return map[dir] || 'default'
}

onMounted(() => {
  // 默认加载热门股票
  selectedStocks.value = ['600519.SH', '000858.SZ', '601318.SH', '000001.SZ', '600036.SH']
  fetchSignals()
})
</script>

<template>
  <div class="signal-dashboard">
    <t-card title="信号可观测面板" bordered>
      <!-- 搜索栏 -->
      <template #actions>
        <t-input
          v-model="searchInput"
          placeholder="输入股票代码（逗号分隔），如 600519.SH,000858.SZ"
          style="width: 400px"
          @enter="addStock"
          clearable
        >
          <template #suffix-icon>
            <t-button theme="primary" size="small" @click="addStock">查询</t-button>
          </template>
        </t-input>
      </template>

      <!-- 已选股票标签 -->
      <div class="selected-stocks" v-if="selectedStocks.length">
        <t-tag
          v-for="code in selectedStocks"
          :key="code"
          closable
          @close="removeStock(code)"
          theme="primary"
          variant="light"
          style="margin: 2px 4px"
        >
          {{ code }}
        </t-tag>
      </div>

      <!-- 信号列表 -->
      <t-table
        :data="signalStore.stocks"
        :loading="loading"
        row-key="ts_code"
        hover
        stripe
        style="margin-top: 16px"
      >
        <t-table-col title="股票代码" field="ts_code" width="120" />
        <t-table-col title="股票名称" field="stock_name" width="100" />
        <t-table-col title="综合评分" field="composite_score" width="100" align="center">
          <template #cell="{ row }">
            <span :style="{ color: scoreColor(row.composite_score), fontWeight: 'bold', fontSize: '16px' }">
              {{ row.composite_score?.toFixed(1) }}
            </span>
          </template>
        </t-table-col>
        <t-table-col title="方向" field="composite_direction" width="80" align="center">
          <template #cell="{ row }">
            <t-tag :theme="directionTag(row.composite_direction)" size="small">
              {{ directionLabel(row.composite_direction) }}
            </t-tag>
          </template>
        </t-table-col>
        <t-table-col title="消息面" field="news_score" width="90" align="center">
          <template #cell="{ row }">
            <t-progress
              :percentage="row.news_score"
              :color="scoreColor(row.news_score)"
              size="small"
              :label="row.news_score?.toFixed(0)"
            />
          </template>
        </t-table-col>
        <t-table-col title="资金面" field="capital_score" width="90" align="center">
          <template #cell="{ row }">
            <t-progress
              :percentage="row.capital_score"
              :color="scoreColor(row.capital_score)"
              size="small"
              :label="row.capital_score?.toFixed(0)"
            />
          </template>
        </t-table-col>
        <t-table-col title="技术面" field="tech_score" width="90" align="center">
          <template #cell="{ row }">
            <t-progress
              :percentage="row.tech_score"
              :color="scoreColor(row.tech_score)"
              size="small"
              :label="row.tech_score?.toFixed(0)"
            />
          </template>
        </t-table-col>
        <t-table-col title="信号日期" field="signal_date" width="110" />
        <t-table-col title="操作" width="100" align="center">
          <template #cell="{ row }">
            <t-link theme="primary" @click="openTimeline(row.ts_code)">时序追踪</t-link>
          </template>
        </t-table-col>
      </t-table>

      <!-- 空状态 -->
      <t-empty v-if="!loading && signalStore.stocks.length === 0" description="请输入股票代码查询信号评分" />
    </t-card>

    <!-- 时序追踪弹窗 -->
    <t-dialog
      v-model:visible="showTimeline"
      :header="`${timelineStock} 信号时序追踪`"
      width="800px"
      :footer="false"
      destroy-on-close
    >
      <SignalTimeline :ts-code="timelineStock" />
    </t-dialog>
  </div>
</template>

<style scoped>
.signal-dashboard {
  padding: 16px;
}
.selected-stocks {
  margin: 8px 0;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
</style>

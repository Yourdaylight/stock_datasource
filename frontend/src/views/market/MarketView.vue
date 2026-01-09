<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useMarketStore } from '@/stores/market'
import StockSearch from '@/components/common/StockSearch.vue'
import KLineChart from '@/components/charts/KLineChart.vue'

const marketStore = useMarketStore()
const selectedStock = ref('')
const dateRange = ref<[string, string]>(['', ''])

const handleStockSelect = (code: string) => {
  selectedStock.value = code
  if (dateRange.value[0] && dateRange.value[1]) {
    marketStore.fetchKLine(code, dateRange.value[0], dateRange.value[1])
    marketStore.fetchIndicators(code, ['macd', 'rsi', 'kdj'])
  }
}

const handleDateChange = (dates: [string, string]) => {
  dateRange.value = dates
  if (selectedStock.value && dates[0] && dates[1]) {
    marketStore.fetchKLine(selectedStock.value, dates[0], dates[1])
  }
}

const indicators = ['MACD', 'RSI', 'KDJ', 'BOLL', 'MA']
const selectedIndicators = ref(['MACD'])

onMounted(() => {
  // Set default date range (last 3 months)
  const end = new Date()
  const start = new Date()
  start.setMonth(start.getMonth() - 3)
  dateRange.value = [
    start.toISOString().split('T')[0],
    end.toISOString().split('T')[0]
  ]
})
</script>

<template>
  <div class="market-view">
    <t-card title="行情分析" class="main-card">
      <template #actions>
        <t-space>
          <StockSearch @select="handleStockSelect" />
          <t-date-range-picker
            v-model="dateRange"
            :enable-time-picker="false"
            @change="handleDateChange"
          />
        </t-space>
      </template>

      <div v-if="!selectedStock" class="empty-state">
        <t-icon name="chart-line" size="64px" style="color: #ddd" />
        <p>请选择股票查看行情</p>
      </div>

      <div v-else class="chart-container">
        <div class="chart-header">
          <h3>{{ marketStore.currentCode }}</h3>
          <t-checkbox-group v-model="selectedIndicators">
            <t-checkbox v-for="ind in indicators" :key="ind" :value="ind">
              {{ ind }}
            </t-checkbox>
          </t-checkbox-group>
        </div>
        
        <KLineChart
          :data="marketStore.klineData"
          :indicators="marketStore.indicators"
          :loading="marketStore.loading"
        />

        <t-divider />

        <div class="analysis-section">
          <t-button theme="primary" @click="marketStore.analyzeStock(selectedStock)">
            <template #icon><t-icon name="root-list" /></template>
            AI 智能分析
          </t-button>
          
          <div v-if="marketStore.analysis" class="analysis-result">
            <t-alert theme="info" :message="marketStore.analysis" />
          </div>
        </div>
      </div>
    </t-card>
  </div>
</template>

<style scoped>
.market-view {
  height: 100%;
}

.main-card {
  height: 100%;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 400px;
  color: #999;
}

.chart-container {
  min-height: 500px;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.analysis-section {
  margin-top: 16px;
}

.analysis-result {
  margin-top: 16px;
}
</style>

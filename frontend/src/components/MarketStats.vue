<template>
  <div class="market-stats">
    <div class="stats-header">
      <h3>市场统计</h3>
      <div class="header-controls">
        <input 
          type="date" 
          v-model="selectedDate" 
          @change="handleDateChange"
          class="date-input"
        />
        <button @click="refreshStats" :disabled="loading" class="refresh-btn">
          {{ loading ? '加载中...' : '刷新' }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="loading">
      <div class="loading-spinner">加载市场统计中...</div>
    </div>

    <div v-else-if="error" class="error">
      {{ error }}
      <button @click="retryLoad" class="retry-btn">重试</button>
    </div>

    <div v-else-if="marketStats" class="stats-content">
      <!-- 总体统计 -->
      <div class="overview-section">
        <h4>总体概况</h4>
        <div class="overview-metrics">
          <div class="metric-card">
            <div class="metric-icon">📊</div>
            <div class="metric-content">
              <div class="metric-value">{{ marketStats.total_stocks }}</div>
              <div class="metric-label">上榜股票数</div>
            </div>
          </div>
          <div class="metric-card">
            <div class="metric-icon">💰</div>
            <div class="metric-content">
              <div class="metric-value">{{ formatAmount(marketStats.total_amount) }}</div>
              <div class="metric-label">总成交额</div>
            </div>
          </div>
          <div class="metric-card">
            <div class="metric-icon">📈</div>
            <div class="metric-content">
              <div class="metric-value" :class="{ 'positive': marketStats.avg_pct_chg > 0, 'negative': marketStats.avg_pct_chg < 0 }">
                {{ marketStats.avg_pct_chg?.toFixed(2) }}%
              </div>
              <div class="metric-label">平均涨跌幅</div>
            </div>
          </div>
          <div class="metric-card">
            <div class="metric-icon">🎯</div>
            <div class="metric-content">
              <div class="metric-value">{{ marketStats.top_reasons?.length || 0 }}</div>
              <div class="metric-label">上榜原因种类</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 上榜原因分布 -->
      <div class="reasons-section" v-if="marketStats.top_reasons && marketStats.top_reasons.length > 0">
        <h4>上榜原因分布</h4>
        <div class="reasons-chart">
          <div class="chart-container">
            <div v-for="reason in marketStats.top_reasons" :key="reason.reason" class="reason-bar">
              <div class="reason-label">{{ reason.reason }}</div>
              <div class="reason-progress">
                <div class="progress-bar">
                  <div 
                    class="progress-fill" 
                    :style="{ width: `${(reason.count / maxReasonCount) * 100}%` }"
                  ></div>
                </div>
                <div class="reason-count">{{ reason.count }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 行业分布 -->
      <div class="sectors-section" v-if="marketStats.sector_distribution && marketStats.sector_distribution.length > 0">
        <h4>行业分布</h4>
        <div class="sectors-grid">
          <div v-for="sector in marketStats.sector_distribution" :key="sector.sector" class="sector-card">
            <div class="sector-header">
              <div class="sector-name">{{ sector.sector }}</div>
              <div class="sector-count">{{ sector.count }}只</div>
            </div>
            <div class="sector-metrics">
              <div class="sector-metric">
                <span class="metric-label">平均涨跌幅:</span>
                <span class="metric-value" :class="{ 'positive': sector.avg_pct_chg > 0, 'negative': sector.avg_pct_chg < 0 }">
                  {{ sector.avg_pct_chg?.toFixed(2) }}%
                </span>
              </div>
            </div>
            <div class="sector-progress">
              <div class="progress-bar">
                <div 
                  class="progress-fill" 
                  :style="{ width: `${(sector.count / maxSectorCount) * 100}%` }"
                ></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 详细数据表格 -->
      <div class="details-section">
        <h4>详细统计</h4>
        <div class="details-table-container">
          <table class="details-table">
            <thead>
              <tr>
                <th>统计项目</th>
                <th>数值</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>上榜股票总数</td>
                <td>{{ marketStats.total_stocks }}</td>
                <td>当日进入龙虎榜的股票数量</td>
              </tr>
              <tr>
                <td>总成交额</td>
                <td>{{ formatAmount(marketStats.total_amount) }}</td>
                <td>所有上榜股票的成交额总和</td>
              </tr>
              <tr>
                <td>平均涨跌幅</td>
                <td :class="{ 'positive': marketStats.avg_pct_chg > 0, 'negative': marketStats.avg_pct_chg < 0 }">
                  {{ marketStats.avg_pct_chg?.toFixed(2) }}%
                </td>
                <td>上榜股票的平均涨跌幅度</td>
              </tr>
              <tr>
                <td>上涨股票数</td>
                <td class="positive">{{ getPositiveCount() }}</td>
                <td>涨跌幅为正的股票数量</td>
              </tr>
              <tr>
                <td>下跌股票数</td>
                <td class="negative">{{ getNegativeCount() }}</td>
                <td>涨跌幅为负的股票数量</td>
              </tr>
              <tr>
                <td>涨停股票数</td>
                <td class="limit-up">{{ getLimitUpCount() }}</td>
                <td>涨幅超过9.5%的股票数量</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div v-else class="no-data">
      <div class="no-data-icon">📊</div>
      <div class="no-data-message">暂无统计数据</div>
      <div class="no-data-desc">请选择日期查看龙虎榜市场统计</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useTopListStore } from '@/stores/toplist'

// Store
const topListStore = useTopListStore()

// Computed
const marketStats = computed(() => topListStore.marketStats)
const loading = computed(() => topListStore.loading)
const error = computed(() => topListStore.error)

// Local state
const selectedDate = ref(new Date().toISOString().split('T')[0])

// Computed local
const maxReasonCount = computed(() => {
  if (!marketStats.value?.top_reasons?.length) return 1
  return Math.max(...marketStats.value.top_reasons.map(r => r.count))
})

const maxSectorCount = computed(() => {
  if (!marketStats.value?.sector_distribution?.length) return 1
  return Math.max(...marketStats.value.sector_distribution.map(s => s.count))
})

// Methods
const handleDateChange = () => {
  refreshStats()
}

const refreshStats = async () => {
  await topListStore.fetchMarketStats(selectedDate.value)
}

const retryLoad = () => {
  topListStore.clearError()
  refreshStats()
}

const formatAmount = (amount?: number): string => {
  if (!amount) return '-'
  if (Math.abs(amount) >= 100000000) {
    return (amount / 100000000).toFixed(2) + '亿'
  } else if (Math.abs(amount) >= 10000) {
    return (amount / 10000).toFixed(2) + '万'
  }
  return amount.toFixed(2)
}

const getPositiveCount = (): number => {
  if (!marketStats.value?.sector_distribution) return 0
  return marketStats.value.sector_distribution
    .filter(s => s.avg_pct_chg > 0)
    .reduce((sum, s) => sum + s.count, 0)
}

const getNegativeCount = (): number => {
  if (!marketStats.value?.sector_distribution) return 0
  return marketStats.value.sector_distribution
    .filter(s => s.avg_pct_chg < 0)
    .reduce((sum, s) => sum + s.count, 0)
}

const getLimitUpCount = (): number => {
  if (!marketStats.value?.sector_distribution) return 0
  return marketStats.value.sector_distribution
    .filter(s => s.avg_pct_chg > 9.5)
    .reduce((sum, s) => sum + s.count, 0)
}

// Initialize
onMounted(() => {
  refreshStats()
})
</script>

<style scoped>
.market-stats {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.stats-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 2px solid #f0f0f0;
}

.stats-header h3 {
  margin: 0;
  color: #333;
  font-size: 18px;
}

.header-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.date-input {
  padding: 6px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

.refresh-btn, .retry-btn {
  padding: 6px 16px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.refresh-btn:hover:not(:disabled), .retry-btn:hover {
  background: #0056b3;
}

.refresh-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.loading, .error, .no-data {
  text-align: center;
  padding: 40px;
  color: #666;
}

.loading-spinner {
  font-size: 16px;
}

.no-data-icon {
  font-size: 48px;
  margin-bottom: 15px;
}

.no-data-message {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 8px;
  color: #333;
}

.no-data-desc {
  font-size: 14px;
  color: #666;
}

.stats-content > div {
  margin-bottom: 30px;
}

.stats-content h4 {
  margin: 0 0 15px 0;
  color: #333;
  font-size: 16px;
  border-left: 4px solid #007bff;
  padding-left: 12px;
}

.overview-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
}

.metric-card {
  background: #f8f9fa;
  padding: 20px;
  border-radius: 8px;
  border: 1px solid #e9ecef;
  display: flex;
  align-items: center;
  gap: 15px;
}

.metric-icon {
  font-size: 32px;
}

.metric-content {
  flex: 1;
}

.metric-value {
  font-size: 24px;
  font-weight: bold;
  margin-bottom: 5px;
}

.metric-label {
  font-size: 14px;
  color: #666;
}

.reasons-chart {
  background: #f8f9fa;
  padding: 20px;
  border-radius: 8px;
  border: 1px solid #e9ecef;
}

.chart-container {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.reason-bar {
  display: flex;
  align-items: center;
  gap: 15px;
}

.reason-label {
  min-width: 120px;
  font-size: 14px;
  color: #333;
  font-weight: 500;
}

.reason-progress {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
}

.progress-bar {
  flex: 1;
  height: 20px;
  background: #e9ecef;
  border-radius: 10px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #007bff, #0056b3);
  transition: width 0.3s ease;
}

.reason-count {
  min-width: 40px;
  text-align: right;
  font-weight: 600;
  color: #333;
}

.sectors-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 15px;
}

.sector-card {
  background: #f8f9fa;
  padding: 15px;
  border-radius: 8px;
  border: 1px solid #e9ecef;
}

.sector-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.sector-name {
  font-weight: 600;
  color: #333;
}

.sector-count {
  font-size: 12px;
  color: #666;
  background: white;
  padding: 2px 8px;
  border-radius: 12px;
}

.sector-metrics {
  margin-bottom: 10px;
}

.sector-metric {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
}

.sector-metric .metric-label {
  color: #666;
}

.sector-metric .metric-value {
  font-weight: 600;
}

.sector-progress .progress-bar {
  height: 6px;
}

.sector-progress .progress-fill {
  background: linear-gradient(90deg, #28a745, #20c997);
}

.details-table-container {
  overflow-x: auto;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
}

.details-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.details-table th {
  background: #f5f5f5;
  padding: 12px;
  text-align: left;
  font-weight: 600;
  border-bottom: 2px solid #e0e0e0;
}

.details-table td {
  padding: 12px;
  border-bottom: 1px solid #f0f0f0;
}

.details-table tr:hover {
  background: #f8f9fa;
}

/* Color classes */
.positive {
  color: #dc3545;
}

.negative {
  color: #28a745;
}

.limit-up {
  color: #dc3545;
  font-weight: bold;
}

/* Responsive design */
@media (max-width: 768px) {
  .stats-header {
    flex-direction: column;
    align-items: stretch;
    gap: 15px;
  }
  
  .header-controls {
    justify-content: space-between;
  }
  
  .overview-metrics {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .metric-card {
    flex-direction: column;
    text-align: center;
    gap: 10px;
  }
  
  .sectors-grid {
    grid-template-columns: 1fr;
  }
  
  .reason-bar {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }
  
  .reason-label {
    min-width: auto;
  }
  
  .sector-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 5px;
  }
}
</style>
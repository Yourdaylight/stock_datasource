<template>
  <div class="portfolio-toplist-analysis">
    <div class="analysis-header">
      <h3>投资组合龙虎榜分析</h3>
      <div class="header-actions">
        <button @click="refreshAnalysis" :disabled="loading" class="refresh-btn">
          {{ loading ? '分析中...' : '刷新分析' }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="loading">
      <div class="loading-spinner">正在分析投资组合龙虎榜情况...</div>
    </div>

    <div v-else-if="error" class="error">
      {{ error }}
      <button @click="retryAnalysis" class="retry-btn">重试</button>
    </div>

    <div v-else-if="portfolioAnalysis" class="analysis-content">
      <!-- 概览统计 -->
      <div class="overview-section">
        <h4>概览统计</h4>
        <div class="overview-metrics">
          <div class="metric-card">
            <div class="metric-value">{{ portfolioAnalysis.capital_flow_analysis.positions_on_toplist }}</div>
            <div class="metric-label">上榜持仓</div>
          </div>
          <div class="metric-card">
            <div class="metric-value" :class="{ 'positive': portfolioAnalysis.capital_flow_analysis.total_net_flow > 0, 'negative': portfolioAnalysis.capital_flow_analysis.total_net_flow < 0 }">
              {{ formatAmount(portfolioAnalysis.capital_flow_analysis.total_net_flow) }}
            </div>
            <div class="metric-label">总净流向</div>
          </div>
          <div class="metric-card">
            <div class="metric-value" :class="getConcentrationClass(portfolioAnalysis.capital_flow_analysis.average_concentration)">
              {{ (portfolioAnalysis.capital_flow_analysis.average_concentration * 100).toFixed(1) }}%
            </div>
            <div class="metric-label">平均集中度</div>
          </div>
          <div class="metric-card">
            <div class="metric-value" :class="getRiskCountClass(portfolioAnalysis.capital_flow_analysis.high_risk_positions)">
              {{ portfolioAnalysis.capital_flow_analysis.high_risk_positions }}
            </div>
            <div class="metric-label">高风险持仓</div>
          </div>
        </div>
      </div>

      <!-- 持仓龙虎榜详情 -->
      <div class="positions-section">
        <h4>持仓龙虎榜详情</h4>
        <div class="positions-table-container">
          <table class="positions-table">
            <thead>
              <tr>
                <th>股票代码</th>
                <th>股票名称</th>
                <th>持仓权重</th>
                <th>上榜次数</th>
                <th>最近上榜</th>
                <th>席位集中度</th>
                <th>机构主导度</th>
                <th>近期净流向</th>
                <th>风险等级</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="position in portfolioAnalysis.on_list_positions" :key="position.ts_code" class="position-row">
                <td class="ts-code">{{ position.ts_code }}</td>
                <td class="stock-name">{{ position.stock_name }}</td>
                <td class="position-weight">{{ (position.position_weight * 100).toFixed(2) }}%</td>
                <td class="appearances">{{ position.toplist_appearances }}</td>
                <td class="latest-date">{{ formatDate(position.latest_appearance) }}</td>
                <td class="concentration" :class="getConcentrationClass(position.concentration_index)">
                  {{ (position.concentration_index * 100).toFixed(1) }}%
                </td>
                <td class="dominance" :class="getDominanceClass(position.institution_dominance)">
                  {{ (position.institution_dominance * 100).toFixed(1) }}%
                </td>
                <td class="net-flow" :class="{ 'positive': position.recent_net_flow > 0, 'negative': position.recent_net_flow < 0 }">
                  {{ formatAmount(position.recent_net_flow) }}
                </td>
                <td class="risk-level" :class="getRiskClass(position.risk_level)">
                  {{ getRiskLabel(position.risk_level) }}
                </td>
                <td class="actions">
                  <button @click="viewStockDetail(position)" class="detail-btn">详情</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 风险预警 -->
      <div class="alerts-section" v-if="portfolioAnalysis.risk_alerts.length > 0">
        <h4>风险预警</h4>
        <div class="alerts-list">
          <div v-for="alert in portfolioAnalysis.risk_alerts" :key="`${alert.ts_code}-${alert.type}`" class="alert-item" :class="getAlertClass(alert.type)">
            <div class="alert-icon">⚠️</div>
            <div class="alert-content">
              <div class="alert-stock">{{ alert.ts_code }}</div>
              <div class="alert-message">{{ alert.message }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 投资建议 -->
      <div class="suggestions-section" v-if="portfolioAnalysis.investment_suggestions.length > 0">
        <h4>投资建议</h4>
        <div class="suggestions-list">
          <div v-for="(suggestion, index) in portfolioAnalysis.investment_suggestions" :key="index" class="suggestion-item">
            <div class="suggestion-icon">💡</div>
            <div class="suggestion-text">{{ suggestion }}</div>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="no-data">
      <p>暂无投资组合数据</p>
      <button @click="startAnalysis" class="analyze-btn">开始分析</button>
    </div>

    <!-- 股票详情弹窗 -->
    <div v-if="showDetailModal" class="modal-overlay" @click="closeDetailModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>{{ selectedPosition?.stock_name }} ({{ selectedPosition?.ts_code }}) 详细分析</h3>
          <button @click="closeDetailModal" class="close-btn">×</button>
        </div>
        <div class="modal-body">
          <TopListAnalysis 
            v-if="selectedPosition" 
            :ts-code="selectedPosition.ts_code" 
            :stock-name="selectedPosition.stock_name"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useTopListStore } from '@/stores/toplist'
import TopListAnalysis from './TopListAnalysis.vue'
import type { PortfolioTopListAnalysis } from '@/api/toplist'

// Store
const topListStore = useTopListStore()

// Computed
const portfolioAnalysis = computed(() => topListStore.portfolioAnalysis)
const loading = computed(() => topListStore.loading)
const error = computed(() => topListStore.error)

// Local state
const showDetailModal = ref(false)
const selectedPosition = ref<any>(null)

// Methods
const refreshAnalysis = async () => {
  await topListStore.analyzePortfolio()
}

const startAnalysis = async () => {
  await topListStore.analyzePortfolio()
}

const retryAnalysis = () => {
  topListStore.clearError()
  startAnalysis()
}

const viewStockDetail = (position: any) => {
  selectedPosition.value = position
  showDetailModal.value = true
}

const closeDetailModal = () => {
  showDetailModal.value = false
  selectedPosition.value = null
}

const formatAmount = (amount: number): string => {
  if (!amount) return '-'
  if (Math.abs(amount) >= 100000000) {
    return (amount / 100000000).toFixed(2) + '亿'
  } else if (Math.abs(amount) >= 10000) {
    return (amount / 10000).toFixed(2) + '万'
  }
  return amount.toFixed(2)
}

const formatDate = (dateStr?: string): string => {
  if (!dateStr) return '-'
  return dateStr.replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3')
}

const getConcentrationClass = (concentration: number): string => {
  if (concentration > 0.7) return 'high-concentration'
  if (concentration > 0.5) return 'medium-concentration'
  return 'low-concentration'
}

const getDominanceClass = (dominance: number): string => {
  if (dominance > 0.7) return 'high-dominance'
  if (dominance > 0.4) return 'medium-dominance'
  return 'low-dominance'
}

const getRiskClass = (risk: string): string => {
  switch (risk.toLowerCase()) {
    case 'high': return 'high-risk'
    case 'medium': return 'medium-risk'
    case 'low': return 'low-risk'
    default: return ''
  }
}

const getRiskLabel = (risk: string): string => {
  switch (risk.toLowerCase()) {
    case 'high': return '高风险'
    case 'medium': return '中等风险'
    case 'low': return '低风险'
    default: return risk
  }
}

const getRiskCountClass = (count: number): string => {
  if (count > 3) return 'high-risk'
  if (count > 1) return 'medium-risk'
  return 'low-risk'
}

const getAlertClass = (type: string): string => {
  switch (type) {
    case 'high_concentration': return 'concentration-alert'
    case 'capital_outflow': return 'outflow-alert'
    default: return 'general-alert'
  }
}

// Initialize
onMounted(() => {
  startAnalysis()
})
</script>

<style scoped>
.portfolio-toplist-analysis {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.analysis-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 2px solid #f0f0f0;
}

.analysis-header h3 {
  margin: 0;
  color: #333;
  font-size: 18px;
}

.refresh-btn, .retry-btn, .analyze-btn {
  padding: 8px 16px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.refresh-btn:hover:not(:disabled), .retry-btn:hover, .analyze-btn:hover {
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

.analysis-content > div {
  margin-bottom: 30px;
}

.analysis-content h4 {
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
  text-align: center;
  border: 1px solid #e9ecef;
}

.metric-value {
  font-size: 24px;
  font-weight: bold;
  margin-bottom: 8px;
}

.metric-label {
  font-size: 14px;
  color: #666;
}

.positions-table-container {
  overflow-x: auto;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
}

.positions-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.positions-table th {
  background: #f5f5f5;
  padding: 12px 8px;
  text-align: left;
  font-weight: 600;
  border-bottom: 2px solid #e0e0e0;
  white-space: nowrap;
}

.positions-table td {
  padding: 10px 8px;
  border-bottom: 1px solid #f0f0f0;
  white-space: nowrap;
}

.position-row:hover {
  background: #f8f9fa;
}

.ts-code {
  font-family: monospace;
  font-weight: 600;
  color: #007bff;
}

.stock-name {
  font-weight: 500;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.detail-btn {
  padding: 4px 8px;
  border: 1px solid #ddd;
  border-radius: 3px;
  background: white;
  cursor: pointer;
  font-size: 12px;
}

.detail-btn:hover {
  background: #e9ecef;
}

.alerts-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.alert-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 6px;
  border-left: 4px solid;
}

.concentration-alert {
  background: #fff3cd;
  border-left-color: #ffc107;
}

.outflow-alert {
  background: #f8d7da;
  border-left-color: #dc3545;
}

.general-alert {
  background: #d1ecf1;
  border-left-color: #17a2b8;
}

.alert-icon {
  font-size: 18px;
}

.alert-content {
  flex: 1;
}

.alert-stock {
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
}

.alert-message {
  color: #666;
  font-size: 14px;
}

.suggestions-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.suggestion-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 16px;
  background: #d4edda;
  border-radius: 6px;
  border-left: 4px solid #28a745;
}

.suggestion-icon {
  font-size: 18px;
  margin-top: 2px;
}

.suggestion-text {
  color: #155724;
  font-size: 14px;
  line-height: 1.4;
}

/* Modal styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 8px;
  width: 90%;
  max-width: 800px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #e0e0e0;
}

.modal-header h3 {
  margin: 0;
  color: #333;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #666;
  padding: 0;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-btn:hover {
  color: #333;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

/* Color classes */
.positive {
  color: #dc3545;
}

.negative {
  color: #28a745;
}

.high-concentration, .high-dominance, .high-risk {
  color: #dc3545;
}

.medium-concentration, .medium-dominance, .medium-risk {
  color: #ffc107;
}

.low-concentration, .low-dominance, .low-risk {
  color: #28a745;
}
</style>
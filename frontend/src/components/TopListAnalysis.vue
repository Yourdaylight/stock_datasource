<template>
  <div class="top-list-analysis">
    <div class="analysis-header">
      <h3>{{ stockName || tsCode }} 龙虎榜分析</h3>
      <div class="time-range-selector">
        <label>分析周期:</label>
        <select v-model="selectedTimeRange" @change="handleTimeRangeChange">
          <option value="5">近5天</option>
          <option value="10">近10天</option>
          <option value="20">近20天</option>
          <option value="30">近30天</option>
        </select>
      </div>
    </div>

    <div v-if="loading" class="loading">
      <div class="loading-spinner">分析中...</div>
    </div>

    <div v-else-if="error" class="error">
      {{ error }}
      <button @click="retryAnalysis" class="retry-btn">重试</button>
    </div>

    <div v-else-if="analysis" class="analysis-content">
      <!-- 席位集中度分析 -->
      <div class="analysis-section">
        <h4>席位集中度分析</h4>
        <div class="concentration-metrics">
          <div class="metric-card">
            <div class="metric-label">集中度指数</div>
            <div class="metric-value" :class="getConcentrationClass(analysis.seat_concentration.concentration_index)">
              {{ (analysis.seat_concentration.concentration_index * 100).toFixed(1) }}%
            </div>
            <div class="metric-desc">{{ getConcentrationDesc(analysis.seat_concentration.concentration_index) }}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">机构主导度</div>
            <div class="metric-value" :class="getDominanceClass(analysis.seat_concentration.institution_dominance)">
              {{ (analysis.seat_concentration.institution_dominance * 100).toFixed(1) }}%
            </div>
            <div class="metric-desc">{{ getDominanceDesc(analysis.seat_concentration.institution_dominance) }}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">风险等级</div>
            <div class="metric-value" :class="getRiskClass(analysis.seat_concentration.risk_level)">
              {{ getRiskLabel(analysis.seat_concentration.risk_level) }}
            </div>
            <div class="metric-desc">基于席位集中度评估</div>
          </div>
        </div>
      </div>

      <!-- 资金流向趋势 -->
      <div class="analysis-section">
        <h4>资金流向趋势</h4>
        <div class="flow-metrics">
          <div class="flow-card">
            <div class="flow-label">5日净流向</div>
            <div class="flow-value" :class="{ 'positive': analysis.capital_flow_trend.net_flow_5d > 0, 'negative': analysis.capital_flow_trend.net_flow_5d < 0 }">
              {{ formatAmount(analysis.capital_flow_trend.net_flow_5d) }}
            </div>
          </div>
          <div class="flow-card">
            <div class="flow-label">10日净流向</div>
            <div class="flow-value" :class="{ 'positive': analysis.capital_flow_trend.net_flow_10d > 0, 'negative': analysis.capital_flow_trend.net_flow_10d < 0 }">
              {{ formatAmount(analysis.capital_flow_trend.net_flow_10d) }}
            </div>
          </div>
          <div class="flow-card">
            <div class="flow-label">流向方向</div>
            <div class="flow-direction" :class="getFlowDirectionClass(analysis.capital_flow_trend.flow_direction)">
              {{ analysis.capital_flow_trend.flow_direction }}
            </div>
          </div>
          <div class="flow-card">
            <div class="flow-label">稳定性评分</div>
            <div class="stability-score">
              <div class="score-bar">
                <div class="score-fill" :style="{ width: `${analysis.capital_flow_trend.stability_score * 100}%` }"></div>
              </div>
              <span class="score-text">{{ (analysis.capital_flow_trend.stability_score * 100).toFixed(0) }}分</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 交易模式分析 -->
      <div class="analysis-section">
        <h4>交易模式分析</h4>
        <div class="trading-metrics">
          <div class="trading-item">
            <span class="label">平均换手率:</span>
            <span class="value">{{ analysis.trading_pattern.avg_turnover_rate?.toFixed(2) }}%</span>
          </div>
          <div class="trading-item">
            <span class="label">波动指数:</span>
            <span class="value" :class="getVolatilityClass(analysis.trading_pattern.volatility_index)">
              {{ analysis.trading_pattern.volatility_index?.toFixed(2) }}
            </span>
          </div>
          <div class="trading-item">
            <span class="label">成交量异动次数:</span>
            <span class="value">{{ analysis.trading_pattern.volume_surge_count }}次</span>
          </div>
        </div>
      </div>

      <!-- 风险评估 -->
      <div class="analysis-section">
        <h4>风险评估</h4>
        <div class="risk-assessment">
          <div class="overall-risk">
            <span class="risk-label">整体风险:</span>
            <span class="risk-level" :class="getRiskClass(analysis.risk_assessment.overall_risk)">
              {{ getRiskLabel(analysis.risk_assessment.overall_risk) }}
            </span>
          </div>
          
          <div class="risk-factors" v-if="analysis.risk_assessment.risk_factors.length > 0">
            <h5>风险因子:</h5>
            <ul class="risk-list">
              <li v-for="factor in analysis.risk_assessment.risk_factors" :key="factor" class="risk-factor">
                {{ factor }}
              </li>
            </ul>
          </div>
          
          <div class="suggestions" v-if="analysis.risk_assessment.suggestions.length > 0">
            <h5>投资建议:</h5>
            <ul class="suggestion-list">
              <li v-for="suggestion in analysis.risk_assessment.suggestions" :key="suggestion" class="suggestion">
                {{ suggestion }}
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="no-analysis">
      <p>暂无分析数据</p>
      <button @click="startAnalysis" class="analyze-btn">开始分析</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useTopListStore } from '@/stores/toplist'
import type { TopListAnalysis } from '@/api/toplist'

// Props
interface Props {
  tsCode: string
  stockName?: string
}

const props = defineProps<Props>()

// Store
const topListStore = useTopListStore()

// Computed
const analysis = computed(() => topListStore.currentAnalysis)
const loading = computed(() => topListStore.loading)
const error = computed(() => topListStore.error)

// Local state
const selectedTimeRange = ref(10)

// Methods
const handleTimeRangeChange = () => {
  topListStore.setAnalysisTimeRange(selectedTimeRange.value)
  startAnalysis()
}

const startAnalysis = async () => {
  await topListStore.fetchStockAnalysis(props.tsCode, selectedTimeRange.value)
}

const retryAnalysis = () => {
  topListStore.clearError()
  startAnalysis()
}

const formatAmount = (amount: number): string => {
  if (Math.abs(amount) >= 100000000) {
    return (amount / 100000000).toFixed(2) + '亿'
  } else if (Math.abs(amount) >= 10000) {
    return (amount / 10000).toFixed(2) + '万'
  }
  return amount.toFixed(2)
}

const getConcentrationClass = (index: number): string => {
  if (index > 0.7) return 'high-risk'
  if (index > 0.5) return 'medium-risk'
  return 'low-risk'
}

const getConcentrationDesc = (index: number): string => {
  if (index > 0.7) return '高度集中'
  if (index > 0.5) return '中度集中'
  return '相对分散'
}

const getDominanceClass = (dominance: number): string => {
  if (dominance > 0.7) return 'high-dominance'
  if (dominance > 0.4) return 'medium-dominance'
  return 'low-dominance'
}

const getDominanceDesc = (dominance: number): string => {
  if (dominance > 0.7) return '机构主导明显'
  if (dominance > 0.4) return '机构参与较多'
  return '散户为主'
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

const getFlowDirectionClass = (direction: string): string => {
  if (direction.includes('流入')) return 'inflow'
  if (direction.includes('流出')) return 'outflow'
  return 'neutral'
}

const getVolatilityClass = (volatility: number): string => {
  if (volatility > 0.3) return 'high-volatility'
  if (volatility > 0.15) return 'medium-volatility'
  return 'low-volatility'
}

// Watch for prop changes
watch(() => props.tsCode, (newCode) => {
  if (newCode) {
    startAnalysis()
  }
})

// Initialize
onMounted(() => {
  if (props.tsCode) {
    startAnalysis()
  }
})
</script>

<style scoped>
.top-list-analysis {
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

.time-range-selector {
  display: flex;
  align-items: center;
  gap: 8px;
}

.time-range-selector label {
  font-weight: 500;
  color: #666;
}

.time-range-selector select {
  padding: 6px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

.loading, .error, .no-analysis {
  text-align: center;
  padding: 40px;
  color: #666;
}

.loading-spinner {
  font-size: 16px;
}

.retry-btn, .analyze-btn {
  margin-left: 12px;
  padding: 6px 16px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.retry-btn:hover, .analyze-btn:hover {
  background: #0056b3;
}

.analysis-section {
  margin-bottom: 30px;
}

.analysis-section h4 {
  margin: 0 0 15px 0;
  color: #333;
  font-size: 16px;
  border-left: 4px solid #007bff;
  padding-left: 12px;
}

.concentration-metrics {
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

.metric-label {
  font-size: 14px;
  color: #666;
  margin-bottom: 8px;
}

.metric-value {
  font-size: 24px;
  font-weight: bold;
  margin-bottom: 8px;
}

.metric-desc {
  font-size: 12px;
  color: #888;
}

.flow-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 15px;
}

.flow-card {
  background: #f8f9fa;
  padding: 15px;
  border-radius: 6px;
  border: 1px solid #e9ecef;
}

.flow-label {
  font-size: 14px;
  color: #666;
  margin-bottom: 8px;
}

.flow-value {
  font-size: 18px;
  font-weight: bold;
}

.flow-direction {
  font-size: 16px;
  font-weight: 600;
}

.stability-score {
  display: flex;
  align-items: center;
  gap: 10px;
}

.score-bar {
  flex: 1;
  height: 8px;
  background: #e9ecef;
  border-radius: 4px;
  overflow: hidden;
}

.score-fill {
  height: 100%;
  background: linear-gradient(90deg, #dc3545, #ffc107, #28a745);
  transition: width 0.3s ease;
}

.score-text {
  font-size: 14px;
  font-weight: 600;
}

.trading-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
}

.trading-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 15px;
  background: #f8f9fa;
  border-radius: 6px;
  border: 1px solid #e9ecef;
}

.trading-item .label {
  color: #666;
  font-size: 14px;
}

.trading-item .value {
  font-weight: 600;
  font-size: 16px;
}

.risk-assessment {
  background: #f8f9fa;
  padding: 20px;
  border-radius: 8px;
  border: 1px solid #e9ecef;
}

.overall-risk {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  font-size: 16px;
}

.risk-label {
  font-weight: 600;
  color: #333;
}

.risk-level {
  padding: 4px 12px;
  border-radius: 20px;
  font-weight: 600;
  font-size: 14px;
}

.risk-factors, .suggestions {
  margin-bottom: 15px;
}

.risk-factors h5, .suggestions h5 {
  margin: 0 0 10px 0;
  color: #333;
  font-size: 14px;
}

.risk-list, .suggestion-list {
  margin: 0;
  padding-left: 20px;
}

.risk-factor, .suggestion {
  margin-bottom: 8px;
  color: #555;
  font-size: 14px;
  line-height: 1.4;
}

/* Color classes */
.positive {
  color: #dc3545;
}

.negative {
  color: #28a745;
}

.high-risk {
  color: #dc3545;
}

.medium-risk {
  color: #ffc107;
}

.low-risk {
  color: #28a745;
}

.high-dominance {
  color: #007bff;
}

.medium-dominance {
  color: #6c757d;
}

.low-dominance {
  color: #28a745;
}

.inflow {
  color: #dc3545;
}

.outflow {
  color: #28a745;
}

.neutral {
  color: #6c757d;
}

.high-volatility {
  color: #dc3545;
}

.medium-volatility {
  color: #ffc107;
}

.low-volatility {
  color: #28a745;
}

.risk-level.high-risk {
  background: #f8d7da;
  color: #721c24;
}

.risk-level.medium-risk {
  background: #fff3cd;
  color: #856404;
}

.risk-level.low-risk {
  background: #d4edda;
  color: #155724;
}
</style>
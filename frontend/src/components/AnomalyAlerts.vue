<template>
  <div class="anomaly-alerts">
    <div class="alerts-header">
      <h3>异动预警</h3>
      <div class="header-controls">
        <div class="filter-controls">
          <select v-model="selectedSeverity" @change="handleSeverityChange" class="severity-select">
            <option value="">全部级别</option>
            <option value="high">高风险</option>
            <option value="medium">中等风险</option>
            <option value="low">低风险</option>
          </select>
          <input 
            type="date" 
            v-model="selectedDate" 
            @change="handleDateChange"
            class="date-input"
          />
        </div>
        <button @click="refreshAlerts" :disabled="loading" class="refresh-btn">
          {{ loading ? '加载中...' : '刷新' }}
        </button>
      </div>
    </div>

    <!-- 统计概览 -->
    <div class="alerts-summary" v-if="alertsSummary">
      <div class="summary-card high-risk">
        <div class="summary-value">{{ alertsSummary.high }}</div>
        <div class="summary-label">高风险预警</div>
      </div>
      <div class="summary-card medium-risk">
        <div class="summary-value">{{ alertsSummary.medium }}</div>
        <div class="summary-label">中等风险预警</div>
      </div>
      <div class="summary-card low-risk">
        <div class="summary-value">{{ alertsSummary.low }}</div>
        <div class="summary-label">低风险预警</div>
      </div>
      <div class="summary-card total">
        <div class="summary-value">{{ alertsSummary.total }}</div>
        <div class="summary-label">总预警数</div>
      </div>
    </div>

    <div v-if="loading" class="loading">
      <div class="loading-spinner">加载预警信息中...</div>
    </div>

    <div v-else-if="error" class="error">
      {{ error }}
      <button @click="retryLoad" class="retry-btn">重试</button>
    </div>

    <div v-else-if="hasAlerts" class="alerts-content">
      <!-- 高风险预警优先显示 -->
      <div v-if="highRiskAlerts.length > 0" class="priority-alerts">
        <h4>🚨 高风险预警</h4>
        <div class="alerts-list">
          <div v-for="alert in highRiskAlerts" :key="`${alert.ts_code}-${alert.alert_type}`" class="alert-item high-severity">
            <div class="alert-header">
              <div class="alert-stock">
                <span class="stock-code">{{ alert.ts_code }}</span>
                <span class="stock-name">{{ alert.stock_name || '-' }}</span>
              </div>
              <div class="alert-time">{{ formatTime(alert.detected_at) }}</div>
            </div>
            <div class="alert-body">
              <div class="alert-type">{{ getAlertTypeLabel(alert.alert_type) }}</div>
              <div class="alert-message">{{ alert.message }}</div>
              <div class="alert-indicators" v-if="alert.indicators && Object.keys(alert.indicators).length > 0">
                <div class="indicators-title">关键指标:</div>
                <div class="indicators-list">
                  <span v-for="(value, key) in alert.indicators" :key="key" class="indicator-item">
                    {{ key }}: {{ formatIndicatorValue(value) }}
                  </span>
                </div>
              </div>
            </div>
            <div class="alert-actions">
              <button @click="viewStockDetail(alert)" class="detail-btn">查看详情</button>
              <button @click="analyzeStock(alert)" class="analyze-btn">深度分析</button>
            </div>
          </div>
        </div>
      </div>

      <!-- 所有预警列表 -->
      <div class="all-alerts">
        <h4>所有预警 ({{ anomalyAlerts.length }})</h4>
        <div class="alerts-list">
          <div v-for="alert in anomalyAlerts" :key="`${alert.ts_code}-${alert.alert_type}`" 
               class="alert-item" 
               :class="getSeverityClass(alert.severity)">
            <div class="alert-header">
              <div class="alert-stock">
                <span class="stock-code">{{ alert.ts_code }}</span>
                <span class="stock-name">{{ alert.stock_name || '-' }}</span>
                <span class="severity-badge" :class="getSeverityClass(alert.severity)">
                  {{ getSeverityLabel(alert.severity) }}
                </span>
              </div>
              <div class="alert-time">{{ formatTime(alert.detected_at) }}</div>
            </div>
            <div class="alert-body">
              <div class="alert-type">{{ getAlertTypeLabel(alert.alert_type) }}</div>
              <div class="alert-message">{{ alert.message }}</div>
              <div class="alert-indicators" v-if="alert.indicators && Object.keys(alert.indicators).length > 0">
                <div class="indicators-title">关键指标:</div>
                <div class="indicators-list">
                  <span v-for="(value, key) in alert.indicators" :key="key" class="indicator-item">
                    {{ key }}: {{ formatIndicatorValue(value) }}
                  </span>
                </div>
              </div>
            </div>
            <div class="alert-actions">
              <button @click="viewStockDetail(alert)" class="detail-btn">查看详情</button>
              <button @click="analyzeStock(alert)" class="analyze-btn">深度分析</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="no-alerts">
      <div class="no-alerts-icon">✅</div>
      <div class="no-alerts-message">暂无异动预警</div>
      <div class="no-alerts-desc">当前时间段内未检测到异常交易行为</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useTopListStore } from '@/stores/toplist'
import type { AnomalyAlert } from '@/api/toplist'

// Store
const topListStore = useTopListStore()

// Computed
const anomalyAlerts = computed(() => topListStore.anomalyAlerts)
const loading = computed(() => topListStore.loading)
const error = computed(() => topListStore.error)
const hasAlerts = computed(() => topListStore.hasAlerts)
const highRiskAlerts = computed(() => topListStore.highRiskAlerts)

// Local state
const selectedSeverity = ref('')
const selectedDate = ref(new Date().toISOString().split('T')[0])

// Computed local
const alertsSummary = computed(() => {
  if (!anomalyAlerts.value.length) return null
  
  const summary = {
    high: 0,
    medium: 0,
    low: 0,
    total: anomalyAlerts.value.length
  }
  
  anomalyAlerts.value.forEach(alert => {
    summary[alert.severity]++
  })
  
  return summary
})

// Emits
const emit = defineEmits<{
  viewDetail: [alert: AnomalyAlert]
  analyzeStock: [alert: AnomalyAlert]
}>()

// Methods
const handleSeverityChange = () => {
  topListStore.setSelectedSeverity(selectedSeverity.value)
  refreshAlerts()
}

const handleDateChange = () => {
  refreshAlerts()
}

const refreshAlerts = async () => {
  await topListStore.fetchAnomalyAlerts(selectedDate.value, selectedSeverity.value)
}

const retryLoad = () => {
  topListStore.clearError()
  refreshAlerts()
}

const viewStockDetail = (alert: AnomalyAlert) => {
  emit('viewDetail', alert)
}

const analyzeStock = (alert: AnomalyAlert) => {
  emit('analyzeStock', alert)
}

const formatTime = (timeStr: string): string => {
  const date = new Date(timeStr)
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const getSeverityClass = (severity: string): string => {
  return `${severity}-severity`
}

const getSeverityLabel = (severity: string): string => {
  switch (severity) {
    case 'high': return '高风险'
    case 'medium': return '中等风险'
    case 'low': return '低风险'
    default: return severity
  }
}

const getAlertTypeLabel = (type: string): string => {
  const typeLabels: Record<string, string> = {
    'volume_surge': '成交量异动',
    'price_volatility': '价格异常波动',
    'seat_concentration': '席位高度集中',
    'capital_flow_anomaly': '资金流向异常',
    'turnover_spike': '换手率激增',
    'institutional_activity': '机构异常活动'
  }
  return typeLabels[type] || type
}

const formatIndicatorValue = (value: any): string => {
  if (typeof value === 'number') {
    if (Math.abs(value) >= 100000000) {
      return (value / 100000000).toFixed(2) + '亿'
    } else if (Math.abs(value) >= 10000) {
      return (value / 10000).toFixed(2) + '万'
    } else if (value < 1 && value > 0) {
      return (value * 100).toFixed(2) + '%'
    }
    return value.toFixed(2)
  }
  return String(value)
}

// Watch for store changes
watch(() => topListStore.selectedSeverity, (newSeverity) => {
  selectedSeverity.value = newSeverity
})

// Initialize
onMounted(() => {
  refreshAlerts()
})
</script>

<style scoped>
.anomaly-alerts {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.alerts-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 2px solid #f0f0f0;
}

.alerts-header h3 {
  margin: 0;
  color: #333;
  font-size: 18px;
}

.header-controls {
  display: flex;
  align-items: center;
  gap: 15px;
}

.filter-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.severity-select, .date-input {
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

.alerts-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 15px;
  margin-bottom: 25px;
}

.summary-card {
  padding: 15px;
  border-radius: 8px;
  text-align: center;
  border: 1px solid;
}

.summary-card.high-risk {
  background: #f8d7da;
  border-color: #dc3545;
}

.summary-card.medium-risk {
  background: #fff3cd;
  border-color: #ffc107;
}

.summary-card.low-risk {
  background: #d4edda;
  border-color: #28a745;
}

.summary-card.total {
  background: #d1ecf1;
  border-color: #17a2b8;
}

.summary-value {
  font-size: 24px;
  font-weight: bold;
  margin-bottom: 5px;
}

.summary-label {
  font-size: 12px;
  color: #666;
}

.loading, .error, .no-alerts {
  text-align: center;
  padding: 40px;
  color: #666;
}

.loading-spinner {
  font-size: 16px;
}

.no-alerts-icon {
  font-size: 48px;
  margin-bottom: 15px;
}

.no-alerts-message {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 8px;
  color: #333;
}

.no-alerts-desc {
  font-size: 14px;
  color: #666;
}

.alerts-content > div {
  margin-bottom: 30px;
}

.alerts-content h4 {
  margin: 0 0 15px 0;
  color: #333;
  font-size: 16px;
  border-left: 4px solid #007bff;
  padding-left: 12px;
}

.priority-alerts h4 {
  border-left-color: #dc3545;
  color: #dc3545;
}

.alerts-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.alert-item {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 15px;
  background: white;
  transition: all 0.2s ease;
}

.alert-item:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.alert-item.high-severity {
  border-left: 4px solid #dc3545;
  background: #fefefe;
}

.alert-item.medium-severity {
  border-left: 4px solid #ffc107;
}

.alert-item.low-severity {
  border-left: 4px solid #28a745;
}

.alert-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.alert-stock {
  display: flex;
  align-items: center;
  gap: 10px;
}

.stock-code {
  font-family: monospace;
  font-weight: 600;
  color: #007bff;
  font-size: 14px;
}

.stock-name {
  font-weight: 500;
  color: #333;
}

.severity-badge {
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.severity-badge.high-severity {
  background: #dc3545;
  color: white;
}

.severity-badge.medium-severity {
  background: #ffc107;
  color: #333;
}

.severity-badge.low-severity {
  background: #28a745;
  color: white;
}

.alert-time {
  font-size: 12px;
  color: #666;
}

.alert-body {
  margin-bottom: 15px;
}

.alert-type {
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
  font-size: 14px;
}

.alert-message {
  color: #555;
  line-height: 1.4;
  margin-bottom: 10px;
}

.alert-indicators {
  background: #f8f9fa;
  padding: 10px;
  border-radius: 4px;
  border: 1px solid #e9ecef;
}

.indicators-title {
  font-size: 12px;
  color: #666;
  margin-bottom: 6px;
  font-weight: 500;
}

.indicators-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.indicator-item {
  background: white;
  padding: 4px 8px;
  border-radius: 3px;
  font-size: 12px;
  border: 1px solid #ddd;
  color: #333;
}

.alert-actions {
  display: flex;
  gap: 10px;
}

.detail-btn, .analyze-btn {
  padding: 6px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: white;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s ease;
}

.detail-btn:hover {
  background: #f8f9fa;
  border-color: #007bff;
  color: #007bff;
}

.analyze-btn {
  background: #007bff;
  color: white;
  border-color: #007bff;
}

.analyze-btn:hover {
  background: #0056b3;
  border-color: #0056b3;
}

/* Responsive design */
@media (max-width: 768px) {
  .alerts-header {
    flex-direction: column;
    align-items: stretch;
    gap: 15px;
  }
  
  .header-controls {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }
  
  .filter-controls {
    flex-direction: column;
    gap: 8px;
  }
  
  .alerts-summary {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .alert-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  
  .alert-stock {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }
  
  .indicators-list {
    flex-direction: column;
    gap: 4px;
  }
  
  .alert-actions {
    flex-direction: column;
    gap: 8px;
  }
}
</style>
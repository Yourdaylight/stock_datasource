<template>
  <el-card class="daily-analysis-card">
    <template #header>
      <div class="card-header">
        <span>每日分析报告</span>
        <el-button 
          size="small" 
          type="primary" 
          :loading="loading"
          @click="$emit('trigger-analysis')"
        >
          生成报告
        </el-button>
      </div>
    </template>

    <div v-loading="loading" class="analysis-content">
      <div v-if="!loading && !analysisData" class="empty-analysis">
        <el-empty description="暂无分析报告">
          <el-button type="primary" @click="$emit('trigger-analysis')">
            生成今日报告
          </el-button>
        </el-empty>
      </div>

      <div v-else-if="analysisData" class="analysis-report">
        <!-- Report Header -->
        <div class="report-header">
          <div class="report-date">
            <el-icon><Calendar /></el-icon>
            {{ formatDate(analysisData.report_date) }}
          </div>
          <el-tag 
            :type="getStatusType(analysisData.status)"
            size="small"
          >
            {{ getStatusText(analysisData.status) }}
          </el-tag>
        </div>

        <!-- AI Insights -->
        <div v-if="analysisData.ai_insights" class="analysis-section">
          <h4>
            <el-icon><ChatDotRound /></el-icon>
            AI 分析洞察
          </h4>
          <div class="insights-content">
            {{ analysisData.ai_insights }}
          </div>
        </div>

        <!-- Portfolio Summary -->
        <div v-if="portfolioSummaryData" class="analysis-section">
          <h4>
            <el-icon><PieChart /></el-icon>
            投资组合概览
          </h4>
          <el-row :gutter="10">
            <el-col :span="12">
              <div class="summary-item">
                <span class="label">总市值:</span>
                <span class="value">¥{{ formatNumber(portfolioSummaryData.total_value) }}</span>
              </div>
            </el-col>
            <el-col :span="12">
              <div class="summary-item">
                <span class="label">总盈亏:</span>
                <span 
                  class="value" 
                  :class="portfolioSummaryData.total_profit >= 0 ? 'profit' : 'loss'"
                >
                  ¥{{ formatNumber(portfolioSummaryData.total_profit) }}
                </span>
              </div>
            </el-col>
            <el-col :span="12">
              <div class="summary-item">
                <span class="label">收益率:</span>
                <span 
                  class="value" 
                  :class="portfolioSummaryData.profit_rate >= 0 ? 'profit' : 'loss'"
                >
                  {{ portfolioSummaryData.profit_rate?.toFixed(2) }}%
                </span>
              </div>
            </el-col>
            <el-col :span="12">
              <div class="summary-item">
                <span class="label">持仓数:</span>
                <span class="value">{{ portfolioSummaryData.position_count }}只</span>
              </div>
            </el-col>
          </el-row>
        </div>

        <!-- Market Analysis -->
        <div v-if="marketAnalysisData" class="analysis-section">
          <h4>
            <el-icon><TrendCharts /></el-icon>
            市场环境分析
          </h4>
          <div class="market-info">
            <div v-if="marketAnalysisData.trend" class="market-item">
              <span class="label">市场趋势:</span>
              <el-tag :type="getTrendType(marketAnalysisData.trend)" size="small">
                {{ getTrendText(marketAnalysisData.trend) }}
              </el-tag>
            </div>
            <div v-if="marketAnalysisData.volatility" class="market-item">
              <span class="label">波动水平:</span>
              <span class="value">{{ marketAnalysisData.volatility }}</span>
            </div>
            <div v-if="marketAnalysisData.sentiment" class="market-item">
              <span class="label">市场情绪:</span>
              <span class="value">{{ marketAnalysisData.sentiment }}</span>
            </div>
          </div>
        </div>

        <!-- Recommendations -->
        <div v-if="recommendationsData && recommendationsData.length > 0" class="analysis-section">
          <h4>
            <el-icon><Guide /></el-icon>
            投资建议
          </h4>
          <div class="recommendations">
            <div 
              v-for="(rec, index) in recommendationsData.slice(0, 3)" 
              :key="index"
              class="recommendation-item"
            >
              <el-tag 
                :type="getPriorityType(rec.priority)" 
                size="small"
                class="priority-tag"
              >
                {{ getPriorityText(rec.priority) }}
              </el-tag>
              <span class="rec-text">{{ rec.description || rec.message }}</span>
            </div>
          </div>
        </div>

        <!-- Risk Assessment -->
        <div v-if="riskAssessmentData" class="analysis-section">
          <h4>
            <el-icon><Warning /></el-icon>
            风险评估
          </h4>
          <div class="risk-info">
            <div v-if="riskAssessmentData.overall_risk" class="risk-item">
              <span class="label">整体风险:</span>
              <el-tag 
                :type="getRiskType(riskAssessmentData.overall_risk)" 
                size="small"
              >
                {{ riskAssessmentData.overall_risk }}
              </el-tag>
            </div>
            <div v-if="riskAssessmentData.risk_score" class="risk-item">
              <span class="label">风险评分:</span>
              <span class="value">{{ riskAssessmentData.risk_score }}/100</span>
            </div>
          </div>
        </div>

        <!-- View Full Report -->
        <div class="report-actions">
          <el-button size="small" @click="showFullReport = true">
            查看完整报告
          </el-button>
        </div>
      </div>
    </div>

    <!-- Full Report Dialog -->
    <el-dialog 
      v-model="showFullReport" 
      title="完整分析报告" 
      width="80%"
      :before-close="() => showFullReport = false"
    >
      <div v-if="analysisData" class="full-report">
        <el-tabs v-model="activeTab" type="border-card">
          <el-tab-pane label="市场分析" name="market">
            <pre class="report-content">{{ analysisData.market_analysis }}</pre>
          </el-tab-pane>
          <el-tab-pane label="个股分析" name="individual">
            <pre class="report-content">{{ analysisData.individual_analysis }}</pre>
          </el-tab-pane>
          <el-tab-pane label="风险评估" name="risk">
            <pre class="report-content">{{ analysisData.risk_assessment }}</pre>
          </el-tab-pane>
          <el-tab-pane label="投资建议" name="recommendations">
            <pre class="report-content">{{ analysisData.recommendations }}</pre>
          </el-tab-pane>
          <el-tab-pane label="AI洞察" name="insights">
            <div class="report-content">{{ analysisData.ai_insights }}</div>
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { 
  Calendar, 
  ChatDotRound, 
  PieChart, 
  TrendCharts, 
  Guide, 
  Warning 
} from '@element-plus/icons-vue'
import type { AnalysisReport } from '@/types/portfolio'

interface Props {
  analysisData: AnalysisReport | null
  loading?: boolean
}

interface Emits {
  (e: 'trigger-analysis'): void
}

const props = withDefaults(defineProps<Props>(), {
  loading: false
})

defineEmits<Emits>()

// Reactive data
const showFullReport = ref(false)
const activeTab = ref('market')

// Computed
const portfolioSummaryData = computed(() => {
  if (!props.analysisData?.portfolio_summary) return null
  try {
    return JSON.parse(props.analysisData.portfolio_summary)
  } catch {
    return null
  }
})

const marketAnalysisData = computed(() => {
  if (!props.analysisData?.market_analysis) return null
  try {
    return JSON.parse(props.analysisData.market_analysis)
  } catch {
    return null
  }
})

const recommendationsData = computed(() => {
  if (!props.analysisData?.recommendations) return []
  try {
    return JSON.parse(props.analysisData.recommendations)
  } catch {
    return []
  }
})

const riskAssessmentData = computed(() => {
  if (!props.analysisData?.risk_assessment) return null
  try {
    return JSON.parse(props.analysisData.risk_assessment)
  } catch {
    return null
  }
})

// Methods
const formatDate = (dateString: string): string => {
  const date = new Date(dateString)
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
}

const formatNumber = (value: number): string => {
  if (!value) return '0.00'
  return value.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })
}

const getStatusType = (status: string) => {
  const statusMap: Record<string, string> = {
    'completed': 'success',
    'pending': 'warning',
    'failed': 'danger'
  }
  return statusMap[status] || 'info'
}

const getStatusText = (status: string) => {
  const statusMap: Record<string, string> = {
    'completed': '已完成',
    'pending': '处理中',
    'failed': '失败'
  }
  return statusMap[status] || status
}

const getTrendType = (trend: string) => {
  const trendMap: Record<string, string> = {
    'bullish': 'success',
    'bearish': 'danger',
    'neutral': 'warning'
  }
  return trendMap[trend] || 'info'
}

const getTrendText = (trend: string) => {
  const trendMap: Record<string, string> = {
    'bullish': '看涨',
    'bearish': '看跌',
    'neutral': '中性'
  }
  return trendMap[trend] || trend
}

const getPriorityType = (priority: string) => {
  const priorityMap: Record<string, string> = {
    'high': 'danger',
    'medium': 'warning',
    'low': 'info'
  }
  return priorityMap[priority] || 'info'
}

const getPriorityText = (priority: string) => {
  const priorityMap: Record<string, string> = {
    'high': '高',
    'medium': '中',
    'low': '低'
  }
  return priorityMap[priority] || priority
}

const getRiskType = (risk: string) => {
  const riskMap: Record<string, string> = {
    '高': 'danger',
    '中': 'warning',
    '低': 'success'
  }
  return riskMap[risk] || 'info'
}
</script>

<style scoped>
.daily-analysis-card {
  height: 500px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.analysis-content {
  height: 420px;
  overflow-y: auto;
}

.empty-analysis {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.analysis-report {
  padding: 10px 0;
}

.report-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 10px;
  border-bottom: 1px solid #ebeef5;
}

.report-date {
  display: flex;
  align-items: center;
  gap: 5px;
  font-weight: bold;
  color: #303133;
}

.analysis-section {
  margin-bottom: 20px;
}

.analysis-section h4 {
  display: flex;
  align-items: center;
  gap: 5px;
  margin: 0 0 10px 0;
  font-size: 14px;
  color: #409eff;
}

.insights-content {
  background-color: #f8f9fa;
  padding: 12px;
  border-radius: 4px;
  font-size: 13px;
  line-height: 1.6;
  color: #606266;
}

.summary-item,
.market-item,
.risk-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
}

.label {
  color: #909399;
}

.value {
  font-weight: bold;
  color: #303133;
}

.value.profit {
  color: #67c23a;
}

.value.loss {
  color: #f56c6c;
}

.market-info,
.risk-info {
  background-color: #fafafa;
  padding: 10px;
  border-radius: 4px;
}

.recommendations {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.recommendation-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px;
  background-color: #f8f9fa;
  border-radius: 4px;
}

.priority-tag {
  flex-shrink: 0;
}

.rec-text {
  font-size: 13px;
  line-height: 1.4;
  color: #606266;
}

.report-actions {
  text-align: center;
  padding-top: 15px;
  border-top: 1px solid #ebeef5;
}

.full-report {
  max-height: 600px;
}

.report-content {
  white-space: pre-wrap;
  font-size: 13px;
  line-height: 1.6;
  color: #606266;
  background-color: #fafafa;
  padding: 15px;
  border-radius: 4px;
  max-height: 400px;
  overflow-y: auto;
}

:deep(.el-tabs__content) {
  padding: 0;
}
</style>
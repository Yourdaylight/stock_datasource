<script setup lang="ts">
import { ref, computed } from 'vue'
import { useReportStore } from '@/stores/report'
import StockSearch from '@/components/common/StockSearch.vue'
import FinancialTable from '@/components/report/FinancialTable.vue'
import TrendChart from '@/components/report/TrendChart.vue'
import AIInsight from '@/components/report/AIInsight.vue'

const reportStore = useReportStore()
const selectedStock = ref('')
const activeTab = ref('overview')
const periods = ref(4)

// Computed properties
const hasData = computed(() => !!reportStore.financialData)
const stockName = computed(() => reportStore.financialData?.name || selectedStock.value)

// Handle stock selection
const handleStockSelect = async (code: string) => {
  selectedStock.value = code
  reportStore.clearData()
  
  try {
    await reportStore.fetchComprehensiveReport(code, periods.value)
  } catch (error) {
    console.error('Failed to load stock data:', error)
  }
}

// Handle periods change
const handlePeriodsChange = async (newPeriods: number) => {
  periods.value = newPeriods
  if (selectedStock.value) {
    try {
      await reportStore.fetchFinancial(selectedStock.value, newPeriods)
    } catch (error) {
      console.error('Failed to update periods:', error)
    }
  }
}

// Handle analysis type change
const handleAnalysisTypeChange = async (type: string) => {
  if (selectedStock.value) {
    try {
      await reportStore.fetchAnalysis(
        selectedStock.value, 
        type as 'comprehensive' | 'peer_comparison' | 'investment_insights',
        periods.value
      )
    } catch (error) {
      console.error('Failed to change analysis type:', error)
    }
  }
}

// Handle refresh analysis
const handleRefreshAnalysis = async () => {
  if (selectedStock.value) {
    try {
      await reportStore.fetchAnalysis(selectedStock.value, 'comprehensive', periods.value)
    } catch (error) {
      console.error('Failed to refresh analysis:', error)
    }
  }
}

// Handle refresh comparison
const handleRefreshComparison = async () => {
  if (selectedStock.value) {
    try {
      await reportStore.fetchComparison(selectedStock.value)
    } catch (error) {
      console.error('Failed to refresh comparison:', error)
    }
  }
}

// Period options - 用更通俗的表达
const periodOptions = [
  { value: 4, label: '近1年' },
  { value: 8, label: '近2年' },
  { value: 12, label: '近3年' },
  { value: 16, label: '近4年' }
]
</script>

<template>
  <div class="report-view">
    <t-card title="财报分析">
      <template #actions>
        <t-space>
          <t-select
            v-if="hasData"
            v-model="periods"
            :options="periodOptions"
            style="width: 100px"
            placeholder="选择时间范围"
            @change="handlePeriodsChange"
          />
          <StockSearch @select="handleStockSelect" />
        </t-space>
      </template>

      <!-- Empty State -->
      <div v-if="!selectedStock" class="empty-state">
        <t-icon name="chart-line" size="64px" style="color: #ddd" />
        <h3>专业财报分析</h3>
        <p>请选择股票开始全面的财务分析</p>
        <div class="features">
          <t-tag theme="primary" variant="light">📊 财务健康度评估</t-tag>
          <t-tag theme="success" variant="light">📈 多年趋势对比</t-tag>
          <t-tag theme="warning" variant="light">🤖 AI智能洞察</t-tag>
          <t-tag theme="danger" variant="light">📉 可视化图表</t-tag>
        </div>
        <div class="tip">
          <p style="margin-top: 16px; font-size: 14px; color: #666;">
            💡 支持分析近1-4年的财务数据，帮助您全面了解公司财务状况
          </p>
        </div>
      </div>

      <!-- Loading State -->
      <div v-else-if="reportStore.loading && !hasData" class="loading-state">
        <t-loading size="large" text="正在加载财务数据..." />
      </div>

      <!-- Main Content -->
      <div v-else-if="hasData" class="report-content">
        <!-- Stock Header -->
        <div class="stock-header">
          <div class="stock-info">
            <h2>{{ stockName }}</h2>
            <t-tag theme="primary">{{ selectedStock }}</t-tag>
          </div>
          <div class="health-score" v-if="reportStore.financialData?.summary?.health_score">
            <span class="score-label">财务健康度</span>
            <t-progress 
              :percentage="reportStore.financialData.summary.health_score" 
              :theme="reportStore.financialData.summary.health_score >= 70 ? 'success' : 
                     reportStore.financialData.summary.health_score >= 50 ? 'warning' : 'error'"
              size="large"
            />
          </div>
        </div>

        <!-- Tab Navigation -->
        <t-tabs v-model="activeTab" size="large">
          <t-tab-panel value="overview" label="综合概览">
            <t-row :gutter="16">
              <t-col :span="24">
                <FinancialTable 
                  :data="reportStore.financialData?.data || []"
                  :summary="reportStore.financialData?.summary"
                  :loading="reportStore.loading"
                />
              </t-col>
            </t-row>
          </t-tab-panel>
          
          <t-tab-panel value="charts" label="趋势图表">
            <TrendChart 
              :data="reportStore.financialData?.data || []"
              :comparison-data="reportStore.comparisonData"
              :loading="reportStore.loading || reportStore.comparisonLoading"
            />
            
            <div class="chart-actions">
              <t-button 
                theme="primary" 
                variant="outline" 
                :loading="reportStore.comparisonLoading"
                @click="handleRefreshComparison"
              >
                <template #icon><t-icon name="refresh" /></template>
                更新对比数据
              </t-button>
            </div>
          </t-tab-panel>
          
          <t-tab-panel value="analysis" label="AI分析">
            <AIInsight
              :analysis="reportStore.analysisData ?? undefined"
              :loading="reportStore.analysisLoading"
              @refresh="handleRefreshAnalysis"
              @change-type="handleAnalysisTypeChange"
            />
          </t-tab-panel>
        </t-tabs>
      </div>

      <!-- Error State -->
      <div v-else class="error-state">
        <t-icon name="close-circle" size="64px" style="color: #f5222d" />
        <h3>加载失败</h3>
        <p>无法获取 {{ selectedStock }} 的财务数据</p>
        <t-button theme="primary" @click="handleStockSelect(selectedStock)">
          重试
        </t-button>
      </div>
    </t-card>
  </div>
</template>

<style scoped>
.report-view {
  height: 100%;
  padding: 16px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 500px;
  color: #999;
  text-align: center;
}

.empty-state h3 {
  margin: 16px 0 8px;
  color: var(--td-text-color-primary);
}

.empty-state p {
  margin-bottom: 16px;
  color: var(--td-text-color-secondary);
}

.features {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: center;
}

.loading-state,
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 400px;
  text-align: center;
}

.error-state h3 {
  margin: 16px 0 8px;
  color: var(--td-error-color);
}

.error-state p {
  margin-bottom: 16px;
  color: var(--td-text-color-secondary);
}

.report-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.stock-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 0;
  border-bottom: 1px solid var(--td-border-level-1-color);
}

.stock-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stock-info h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}

.health-score {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 200px;
}

.score-label {
  font-size: 14px;
  color: var(--td-text-color-secondary);
  white-space: nowrap;
}

.chart-actions {
  display: flex;
  justify-content: center;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--td-border-level-1-color);
}

:deep(.t-tabs__content) {
  padding-top: 16px;
}

:deep(.t-card__body) {
  padding: 24px;
}
</style>

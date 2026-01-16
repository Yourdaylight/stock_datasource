<template>
  <div class="portfolio-view">
    <div class="portfolio-header">
      <h1>投资组合管理</h1>
      <div class="header-actions">
        <el-button type="primary" @click="showAddModal = true">
          <el-icon><Plus /></el-icon>
          添加持仓
        </el-button>
        <el-button @click="refreshData">
          <el-icon><Refresh /></el-icon>
          刷新数据
        </el-button>
      </div>
    </div>

    <!-- Portfolio Summary -->
    <div class="portfolio-summary">
      <el-row :gutter="20">
        <el-col :span="6">
          <el-card class="summary-card">
            <div class="summary-item">
              <div class="summary-label">总市值</div>
              <div class="summary-value">¥{{ formatNumber(summary.total_value) }}</div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card class="summary-card">
            <div class="summary-item">
              <div class="summary-label">总盈亏</div>
              <div class="summary-value" :class="summary.total_profit >= 0 ? 'profit' : 'loss'">
                ¥{{ formatNumber(summary.total_profit) }}
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card class="summary-card">
            <div class="summary-item">
              <div class="summary-label">收益率</div>
              <div class="summary-value" :class="summary.profit_rate >= 0 ? 'profit' : 'loss'">
                {{ summary.profit_rate?.toFixed(2) }}%
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card class="summary-card">
            <div class="summary-item">
              <div class="summary-label">持仓数量</div>
              <div class="summary-value">{{ summary.position_count }}只</div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- Main Content with Tabs -->
    <div class="main-content">
      <el-tabs v-model="activeTab" class="portfolio-tabs">
        <el-tab-pane label="持仓管理" name="positions">
          <el-row :gutter="20">
            <!-- Position List -->
            <el-col :span="16">
              <PositionList 
                :positions="positions" 
                :loading="loading"
                @edit="handleEditPosition"
                @delete="handleDeletePosition"
                @refresh="loadPositions"
              />
            </el-col>
            
            <!-- Charts and Analysis -->
            <el-col :span="8">
              <div class="right-panel">
                <!-- Profit Chart -->
                <ProfitChart 
                  :profit-history="profitHistory"
                  :loading="chartLoading"
                  class="chart-section"
                />
                
                <!-- Daily Analysis -->
                <DailyAnalysis 
                  :analysis-data="analysisData"
                  :loading="analysisLoading"
                  @trigger-analysis="triggerAnalysis"
                  class="analysis-section"
                />
              </div>
            </el-col>
          </el-row>
        </el-tab-pane>
        
        <el-tab-pane label="龙虎榜分析" name="toplist">
          <PortfolioTopListAnalysis />
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- Add Position Modal -->
    <AddPositionModal 
      v-model="showAddModal"
      @success="handleAddSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import PositionList from '@/components/PositionList.vue'
import ProfitChart from '@/components/ProfitChart.vue'
import DailyAnalysis from '@/components/DailyAnalysis.vue'
import AddPositionModal from '@/components/AddPositionModal.vue'
import PortfolioTopListAnalysis from '@/components/PortfolioTopListAnalysis.vue'
import { portfolioApi } from '@/api/portfolio'
import type { Position, PortfolioSummary } from '@/types/portfolio'

// Reactive data
const loading = ref(false)
const chartLoading = ref(false)
const analysisLoading = ref(false)
const showAddModal = ref(false)
const activeTab = ref('positions')

const positions = ref<Position[]>([])
const summary = reactive<PortfolioSummary>({
  total_value: 0,
  total_cost: 0,
  total_profit: 0,
  profit_rate: 0,
  daily_change: 0,
  daily_change_rate: 0,
  position_count: 0
})

const profitHistory = ref([])
const analysisData = ref(null)

// Methods
const loadPositions = async () => {
  try {
    loading.value = true
    const response = await portfolioApi.getPositions()
    positions.value = response.data
  } catch (error) {
    ElMessage.error('加载持仓数据失败')
    console.error('Load positions error:', error)
  } finally {
    loading.value = false
  }
}

const loadSummary = async () => {
  try {
    const response = await portfolioApi.getSummary()
    Object.assign(summary, response.data)
  } catch (error) {
    ElMessage.error('加载汇总数据失败')
    console.error('Load summary error:', error)
  }
}

const loadProfitHistory = async () => {
  try {
    chartLoading.value = true
    const response = await portfolioApi.getProfitHistory()
    profitHistory.value = response.data.data
  } catch (error) {
    ElMessage.error('加载盈亏历史失败')
    console.error('Load profit history error:', error)
  } finally {
    chartLoading.value = false
  }
}

const loadAnalysisData = async () => {
  try {
    analysisLoading.value = true
    const today = new Date().toISOString().split('T')[0]
    const response = await portfolioApi.getAnalysisReport(today)
    analysisData.value = response.data
  } catch (error) {
    // Analysis data might not exist for today, that's ok
    console.log('No analysis data for today')
  } finally {
    analysisLoading.value = false
  }
}

const refreshData = async () => {
  await Promise.all([
    loadPositions(),
    loadSummary(),
    loadProfitHistory(),
    loadAnalysisData()
  ])
  ElMessage.success('数据刷新成功')
}

const handleEditPosition = (position: Position) => {
  // TODO: Implement edit functionality
  ElMessage.info('编辑功能开发中')
}

const handleDeletePosition = async (position: Position) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除持仓 ${position.stock_name} 吗？`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    
    await portfolioApi.deletePosition(position.id)
    ElMessage.success('删除成功')
    await refreshData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
      console.error('Delete position error:', error)
    }
  }
}

const handleAddSuccess = () => {
  showAddModal.value = false
  refreshData()
  ElMessage.success('添加持仓成功')
}

const triggerAnalysis = async () => {
  try {
    analysisLoading.value = true
    await portfolioApi.triggerDailyAnalysis()
    ElMessage.success('分析任务已启动')
    
    // Reload analysis data after a delay
    setTimeout(loadAnalysisData, 3000)
  } catch (error) {
    ElMessage.error('启动分析失败')
    console.error('Trigger analysis error:', error)
  } finally {
    analysisLoading.value = false
  }
}

const formatNumber = (value: number): string => {
  if (!value) return '0.00'
  return value.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })
}

// Lifecycle
onMounted(() => {
  refreshData()
})
</script>

<style scoped>
.portfolio-view {
  padding: 20px;
}

.portfolio-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.portfolio-header h1 {
  margin: 0;
  color: #303133;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.portfolio-summary {
  margin-bottom: 20px;
}

.summary-card {
  text-align: center;
}

.summary-item {
  padding: 10px;
}

.summary-label {
  font-size: 14px;
  color: #909399;
  margin-bottom: 8px;
}

.summary-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}

.summary-value.profit {
  color: #67c23a;
}

.summary-value.loss {
  color: #f56c6c;
}

.main-content {
  margin-top: 20px;
}

.portfolio-tabs {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.portfolio-tabs :deep(.el-tabs__header) {
  margin-bottom: 20px;
}

.portfolio-tabs :deep(.el-tabs__nav-wrap) {
  padding: 0 20px;
}

.portfolio-tabs :deep(.el-tabs__content) {
  padding: 0;
}

.right-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.chart-section,
.analysis-section {
  flex: 1;
}
</style>
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import TopListTable from '@/components/TopListTable.vue'
import PortfolioTopListAnalysis from '@/components/PortfolioTopListAnalysis.vue'
import TopListAnalysis from '@/components/TopListAnalysis.vue'
import AnomalyAlerts from '@/components/AnomalyAlerts.vue'
import MarketStats from '@/components/MarketStats.vue'
import type { TopListItem } from '@/api/toplist'

// Local state
const activeTab = ref('toplist')
const showDetailModal = ref(false)
const showAnalysisModal = ref(false)
const selectedStock = ref<TopListItem | null>(null)

// Tab configuration
const tabs = [
  { value: 'toplist', label: '龙虎榜数据' },
  { value: 'portfolio', label: '投资组合分析' },
  { value: 'alerts', label: '异动预警' },
  { value: 'stats', label: '市场统计' }
]

// Methods
const handleViewDetail = (item: TopListItem) => {
  selectedStock.value = item
  showDetailModal.value = true
}

const handleViewAnalysis = (item: TopListItem) => {
  selectedStock.value = item
  showAnalysisModal.value = true
}

const closeDetailModal = () => {
  showDetailModal.value = false
  selectedStock.value = null
}

const closeAnalysisModal = () => {
  showAnalysisModal.value = false
  selectedStock.value = null
}

const formatDate = (dateStr?: string): string => {
  if (!dateStr) return '-'
  return dateStr.replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3')
}
</script>

<template>
  <div class="toplist-panel">
    <!-- Sub tabs -->
    <div class="panel-tabs">
      <t-radio-group v-model="activeTab" variant="default-filled">
        <t-radio-button v-for="tab in tabs" :key="tab.value" :value="tab.value">
          {{ tab.label }}
        </t-radio-button>
      </t-radio-group>
    </div>

    <!-- Tab content -->
    <div class="panel-content">
      <!-- 龙虎榜数据 -->
      <div v-if="activeTab === 'toplist'" class="tab-content">
        <TopListTable 
          @view-detail="handleViewDetail"
          @view-analysis="handleViewAnalysis"
        />
      </div>

      <!-- 投资组合分析 -->
      <div v-if="activeTab === 'portfolio'" class="tab-content">
        <PortfolioTopListAnalysis />
      </div>

      <!-- 异动预警 -->
      <div v-if="activeTab === 'alerts'" class="tab-content">
        <AnomalyAlerts />
      </div>

      <!-- 市场统计 -->
      <div v-if="activeTab === 'stats'" class="tab-content">
        <MarketStats />
      </div>
    </div>

    <!-- 股票详情弹窗 -->
    <t-dialog
      v-model:visible="showDetailModal"
      :header="(selectedStock?.name || selectedStock?.ts_code) + ' 龙虎榜详情'"
      width="1000px"
      :footer="false"
    >
      <div class="stock-basic-info" v-if="selectedStock">
        <t-row :gutter="16">
          <t-col :span="4">
            <div class="info-item">
              <span class="label">股票代码</span>
              <span class="value">{{ selectedStock.ts_code }}</span>
            </div>
          </t-col>
          <t-col :span="4">
            <div class="info-item">
              <span class="label">股票名称</span>
              <span class="value">{{ selectedStock.name || '-' }}</span>
            </div>
          </t-col>
          <t-col :span="4">
            <div class="info-item">
              <span class="label">交易日期</span>
              <span class="value">{{ formatDate(selectedStock.trade_date) }}</span>
            </div>
          </t-col>
          <t-col :span="4">
            <div class="info-item">
              <span class="label">收盘价</span>
              <span class="value">{{ selectedStock.close?.toFixed(2) || '-' }}</span>
            </div>
          </t-col>
          <t-col :span="4">
            <div class="info-item">
              <span class="label">涨跌幅</span>
              <span class="value" :class="{ 'text-up': (selectedStock.pct_chg || 0) > 0, 'text-down': (selectedStock.pct_chg || 0) < 0 }">
                {{ selectedStock.pct_chg?.toFixed(2) || '-' }}%
              </span>
            </div>
          </t-col>
          <t-col :span="4">
            <div class="info-item">
              <span class="label">上榜原因</span>
              <span class="value">{{ selectedStock.reason || '-' }}</span>
            </div>
          </t-col>
        </t-row>
      </div>
      
      <t-divider>历史龙虎榜记录</t-divider>
      
      <TopListTable 
        :ts-code="selectedStock?.ts_code"
        :show-filters="false"
        :show-pagination="false"
        mode="history"
      />
    </t-dialog>

    <!-- 分析弹窗 -->
    <t-dialog
      v-model:visible="showAnalysisModal"
      :header="(selectedStock?.name || selectedStock?.ts_code) + ' 深度分析'"
      width="1200px"
      :footer="false"
    >
      <TopListAnalysis 
        v-if="selectedStock" 
        :ts-code="selectedStock.ts_code" 
        :stock-name="selectedStock.name"
      />
    </t-dialog>
  </div>
</template>

<style scoped>
.toplist-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.panel-tabs {
  display: flex;
  justify-content: flex-start;
}

.panel-content {
  min-height: 500px;
}

.tab-content {
  background: #ffffff;
  border-radius: 8px;
  border: 1px solid #e8e8e8;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.stock-basic-info {
  background: var(--td-bg-color-component);
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-item .label {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.info-item .value {
  font-size: 14px;
  font-weight: 500;
  color: var(--td-text-color-primary);
}

.text-up {
  color: var(--td-error-color);
}

.text-down {
  color: var(--td-success-color);
}
</style>

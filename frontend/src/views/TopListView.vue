<template>
  <div class="top-list-view">
    <div class="page-header">
      <h1>龙虎榜分析</h1>
      <div class="header-tabs">
        <button 
          v-for="tab in tabs" 
          :key="tab.key"
          @click="activeTab = tab.key"
          :class="['tab-btn', { active: activeTab === tab.key }]"
        >
          {{ tab.label }}
        </button>
      </div>
    </div>

    <div class="page-content">
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
    <div v-if="showDetailModal" class="modal-overlay" @click="closeDetailModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>{{ selectedStock?.name || selectedStock?.ts_code }} 龙虎榜详情</h3>
          <button @click="closeDetailModal" class="close-btn">×</button>
        </div>
        <div class="modal-body">
          <div class="stock-basic-info" v-if="selectedStock">
            <div class="info-row">
              <span class="label">股票代码:</span>
              <span class="value">{{ selectedStock.ts_code }}</span>
            </div>
            <div class="info-row">
              <span class="label">股票名称:</span>
              <span class="value">{{ selectedStock.name || '-' }}</span>
            </div>
            <div class="info-row">
              <span class="label">交易日期:</span>
              <span class="value">{{ formatDate(selectedStock.trade_date) }}</span>
            </div>
            <div class="info-row">
              <span class="label">收盘价:</span>
              <span class="value">{{ selectedStock.close?.toFixed(2) || '-' }}</span>
            </div>
            <div class="info-row">
              <span class="label">涨跌幅:</span>
              <span class="value" :class="{ 'positive': (selectedStock.pct_chg || 0) > 0, 'negative': (selectedStock.pct_chg || 0) < 0 }">
                {{ selectedStock.pct_chg?.toFixed(2) || '-' }}%
              </span>
            </div>
            <div class="info-row">
              <span class="label">上榜原因:</span>
              <span class="value">{{ selectedStock.reason || '-' }}</span>
            </div>
          </div>
          
          <div class="stock-history">
            <h4>历史龙虎榜记录</h4>
            <TopListTable 
              :ts-code="selectedStock?.ts_code"
              :show-filters="false"
              :show-pagination="false"
              mode="history"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- 分析弹窗 -->
    <div v-if="showAnalysisModal" class="modal-overlay" @click="closeAnalysisModal">
      <div class="modal-content analysis-modal" @click.stop>
        <div class="modal-header">
          <h3>{{ selectedStock?.name || selectedStock?.ts_code }} 深度分析</h3>
          <button @click="closeAnalysisModal" class="close-btn">×</button>
        </div>
        <div class="modal-body">
          <TopListAnalysis 
            v-if="selectedStock" 
            :ts-code="selectedStock.ts_code" 
            :stock-name="selectedStock.name"
          />
        </div>
      </div>
    </div>
  </div>
</template>

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
  { key: 'toplist', label: '龙虎榜数据' },
  { key: 'portfolio', label: '投资组合分析' },
  { key: 'alerts', label: '异动预警' },
  { key: 'stats', label: '市场统计' }
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

// Initialize
onMounted(() => {
  // Page initialization logic if needed
})
</script>

<style scoped>
.top-list-view {
  min-height: 100vh;
  background: #f5f5f5;
  padding: 20px;
}

.page-header {
  background: white;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.page-header h1 {
  margin: 0 0 20px 0;
  color: #333;
  font-size: 24px;
}

.header-tabs {
  display: flex;
  gap: 4px;
}

.tab-btn {
  padding: 10px 20px;
  border: none;
  background: #f8f9fa;
  color: #666;
  border-radius: 6px 6px 0 0;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s ease;
}

.tab-btn:hover {
  background: #e9ecef;
  color: #333;
}

.tab-btn.active {
  background: #007bff;
  color: white;
}

.page-content {
  min-height: 600px;
}

.tab-content {
  background: white;
  border-radius: 0 8px 8px 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  overflow: hidden;
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
  max-width: 1000px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.analysis-modal {
  max-width: 1200px;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #e0e0e0;
  background: #f8f9fa;
}

.modal-header h3 {
  margin: 0;
  color: #333;
  font-size: 18px;
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
  border-radius: 50%;
}

.close-btn:hover {
  color: #333;
  background: #e9ecef;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.stock-basic-info {
  background: #f8f9fa;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 20px;
  border: 1px solid #e9ecef;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #e9ecef;
}

.info-row:last-child {
  border-bottom: none;
}

.info-row .label {
  font-weight: 500;
  color: #666;
  min-width: 80px;
}

.info-row .value {
  font-weight: 600;
  color: #333;
  text-align: right;
}

.stock-history h4 {
  margin: 0 0 15px 0;
  color: #333;
  font-size: 16px;
  border-left: 4px solid #007bff;
  padding-left: 12px;
}

/* Color classes */
.positive {
  color: #dc3545;
}

.negative {
  color: #28a745;
}

/* Responsive design */
@media (max-width: 768px) {
  .top-list-view {
    padding: 10px;
  }
  
  .page-header {
    padding: 15px;
  }
  
  .page-header h1 {
    font-size: 20px;
    margin-bottom: 15px;
  }
  
  .header-tabs {
    flex-wrap: wrap;
    gap: 8px;
  }
  
  .tab-btn {
    padding: 8px 16px;
    font-size: 13px;
  }
  
  .modal-content {
    width: 95%;
    max-height: 95vh;
  }
  
  .modal-header {
    padding: 15px;
  }
  
  .modal-body {
    padding: 15px;
  }
  
  .info-row {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }
  
  .info-row .value {
    text-align: left;
  }
}
</style>
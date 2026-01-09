<script setup lang="ts">
import { ref, onMounted, onActivated } from 'vue'
import { usePortfolioStore } from '@/stores/portfolio'
import { MessagePlugin } from 'tdesign-vue-next'

const portfolioStore = usePortfolioStore()
const showAddModal = ref(false)
const addForm = ref({
  ts_code: '',
  quantity: 100,
  cost_price: 0,
  buy_date: '',
  notes: ''
})

const positionColumns = [
  { colKey: 'ts_code', title: '代码', width: 100 },
  { colKey: 'stock_name', title: '名称', width: 100 },
  { colKey: 'quantity', title: '数量', width: 80 },
  { colKey: 'cost_price', title: '成本价', width: 100 },
  { colKey: 'current_price', title: '现价', width: 100 },
  { colKey: 'market_value', title: '市值', width: 120 },
  { colKey: 'profit_loss', title: '盈亏', width: 120 },
  { colKey: 'profit_rate', title: '收益率', width: 100 },
  { colKey: 'operation', title: '操作', width: 100 }
]

const formatMoney = (num?: number) => {
  if (num === undefined) return '-'
  return num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const handleAddPosition = async () => {
  try {
    await portfolioStore.addPosition(addForm.value)
    showAddModal.value = false
    addForm.value = { ts_code: '', quantity: 100, cost_price: 0, buy_date: '', notes: '' }
    MessagePlugin.success('添加成功')
  } catch (e) {
    // Error handled by request interceptor
  }
}

const handleDeletePosition = (id: string) => {
  portfolioStore.deletePosition(id)
}

const handleTriggerAnalysis = () => {
  portfolioStore.triggerDailyAnalysis()
}

const refreshData = () => {
  portfolioStore.fetchPositions()
  portfolioStore.fetchSummary()
  portfolioStore.fetchAnalysis()
}

onMounted(() => {
  refreshData()
})

// Refresh data when component is activated (useful with keep-alive)
onActivated(() => {
  refreshData()
})
</script>

<template>
  <div class="portfolio-view">
    <t-row :gutter="16" style="margin-bottom: 16px">
      <t-col :span="3">
        <t-card title="总市值" :bordered="false">
          <div class="stat-value">{{ formatMoney(portfolioStore.summary?.total_value) }}</div>
        </t-card>
      </t-col>
      <t-col :span="3">
        <t-card title="总成本" :bordered="false">
          <div class="stat-value">{{ formatMoney(portfolioStore.summary?.total_cost) }}</div>
        </t-card>
      </t-col>
      <t-col :span="3">
        <t-card title="总盈亏" :bordered="false">
          <div
            class="stat-value"
            :style="{ color: (portfolioStore.summary?.total_profit || 0) >= 0 ? '#e34d59' : '#00a870' }"
          >
            {{ formatMoney(portfolioStore.summary?.total_profit) }}
          </div>
        </t-card>
      </t-col>
      <t-col :span="3">
        <t-card title="收益率" :bordered="false">
          <div
            class="stat-value"
            :style="{ color: (portfolioStore.summary?.profit_rate || 0) >= 0 ? '#e34d59' : '#00a870' }"
          >
            {{ portfolioStore.summary?.profit_rate?.toFixed(2) }}%
          </div>
        </t-card>
      </t-col>
    </t-row>

    <t-row :gutter="16">
      <t-col :span="8">
        <t-card title="持仓列表">
          <template #actions>
            <t-button theme="primary" @click="showAddModal = true">
              <template #icon><t-icon name="add" /></template>
              添加持仓
            </t-button>
          </template>
          
          <t-table
            :data="portfolioStore.positions"
            :columns="positionColumns"
            :loading="portfolioStore.loading"
            row-key="id"
          >
            <template #profit_loss="{ row }">
              <span :style="{ color: (row.profit_loss || 0) >= 0 ? '#e34d59' : '#00a870' }">
                {{ formatMoney(row.profit_loss) }}
              </span>
            </template>
            <template #profit_rate="{ row }">
              <span :style="{ color: (row.profit_rate || 0) >= 0 ? '#e34d59' : '#00a870' }">
                {{ row.profit_rate?.toFixed(2) }}%
              </span>
            </template>
            <template #operation="{ row }">
              <t-popconfirm content="确定删除该持仓？" @confirm="handleDeletePosition(row.id)">
                <t-link theme="danger">删除</t-link>
              </t-popconfirm>
            </template>
          </t-table>
        </t-card>
      </t-col>

      <t-col :span="4">
        <t-card title="每日分析">
          <template #actions>
            <t-button variant="text" @click="handleTriggerAnalysis">
              <template #icon><t-icon name="refresh" /></template>
              刷新分析
            </t-button>
          </template>
          
          <div v-if="portfolioStore.analysis" class="analysis-content">
            <div class="analysis-date">{{ portfolioStore.analysis.analysis_date }}</div>
            <t-divider />
            <div class="analysis-summary">{{ portfolioStore.analysis.analysis_summary }}</div>
            
            <div v-if="portfolioStore.analysis.risk_alerts?.length" class="risk-alerts">
              <h4>风险提示</h4>
              <t-alert
                v-for="(alert, index) in portfolioStore.analysis.risk_alerts"
                :key="index"
                theme="warning"
                :message="alert"
                style="margin-bottom: 8px"
              />
            </div>
            
            <div v-if="portfolioStore.analysis.recommendations?.length" class="recommendations">
              <h4>操作建议</h4>
              <ul>
                <li v-for="(rec, index) in portfolioStore.analysis.recommendations" :key="index">
                  {{ rec }}
                </li>
              </ul>
            </div>
          </div>
          
          <t-empty v-else description="暂无分析数据" />
        </t-card>
      </t-col>
    </t-row>

    <t-dialog v-model:visible="showAddModal" header="添加持仓" @confirm="handleAddPosition">
      <t-form label-width="80px">
        <t-form-item label="股票代码">
          <t-input v-model="addForm.ts_code" placeholder="例如：000001.SZ" />
        </t-form-item>
        <t-form-item label="数量">
          <t-input-number v-model="addForm.quantity" :min="100" :step="100" />
        </t-form-item>
        <t-form-item label="成本价">
          <t-input-number v-model="addForm.cost_price" :min="0" :decimal-places="2" />
        </t-form-item>
        <t-form-item label="买入日期">
          <t-date-picker v-model="addForm.buy_date" />
        </t-form-item>
        <t-form-item label="备注">
          <t-textarea v-model="addForm.notes" />
        </t-form-item>
      </t-form>
    </t-dialog>
  </div>
</template>

<style scoped>
.portfolio-view {
  height: 100%;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
}

.analysis-content {
  font-size: 14px;
  line-height: 1.8;
}

.analysis-date {
  color: #999;
  font-size: 12px;
}

.analysis-summary {
  margin-bottom: 16px;
}

.risk-alerts, .recommendations {
  margin-top: 16px;
}

.risk-alerts h4, .recommendations h4 {
  font-size: 14px;
  margin-bottom: 8px;
}

.recommendations ul {
  padding-left: 20px;
}
</style>

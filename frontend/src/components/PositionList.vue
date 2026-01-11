<template>
  <el-card class="position-list-card">
    <template #header>
      <div class="card-header">
        <span>持仓列表</span>
        <el-button text @click="$emit('refresh')">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>
    </template>

    <el-table 
      :data="positions" 
      :loading="loading"
      stripe
      style="width: 100%"
      @sort-change="handleSortChange"
    >
      <el-table-column prop="ts_code" label="股票代码" width="120" />
      <el-table-column prop="stock_name" label="股票名称" width="150" />
      <el-table-column prop="quantity" label="持仓数量" width="100" align="right">
        <template #default="{ row }">
          {{ formatNumber(row.quantity, 0) }}
        </template>
      </el-table-column>
      <el-table-column prop="cost_price" label="成本价" width="100" align="right">
        <template #default="{ row }">
          ¥{{ formatNumber(row.cost_price) }}
        </template>
      </el-table-column>
      <el-table-column prop="current_price" label="现价" width="100" align="right">
        <template #default="{ row }">
          <span :class="getPriceChangeClass(row)">
            ¥{{ formatNumber(row.current_price) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="market_value" label="市值" width="120" align="right">
        <template #default="{ row }">
          ¥{{ formatNumber(row.market_value) }}
        </template>
      </el-table-column>
      <el-table-column prop="profit_loss" label="盈亏" width="120" align="right" sortable="custom">
        <template #default="{ row }">
          <span :class="row.profit_loss >= 0 ? 'profit' : 'loss'">
            ¥{{ formatNumber(row.profit_loss) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="profit_rate" label="收益率" width="100" align="right" sortable="custom">
        <template #default="{ row }">
          <span :class="row.profit_rate >= 0 ? 'profit' : 'loss'">
            {{ formatNumber(row.profit_rate) }}%
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="buy_date" label="买入日期" width="120">
        <template #default="{ row }">
          {{ formatDate(row.buy_date) }}
        </template>
      </el-table-column>
      <el-table-column prop="sector" label="行业" width="100" />
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="$emit('edit', row)">
            编辑
          </el-button>
          <el-button size="small" type="danger" @click="$emit('delete', row)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Empty state -->
    <div v-if="!loading && positions.length === 0" class="empty-state">
      <el-empty description="暂无持仓数据">
        <el-button type="primary" @click="$emit('add')">添加持仓</el-button>
      </el-empty>
    </div>

    <!-- Position details modal -->
    <el-dialog v-model="showDetailsModal" title="持仓详情" width="600px">
      <div v-if="selectedPosition" class="position-details">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="股票代码">
            {{ selectedPosition.ts_code }}
          </el-descriptions-item>
          <el-descriptions-item label="股票名称">
            {{ selectedPosition.stock_name }}
          </el-descriptions-item>
          <el-descriptions-item label="持仓数量">
            {{ formatNumber(selectedPosition.quantity, 0) }}股
          </el-descriptions-item>
          <el-descriptions-item label="成本价">
            ¥{{ formatNumber(selectedPosition.cost_price) }}
          </el-descriptions-item>
          <el-descriptions-item label="现价">
            ¥{{ formatNumber(selectedPosition.current_price) }}
          </el-descriptions-item>
          <el-descriptions-item label="市值">
            ¥{{ formatNumber(selectedPosition.market_value) }}
          </el-descriptions-item>
          <el-descriptions-item label="盈亏金额">
            <span :class="selectedPosition.profit_loss >= 0 ? 'profit' : 'loss'">
              ¥{{ formatNumber(selectedPosition.profit_loss) }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="收益率">
            <span :class="selectedPosition.profit_rate >= 0 ? 'profit' : 'loss'">
              {{ formatNumber(selectedPosition.profit_rate) }}%
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="买入日期">
            {{ formatDate(selectedPosition.buy_date) }}
          </el-descriptions-item>
          <el-descriptions-item label="持仓天数">
            {{ calculateHoldingDays(selectedPosition.buy_date) }}天
          </el-descriptions-item>
          <el-descriptions-item label="行业">
            {{ selectedPosition.sector || '未知' }}
          </el-descriptions-item>
          <el-descriptions-item label="备注" :span="2">
            {{ selectedPosition.notes || '无' }}
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import type { Position } from '@/types/portfolio'

interface Props {
  positions: Position[]
  loading?: boolean
}

interface Emits {
  (e: 'edit', position: Position): void
  (e: 'delete', position: Position): void
  (e: 'refresh'): void
  (e: 'add'): void
}

const props = withDefaults(defineProps<Props>(), {
  loading: false
})

const emit = defineEmits<Emits>()

// Reactive data
const showDetailsModal = ref(false)
const selectedPosition = ref<Position | null>(null)
const sortConfig = ref({ prop: '', order: '' })

// Computed
const sortedPositions = computed(() => {
  if (!sortConfig.value.prop) return props.positions
  
  const { prop, order } = sortConfig.value
  const positions = [...props.positions]
  
  return positions.sort((a, b) => {
    const aVal = a[prop as keyof Position] || 0
    const bVal = b[prop as keyof Position] || 0
    
    if (order === 'ascending') {
      return Number(aVal) - Number(bVal)
    } else {
      return Number(bVal) - Number(aVal)
    }
  })
})

// Methods
const handleSortChange = ({ prop, order }: { prop: string; order: string }) => {
  sortConfig.value = { prop, order }
}

const showPositionDetails = (position: Position) => {
  selectedPosition.value = position
  showDetailsModal.value = true
}

const getPriceChangeClass = (position: Position) => {
  if (!position.current_price || !position.cost_price) return ''
  
  const change = position.current_price - position.cost_price
  return change >= 0 ? 'profit' : 'loss'
}

const formatNumber = (value: number | null | undefined, decimals = 2): string => {
  if (value === null || value === undefined) return '0.00'
  return value.toLocaleString('zh-CN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  })
}

const formatDate = (dateString: string): string => {
  if (!dateString) return ''
  const date = new Date(dateString)
  return date.toLocaleDateString('zh-CN')
}

const calculateHoldingDays = (buyDate: string): number => {
  if (!buyDate) return 0
  const buy = new Date(buyDate)
  const now = new Date()
  const diffTime = Math.abs(now.getTime() - buy.getTime())
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24))
}
</script>

<style scoped>
.position-list-card {
  height: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.profit {
  color: #67c23a;
  font-weight: bold;
}

.loss {
  color: #f56c6c;
  font-weight: bold;
}

.empty-state {
  padding: 40px 0;
  text-align: center;
}

.position-details {
  padding: 20px 0;
}

:deep(.el-table) {
  font-size: 13px;
}

:deep(.el-table th) {
  background-color: #fafafa;
}

:deep(.el-table .cell) {
  padding: 0 8px;
}

.clickable-row {
  cursor: pointer;
}

.clickable-row:hover {
  background-color: #f5f7fa;
}
</style>
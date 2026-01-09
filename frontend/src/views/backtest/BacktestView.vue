<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useBacktestStore } from '@/stores/backtest'

const backtestStore = useBacktestStore()
const activeTab = ref('run')

const backtestForm = ref({
  strategy_id: '',
  ts_codes: [] as string[],
  start_date: '',
  end_date: '',
  initial_capital: 100000,
  params: {} as Record<string, any>
})

const dateRange = computed({
  get: () => [backtestForm.value.start_date, backtestForm.value.end_date],
  set: (val: string[]) => {
    backtestForm.value.start_date = val[0] || ''
    backtestForm.value.end_date = val[1] || ''
  }
})

const tsCodeInput = ref('')

const handleAddStock = () => {
  if (tsCodeInput.value && !backtestForm.value.ts_codes.includes(tsCodeInput.value)) {
    backtestForm.value.ts_codes.push(tsCodeInput.value)
    tsCodeInput.value = ''
  }
}

const handleRemoveStock = (code: string) => {
  const index = backtestForm.value.ts_codes.indexOf(code)
  if (index > -1) {
    backtestForm.value.ts_codes.splice(index, 1)
  }
}

const handleStrategyChange = (strategyId: string) => {
  const strategy = backtestStore.strategies.find(s => s.id === strategyId)
  if (strategy) {
    backtestForm.value.params = {}
    strategy.params.forEach(p => {
      backtestForm.value.params[p.name] = p.default
    })
  }
}

const handleRunBacktest = async () => {
  await backtestStore.runBacktest(backtestForm.value)
}

const tradeColumns = [
  { colKey: 'date', title: '日期', width: 100 },
  { colKey: 'direction', title: '方向', width: 80 },
  { colKey: 'price', title: '价格', width: 100 },
  { colKey: 'quantity', title: '数量', width: 80 },
  { colKey: 'amount', title: '金额', width: 120 },
  { colKey: 'signal_reason', title: '信号原因', width: 200 }
]

const resultColumns = [
  { colKey: 'strategy_name', title: '策略', width: 100 },
  { colKey: 'ts_codes', title: '标的', width: 150 },
  { colKey: 'total_return', title: '总收益率', width: 100 },
  { colKey: 'max_drawdown', title: '最大回撤', width: 100 },
  { colKey: 'sharpe_ratio', title: '夏普比率', width: 100 },
  { colKey: 'win_rate', title: '胜率', width: 80 },
  { colKey: 'trade_count', title: '交易次数', width: 80 }
]

onMounted(() => {
  backtestStore.fetchStrategies()
  backtestStore.fetchResults()
  
  // Set default dates
  const end = new Date()
  const start = new Date()
  start.setFullYear(start.getFullYear() - 1)
  backtestForm.value.start_date = start.toISOString().split('T')[0]
  backtestForm.value.end_date = end.toISOString().split('T')[0]
})
</script>

<template>
  <div class="backtest-view">
    <t-tabs v-model="activeTab">
      <t-tab-panel value="run" label="执行回测">
        <t-row :gutter="16">
          <t-col :span="4">
            <t-card title="回测配置">
              <t-form label-width="100px">
                <t-form-item label="选择策略">
                  <t-select
                    v-model="backtestForm.strategy_id"
                    placeholder="请选择策略"
                    @change="handleStrategyChange"
                  >
                    <t-option
                      v-for="strategy in backtestStore.strategies"
                      :key="strategy.id"
                      :value="strategy.id"
                      :label="strategy.name"
                    />
                  </t-select>
                </t-form-item>
                
                <t-form-item label="回测标的">
                  <div class="stock-input">
                    <t-input
                      v-model="tsCodeInput"
                      placeholder="输入股票代码"
                      @keyup.enter="handleAddStock"
                    />
                    <t-button @click="handleAddStock">添加</t-button>
                  </div>
                  <div class="stock-tags">
                    <t-tag
                      v-for="code in backtestForm.ts_codes"
                      :key="code"
                      closable
                      @close="handleRemoveStock(code)"
                    >
                      {{ code }}
                    </t-tag>
                  </div>
                </t-form-item>
                
                <t-form-item label="回测区间">
                  <t-date-range-picker
                    v-model="dateRange"
                    :enable-time-picker="false"
                  />
                </t-form-item>
                
                <t-form-item label="初始资金">
                  <t-input-number
                    v-model="backtestForm.initial_capital"
                    :min="10000"
                    :step="10000"
                  />
                </t-form-item>
                
                <t-divider>策略参数</t-divider>
                
                <template v-if="backtestForm.strategy_id">
                  <t-form-item
                    v-for="param in backtestStore.strategies.find(s => s.id === backtestForm.strategy_id)?.params"
                    :key="param.name"
                    :label="param.description"
                  >
                    <t-input-number
                      v-if="param.type === 'int' || param.type === 'float'"
                      v-model="backtestForm.params[param.name]"
                      :min="param.min_value"
                      :max="param.max_value"
                    />
                    <t-switch
                      v-else-if="param.type === 'bool'"
                      v-model="backtestForm.params[param.name]"
                    />
                  </t-form-item>
                </template>
                
                <t-form-item>
                  <t-button
                    theme="primary"
                    block
                    :loading="backtestStore.loading"
                    @click="handleRunBacktest"
                  >
                    开始回测
                  </t-button>
                </t-form-item>
              </t-form>
            </t-card>
          </t-col>
          
          <t-col :span="8">
            <t-card v-if="backtestStore.currentResult" title="回测结果">
              <t-row :gutter="16" style="margin-bottom: 16px">
                <t-col :span="3">
                  <t-statistic
                    title="总收益率"
                    :value="backtestStore.currentResult.total_return"
                    suffix="%"
                    :trend="backtestStore.currentResult.total_return >= 0 ? 'increase' : 'decrease'"
                  />
                </t-col>
                <t-col :span="3">
                  <t-statistic
                    title="年化收益"
                    :value="backtestStore.currentResult.annual_return"
                    suffix="%"
                  />
                </t-col>
                <t-col :span="3">
                  <t-statistic
                    title="最大回撤"
                    :value="backtestStore.currentResult.max_drawdown"
                    suffix="%"
                    trend="decrease"
                  />
                </t-col>
                <t-col :span="3">
                  <t-statistic
                    title="夏普比率"
                    :value="backtestStore.currentResult.sharpe_ratio"
                    :decimal-places="2"
                  />
                </t-col>
              </t-row>
              
              <t-row :gutter="16" style="margin-bottom: 16px">
                <t-col :span="3">
                  <t-statistic
                    title="胜率"
                    :value="backtestStore.currentResult.win_rate"
                    suffix="%"
                  />
                </t-col>
                <t-col :span="3">
                  <t-statistic
                    title="交易次数"
                    :value="backtestStore.currentResult.trade_count"
                  />
                </t-col>
                <t-col :span="3">
                  <t-statistic
                    title="初始资金"
                    :value="backtestStore.currentResult.initial_capital"
                    prefix="¥"
                  />
                </t-col>
                <t-col :span="3">
                  <t-statistic
                    title="最终资金"
                    :value="backtestStore.currentResult.final_capital"
                    prefix="¥"
                  />
                </t-col>
              </t-row>
              
              <t-divider>交易记录</t-divider>
              
              <t-table
                :data="backtestStore.currentResult.trades"
                :columns="tradeColumns"
                row-key="date"
                max-height="300"
              >
                <template #direction="{ row }">
                  <t-tag :theme="row.direction === 'buy' ? 'danger' : 'success'">
                    {{ row.direction === 'buy' ? '买入' : '卖出' }}
                  </t-tag>
                </template>
              </t-table>
            </t-card>
            
            <t-card v-else title="回测结果">
              <t-empty description="请配置参数并执行回测" />
            </t-card>
          </t-col>
        </t-row>
      </t-tab-panel>
      
      <t-tab-panel value="history" label="历史记录">
        <t-table
          :data="backtestStore.results"
          :columns="resultColumns"
          :loading="backtestStore.loading"
          row-key="task_id"
        >
          <template #ts_codes="{ row }">
            {{ row.ts_codes?.join(', ') }}
          </template>
          <template #total_return="{ row }">
            <span :style="{ color: row.total_return >= 0 ? '#e34d59' : '#00a870' }">
              {{ row.total_return?.toFixed(2) }}%
            </span>
          </template>
          <template #max_drawdown="{ row }">
            <span style="color: #00a870">{{ row.max_drawdown?.toFixed(2) }}%</span>
          </template>
        </t-table>
      </t-tab-panel>
    </t-tabs>
  </div>
</template>

<style scoped>
.backtest-view {
  height: 100%;
}

.stock-input {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.stock-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
</style>

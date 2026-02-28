<template>
  <div class="charts-demo">
    <h1>绩效图表组件演示</h1>
    
    <div class="demo-section">
      <h2>回撤曲线图</h2>
      <DrawdownChart 
        :drawdown-data="mockDrawdownData"
        :loading="false"
        height="400px"
      />
    </div>
    
    <div class="demo-section">
      <h2>每日盈亏图</h2>
      <DailyPnLChart 
        :daily-pn-l-data="mockDailyPnLData"
        :loading="false"
        height="400px"
        :show-cumulative="true"
      />
    </div>
    
    <div class="demo-section">
      <h2>收益分布图</h2>
      <ReturnDistributionChart 
        :return-data="mockReturnData"
        :loading="false"
        height="400px"
        :show-normal-curve="true"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import DrawdownChart from '@/components/charts/DrawdownChart.vue'
import DailyPnLChart from '@/components/charts/DailyPnLChart.vue'
import ReturnDistributionChart from '@/components/charts/ReturnDistributionChart.vue'

// 模拟回撤数据
const mockDrawdownData = ref([
  { date: '2024-01-01', drawdown: 0, equity: 100000 },
  { date: '2024-01-02', drawdown: -0.02, equity: 98000 },
  { date: '2024-01-03', drawdown: -0.05, equity: 95000 },
  { date: '2024-01-04', drawdown: -0.03, equity: 97000 },
  { date: '2024-01-05', drawdown: -0.08, equity: 92000 },
  { date: '2024-01-06', drawdown: -0.04, equity: 96000 },
  { date: '2024-01-07', drawdown: -0.01, equity: 99000 },
  { date: '2024-01-08', drawdown: 0, equity: 102000 },
  { date: '2024-01-09', drawdown: -0.02, equity: 100000 },
  { date: '2024-01-10', drawdown: 0, equity: 105000 }
])

// 模拟每日盈亏数据
const mockDailyPnLData = ref([
  { date: '2024-01-01', pnl: 0, pnlPercent: 0, cumulativePnL: 0 },
  { date: '2024-01-02', pnl: -2000, pnlPercent: -2.0, cumulativePnL: -2.0 },
  { date: '2024-01-03', pnl: -3000, pnlPercent: -3.0, cumulativePnL: -5.0 },
  { date: '2024-01-04', pnl: 2000, pnlPercent: 2.1, cumulativePnL: -3.0 },
  { date: '2024-01-05', pnl: -5000, pnlPercent: -5.2, cumulativePnL: -8.0 },
  { date: '2024-01-06', pnl: 4000, pnlPercent: 4.3, cumulativePnL: -4.0 },
  { date: '2024-01-07', pnl: 3000, pnlPercent: 3.1, cumulativePnL: -1.0 },
  { date: '2024-01-08', pnl: 3000, pnlPercent: 3.0, cumulativePnL: 2.0 },
  { date: '2024-01-09', pnl: -2000, pnlPercent: -2.0, cumulativePnL: 0 },
  { date: '2024-01-10', pnl: 5000, pnlPercent: 5.0, cumulativePnL: 5.0 }
])

// 模拟收益分布数据
const mockReturnData = ref([
  -0.08, -0.06, -0.04, -0.03, -0.02, -0.01, 0, 0.01, 0.02, 0.03,
  0.04, 0.05, -0.05, -0.02, 0.01, 0.03, -0.01, 0.02, -0.03, 0.04,
  0.01, -0.02, 0.03, -0.01, 0.02, 0.05, -0.04, 0.01, 0.02, -0.01,
  0.03, -0.02, 0.01, 0.04, -0.03, 0.02, 0.01, -0.01, 0.03, -0.02,
  0.02, 0.01, -0.01, 0.03, -0.02, 0.04, -0.01, 0.02, 0.01, -0.03
])
</script>

<style scoped>
.charts-demo {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.charts-demo h1 {
  text-align: center;
  margin-bottom: 32px;
  color: #262626;
}

.demo-section {
  margin-bottom: 48px;
}

.demo-section h2 {
  margin-bottom: 24px;
  color: #595959;
  font-size: 18px;
  font-weight: 600;
}

.demo-section:last-child {
  margin-bottom: 0;
}
</style>
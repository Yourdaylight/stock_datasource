<template>
  <div class="backtest-results">
    <!-- 结果概览 -->
    <div class="results-overview">
      <div class="overview-cards">
        <div class="metric-card">
          <div
            class="metric-value"
            :class="getReturnClass(result.performance_metrics.total_return)"
            :style="{ color: getReturnColor(result.performance_metrics.total_return) }"
          >
            {{ formatPercent(result.performance_metrics.total_return) }}
          </div>
          <div class="metric-label">总收益率</div>
        </div>
        
        <div class="metric-card">
          <div class="metric-value" :class="getReturnClass(result.performance_metrics.annualized_return)">
            {{ formatPercent(result.performance_metrics.annualized_return) }}
          </div>
          <div class="metric-label">年化收益率</div>
        </div>
        
        <div class="metric-card">
          <div class="metric-value negative">
            {{ formatPercent(result.performance_metrics.max_drawdown) }}
          </div>
          <div class="metric-label">最大回撤</div>
        </div>
        
        <div class="metric-card">
          <div class="metric-value" :class="getSharpeClass(result.performance_metrics.sharpe_ratio)">
            {{ formatNumber(result.performance_metrics.sharpe_ratio, 2) }}
          </div>
          <div class="metric-label">夏普比率</div>
        </div>
        
        <div class="metric-card">
          <div class="metric-value">
            {{ formatPercent(result.performance_metrics.win_rate) }}
          </div>
          <div class="metric-label">胜率</div>
        </div>
        
        <div class="metric-card">
          <div class="metric-value">
            {{ result.performance_metrics.total_trades }}
          </div>
          <div class="metric-label">交易次数</div>
        </div>
      </div>
    </div>

    <!-- 详细结果标签页 -->
    <t-tabs v-model="activeTab" class="results-tabs">
      <!-- 绩效图表 -->
      <t-tab-panel label="绩效图表" value="charts">
        <div class="charts-container">
          <!-- 权益曲线图 -->
          <div class="chart-section">
            <ReturnCurveChart 
              :data="equityChartData"
              :benchmark="benchmarkData"
            />
          </div>
          
          <!-- 回撤曲线图 -->
          <div class="chart-section">
            <DrawdownChart 
              :drawdown-data="drawdownChartData"
              :loading="false"
              height="350px"
            />
          </div>
          
          <!-- 每日盈亏图 -->
          <div class="chart-section">
            <DailyPnLChart 
              :daily-pn-l-data="dailyPnLChartData"
              :loading="false"
              height="350px"
              :show-cumulative="true"
            />
          </div>
          
          <!-- 收益分布图 -->
          <div class="chart-section">
            <ReturnDistributionChart 
              :return-data="returnDistributionData"
              :loading="false"
              height="350px"
              :show-normal-curve="true"
            />
          </div>
        </div>
      </t-tab-panel>

      <!-- 绩效指标 -->
      <t-tab-panel label="绩效指标" value="metrics">
        <div class="metrics-container">
          <div class="metrics-grid">
            <!-- 收益指标 -->
            <div class="metrics-section">
              <h4>收益指标</h4>
              <t-descriptions :column="1" bordered>
                <t-descriptions-item label="总收益率">
                  <span
                    :class="getReturnClass(result.performance_metrics.total_return)"
                    :style="{ color: getReturnColor(result.performance_metrics.total_return) }"
                  >
                    {{ formatPercent(result.performance_metrics.total_return) }}
                  </span>
                </t-descriptions-item>
                <t-descriptions-item label="年化收益率">
                  <span :class="getReturnClass(result.performance_metrics.annualized_return)">
                    {{ formatPercent(result.performance_metrics.annualized_return) }}
                  </span>
                </t-descriptions-item>
                <t-descriptions-item label="超额收益率">
                  <span
                    :class="getReturnClass(result.performance_metrics.excess_return)"
                    :style="{ color: getReturnColor(result.performance_metrics.excess_return) }"
                  >
                    {{ formatPercent(result.performance_metrics.excess_return) }}
                  </span>
                </t-descriptions-item>
                <t-descriptions-item label="阿尔法系数">
                  {{ formatNumber(result.performance_metrics.alpha, 4) }}
                </t-descriptions-item>
                <t-descriptions-item label="贝塔系数">
                  {{ formatNumber(result.performance_metrics.beta, 2) }}
                </t-descriptions-item>
              </t-descriptions>
            </div>

            <!-- 风险指标 -->
            <div class="metrics-section">
              <h4>风险指标</h4>
              <t-descriptions :column="1" bordered>
                <t-descriptions-item label="波动率">
                  {{ formatPercent(result.performance_metrics.volatility) }}
                </t-descriptions-item>
                <t-descriptions-item label="最大回撤">
                  <span class="drawdown">
                    {{ formatPercent(result.performance_metrics.max_drawdown) }}
                  </span>
                </t-descriptions-item>
                <t-descriptions-item label="回撤持续期">
                  {{ result.performance_metrics.max_drawdown_duration }} 天
                </t-descriptions-item>
                <t-descriptions-item label="VaR (95%)">
                  {{ formatPercent(result.risk_metrics.var_95) }}
                </t-descriptions-item>
                <t-descriptions-item label="CVaR (95%)">
                  {{ formatPercent(result.risk_metrics.cvar_95) }}
                </t-descriptions-item>
              </t-descriptions>
            </div>

            <!-- 风险调整收益 -->
            <div class="metrics-section">
              <h4>风险调整收益</h4>
              <t-descriptions :column="1" bordered>
                <t-descriptions-item label="夏普比率">
                  <span :class="getSharpeClass(result.performance_metrics.sharpe_ratio)">
                    {{ formatNumber(result.performance_metrics.sharpe_ratio, 2) }}
                  </span>
                </t-descriptions-item>
                <t-descriptions-item label="索提诺比率">
                  <span :class="getSharpeClass(result.performance_metrics.sortino_ratio)">
                    {{ formatNumber(result.performance_metrics.sortino_ratio, 2) }}
                  </span>
                </t-descriptions-item>
                <t-descriptions-item label="卡玛比率">
                  <span :class="getSharpeClass(result.performance_metrics.calmar_ratio)">
                    {{ formatNumber(result.performance_metrics.calmar_ratio, 2) }}
                  </span>
                </t-descriptions-item>
                <t-descriptions-item label="信息比率">
                  {{ formatNumber(result.performance_metrics.information_ratio, 2) }}
                </t-descriptions-item>
              </t-descriptions>
            </div>

            <!-- 交易统计 -->
            <div class="metrics-section">
              <h4>交易统计</h4>
              <t-descriptions :column="1" bordered>
                <t-descriptions-item label="总交易次数">
                  {{ result.performance_metrics.total_trades }}
                </t-descriptions-item>
                <t-descriptions-item label="盈利交易">
                  {{ result.performance_metrics.winning_trades }}
                </t-descriptions-item>
                <t-descriptions-item label="亏损交易">
                  {{ result.performance_metrics.losing_trades }}
                </t-descriptions-item>
                <t-descriptions-item label="胜率">
                  {{ formatPercent(result.performance_metrics.win_rate) }}
                </t-descriptions-item>
                <t-descriptions-item label="平均盈利">
                  {{ formatCurrency(result.performance_metrics.avg_win) }}
                </t-descriptions-item>
                <t-descriptions-item label="平均亏损">
                  {{ formatCurrency(result.performance_metrics.avg_loss) }}
                </t-descriptions-item>
                <t-descriptions-item label="盈利因子">
                  {{ formatNumber(result.performance_metrics.profit_factor, 2) }}
                </t-descriptions-item>
              </t-descriptions>
            </div>
          </div>
        </div>
      </t-tab-panel>

      <!-- 交易记录 -->
      <t-tab-panel label="交易记录" value="trades">
        <div class="trades-container">
          <t-table 
            :data="paginatedTrades" 
            :columns="tradeColumns"
            size="small"
            stripe
            max-height="400"
          />
          
          <div class="pagination-container">
            <t-pagination
              v-model="currentPage"
              :page-size="pageSize"
              :total="result.trades?.length || 0"
              show-total
              show-previous-and-next-btn
              size="small"
            />
          </div>
        </div>
      </t-tab-panel>

      <!-- AI洞察 -->
      <t-tab-panel 
        v-if="result.ai_insights" 
        label="AI洞察" 
        value="insights"
      >
        <div class="insights-container">
          <div class="insight-section">
            <h4>绩效摘要</h4>
            <div class="insight-content">
              {{ result.ai_insights.summary }}
            </div>
          </div>
          
          <div class="insight-section">
            <h4>风险分析</h4>
            <div class="insight-content">
              {{ result.ai_insights.risk_analysis }}
            </div>
          </div>
          
          <div class="insight-section">
            <h4>改进建议</h4>
            <ul class="recommendations-list">
              <li 
                v-for="(recommendation, index) in result.ai_insights.recommendations" 
                :key="index"
              >
                {{ recommendation }}
              </li>
            </ul>
          </div>
        </div>
      </t-tab-panel>
    </t-tabs>

    <!-- 导出按钮 -->
    <div class="export-actions">
      <t-button @click="exportReport">
        导出报告
      </t-button>
      <t-button @click="exportData">
        导出数据
      </t-button>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, nextTick, h } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import ReturnCurveChart from '@/views/arena/components/ReturnCurveChart.vue'
import DrawdownChart from '@/components/charts/DrawdownChart.vue'
import DailyPnLChart from '@/components/charts/DailyPnLChart.vue'
import ReturnDistributionChart from '@/components/charts/ReturnDistributionChart.vue'

export default {
  name: 'BacktestResults',
  components: {
    ReturnCurveChart,
    DrawdownChart,
    DailyPnLChart,
    ReturnDistributionChart
  },
  props: {
    result: {
      type: Object,
      required: true
    }
  },
  setup(props) {
    // 响应式数据
    const activeTab = ref('charts')
    const currentPage = ref(1)
    const pageSize = ref(20)
    
    // 图表引用 - 已移除，使用新的Vue组件
    
    // 图表实例 - 已移除，使用新的Vue组件

    // 计算属性
    const paginatedTrades = computed(() => {
      const trades = props.result.trades || []
      const start = (currentPage.value - 1) * pageSize.value
      const end = start + pageSize.value
      return trades.slice(start, end)
    })

    const normalizeCurveToPercent = (values) => {
      if (!values.length) return []
      const numericValues = values.map(value => Number(value))
      const maxValue = Math.max(...numericValues)
      const minValue = Math.min(...numericValues)

      // 认为是资金曲线（金额）时转为累计收益率百分比
      if (maxValue > 10 && minValue > 0) {
        const base = numericValues[0] || 1
        return numericValues.map(value => ((value / base) - 1) * 100)
      }

      // 默认认为已经是百分比
      return numericValues
    }

    // 权益曲线数据
    const equityChartData = computed(() => {
      if (!props.result.equity_curve) return []
      
      const dates = Object.keys(props.result.equity_curve)
      const values = Object.values(props.result.equity_curve)
      const returns = normalizeCurveToPercent(values)
      
      return [{
        name: '策略收益',
        dates: dates,
        returns: returns
      }]
    })

    // 基准数据（如果有的话）
    const benchmarkData = computed(() => {
      if (!props.result.benchmark_curve) return null
      
      const dates = Object.keys(props.result.benchmark_curve)
      const values = Object.values(props.result.benchmark_curve)
      const returns = normalizeCurveToPercent(values)
      
      return {
        name: '基准收益',
        dates: dates,
        returns: returns
      }
    })

    // 回撤曲线数据
    const drawdownChartData = computed(() => {
      if (!props.result.drawdown_series || !props.result.equity_curve) return []
      
      const dates = Object.keys(props.result.drawdown_series)
      const drawdowns = Object.values(props.result.drawdown_series)
      const equities = Object.values(props.result.equity_curve)
      
      return dates.map((date, index) => ({
        date: date,
        drawdown: drawdowns[index] || 0,
        equity: equities[index] || 0
      }))
    })

    // 每日盈亏数据
    const dailyPnLChartData = computed(() => {
      if (!props.result.daily_returns) return []
      
      const dates = Object.keys(props.result.daily_returns)
      const returns = Object.values(props.result.daily_returns)
      
      let cumulativeFactor = 1
      const initialCapital = props.result.initial_capital || 100000
      
      return dates.map((date, index) => {
        const dailyReturn = Number(returns[index] || 0)
        cumulativeFactor *= (1 + dailyReturn)
        const cumulativePnLPercent = (cumulativeFactor - 1) * 100
        const dailyReturnPercent = dailyReturn * 100
        
        return {
          date: date,
          pnl: dailyReturn * initialCapital,
          pnlPercent: dailyReturnPercent,
          cumulativePnL: cumulativePnLPercent
        }
      })
    })

    // 收益分布数据
    const returnDistributionData = computed(() => {
      if (!props.result.daily_returns) return []
      
      return Object.values(props.result.daily_returns)
        .filter(ret => ret !== null && ret !== undefined)
        .map(ret => Number(ret) * 100)
    })

    // TDesign 表格列配置
    const tradeColumns = [
      {
        colKey: 'timestamp',
        title: '时间',
        width: 120,
        cell: (h, { row }) => formatDateTime(row.timestamp)
      },
      {
        colKey: 'symbol',
        title: '股票',
        width: 100
      },
      {
        colKey: 'trade_type',
        title: '方向',
        width: 80,
        cell: (h, { row }) => h('t-tag', {
          theme: row.trade_type === 'buy' ? 'success' : 'danger',
          size: 'small'
        }, row.trade_type === 'buy' ? '买入' : '卖出')
      },
      {
        colKey: 'quantity',
        title: '数量',
        width: 100
      },
      {
        colKey: 'price',
        title: '价格',
        width: 100,
        cell: (h, { row }) => formatCurrency(row.price)
      },
      {
        colKey: 'trade_value',
        title: '金额',
        width: 120,
        cell: (h, { row }) => formatCurrency(row.quantity * row.price)
      },
      {
        colKey: 'commission',
        title: '手续费',
        width: 100,
        cell: (h, { row }) => formatCurrency(row.commission)
      },
      {
        colKey: 'signal_reason',
        title: '信号原因',
        minWidth: 200
      }
    ]

    // 方法
    const formatPercent = (value) => {
      if (value === null || value === undefined) return '-'
      return (value * 100).toFixed(2) + '%'
    }

    const formatNumber = (value, decimals = 2) => {
      if (value === null || value === undefined) return '-'
      return Number(value).toFixed(decimals)
    }

    const formatCurrency = (value) => {
      if (value === null || value === undefined) return '-'
      return '¥' + Number(value).toLocaleString('zh-CN', { minimumFractionDigits: 2 })
    }

    const formatDateTime = (dateStr) => {
      return new Date(dateStr).toLocaleString('zh-CN')
    }

    const getReturnClass = (value) => {
      const numericValue = Number(value)
      if (Number.isNaN(numericValue)) return ''
      if (numericValue > 0) return 'positive'
      if (numericValue < 0) return 'negative'
      return ''
    }

    const getReturnColor = (value) => {
      const numericValue = Number(value)
      if (Number.isNaN(numericValue)) return undefined
      if (numericValue > 0) return '#ff4d4f'
      if (numericValue < 0) return '#52c41a'
      return undefined
    }

    const getSharpeClass = (value) => {
      if (value > 1) return 'excellent'
      if (value > 0.5) return 'good'
      if (value > 0) return 'fair'
      return 'poor'
    }

    const exportReport = () => {
      // 导出PDF报告的逻辑
      MessagePlugin.info('报告导出功能开发中...')
    }

    const exportData = () => {
      // 导出Excel数据的逻辑
      MessagePlugin.info('数据导出功能开发中...')
    }

    return {
      // 数据
      activeTab,
      currentPage,
      pageSize,
      paginatedTrades,
      tradeColumns,
      
      // 图表数据
      equityChartData,
      benchmarkData,
      drawdownChartData,
      dailyPnLChartData,
      returnDistributionData,

      // 方法
      formatPercent,
      formatNumber,
      formatCurrency,
      formatDateTime,
      getReturnClass,
      getReturnColor,
      getSharpeClass,
      exportReport,
      exportData
    }
  }
}
</script>

<style scoped>
.backtest-results {
  padding: 16px 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.results-overview {
  margin-bottom: 24px;
  flex: 0 0 auto;
}

.overview-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 16px;
}

.metric-card {
  background: white;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 16px;
  text-align: center;
}

.metric-value {
  font-size: 24px;
  font-weight: bold;
  margin-bottom: 8px;
}

.metric-value.positive { color: #ff4d4f; }
.metric-value.negative { color: #52c41a; }
.metric-value.excellent { color: #ff4d4f; }
.metric-value.good { color: #e6a23c; }
.metric-value.fair { color: #909399; }
.metric-value.poor { color: #52c41a; }

.metric-label {
  font-size: 12px;
  color: #606266;
}

.results-tabs {
  background: white;
  border-radius: 4px;
  padding: 16px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.charts-container {
  display: flex;
  flex-direction: column;
  gap: 32px;
  padding: 16px 0;
}

.chart-section {
  width: 100%;
  margin-bottom: 24px;
}

.chart-section:last-child {
  margin-bottom: 0;
}

.metrics-container {
  max-height: 500px;
  overflow-y: auto;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 24px;
}

.metrics-section h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 500;
}

.trades-container {
  max-height: 500px;
  overflow-y: auto;
}

.pagination-container {
  margin-top: 16px;
  text-align: center;
}

.insights-container {
  max-height: 500px;
  overflow-y: auto;
}

.insight-section {
  margin-bottom: 24px;
}

.insight-section h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 500;
}

.insight-content {
  background: #f8f9fa;
  padding: 16px;
  border-radius: 4px;
  line-height: 1.6;
}

.recommendations-list {
  margin: 0;
  padding-left: 20px;
}

.recommendations-list li {
  margin-bottom: 8px;
  line-height: 1.6;
}

.export-actions {
  margin-top: 24px;
  text-align: right;
}

.export-actions .t-button {
  margin-left: 8px;
}

.positive { color: #ff4d4f; }
.negative { color: #52c41a; }
.drawdown { color: #ff4d4f; }
</style>
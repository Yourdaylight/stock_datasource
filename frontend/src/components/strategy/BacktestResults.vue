<template>
  <div class="backtest-results">
    <!-- 结果概览 -->
    <div class="results-overview">
      <div class="overview-cards">
        <div class="metric-card">
          <div class="metric-value" :class="getReturnClass(result.performance_metrics.total_return)">
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
            <h4>权益曲线</h4>
            <div ref="equityChartRef" class="chart" style="height: 300px;"></div>
          </div>
          
          <!-- 回撤图 -->
          <div class="chart-section">
            <h4>回撤分析</h4>
            <div ref="drawdownChartRef" class="chart" style="height: 200px;"></div>
          </div>
          
          <!-- 收益分布 -->
          <div class="chart-section">
            <h4>收益分布</h4>
            <div ref="returnsChartRef" class="chart" style="height: 250px;"></div>
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
                  <span :class="getReturnClass(result.performance_metrics.total_return)">
                    {{ formatPercent(result.performance_metrics.total_return) }}
                  </span>
                </t-descriptions-item>
                <t-descriptions-item label="年化收益率">
                  <span :class="getReturnClass(result.performance_metrics.annualized_return)">
                    {{ formatPercent(result.performance_metrics.annualized_return) }}
                  </span>
                </t-descriptions-item>
                <t-descriptions-item label="超额收益率">
                  <span :class="getReturnClass(result.performance_metrics.excess_return)">
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
                  <span class="negative">
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
import * as echarts from 'echarts'

export default {
  name: 'BacktestResults',
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
    
    // 图表引用
    const equityChartRef = ref(null)
    const drawdownChartRef = ref(null)
    const returnsChartRef = ref(null)
    
    // 图表实例
    let equityChart = null
    let drawdownChart = null
    let returnsChart = null

    // 计算属性
    const paginatedTrades = computed(() => {
      const trades = props.result.trades || []
      const start = (currentPage.value - 1) * pageSize.value
      const end = start + pageSize.value
      return trades.slice(start, end)
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
      if (value > 0) return 'positive'
      if (value < 0) return 'negative'
      return ''
    }

    const getSharpeClass = (value) => {
      if (value > 1) return 'excellent'
      if (value > 0.5) return 'good'
      if (value > 0) return 'fair'
      return 'poor'
    }

    const initCharts = async () => {
      await nextTick()
      
      // 权益曲线图
      if (equityChartRef.value) {
        equityChart = echarts.init(equityChartRef.value)
        updateEquityChart()
      }
      
      // 回撤图
      if (drawdownChartRef.value) {
        drawdownChart = echarts.init(drawdownChartRef.value)
        updateDrawdownChart()
      }
      
      // 收益分布图
      if (returnsChartRef.value) {
        returnsChart = echarts.init(returnsChartRef.value)
        updateReturnsChart()
      }
    }

    const updateEquityChart = () => {
      if (!equityChart || !props.result.equity_curve) return

      const dates = Object.keys(props.result.equity_curve)
      const values = Object.values(props.result.equity_curve)

      const option = {
        title: {
          text: '权益曲线',
          left: 'center',
          textStyle: { fontSize: 14 }
        },
        tooltip: {
          trigger: 'axis',
          formatter: (params) => {
            const point = params[0]
            return `${point.name}<br/>组合价值: ${formatCurrency(point.value)}`
          }
        },
        xAxis: {
          type: 'category',
          data: dates,
          axisLabel: { fontSize: 10 }
        },
        yAxis: {
          type: 'value',
          axisLabel: {
            fontSize: 10,
            formatter: (value) => formatCurrency(value)
          }
        },
        series: [{
          name: '组合价值',
          type: 'line',
          data: values,
          smooth: true,
          lineStyle: { color: '#409EFF' },
          areaStyle: { 
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(64, 158, 255, 0.3)' },
              { offset: 1, color: 'rgba(64, 158, 255, 0.1)' }
            ])
          }
        }],
        grid: {
          left: '10%',
          right: '10%',
          bottom: '15%',
          top: '15%'
        }
      }

      equityChart.setOption(option)
    }

    const updateDrawdownChart = () => {
      if (!drawdownChart || !props.result.drawdown_series) return

      const dates = Object.keys(props.result.drawdown_series)
      const values = Object.values(props.result.drawdown_series).map(v => v * 100)

      const option = {
        title: {
          text: '回撤分析',
          left: 'center',
          textStyle: { fontSize: 14 }
        },
        tooltip: {
          trigger: 'axis',
          formatter: (params) => {
            const point = params[0]
            return `${point.name}<br/>回撤: ${point.value.toFixed(2)}%`
          }
        },
        xAxis: {
          type: 'category',
          data: dates,
          axisLabel: { fontSize: 10 }
        },
        yAxis: {
          type: 'value',
          axisLabel: {
            fontSize: 10,
            formatter: '{value}%'
          }
        },
        series: [{
          name: '回撤',
          type: 'line',
          data: values,
          smooth: true,
          lineStyle: { color: '#F56C6C' },
          areaStyle: { 
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(245, 108, 108, 0.3)' },
              { offset: 1, color: 'rgba(245, 108, 108, 0.1)' }
            ])
          }
        }],
        grid: {
          left: '10%',
          right: '10%',
          bottom: '15%',
          top: '15%'
        }
      }

      drawdownChart.setOption(option)
    }

    const updateReturnsChart = () => {
      if (!returnsChart || !props.result.returns_series) return

      const returns = Object.values(props.result.returns_series).map(v => v * 100)
      
      // 计算收益分布
      const bins = 20
      const min = Math.min(...returns)
      const max = Math.max(...returns)
      const binWidth = (max - min) / bins
      
      const histogram = new Array(bins).fill(0)
      const binLabels = []
      
      for (let i = 0; i < bins; i++) {
        const binStart = min + i * binWidth
        const binEnd = min + (i + 1) * binWidth
        binLabels.push(`${binStart.toFixed(1)}%`)
        
        returns.forEach(ret => {
          if (ret >= binStart && ret < binEnd) {
            histogram[i]++
          }
        })
      }

      const option = {
        title: {
          text: '收益分布',
          left: 'center',
          textStyle: { fontSize: 14 }
        },
        tooltip: {
          trigger: 'axis',
          formatter: (params) => {
            const point = params[0]
            return `收益区间: ${point.name}<br/>频次: ${point.value}`
          }
        },
        xAxis: {
          type: 'category',
          data: binLabels,
          axisLabel: { 
            fontSize: 10,
            rotate: 45
          }
        },
        yAxis: {
          type: 'value',
          axisLabel: { fontSize: 10 }
        },
        series: [{
          name: '频次',
          type: 'bar',
          data: histogram,
          itemStyle: { color: '#67C23A' }
        }],
        grid: {
          left: '10%',
          right: '10%',
          bottom: '25%',
          top: '15%'
        }
      }

      returnsChart.setOption(option)
    }

    const exportReport = () => {
      // 导出PDF报告的逻辑
      MessagePlugin.info('报告导出功能开发中...')
    }

    const exportData = () => {
      // 导出Excel数据的逻辑
      MessagePlugin.info('数据导出功能开发中...')
    }

    // 生命周期
    onMounted(() => {
      initCharts()
    })

    return {
      // 数据
      activeTab,
      currentPage,
      pageSize,
      equityChartRef,
      drawdownChartRef,
      returnsChartRef,
      paginatedTrades,
      tradeColumns,

      // 方法
      formatPercent,
      formatNumber,
      formatCurrency,
      formatDateTime,
      getReturnClass,
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
}

.results-overview {
  margin-bottom: 24px;
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

.metric-value.positive { color: #67c23a; }
.metric-value.negative { color: #f56c6c; }
.metric-value.excellent { color: #67c23a; }
.metric-value.good { color: #e6a23c; }
.metric-value.fair { color: #909399; }
.metric-value.poor { color: #f56c6c; }

.metric-label {
  font-size: 12px;
  color: #606266;
}

.results-tabs {
  background: white;
  border-radius: 4px;
  padding: 16px;
}

.charts-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.chart-section h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 500;
}

.chart {
  border: 1px solid #e4e7ed;
  border-radius: 4px;
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

.positive { color: #67c23a; }
.negative { color: #f56c6c; }
</style>
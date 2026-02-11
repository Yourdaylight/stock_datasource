<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import * as echarts from 'echarts'
import { useReportStore } from '@/stores/report'
import type { FinancialData } from '@/api/report'

const reportStore = useReportStore()
const stockCode = ref('')
const selectedStock = ref('')
const activeTab = ref('overview')
const periods = ref(4)
const loading = ref(false)

// Computed properties
const hasData = computed(() => !!reportStore.financialData)
const stockName = computed(() => reportStore.financialData?.name || selectedStock.value)
const healthScore = computed(() => reportStore.financialData?.summary?.health_score || 0)
const summary = computed(() => reportStore.financialData?.summary)
const financialRows = computed(() => reportStore.financialData?.data || [])

// Health score theme
const scoreTheme = computed(() => {
  if (healthScore.value >= 70) return 'success'
  if (healthScore.value >= 50) return 'warning'
  return 'error'
})

const scoreColor = computed(() => {
  if (healthScore.value >= 70) return '#2ba471'
  if (healthScore.value >= 50) return '#e37318'
  return '#d54941'
})

// Format helpers
const formatValue = (val: any): string => {
  if (val === null || val === undefined || val === 'N/A' || val === '\\N') return '-'
  const num = typeof val === 'string' ? parseFloat(val) : val
  if (isNaN(num)) return String(val)
  return num.toFixed(2)
}

const formatPct = (val: any): string => {
  const v = formatValue(val)
  return v === '-' ? '-' : v + '%'
}

const formatAmount = (val: number | null | undefined): string => {
  if (val === null || val === undefined) return '-'
  const abs = Math.abs(val)
  if (abs >= 1e8) return (val / 1e8).toFixed(2) + '亿'
  if (abs >= 1e4) return (val / 1e4).toFixed(2) + '万'
  return val.toFixed(2)
}

// Get value color
const getValueColor = (val: any): string => {
  if (val === null || val === undefined || val === 'N/A' || val === '\\N') return 'var(--td-text-color-placeholder)'
  const num = typeof val === 'string' ? parseFloat(val) : val
  if (isNaN(num)) return 'var(--td-text-color-primary)'
  if (num > 20) return 'var(--td-success-color)'
  if (num < 0) return 'var(--td-error-color)'
  return 'var(--td-text-color-primary)'
}

// Period options
const periodOptions = [
  { value: 4, label: '近1年' },
  { value: 8, label: '近2年' },
  { value: 12, label: '近3年' },
  { value: 16, label: '近4年' }
]

// Example stocks
const exampleStocks = [
  { code: '000001', name: '平安银行' },
  { code: '600519', name: '贵州茅台' },
  { code: '000858', name: '五粮液' },
  { code: '002594', name: '比亚迪' },
  { code: '600036', name: '招商银行' }
]

// Handle search
const handleSearch = async () => {
  if (!stockCode.value) {
    MessagePlugin.warning('请输入股票代码')
    return
  }
  
  selectedStock.value = stockCode.value
  reportStore.clearData()
  loading.value = true
  
  try {
    await reportStore.fetchComprehensiveReport(stockCode.value, periods.value)
  } catch (error) {
    console.error('Failed to load stock data:', error)
  } finally {
    loading.value = false
  }
}

// Handle periods change
const handlePeriodsChange = async () => {
  if (selectedStock.value) {
    loading.value = true
    try {
      await reportStore.fetchFinancial(selectedStock.value, periods.value)
    } catch (error) {
      console.error('Failed to update periods:', error)
    } finally {
      loading.value = false
    }
  }
}

const selectExample = (code: string) => {
  stockCode.value = code
  handleSearch()
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

// ======== AI Analysis Parsing ========
const aiSections = computed(() => {
  if (!reportStore.analysisData?.content) return []
  const content = reportStore.analysisData.content
  const result: Array<{ title: string; icon: string; items: string[]; type: 'list' | 'kv' }> = []
  const parts = content.split(/^### /m).filter(Boolean)
  for (const part of parts) {
    const lines = part.trim().split('\n')
    const titleLine = lines[0].trim()
    const iconMatch = titleLine.match(/^([\p{Emoji}\u200d\ufe0f]+)\s*(.+)/u)
    const icon = iconMatch ? iconMatch[1] : ''
    const title = iconMatch ? iconMatch[2] : titleLine
    const items = lines.slice(1).map(l => l.trim()).filter(l => l.startsWith('- ')).map(l => l.substring(2).trim()).filter(Boolean)
    if (items.length > 0) {
      const isKV = items.every(item => /[:：]/.test(item))
      result.push({ title, icon, items, type: isKV ? 'kv' : 'list' })
    }
  }
  return result
})

const aiHealthScore = computed(() => {
  if (!reportStore.analysisData?.content) return null
  const match = reportStore.analysisData.content.match(/财务健康度评分[:：]\s*(\d+)\s*\/\s*100/)
  return match ? parseInt(match[1]) : null
})

const aiScoreTheme = computed(() => {
  if (!aiHealthScore.value) return 'warning'
  if (aiHealthScore.value >= 70) return 'success'
  if (aiHealthScore.value >= 50) return 'warning'
  return 'error'
})

const getSectionTheme = (title: string): string => {
  if (title.includes('优势')) return 'success'
  if (title.includes('关注')) return 'warning'
  if (title.includes('盈利')) return 'primary'
  if (title.includes('偿债')) return 'default'
  if (title.includes('成长')) return 'success'
  if (title.includes('投资建议')) return 'primary'
  if (title.includes('数据说明')) return 'default'
  return 'default'
}

const parseKV = (item: string): { key: string; value: string } => {
  const sep = item.indexOf('：') !== -1 ? '：' : ':'
  const idx = item.indexOf(sep)
  if (idx === -1) return { key: item, value: '' }
  return { key: item.substring(0, idx).trim(), value: item.substring(idx + 1).trim() }
}

const getKVColor = (value: string): string => {
  if (value === 'N/A') return 'var(--td-text-color-placeholder)'
  if (value.includes('%')) {
    const num = parseFloat(value)
    if (!isNaN(num)) {
      if (num > 20) return 'var(--td-success-color)'
      if (num < 0) return 'var(--td-error-color)'
    }
  }
  return 'var(--td-text-color-primary)'
}

// Filter AI sections to exclude those already shown in static data cards
const aiUniqueSections = computed(() => {
  const duplicateKeywords = ['健康度评分', '盈利能力', '偿债能力', '运营效率', '成长性', '数据说明']
  return aiSections.value.filter(section => {
    return !duplicateKeywords.some(kw => section.title.includes(kw))
  })
})

const insights = computed(() => reportStore.analysisData?.insights)

const getPositionColor = (position: string) => {
  if (position.includes('领先')) return 'success'
  if (position.includes('中上游')) return 'warning'
  if (position.includes('中游')) return 'default'
  return 'error'
}

const getStrengthColor = (level: string) => {
  if (level === '强') return 'success'
  if (level.includes('中等')) return 'warning'
  return 'error'
}

// ======== Table Columns ========
const activeTableTab = ref('overview')

const overviewColumns = [
  { colKey: 'period', title: '报告期', width: 120, fixed: 'left' as const },
  { colKey: 'revenue', title: '营业收入', width: 130 },
  { colKey: 'net_profit', title: '净利润', width: 130 },
  { colKey: 'net_profit_attr_p', title: '归母净利润', width: 130 },
  { colKey: 'basic_eps', title: 'EPS', width: 90 },
  { colKey: 'roe', title: 'ROE(%)', width: 100 },
  { colKey: 'roa', title: 'ROA(%)', width: 100 },
  { colKey: 'gross_margin', title: '毛利率(%)', width: 110 },
  { colKey: 'net_margin', title: '净利率(%)', width: 110 },
  { colKey: 'debt_ratio', title: '资产负债率(%)', width: 120 },
  { colKey: 'current_ratio', title: '流动比率', width: 100 }
]

const profitColumns = [
  { colKey: 'period', title: '报告期', width: 120, fixed: 'left' as const },
  { colKey: 'revenue', title: '营业收入', width: 130 },
  { colKey: 'oper_cost', title: '营业成本', width: 130 },
  { colKey: 'operate_profit', title: '营业利润', width: 130 },
  { colKey: 'total_profit', title: '利润总额', width: 130 },
  { colKey: 'net_profit', title: '净利润', width: 130 },
  { colKey: 'net_profit_attr_p', title: '归母净利润', width: 130 },
  { colKey: 'income_tax', title: '所得税', width: 120 },
  { colKey: 'minority_gain', title: '少数股东损益', width: 120 }
]

const expenseColumns = [
  { colKey: 'period', title: '报告期', width: 120, fixed: 'left' as const },
  { colKey: 'sell_exp', title: '销售费用', width: 130 },
  { colKey: 'admin_exp', title: '管理费用', width: 130 },
  { colKey: 'rd_exp', title: '研发费用', width: 130 },
  { colKey: 'fin_exp', title: '财务费用', width: 130 },
  { colKey: 'sell_exp_ratio', title: '销售费用率(%)', width: 120 },
  { colKey: 'admin_exp_ratio', title: '管理费用率(%)', width: 120 },
  { colKey: 'rd_exp_ratio', title: '研发费用率(%)', width: 120 },
  { colKey: 'fin_exp_ratio', title: '财务费用率(%)', width: 120 }
]

const otherColumns = [
  { colKey: 'period', title: '报告期', width: 120, fixed: 'left' as const },
  { colKey: 'ebit', title: 'EBIT', width: 130 },
  { colKey: 'ebitda', title: 'EBITDA', width: 130 },
  { colKey: 'invest_income', title: '投资收益', width: 130 },
  { colKey: 'non_oper_income', title: '营业外收入', width: 120 },
  { colKey: 'non_oper_exp', title: '营业外支出', width: 120 },
  { colKey: 'biz_tax_surchg', title: '税金及附加', width: 120 },
  { colKey: 'operating_margin', title: '营业利润率(%)', width: 120 }
]

const currentTableColumns = computed(() => {
  switch (activeTableTab.value) {
    case 'profit': return profitColumns
    case 'expense': return expenseColumns
    case 'other': return otherColumns
    default: return overviewColumns
  }
})

// ======== Trend Charts ========
const revenueChartRef = ref<HTMLElement>()
const profitabilityChartRef = ref<HTMLElement>()
const marginChartRef = ref<HTMLElement>()
const debtChartRef = ref<HTMLElement>()
const expenseChartRef = ref<HTMLElement>()
const profitStructureChartRef = ref<HTMLElement>()

let charts: echarts.ECharts[] = []

const sortedData = computed(() => {
  if (!financialRows.value.length) return []
  return [...financialRows.value].sort((a, b) => (a.period || '').localeCompare(b.period || ''))
})

const chartPeriods = computed(() => sortedData.value.map(item => item.period))

const parseNum = (val: any): number | null => {
  if (val === null || val === undefined || val === '\\N' || val === '') return null
  const n = typeof val === 'string' ? parseFloat(val) : val
  return isNaN(n) ? null : n
}

const hasMetricData = (values: (number | null)[]) => values.some(v => v !== null && v !== 0)

const baseOption = (title: string): echarts.EChartsOption => ({
  title: { text: title, left: 'center', textStyle: { fontSize: 14, fontWeight: 500 } },
  tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
  grid: { left: '3%', right: '4%', bottom: '3%', top: 60, containLabel: true },
  xAxis: { type: 'category', data: chartPeriods.value, axisLabel: { rotate: 30, fontSize: 11 } }
})

// Revenue & Net Profit
const initRevenueChart = () => {
  if (!revenueChartRef.value) return
  const revenue = sortedData.value.map(r => parseNum(r.revenue))
  const netProfit = sortedData.value.map(r => parseNum(r.net_profit))
  if (!hasMetricData(revenue) && !hasMetricData(netProfit)) return
  const chart = echarts.init(revenueChartRef.value)
  charts.push(chart)
  chart.setOption({
    ...baseOption('营业收入 & 净利润'),
    tooltip: {
      trigger: 'axis', axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        let result = params[0]?.axisValue + '<br/>'
        for (const p of params) { result += `${p.marker} ${p.seriesName}: ${formatAmount(p.value)}<br/>` }
        return result
      }
    },
    legend: { data: ['营业收入', '净利润'], top: 28 },
    yAxis: { type: 'value', axisLabel: { formatter: (val: number) => { if (Math.abs(val) >= 1e8) return (val / 1e8).toFixed(0) + '亿'; if (Math.abs(val) >= 1e4) return (val / 1e4).toFixed(0) + '万'; return val.toString() } } },
    series: [
      { name: '营业收入', type: 'bar', data: revenue, itemStyle: { color: '#1890ff', borderRadius: [4, 4, 0, 0] }, barMaxWidth: 40 },
      { name: '净利润', type: 'bar', data: netProfit, itemStyle: { color: '#52c41a', borderRadius: [4, 4, 0, 0] }, barMaxWidth: 40 }
    ]
  })
}

// ROE & ROA
const initProfitabilityChart = () => {
  if (!profitabilityChartRef.value) return
  const roe = sortedData.value.map(r => parseNum(r.roe))
  const roa = sortedData.value.map(r => parseNum(r.roa))
  if (!hasMetricData(roe) && !hasMetricData(roa)) return
  const chart = echarts.init(profitabilityChartRef.value)
  charts.push(chart)
  chart.setOption({
    ...baseOption('盈利能力：ROE & ROA'),
    legend: { data: ['ROE(%)', 'ROA(%)'], top: 28 },
    yAxis: { type: 'value', name: '%', axisLabel: { formatter: '{value}%' } },
    series: [
      { name: 'ROE(%)', type: 'line', data: roe, smooth: true, lineStyle: { color: '#1890ff', width: 2 }, itemStyle: { color: '#1890ff' }, symbol: 'circle', symbolSize: 6, areaStyle: { color: 'rgba(24,144,255,0.08)' } },
      { name: 'ROA(%)', type: 'line', data: roa, smooth: true, lineStyle: { color: '#52c41a', width: 2 }, itemStyle: { color: '#52c41a' }, symbol: 'circle', symbolSize: 6, areaStyle: { color: 'rgba(82,196,26,0.08)' } }
    ]
  })
}

// Gross Margin & Net Margin
const initMarginChart = () => {
  if (!marginChartRef.value) return
  const grossMargin = sortedData.value.map(r => parseNum(r.gross_margin))
  const netMargin = sortedData.value.map(r => parseNum(r.net_margin))
  if (!hasMetricData(grossMargin) && !hasMetricData(netMargin)) return
  const chart = echarts.init(marginChartRef.value)
  charts.push(chart)
  chart.setOption({
    ...baseOption('利润率：毛利率 & 净利率'),
    legend: { data: ['毛利率(%)', '净利率(%)'], top: 28 },
    yAxis: { type: 'value', name: '%', axisLabel: { formatter: '{value}%' } },
    series: [
      { name: '毛利率(%)', type: 'line', data: grossMargin, smooth: true, lineStyle: { color: '#faad14', width: 2 }, itemStyle: { color: '#faad14' }, symbol: 'circle', symbolSize: 6, areaStyle: { color: 'rgba(250,173,20,0.08)' } },
      { name: '净利率(%)', type: 'line', data: netMargin, smooth: true, lineStyle: { color: '#f5222d', width: 2 }, itemStyle: { color: '#f5222d' }, symbol: 'circle', symbolSize: 6, areaStyle: { color: 'rgba(245,34,45,0.08)' } }
    ]
  })
}

// Debt Ratio & Current Ratio
const initDebtChart = () => {
  if (!debtChartRef.value) return
  const debtRatio = sortedData.value.map(r => parseNum(r.debt_ratio))
  const currentRatio = sortedData.value.map(r => parseNum(r.current_ratio))
  if (!hasMetricData(debtRatio) && !hasMetricData(currentRatio)) return
  const chart = echarts.init(debtChartRef.value)
  charts.push(chart)
  chart.setOption({
    ...baseOption('偿债能力：资产负债率 & 流动比率'),
    legend: { data: ['资产负债率(%)', '流动比率'], top: 28 },
    yAxis: [
      { type: 'value', name: '%', position: 'left', axisLabel: { formatter: '{value}%' } },
      { type: 'value', name: '倍', position: 'right', axisLabel: { formatter: '{value}' }, splitLine: { show: false } }
    ],
    series: [
      { name: '资产负债率(%)', type: 'bar', yAxisIndex: 0, data: debtRatio, itemStyle: { color: '#722ed1', borderRadius: [4, 4, 0, 0] }, barMaxWidth: 40 },
      { name: '流动比率', type: 'line', yAxisIndex: 1, data: currentRatio, smooth: true, lineStyle: { color: '#13c2c2', width: 2 }, itemStyle: { color: '#13c2c2' }, symbol: 'circle', symbolSize: 6 }
    ]
  })
}

// Expense Ratios Chart
const initExpenseChart = () => {
  if (!expenseChartRef.value) return
  const sellRatio = sortedData.value.map(r => parseNum(r.sell_exp_ratio))
  const adminRatio = sortedData.value.map(r => parseNum(r.admin_exp_ratio))
  const rdRatio = sortedData.value.map(r => parseNum(r.rd_exp_ratio))
  const finRatio = sortedData.value.map(r => parseNum(r.fin_exp_ratio))
  if (!hasMetricData(sellRatio) && !hasMetricData(adminRatio) && !hasMetricData(rdRatio) && !hasMetricData(finRatio)) return
  const chart = echarts.init(expenseChartRef.value)
  charts.push(chart)
  chart.setOption({
    ...baseOption('费用率分析'),
    legend: { data: ['销售费用率(%)', '管理费用率(%)', '研发费用率(%)', '财务费用率(%)'], top: 28 },
    yAxis: { type: 'value', name: '%', axisLabel: { formatter: '{value}%' } },
    series: [
      { name: '销售费用率(%)', type: 'bar', data: sellRatio, stack: 'expense', itemStyle: { color: '#1890ff' }, barMaxWidth: 40 },
      { name: '管理费用率(%)', type: 'bar', data: adminRatio, stack: 'expense', itemStyle: { color: '#52c41a' }, barMaxWidth: 40 },
      { name: '研发费用率(%)', type: 'bar', data: rdRatio, stack: 'expense', itemStyle: { color: '#faad14' }, barMaxWidth: 40 },
      { name: '财务费用率(%)', type: 'bar', data: finRatio, stack: 'expense', itemStyle: { color: '#722ed1' }, barMaxWidth: 40 }
    ]
  })
}

// Profit Structure Chart (waterfall-like)
const initProfitStructureChart = () => {
  if (!profitStructureChartRef.value) return
  const revenue = sortedData.value.map(r => parseNum(r.revenue))
  const operateProfit = sortedData.value.map(r => parseNum(r.operate_profit))
  const totalProfit = sortedData.value.map(r => parseNum(r.total_profit))
  const netProfit = sortedData.value.map(r => parseNum(r.net_profit))
  if (!hasMetricData(revenue)) return
  const chart = echarts.init(profitStructureChartRef.value)
  charts.push(chart)
  chart.setOption({
    ...baseOption('利润结构'),
    tooltip: {
      trigger: 'axis', axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        let result = params[0]?.axisValue + '<br/>'
        for (const p of params) { result += `${p.marker} ${p.seriesName}: ${formatAmount(p.value)}<br/>` }
        return result
      }
    },
    legend: { data: ['营业收入', '营业利润', '利润总额', '净利润'], top: 28 },
    yAxis: { type: 'value', axisLabel: { formatter: (val: number) => { if (Math.abs(val) >= 1e8) return (val / 1e8).toFixed(0) + '亿'; if (Math.abs(val) >= 1e4) return (val / 1e4).toFixed(0) + '万'; return val.toString() } } },
    series: [
      { name: '营业收入', type: 'bar', data: revenue, itemStyle: { color: '#1890ff', borderRadius: [4, 4, 0, 0] }, barMaxWidth: 30 },
      { name: '营业利润', type: 'bar', data: operateProfit, itemStyle: { color: '#52c41a', borderRadius: [4, 4, 0, 0] }, barMaxWidth: 30 },
      { name: '利润总额', type: 'bar', data: totalProfit, itemStyle: { color: '#faad14', borderRadius: [4, 4, 0, 0] }, barMaxWidth: 30 },
      { name: '净利润', type: 'bar', data: netProfit, itemStyle: { color: '#f5222d', borderRadius: [4, 4, 0, 0] }, barMaxWidth: 30 }
    ]
  })
}

const disposeCharts = () => {
  charts.forEach(c => c.dispose())
  charts = []
}

const initAllCharts = async () => {
  disposeCharts()
  await nextTick()
  if (!sortedData.value.length) return
  initRevenueChart()
  initProfitabilityChart()
  initMarginChart()
  initDebtChart()
  initExpenseChart()
  initProfitStructureChart()
}

const handleResize = () => {
  charts.forEach(c => c.resize())
}

watch(activeTab, (val) => {
  if (val === 'charts' && sortedData.value.length) {
    setTimeout(initAllCharts, 100)
  }
})

watch(financialRows, () => {
  if (activeTab.value === 'charts') {
    setTimeout(initAllCharts, 100)
  }
}, { deep: true })

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  disposeCharts()
})
</script>

<template>
  <div class="financial-panel">
    <!-- Header with search -->
    <div class="panel-header">
      <t-space>
        <t-input
          v-model="stockCode"
          placeholder="输入股票代码 (如 000001)"
          style="width: 220px"
          @enter="handleSearch"
        >
          <template #prefix-icon>
            <t-icon name="search" />
          </template>
        </t-input>
        <t-select
          v-model="periods"
          :options="periodOptions"
          style="width: 100px"
          @change="handlePeriodsChange"
        />
        <t-button theme="primary" :loading="loading" @click="handleSearch">
          查询
        </t-button>
      </t-space>
    </div>

    <!-- Empty State -->
    <div v-if="!selectedStock" class="empty-state">
      <t-icon name="chart-line" size="64px" style="color: #ddd" />
      <h3>专业财报分析</h3>
      <p>请输入股票代码开始分析</p>
      <div class="example-stocks">
        <span class="example-label">热门股票：</span>
        <t-tag
          v-for="stock in exampleStocks"
          :key="stock.code"
          theme="primary"
          variant="light"
          style="cursor: pointer"
          @click="selectExample(stock.code)"
        >
          {{ stock.code }} {{ stock.name }}
        </t-tag>
      </div>
    </div>

    <!-- Loading State -->
    <div v-else-if="loading && !hasData" class="loading-state">
      <t-loading size="large" text="正在加载财务数据..." />
    </div>

    <!-- Main Content -->
    <div v-else-if="hasData" class="report-content">
      <!-- Stock Header -->
      <div class="stock-header">
        <div class="stock-info">
          <h2>{{ stockName }}</h2>
          <t-tag theme="primary">{{ selectedStock }}</t-tag>
          <t-tag variant="outline">A股</t-tag>
        </div>
      </div>

      <!-- Tab Navigation -->
      <t-tabs v-model="activeTab" size="large">
        <!-- Overview Tab -->
        <t-tab-panel value="overview" label="全面分析">
          <div class="analysis-content">
            <!-- Health Score Card -->
            <div v-if="healthScore" class="score-card" :class="'score-' + scoreTheme">
              <div class="score-circle">
                <t-progress
                  theme="circle"
                  :percentage="healthScore"
                  :color="scoreColor"
                  :stroke-width="8"
                  size="100px"
                >
                  <div class="score-text">
                    <span class="score-number">{{ healthScore }}</span>
                    <span class="score-unit">/100</span>
                  </div>
                </t-progress>
              </div>
              <div class="score-label">财务健康度评分</div>
            </div>

            <!-- Section Cards Grid -->
            <div class="section-grid">
              <!-- Profitability -->
              <div class="section-card theme-primary">
                <div class="section-title">
                  <span class="section-icon">📈</span>
                  <span>盈利能力指标</span>
                </div>
                <div class="kv-list">
                  <div class="kv-item">
                    <span class="kv-key">ROE</span>
                    <span class="kv-value" :style="{ color: getValueColor(summary?.profitability?.roe) }">
                      {{ formatPct(summary?.profitability?.roe) }}
                    </span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">ROA</span>
                    <span class="kv-value" :style="{ color: getValueColor(summary?.profitability?.roa) }">
                      {{ formatPct(summary?.profitability?.roa) }}
                    </span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">毛利率</span>
                    <span class="kv-value" :style="{ color: getValueColor(summary?.profitability?.gross_profit_margin) }">
                      {{ formatPct(summary?.profitability?.gross_profit_margin) }}
                    </span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">净利率</span>
                    <span class="kv-value" :style="{ color: getValueColor(summary?.profitability?.net_profit_margin) }">
                      {{ formatPct(summary?.profitability?.net_profit_margin) }}
                    </span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">每股收益(EPS)</span>
                    <span class="kv-value">{{ formatValue(summary?.profitability?.eps) }}</span>
                  </div>
                </div>
              </div>

              <!-- Solvency -->
              <div class="section-card theme-default">
                <div class="section-title">
                  <span class="section-icon">🏦</span>
                  <span>偿债能力指标</span>
                </div>
                <div class="kv-list">
                  <div class="kv-item">
                    <span class="kv-key">资产负债率</span>
                    <span class="kv-value">{{ formatPct(summary?.solvency?.debt_to_assets) }}</span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">产权比率</span>
                    <span class="kv-value">{{ formatValue(summary?.solvency?.debt_to_equity) }}</span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">流动比率</span>
                    <span class="kv-value">{{ formatValue(summary?.solvency?.current_ratio) }}</span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">速动比率</span>
                    <span class="kv-value">{{ formatValue(summary?.solvency?.quick_ratio) }}</span>
                  </div>
                </div>
              </div>

              <!-- Efficiency -->
              <div class="section-card theme-default">
                <div class="section-title">
                  <span class="section-icon">⚙️</span>
                  <span>运营效率指标</span>
                </div>
                <div class="kv-list">
                  <div class="kv-item">
                    <span class="kv-key">总资产周转率</span>
                    <span class="kv-value">{{ formatValue(summary?.efficiency?.asset_turnover) }}</span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">存货周转率</span>
                    <span class="kv-value">{{ formatValue(summary?.efficiency?.inventory_turnover) }}</span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">应收账款周转率</span>
                    <span class="kv-value">{{ formatValue(summary?.efficiency?.receivable_turnover) }}</span>
                  </div>
                </div>
              </div>

              <!-- Growth -->
              <div class="section-card theme-success">
                <div class="section-title">
                  <span class="section-icon">🚀</span>
                  <span>成长性指标</span>
                </div>
                <div class="kv-list">
                  <div class="kv-item">
                    <span class="kv-key">营收增长率</span>
                    <span class="kv-value" :style="{ color: getValueColor(summary?.growth?.revenue_growth) }">
                      {{ formatPct(summary?.growth?.revenue_growth) }}
                    </span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">利润增长率</span>
                    <span class="kv-value" :style="{ color: getValueColor(summary?.growth?.profit_growth) }">
                      {{ formatPct(summary?.growth?.profit_growth) }}
                    </span>
                  </div>
                </div>
              </div>

              <!-- Income Highlights (from ods_income_statement) -->
              <div v-if="financialRows.length" class="section-card theme-primary">
                <div class="section-title">
                  <span class="section-icon">💰</span>
                  <span>利润结构（最新期）</span>
                </div>
                <div class="kv-list">
                  <div class="kv-item">
                    <span class="kv-key">营业收入</span>
                    <span class="kv-value">{{ formatAmount(financialRows[0]?.revenue) }}</span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">营业成本</span>
                    <span class="kv-value">{{ formatAmount(financialRows[0]?.oper_cost) }}</span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">营业利润</span>
                    <span class="kv-value">{{ formatAmount(financialRows[0]?.operate_profit) }}</span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">利润总额</span>
                    <span class="kv-value">{{ formatAmount(financialRows[0]?.total_profit) }}</span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">归母净利润</span>
                    <span class="kv-value">{{ formatAmount(financialRows[0]?.net_profit_attr_p) }}</span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">基本EPS</span>
                    <span class="kv-value">{{ formatValue(financialRows[0]?.basic_eps) }}</span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">EBITDA</span>
                    <span class="kv-value">{{ formatAmount(financialRows[0]?.ebitda) }}</span>
                  </div>
                </div>
              </div>

              <!-- Expense Analysis -->
              <div v-if="financialRows.length" class="section-card theme-warning">
                <div class="section-title">
                  <span class="section-icon">📊</span>
                  <span>费用分析（最新期）</span>
                </div>
                <div class="kv-list">
                  <div class="kv-item">
                    <span class="kv-key">销售费用</span>
                    <span class="kv-value">{{ formatAmount(financialRows[0]?.sell_exp) }}
                      <span v-if="financialRows[0]?.sell_exp_ratio" class="ratio-badge">{{ formatValue(financialRows[0]?.sell_exp_ratio) }}%</span>
                    </span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">管理费用</span>
                    <span class="kv-value">{{ formatAmount(financialRows[0]?.admin_exp) }}
                      <span v-if="financialRows[0]?.admin_exp_ratio" class="ratio-badge">{{ formatValue(financialRows[0]?.admin_exp_ratio) }}%</span>
                    </span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">研发费用</span>
                    <span class="kv-value">{{ formatAmount(financialRows[0]?.rd_exp) }}
                      <span v-if="financialRows[0]?.rd_exp_ratio" class="ratio-badge">{{ formatValue(financialRows[0]?.rd_exp_ratio) }}%</span>
                    </span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">财务费用</span>
                    <span class="kv-value">{{ formatAmount(financialRows[0]?.fin_exp) }}
                      <span v-if="financialRows[0]?.fin_exp_ratio" class="ratio-badge">{{ formatValue(financialRows[0]?.fin_exp_ratio) }}%</span>
                    </span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">所得税</span>
                    <span class="kv-value">{{ formatAmount(financialRows[0]?.income_tax) }}</span>
                  </div>
                </div>
              </div>

              <!-- Data Info -->
              <div class="section-card theme-default full-width">
                <div class="section-title">
                  <span class="section-icon">📅</span>
                  <span>数据说明</span>
                </div>
                <div class="kv-list">
                  <div class="kv-item">
                    <span class="kv-key">公司名称</span>
                    <span class="kv-value">{{ reportStore.financialData?.name || '-' }}</span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">最新财报</span>
                    <span class="kv-value">{{ reportStore.financialData?.latest_period || '-' }}</span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">分析期数</span>
                    <span class="kv-value">{{ reportStore.financialData?.periods || '-' }}期</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- AI Analysis Section (merged - only non-duplicate content) -->
            <div v-if="reportStore.analysisLoading" class="ai-loading-section">
              <t-divider>AI 智能分析</t-divider>
              <div class="chart-loading">
                <t-loading size="large" text="AI 正在分析中..." />
              </div>
            </div>

            <div v-else-if="reportStore.analysisData" class="ai-merged-section">
              <t-divider>AI 智能分析</t-divider>

              <!-- AI-only Section Cards (exclude duplicates with overview data cards) -->
              <div v-if="aiUniqueSections.length" class="section-grid">
                <template v-for="(section, idx) in aiUniqueSections" :key="idx">
                  <div class="section-card" :class="'theme-' + getSectionTheme(section.title)">
                    <div class="section-title">
                      <span class="section-icon">{{ section.icon }}</span>
                      <span>{{ section.title }}</span>
                    </div>
                    <div v-if="section.type === 'kv'" class="kv-list">
                      <div v-for="(item, i) in section.items" :key="i" class="kv-item">
                        <span class="kv-key">{{ parseKV(item).key }}</span>
                        <span class="kv-value" :style="{ color: getKVColor(parseKV(item).value) }">{{ parseKV(item).value }}</span>
                      </div>
                    </div>
                    <div v-else class="item-list">
                      <div v-for="(item, i) in section.items" :key="i" class="list-item">
                        <t-icon
                          :name="section.title.includes('优势') ? 'check-circle-filled' : section.title.includes('关注') ? 'error-circle-filled' : section.title.includes('建议') ? 'lightbulb' : 'chevron-right'"
                          :class="section.title.includes('优势') ? 'icon-success' : section.title.includes('关注') ? 'icon-warning' : section.title.includes('建议') ? 'icon-primary' : 'icon-default'"
                          size="16px"
                        />
                        <span>{{ item }}</span>
                      </div>
                    </div>
                  </div>
                </template>
              </div>

              <!-- Structured Insights -->
              <div v-if="insights" class="insights-section">
                <t-divider>结构化洞察</t-divider>
                <div class="insights-grid">
                  <div v-if="insights.investment_thesis?.length" class="insight-card">
                    <div class="insight-card-title">投资要点</div>
                    <div v-for="(point, index) in insights.investment_thesis" :key="index" class="insight-point success">
                      <t-icon name="check-circle-filled" size="14px" />
                      <span>{{ point }}</span>
                    </div>
                  </div>
                  <div v-if="insights.risk_factors?.length" class="insight-card">
                    <div class="insight-card-title">风险因素</div>
                    <div v-for="(risk, index) in insights.risk_factors" :key="index" class="insight-point error">
                      <t-icon name="error-circle-filled" size="14px" />
                      <span>{{ risk }}</span>
                    </div>
                  </div>
                  <div v-if="insights.competitive_position" class="insight-card">
                    <div class="insight-card-title">竞争地位</div>
                    <div class="insight-metric">
                      <t-tag :theme="getPositionColor(insights.competitive_position.position)" size="large">
                        {{ insights.competitive_position.position }}
                      </t-tag>
                      <span class="metric-desc">优秀指标: {{ insights.competitive_position.excellent_metrics }}/{{ insights.competitive_position.total_metrics }}</span>
                    </div>
                  </div>
                  <div v-if="insights.financial_strength" class="insight-card">
                    <div class="insight-card-title">财务实力</div>
                    <div class="insight-metric">
                      <t-tag :theme="getStrengthColor(insights.financial_strength.level)" size="large">
                        {{ insights.financial_strength.level }}
                      </t-tag>
                      <t-progress
                        :percentage="insights.financial_strength.score"
                        :color="getStrengthColor(insights.financial_strength.level) === 'success' ? '#2ba471' : '#e37318'"
                        size="small"
                        style="flex: 1; margin-left: 12px"
                      />
                    </div>
                    <div v-if="insights.financial_strength.key_strengths?.length" class="strength-tags">
                      <t-tag v-for="s in insights.financial_strength.key_strengths" :key="s" variant="light" theme="primary" size="small">{{ s }}</t-tag>
                    </div>
                  </div>
                  <div v-if="insights.growth_prospects" class="insight-card wide">
                    <div class="insight-card-title">成长前景</div>
                    <div class="growth-row">
                      <div class="growth-item">
                        <span class="growth-label">营收增长率</span>
                        <span class="growth-value" :class="{ positive: (insights.growth_prospects.revenue_growth ?? 0) > 0, negative: (insights.growth_prospects.revenue_growth ?? 0) < 0 }">
                          {{ insights.growth_prospects.revenue_growth?.toFixed(2) ?? 'N/A' }}%
                        </span>
                      </div>
                      <div class="growth-item">
                        <span class="growth-label">利润增长率</span>
                        <span class="growth-value" :class="{ positive: (insights.growth_prospects.profit_growth ?? 0) > 0, negative: (insights.growth_prospects.profit_growth ?? 0) < 0 }">
                          {{ insights.growth_prospects.profit_growth?.toFixed(2) ?? 'N/A' }}%
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Refresh button -->
              <div class="ai-refresh-bar">
                <t-button theme="primary" variant="outline" size="small" :loading="reportStore.analysisLoading" @click="handleRefreshAnalysis">
                  <template #icon><t-icon name="refresh" /></template>
                  刷新AI分析
                </t-button>
              </div>
            </div>

            <div v-else class="ai-empty-section">
              <t-divider>AI 智能分析</t-divider>
              <div class="chart-empty" style="height: 120px">
                <t-button theme="primary" @click="handleRefreshAnalysis">开始AI分析</t-button>
              </div>
            </div>
          </div>
        </t-tab-panel>

        <!-- Trend Charts Tab -->
        <t-tab-panel value="charts" label="趋势图表">
          <t-card title="数据可视化" :bordered="false">
            <div v-if="reportStore.loading" class="chart-loading">
              <t-loading size="large" text="加载图表数据..." />
            </div>
            <div v-else-if="!sortedData.length" class="chart-empty">
              <t-empty description="暂无趋势数据" />
            </div>
            <div v-else class="charts-grid">
              <div class="chart-item">
                <div ref="revenueChartRef" class="chart-container" />
              </div>
              <div class="chart-item">
                <div ref="profitStructureChartRef" class="chart-container" />
              </div>
              <div class="chart-item">
                <div ref="profitabilityChartRef" class="chart-container" />
              </div>
              <div class="chart-item">
                <div ref="marginChartRef" class="chart-container" />
              </div>
              <div class="chart-item">
                <div ref="expenseChartRef" class="chart-container" />
              </div>
              <div class="chart-item">
                <div ref="debtChartRef" class="chart-container" />
              </div>
            </div>
          </t-card>
        </t-tab-panel>

        <!-- Financial Data Table Tab -->
        <t-tab-panel value="indicators" label="财务指标">
          <t-card title="财务数据明细" :bordered="false">
            <template #actions>
              <t-radio-group v-model="activeTableTab" variant="default-filled" size="small">
                <t-radio-button value="overview">综合</t-radio-button>
                <t-radio-button value="profit">利润结构</t-radio-button>
                <t-radio-button value="expense">费用分析</t-radio-button>
                <t-radio-button value="other">其他指标</t-radio-button>
              </t-radio-group>
            </template>
            <t-table
              :data="financialRows"
              :columns="currentTableColumns"
              :loading="reportStore.loading"
              row-key="period"
              :scroll="{ x: 1200 }"
              :pagination="false"
              size="small"
            >
              <template #revenue="{ row }">
                <span class="number-cell">{{ formatAmount(row.revenue) }}</span>
              </template>
              <template #net_profit="{ row }">
                <span class="number-cell">{{ formatAmount(row.net_profit) }}</span>
              </template>
              <template #net_profit_attr_p="{ row }">
                <span class="number-cell">{{ formatAmount(row.net_profit_attr_p) }}</span>
              </template>
              <template #operate_profit="{ row }">
                <span class="number-cell">{{ formatAmount(row.operate_profit) }}</span>
              </template>
              <template #total_profit="{ row }">
                <span class="number-cell">{{ formatAmount(row.total_profit) }}</span>
              </template>
              <template #oper_cost="{ row }">
                <span class="number-cell">{{ formatAmount(row.oper_cost) }}</span>
              </template>
              <template #income_tax="{ row }">
                <span class="number-cell">{{ formatAmount(row.income_tax) }}</span>
              </template>
              <template #minority_gain="{ row }">
                <span class="number-cell">{{ formatAmount(row.minority_gain) }}</span>
              </template>
              <template #sell_exp="{ row }">
                <span class="number-cell">{{ formatAmount(row.sell_exp) }}</span>
              </template>
              <template #admin_exp="{ row }">
                <span class="number-cell">{{ formatAmount(row.admin_exp) }}</span>
              </template>
              <template #rd_exp="{ row }">
                <span class="number-cell">{{ formatAmount(row.rd_exp) }}</span>
              </template>
              <template #fin_exp="{ row }">
                <span class="number-cell">{{ formatAmount(row.fin_exp) }}</span>
              </template>
              <template #ebit="{ row }">
                <span class="number-cell">{{ formatAmount(row.ebit) }}</span>
              </template>
              <template #ebitda="{ row }">
                <span class="number-cell">{{ formatAmount(row.ebitda) }}</span>
              </template>
              <template #invest_income="{ row }">
                <span class="number-cell">{{ formatAmount(row.invest_income) }}</span>
              </template>
              <template #non_oper_income="{ row }">
                <span class="number-cell">{{ formatAmount(row.non_oper_income) }}</span>
              </template>
              <template #non_oper_exp="{ row }">
                <span class="number-cell">{{ formatAmount(row.non_oper_exp) }}</span>
              </template>
              <template #biz_tax_surchg="{ row }">
                <span class="number-cell">{{ formatAmount(row.biz_tax_surchg) }}</span>
              </template>
              <template #basic_eps="{ row }">
                <span class="number-cell">{{ formatValue(row.basic_eps) }}</span>
              </template>
              <template #roe="{ row }">
                <span class="number-cell" :class="{ positive: (row.roe || 0) > 15, negative: (row.roe || 0) < 5 }">
                  {{ formatValue(row.roe) }}
                </span>
              </template>
              <template #roa="{ row }">
                <span class="number-cell">{{ formatValue(row.roa) }}</span>
              </template>
              <template #gross_margin="{ row }">
                <span class="number-cell">{{ formatValue(row.gross_margin) }}</span>
              </template>
              <template #net_margin="{ row }">
                <span class="number-cell">{{ formatValue(row.net_margin) }}</span>
              </template>
              <template #operating_margin="{ row }">
                <span class="number-cell">{{ formatValue(row.operating_margin) }}</span>
              </template>
              <template #sell_exp_ratio="{ row }">
                <span class="number-cell">{{ formatValue(row.sell_exp_ratio) }}</span>
              </template>
              <template #admin_exp_ratio="{ row }">
                <span class="number-cell">{{ formatValue(row.admin_exp_ratio) }}</span>
              </template>
              <template #rd_exp_ratio="{ row }">
                <span class="number-cell">{{ formatValue(row.rd_exp_ratio) }}</span>
              </template>
              <template #fin_exp_ratio="{ row }">
                <span class="number-cell">{{ formatValue(row.fin_exp_ratio) }}</span>
              </template>
              <template #debt_ratio="{ row }">
                <span class="number-cell" :class="{ negative: (row.debt_ratio || 0) > 70, positive: (row.debt_ratio || 0) < 40 }">
                  {{ formatValue(row.debt_ratio) }}
                </span>
              </template>
              <template #current_ratio="{ row }">
                <span class="number-cell" :class="{ positive: (row.current_ratio || 0) > 1.5, negative: (row.current_ratio || 0) < 1 }">
                  {{ formatValue(row.current_ratio) }}
                </span>
              </template>
            </t-table>
          </t-card>
        </t-tab-panel>
      </t-tabs>
    </div>

    <!-- Error State -->
    <div v-else class="error-state">
      <t-icon name="close-circle" size="64px" style="color: #f5222d" />
      <h3>加载失败</h3>
      <p>无法获取 {{ selectedStock }} 的财务数据</p>
      <t-button theme="primary" @click="handleSearch">重试</t-button>
    </div>
  </div>
</template>

<style scoped>
.financial-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.panel-header {
  display: flex;
  justify-content: flex-start;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 400px;
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

.example-stocks {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: center;
  align-items: center;
  margin-top: 8px;
}

.example-label {
  font-size: 13px;
  color: var(--td-text-color-secondary);
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

/* Analysis Content */
.analysis-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding-top: 8px;
}

/* Health Score Card */
.score-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--td-bg-color-container) 0%, var(--td-bg-color-secondarycontainer) 100%);
  border: 1px solid var(--td-border-level-1-color);
}

.score-card.score-success { border-color: rgba(43, 164, 113, 0.3); }
.score-card.score-warning { border-color: rgba(227, 115, 24, 0.3); }
.score-card.score-error { border-color: rgba(213, 73, 65, 0.3); }

.score-text {
  display: flex;
  align-items: baseline;
  justify-content: center;
}

.score-number {
  font-size: 28px;
  font-weight: 700;
  font-family: 'Monaco', 'Menlo', monospace;
}

.score-unit {
  font-size: 12px;
  color: var(--td-text-color-secondary);
  margin-left: 2px;
}

.score-label {
  margin-top: 8px;
  font-size: 13px;
  color: var(--td-text-color-secondary);
}

/* Section Grid */
.section-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

@media (max-width: 768px) {
  .section-grid {
    grid-template-columns: 1fr;
  }
}

.section-card {
  padding: 16px;
  border-radius: 8px;
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-border-level-1-color);
  transition: box-shadow 0.2s;
}

.section-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.section-card.full-width {
  grid-column: 1 / -1;
}

.section-card.theme-success { border-left: 3px solid var(--td-success-color); }
.section-card.theme-warning { border-left: 3px solid var(--td-warning-color); }
.section-card.theme-primary { border-left: 3px solid var(--td-brand-color); }
.section-card.theme-default { border-left: 3px solid var(--td-border-level-2-color); }

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--td-text-color-primary);
  margin-bottom: 12px;
}

.section-icon {
  font-size: 16px;
}

/* KV List */
.kv-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.kv-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  border-bottom: 1px dashed var(--td-border-level-1-color);
}

.kv-item:last-child {
  border-bottom: none;
}

.kv-key {
  font-size: 13px;
  color: var(--td-text-color-secondary);
}

.kv-value {
  font-size: 14px;
  font-weight: 500;
  font-family: 'Monaco', 'Menlo', monospace;
}

.ratio-badge {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  font-size: 11px;
  font-weight: 400;
  color: var(--td-brand-color);
  background: rgba(0, 82, 217, 0.08);
  border-radius: 4px;
}

/* List Items */
.item-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.list-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  line-height: 1.5;
  color: var(--td-text-color-primary);
}

.list-item .t-icon {
  margin-top: 3px;
  flex-shrink: 0;
}

.icon-success { color: var(--td-success-color); }
.icon-warning { color: var(--td-warning-color); }
.icon-primary { color: var(--td-brand-color); }
.icon-default { color: var(--td-text-color-placeholder); }

/* Charts */
.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.chart-item {
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-border-level-1-color);
  border-radius: 6px;
  padding: 8px;
}

.chart-container {
  width: 100%;
  height: 320px;
}

.chart-loading,
.chart-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 400px;
}

@media (max-width: 960px) {
  .charts-grid {
    grid-template-columns: 1fr;
  }
}

/* Number cells in table */
.number-cell {
  font-family: 'Monaco', 'Menlo', monospace;
  text-align: right;
}

.positive {
  color: var(--td-success-color);
  font-weight: 500;
}

.negative {
  color: var(--td-error-color);
  font-weight: 500;
}

/* AI Merged Section */
.ai-merged-section,
.ai-loading-section,
.ai-empty-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.ai-refresh-bar {
  display: flex;
  justify-content: center;
  padding: 8px 0;
}

/* Insights Section */
.insights-section {
  margin-top: 4px;
}

.insights-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

@media (max-width: 768px) {
  .insights-grid {
    grid-template-columns: 1fr;
  }
}

.insight-card {
  padding: 14px;
  border-radius: 8px;
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-border-level-1-color);
}

.insight-card.wide {
  grid-column: 1 / -1;
}

.insight-card-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--td-text-color-secondary);
  margin-bottom: 10px;
}

.insight-point {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 13px;
  line-height: 1.4;
  padding: 3px 0;
}

.insight-point.success .t-icon { color: var(--td-success-color); }
.insight-point.error .t-icon { color: var(--td-error-color); }

.insight-point .t-icon {
  margin-top: 2px;
  flex-shrink: 0;
}

.insight-metric {
  display: flex;
  align-items: center;
  gap: 8px;
}

.metric-desc {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.strength-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 8px;
}

.growth-row {
  display: flex;
  gap: 24px;
}

.growth-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.growth-label {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.growth-value {
  font-size: 18px;
  font-weight: 600;
  font-family: 'Monaco', 'Menlo', monospace;
  color: var(--td-text-color-primary);
}

.growth-value.positive { color: var(--td-success-color); }
.growth-value.negative { color: var(--td-error-color); }

:deep(.t-tabs__content) {
  padding-top: 16px;
}

:deep(.t-table__content) {
  font-size: 12px;
}

:deep(.t-table th) {
  background-color: var(--td-bg-color-container-select);
  font-weight: 500;
}
</style>

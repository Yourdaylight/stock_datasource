<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted, h } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import * as echarts from 'echarts'
import { hkReportApi, type HKFinancialResponse, type HKFinancialIndicator, type HKAnalysisResponse, type HKStatementRow } from '@/api/hk-report'

const stockCode = ref('')
const periods = ref(8)
const loading = ref(false)
const financialData = ref<HKFinancialResponse | null>(null)
const indicatorData = ref<HKFinancialIndicator[]>([])
const activeTab = ref('overview')
const analysisData = ref<HKAnalysisResponse | null>(null)
const analysisLoading = ref(false)

// Three statements data
const incomeData = ref<HKStatementRow[]>([])
const balanceData = ref<HKStatementRow[]>([])
const cashflowData = ref<HKStatementRow[]>([])

const hasData = computed(() => !!financialData.value && financialData.value.status !== 'error')
const stockName = computed(() => financialData.value?.summary?.name || stockCode.value)
const healthScore = computed(() => financialData.value?.health_analysis?.health_score || 0)

// Period options
const periodOptions = [
  { value: 4, label: '近4期' },
  { value: 8, label: '近8期' },
  { value: 12, label: '近12期' },
  { value: 20, label: '近20期' }
]

// Format value for display
const formatValue = (val: any): string => {
  if (val === null || val === undefined || val === 'N/A' || val === '\\N') return '-'
  const num = typeof val === 'string' ? parseFloat(val) : val
  if (isNaN(num)) return String(val)
  return num.toFixed(2)
}

// Indicator table columns
const indicatorColumns = [
  { colKey: 'end_date', title: '报告期', width: 120, fixed: 'left' as const },
  { colKey: 'roe_avg', title: 'ROE(%)', width: 100 },
  { colKey: 'roa', title: 'ROA(%)', width: 100 },
  { colKey: 'gross_profit_ratio', title: '毛利率(%)', width: 110 },
  { colKey: 'net_profit_ratio', title: '净利率(%)', width: 110 },
  { colKey: 'basic_eps', title: 'EPS', width: 80 },
  { colKey: 'pe_ttm', title: 'PE(TTM)', width: 100 },
  { colKey: 'pb_ttm', title: 'PB(TTM)', width: 100 },
  { colKey: 'debt_asset_ratio', title: '资产负债率(%)', width: 130 },
  { colKey: 'current_ratio', title: '流动比率', width: 100 },
  { colKey: 'equity_multiplier', title: '权益乘数', width: 100 }
]

// Format amount (亿/万), treat 0 as no data
const formatAmount = (val: any): string => {
  if (val === null || val === undefined || val === '\\N' || val === 'N/A' || val === '') return '-'
  const num = typeof val === 'string' ? parseFloat(val) : val
  if (isNaN(num)) return '-'
  if (num === 0) return '-'
  const abs = Math.abs(num)
  if (abs >= 1e8) return (num / 1e8).toFixed(2) + '亿'
  if (abs >= 1e4) return (num / 1e4).toFixed(2) + '万'
  return num.toFixed(2)
}

// Helper: get pivot field value, trying multiple possible field name variants
const getPivotVal = (row: any, ...keys: string[]): any => {
  for (const k of keys) {
    if (row && row[k] !== undefined && row[k] !== null && row[k] !== 0) return row[k]
  }
  // Even if 0, return the first key's value if it exists
  for (const k of keys) {
    if (row && k in row) return row[k]
  }
  return null
}

// Fields to exclude from pivot display (not financial indicators)
const PIVOT_EXCLUDE_KEYS = new Set(['end_date', 'ts_code', 'code', 'ann_date', 'report_type'])

// Transform pivot data to row-per-indicator format for table display
// Input: [{ ts_code: '00700.HK', end_date: '20231231', 营业收入: 100, 营业成本: 50 }, ...]
// Output: [{ indicator: '营业收入', '20231231': '100亿', ... }, ...]
const transformPivotToRows = (data: HKStatementRow[]) => {
  if (!data.length) return { columns: [] as any[], rows: [] as any[] }
  
  // Get all indicator names (keys except metadata fields)
  const indicatorNames = Object.keys(data[0]).filter(k => !PIVOT_EXCLUDE_KEYS.has(k))
  // Get periods sorted ascending
  const dataPeriods = data.map(d => d.end_date).sort()
  
  // Use safe colKey (replace - with _) to avoid Vue dynamic slot name parsing issues
  // e.g. "2023-12-31" -> "p_2023_12_31"
  const safeKey = (p: string) => 'p_' + p.replace(/-/g, '_')
  
  const columns: any[] = [
    { colKey: 'indicator', title: '指标', width: 180, fixed: 'left' as const }
  ]
  dataPeriods.forEach(p => {
    columns.push({
      colKey: safeKey(p),
      title: p,
      width: 140,
      align: 'right' as const,
      cell: (_h: any, { row }: any) => {
        const val = row[safeKey(p)]
        const formatted = formatAmount(val)
        const num = typeof val === 'string' ? parseFloat(val) : val
        const isNeg = typeof num === 'number' && !isNaN(num) && num < 0
        return h('span', { class: isNeg ? 'number-cell negative' : 'number-cell' }, formatted)
      }
    })
  })
  
  const rows = indicatorNames.map(ind => {
    const row: any = { indicator: ind }
    data.forEach(d => {
      row[safeKey(d.end_date)] = d[ind]
    })
    return row
  })
  
  return { columns, rows }
}

// Computed: income table
const incomeTable = computed(() => transformPivotToRows(incomeData.value))
// Computed: balance table
const balanceTable = computed(() => transformPivotToRows(balanceData.value))
// Computed: cashflow table
const cashflowTable = computed(() => transformPivotToRows(cashflowData.value))

// Statement sub-tab
const statementSubTab = ref('income')

// Fetch data
const handleSearch = async () => {
  if (!stockCode.value) {
    MessagePlugin.warning('请输入港股代码')
    return
  }
  
  loading.value = true
  financialData.value = null
  indicatorData.value = []
  incomeData.value = []
  balanceData.value = []
  cashflowData.value = []
  
  try {
    const [financialRes, indicatorRes, incomeRes, balanceRes, cashflowRes] = await Promise.all([
      hkReportApi.getFinancial({ code: stockCode.value, periods: periods.value }),
      hkReportApi.getIndicators({ code: stockCode.value, periods: periods.value }),
      hkReportApi.getIncome({ code: stockCode.value, periods: periods.value }),
      hkReportApi.getBalance({ code: stockCode.value, periods: periods.value }),
      hkReportApi.getCashflow({ code: stockCode.value, periods: periods.value })
    ])
    
    financialData.value = financialRes
    indicatorData.value = indicatorRes.data || []
    incomeData.value = incomeRes.data || []
    balanceData.value = balanceRes.data || []
    cashflowData.value = cashflowRes.data || []
    
    if (financialRes.status === 'error') {
      MessagePlugin.error(financialRes.error || '获取数据失败')
    }
  } catch (error: any) {
    console.error('Failed to load HK stock data:', error)
    MessagePlugin.error(error?.message || '获取港股数据失败')
  } finally {
    loading.value = false
  }
}

// Handle periods change
const handlePeriodsChange = () => {
  if (stockCode.value) {
    handleSearch()
  }
}

// Get health score color/theme
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

// Get value color for metric values (positive = green, negative = red)
const getValueColor = (val: any): string => {
  if (val === null || val === undefined || val === 'N/A' || val === '\\N' || val === 0) return 'var(--td-text-color-placeholder)'
  const num = typeof val === 'string' ? parseFloat(val) : val
  if (isNaN(num)) return 'var(--td-text-color-primary)'
  if (num > 0) return 'var(--td-success-color)'
  if (num < 0) return 'var(--td-error-color)'
  return 'var(--td-text-color-primary)'
}

// HK stock quick search examples
const exampleStocks = [
  { code: '00700', name: '腾讯控股' },
  { code: '09988', name: '阿里巴巴' },
  { code: '03690', name: '美团' },
  { code: '01810', name: '小米集团' },
  { code: '01211', name: '比亚迪股份' }
]

const selectExample = (code: string) => {
  stockCode.value = code
  handleSearch()
}

// ======== AI Analysis ========
const handleRefreshAnalysis = async () => {
  if (!stockCode.value) return
  analysisLoading.value = true
  try {
    analysisData.value = await hkReportApi.getAnalysis({ code: stockCode.value, periods: periods.value })
  } catch (error) {
    console.error('Failed to fetch HK AI analysis:', error)
  } finally {
    analysisLoading.value = false
  }
}

// Parse AI sections from markdown content
const aiSections = computed(() => {
  if (!analysisData.value?.content) return []
  const content = analysisData.value.content
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

// Filter AI sections - only keep 投资建议 (other sections duplicate static cards)
const aiUniqueSections = computed(() => {
  return aiSections.value.filter(section => section.title.includes('投资建议'))
})

const getSectionTheme = (title: string): string => {
  if (title.includes('优势')) return 'success'
  if (title.includes('关注')) return 'warning'
  if (title.includes('盈利')) return 'primary'
  if (title.includes('偿债')) return 'default'
  if (title.includes('成长')) return 'success'
  if (title.includes('投资建议')) return 'primary'
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

// ======== Trend Charts ========
const profitabilityChartRef = ref<HTMLElement>()
const marginChartRef = ref<HTMLElement>()
const epsChartRef = ref<HTMLElement>()
const valuationChartRef = ref<HTMLElement>()
const incomeChartRef = ref<HTMLElement>()
const balanceChartRef = ref<HTMLElement>()
const cashflowChartRef = ref<HTMLElement>()

let charts: echarts.ECharts[] = []

// Sorted data (ascending by end_date for charts)
const sortedIndicators = computed(() => {
  if (!indicatorData.value.length) return []
  return [...indicatorData.value].sort((a, b) => a.end_date.localeCompare(b.end_date))
})

const chartPeriods = computed(() => sortedIndicators.value.map(item => item.end_date))

const parseNum = (val: any): number | null => {
  if (val === null || val === undefined || val === '\\N' || val === 'N/A' || val === '') return null
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

// ROE & ROA
const initProfitabilityChart = () => {
  if (!profitabilityChartRef.value) return
  const roe = sortedIndicators.value.map(r => parseNum(r.roe_avg))
  const roa = sortedIndicators.value.map(r => parseNum(r.roa))
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
  const grossMargin = sortedIndicators.value.map(r => parseNum(r.gross_profit_ratio))
  const netMargin = sortedIndicators.value.map(r => parseNum(r.net_profit_ratio))
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

// EPS
const initEpsChart = () => {
  if (!epsChartRef.value) return
  const eps = sortedIndicators.value.map(r => parseNum(r.basic_eps))
  if (!hasMetricData(eps)) return
  const chart = echarts.init(epsChartRef.value)
  charts.push(chart)
  chart.setOption({
    ...baseOption('每股收益 (EPS)'),
    legend: { data: ['基本EPS'], top: 28 },
    yAxis: { type: 'value', name: '元' },
    series: [
      { name: '基本EPS', type: 'bar', data: eps, itemStyle: { color: '#722ed1', borderRadius: [4, 4, 0, 0] }, barMaxWidth: 40 }
    ]
  })
}

// PE & PB Valuation
const initValuationChart = () => {
  if (!valuationChartRef.value) return
  const pe = sortedIndicators.value.map(r => parseNum(r.pe_ttm))
  const pb = sortedIndicators.value.map(r => parseNum(r.pb_ttm))
  if (!hasMetricData(pe) && !hasMetricData(pb)) return
  const chart = echarts.init(valuationChartRef.value)
  charts.push(chart)
  chart.setOption({
    ...baseOption('估值：PE(TTM) & PB(TTM)'),
    legend: { data: ['PE(TTM)', 'PB(TTM)'], top: 28 },
    yAxis: [
      { type: 'value', name: 'PE', position: 'left' },
      { type: 'value', name: 'PB', position: 'right', splitLine: { show: false } }
    ],
    series: [
      { name: 'PE(TTM)', type: 'line', yAxisIndex: 0, data: pe, smooth: true, lineStyle: { color: '#13c2c2', width: 2 }, itemStyle: { color: '#13c2c2' }, symbol: 'circle', symbolSize: 6 },
      { name: 'PB(TTM)', type: 'line', yAxisIndex: 1, data: pb, smooth: true, lineStyle: { color: '#eb2f96', width: 2 }, itemStyle: { color: '#eb2f96' }, symbol: 'circle', symbolSize: 6 }
    ]
  })
}

// Income Structure Chart (利润结构)
const initIncomeChart = () => {
  if (!incomeChartRef.value || !incomeData.value.length) return
  const sortedIncome = [...incomeData.value].sort((a, b) => a.end_date.localeCompare(b.end_date))
  const incomePeriods = sortedIncome.map(d => d.end_date)
  const revenue = sortedIncome.map(d => parseNum(getPivotVal(d, '营业额', '营运收入', '营业收入', '营业总收入')))
  const grossProfit = sortedIncome.map(d => parseNum(getPivotVal(d, '毛利', '毛利润')))
  const operProfit = sortedIncome.map(d => parseNum(getPivotVal(d, '经营溢利', '营业利润')))
  const netProfit = sortedIncome.map(d => parseNum(getPivotVal(d, '股东应占溢利', '除税后溢利', '净利润')))
  if (!hasMetricData(revenue) && !hasMetricData(netProfit)) return
  const chart = echarts.init(incomeChartRef.value)
  charts.push(chart)
  chart.setOption({
    title: { text: '利润结构趋势', left: 'center', textStyle: { fontSize: 14, fontWeight: 500 } },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (v: any) => v !== null && v !== undefined ? (Math.abs(v) >= 1e8 ? (v/1e8).toFixed(2) + '亿' : (v/1e4).toFixed(2) + '万') : '-' },
    legend: { data: ['营业额', '毛利', '经营溢利', '股东应占溢利'], top: 28 },
    grid: { left: '3%', right: '4%', bottom: '3%', top: 60, containLabel: true },
    xAxis: { type: 'category', data: incomePeriods, axisLabel: { rotate: 30, fontSize: 11 } },
    yAxis: { type: 'value', axisLabel: { formatter: (v: number) => Math.abs(v) >= 1e8 ? (v/1e8).toFixed(0) + '亿' : (v/1e4).toFixed(0) + '万' } },
    series: [
      { name: '营业额', type: 'bar', data: revenue, itemStyle: { color: '#1890ff', borderRadius: [4, 4, 0, 0] }, barMaxWidth: 30 },
      { name: '毛利', type: 'bar', data: grossProfit, itemStyle: { color: '#52c41a', borderRadius: [4, 4, 0, 0] }, barMaxWidth: 30 },
      { name: '经营溢利', type: 'bar', data: operProfit, itemStyle: { color: '#faad14', borderRadius: [4, 4, 0, 0] }, barMaxWidth: 30 },
      { name: '股东应占溢利', type: 'bar', data: netProfit, itemStyle: { color: '#f5222d', borderRadius: [4, 4, 0, 0] }, barMaxWidth: 30 }
    ]
  })
}

// Balance Sheet Structure Chart (资产结构)
const initBalanceChart = () => {
  if (!balanceChartRef.value || !balanceData.value.length) return
  const sortedBalance = [...balanceData.value].sort((a, b) => a.end_date.localeCompare(b.end_date))
  const balPeriods = sortedBalance.map(d => d.end_date)
  const totalAssets = sortedBalance.map(d => parseNum(getPivotVal(d, '总资产', '资产总额')))
  const totalLiab = sortedBalance.map(d => parseNum(getPivotVal(d, '总负债', '负债总额')))
  const equity = sortedBalance.map(d => parseNum(getPivotVal(d, '股东权益', '总权益', '所有者权益')))
  if (!hasMetricData(totalAssets)) return
  const chart = echarts.init(balanceChartRef.value)
  charts.push(chart)
  chart.setOption({
    title: { text: '资产负债结构趋势', left: 'center', textStyle: { fontSize: 14, fontWeight: 500 } },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (v: any) => v !== null && v !== undefined ? (Math.abs(v) >= 1e8 ? (v/1e8).toFixed(2) + '亿' : (v/1e4).toFixed(2) + '万') : '-' },
    legend: { data: ['资产总额', '负债总额', '股东权益'], top: 28 },
    grid: { left: '3%', right: '4%', bottom: '3%', top: 60, containLabel: true },
    xAxis: { type: 'category', data: balPeriods, axisLabel: { rotate: 30, fontSize: 11 } },
    yAxis: { type: 'value', axisLabel: { formatter: (v: number) => Math.abs(v) >= 1e8 ? (v/1e8).toFixed(0) + '亿' : (v/1e4).toFixed(0) + '万' } },
    series: [
      { name: '资产总额', type: 'bar', data: totalAssets, itemStyle: { color: '#1890ff', borderRadius: [4, 4, 0, 0] }, barMaxWidth: 40 },
      { name: '负债总额', type: 'bar', data: totalLiab, itemStyle: { color: '#f5222d', borderRadius: [4, 4, 0, 0] }, barMaxWidth: 40 },
      { name: '股东权益', type: 'bar', data: equity, itemStyle: { color: '#52c41a', borderRadius: [4, 4, 0, 0] }, barMaxWidth: 40 }
    ]
  })
}

// Cash Flow Chart (现金流趋势)
const initCashflowChart = () => {
  if (!cashflowChartRef.value || !cashflowData.value.length) return
  const sortedCf = [...cashflowData.value].sort((a, b) => a.end_date.localeCompare(b.end_date))
  const cfPeriods = sortedCf.map(d => d.end_date)
  const operCf = sortedCf.map(d => parseNum(getPivotVal(d, '经营业务现金净额', '经营活动现金流量净额')))
  const investCf = sortedCf.map(d => parseNum(getPivotVal(d, '投资业务现金净额', '投资活动现金流量净额')))
  const financeCf = sortedCf.map(d => parseNum(getPivotVal(d, '融资业务现金净额', '筹资活动现金流量净额')))
  if (!hasMetricData(operCf) && !hasMetricData(investCf) && !hasMetricData(financeCf)) return
  const chart = echarts.init(cashflowChartRef.value)
  charts.push(chart)
  chart.setOption({
    title: { text: '现金流量趋势', left: 'center', textStyle: { fontSize: 14, fontWeight: 500 } },
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' }, valueFormatter: (v: any) => v !== null && v !== undefined ? (Math.abs(v) >= 1e8 ? (v/1e8).toFixed(2) + '亿' : (v/1e4).toFixed(2) + '万') : '-' },
    legend: { data: ['经营活动', '投资活动', '筹资活动'], top: 28 },
    grid: { left: '3%', right: '4%', bottom: '3%', top: 60, containLabel: true },
    xAxis: { type: 'category', data: cfPeriods, axisLabel: { rotate: 30, fontSize: 11 } },
    yAxis: { type: 'value', axisLabel: { formatter: (v: number) => Math.abs(v) >= 1e8 ? (v/1e8).toFixed(0) + '亿' : (v/1e4).toFixed(0) + '万' } },
    series: [
      { name: '经营活动', type: 'bar', data: operCf, itemStyle: { color: '#52c41a', borderRadius: [4, 4, 0, 0] }, barMaxWidth: 30 },
      { name: '投资活动', type: 'bar', data: investCf, itemStyle: { color: '#faad14', borderRadius: [4, 4, 0, 0] }, barMaxWidth: 30 },
      { name: '筹资活动', type: 'bar', data: financeCf, itemStyle: { color: '#722ed1', borderRadius: [4, 4, 0, 0] }, barMaxWidth: 30 }
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
  if (!sortedIndicators.value.length && !incomeData.value.length) return
  initProfitabilityChart()
  initMarginChart()
  initEpsChart()
  initValuationChart()
  initIncomeChart()
  initBalanceChart()
  initCashflowChart()
}

const handleResize = () => {
  charts.forEach(c => c.resize())
}

// When tab switches to charts, initialize them
watch(activeTab, (val) => {
  if (val === 'charts' && (sortedIndicators.value.length || incomeData.value.length)) {
    setTimeout(initAllCharts, 100)
  }
})

// Re-init when data changes while on charts tab
watch([indicatorData, incomeData, balanceData, cashflowData], () => {
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
  <div class="hk-financial-panel">
    <!-- Header with search -->
    <div class="panel-header">
      <t-space>
        <t-input
          v-model="stockCode"
          placeholder="输入港股代码 (如 00700)"
          style="width: 200px"
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
    <div v-if="!stockCode || (!hasData && !loading)" class="empty-state">
      <t-icon name="chart-line" size="64px" style="color: #ddd" />
      <h3>港股财报分析</h3>
      <p>请输入港股代码开始分析</p>
      <div class="example-stocks">
        <span class="example-label">热门港股：</span>
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
      <t-loading size="large" text="正在加载港股财务数据..." />
    </div>

    <!-- Main Content -->
    <div v-else-if="hasData" class="report-content">
      <!-- Stock Header -->
      <div class="stock-header">
        <div class="stock-info">
          <h2>{{ stockName }}</h2>
          <t-tag theme="warning">{{ stockCode.includes('.HK') ? stockCode : stockCode + '.HK' }}</t-tag>
          <t-tag variant="outline">港股</t-tag>
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
                    <span class="kv-key">ROE (加权平均)</span>
                    <span class="kv-value" :style="{ color: getValueColor(financialData?.summary?.profitability?.roe_avg) }">
                      {{ formatValue(financialData?.summary?.profitability?.roe_avg) }}%
                    </span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">ROA</span>
                    <span class="kv-value" :style="{ color: getValueColor(financialData?.summary?.profitability?.roa) }">
                      {{ formatValue(financialData?.summary?.profitability?.roa) }}%
                    </span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">毛利率</span>
                    <span class="kv-value" :style="{ color: getValueColor(financialData?.summary?.profitability?.gross_profit_ratio) }">
                      {{ formatValue(financialData?.summary?.profitability?.gross_profit_ratio) }}%
                    </span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">净利率</span>
                    <span class="kv-value" :style="{ color: getValueColor(financialData?.summary?.profitability?.net_profit_ratio) }">
                      {{ formatValue(financialData?.summary?.profitability?.net_profit_ratio) }}%
                    </span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">基本每股收益</span>
                    <span class="kv-value">
                      {{ formatValue(financialData?.summary?.profitability?.basic_eps) }}
                    </span>
                  </div>
                </div>
              </div>

              <!-- Valuation -->
              <div class="section-card theme-default">
                <div class="section-title">
                  <span class="section-icon">💰</span>
                  <span>估值指标</span>
                </div>
                <div class="kv-list">
                  <div class="kv-item">
                    <span class="kv-key">PE (TTM)</span>
                    <span class="kv-value">{{ formatValue(financialData?.summary?.valuation?.pe_ttm) }}</span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">PB (TTM)</span>
                    <span class="kv-value">{{ formatValue(financialData?.summary?.valuation?.pb_ttm) }}</span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">总市值</span>
                    <span class="kv-value">{{ financialData?.summary?.valuation?.total_market_cap || '-' }}</span>
                  </div>
                </div>
              </div>

              <!-- Income Summary (latest period) -->
              <div v-if="incomeData.length" class="section-card theme-primary">
                <div class="section-title">
                  <span class="section-icon">📊</span>
                  <span>利润结构（{{ incomeData[0]?.end_date || '最新期' }}）</span>
                </div>
                <div class="kv-list">
                  <div class="kv-item">
                    <span class="kv-key">营业额</span>
                    <span class="kv-value">{{ formatAmount(getPivotVal(incomeData[0], '营业额', '营运收入', '营业收入')) }}</span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">营运支出</span>
                    <span class="kv-value">{{ formatAmount(getPivotVal(incomeData[0], '营运支出', '营业成本')) }}</span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">毛利</span>
                    <span class="kv-value" :style="{ color: getValueColor(getPivotVal(incomeData[0], '毛利', '毛利润')) }">{{ formatAmount(getPivotVal(incomeData[0], '毛利', '毛利润')) }}</span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">经营溢利</span>
                    <span class="kv-value" :style="{ color: getValueColor(getPivotVal(incomeData[0], '经营溢利', '营业利润')) }">{{ formatAmount(getPivotVal(incomeData[0], '经营溢利', '营业利润')) }}</span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">股东应占溢利</span>
                    <span class="kv-value" :style="{ color: getValueColor(getPivotVal(incomeData[0], '股东应占溢利', '除税后溢利', '净利润')) }">{{ formatAmount(getPivotVal(incomeData[0], '股东应占溢利', '除税后溢利', '净利润')) }}</span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">每股基本盈利</span>
                    <span class="kv-value">{{ formatValue(getPivotVal(incomeData[0], '每股基本盈利', '基本每股收益')) }}</span>
                  </div>
                </div>
              </div>

              <!-- Balance Sheet Summary -->
              <div v-if="balanceData.length" class="section-card theme-default">
                <div class="section-title">
                  <span class="section-icon">🏦</span>
                  <span>资产负债（{{ balanceData[0]?.end_date || '最新期' }}）</span>
                </div>
                <div class="kv-list">
                  <div class="kv-item">
                    <span class="kv-key">总资产</span>
                    <span class="kv-value">{{ formatAmount(getPivotVal(balanceData[0], '总资产', '资产总额')) }}</span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">总负债</span>
                    <span class="kv-value" style="color: var(--td-error-color)">{{ formatAmount(getPivotVal(balanceData[0], '总负债', '负债总额')) }}</span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">股东权益</span>
                    <span class="kv-value" style="color: var(--td-success-color)">{{ formatAmount(getPivotVal(balanceData[0], '股东权益', '总权益', '所有者权益')) }}</span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">流动资产</span>
                    <span class="kv-value">{{ formatAmount(getPivotVal(balanceData[0], '流动资产合计', '流动资产')) }}</span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">流动负债</span>
                    <span class="kv-value">{{ formatAmount(getPivotVal(balanceData[0], '流动负债合计', '流动负债')) }}</span>
                  </div>
                </div>
              </div>

              <!-- Cash Flow Summary -->
              <div v-if="cashflowData.length" class="section-card theme-success">
                <div class="section-title">
                  <span class="section-icon">💵</span>
                  <span>现金流量（{{ cashflowData[0]?.end_date || '最新期' }}）</span>
                </div>
                <div class="kv-list">
                  <div class="kv-item">
                    <span class="kv-key">经营业务现金净额</span>
                    <span class="kv-value" :style="{ color: getValueColor(getPivotVal(cashflowData[0], '经营业务现金净额', '经营活动现金流量净额')) }">{{ formatAmount(getPivotVal(cashflowData[0], '经营业务现金净额', '经营活动现金流量净额')) }}</span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">投资业务现金净额</span>
                    <span class="kv-value" :style="{ color: getValueColor(getPivotVal(cashflowData[0], '投资业务现金净额', '投资活动现金流量净额')) }">{{ formatAmount(getPivotVal(cashflowData[0], '投资业务现金净额', '投资活动现金流量净额')) }}</span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">融资业务现金净额</span>
                    <span class="kv-value" :style="{ color: getValueColor(getPivotVal(cashflowData[0], '融资业务现金净额', '筹资活动现金流量净额')) }">{{ formatAmount(getPivotVal(cashflowData[0], '融资业务现金净额', '筹资活动现金流量净额')) }}</span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">期末现金</span>
                    <span class="kv-value">{{ formatAmount(getPivotVal(cashflowData[0], '期末现金', '期末现金及等价物余额')) }}</span>
                  </div>
                </div>
              </div>

              <!-- Strengths -->
              <div class="section-card theme-success">
                <div class="section-title">
                  <span class="section-icon">💪</span>
                  <span>主要优势</span>
                </div>
                <div class="item-list">
                  <div
                    v-for="(s, i) in (financialData?.health_analysis?.strengths || ['暂无明显优势'])"
                    :key="i"
                    class="list-item"
                  >
                    <t-icon name="check-circle-filled" class="icon-success" size="16px" />
                    <span>{{ s }}</span>
                  </div>
                </div>
              </div>

              <!-- Weaknesses -->
              <div class="section-card theme-warning">
                <div class="section-title">
                  <span class="section-icon">⚠️</span>
                  <span>关注点</span>
                </div>
                <div class="item-list">
                  <div
                    v-for="(w, i) in (financialData?.health_analysis?.weaknesses || ['财务状况良好，无明显风险点'])"
                    :key="i"
                    class="list-item"
                  >
                    <t-icon name="error-circle-filled" class="icon-warning" size="16px" />
                    <span>{{ w }}</span>
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
                    <span class="kv-value">{{ financialData?.summary?.name || '-' }}</span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">最新财报</span>
                    <span class="kv-value">{{ financialData?.summary?.latest_period || '-' }}</span>
                  </div>
                  <div class="kv-item">
                    <span class="kv-key">分析期数</span>
                    <span class="kv-value">{{ financialData?.summary?.periods || '-' }}期</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- AI Analysis Section -->
            <div v-if="analysisLoading" class="ai-loading-section">
              <t-divider>AI 智能分析</t-divider>
              <div class="loading-container" style="height: 120px">
                <t-loading size="large" text="AI 正在分析中..." />
              </div>
            </div>

            <div v-else-if="analysisData" class="ai-merged-section">
              <t-divider>AI 智能分析</t-divider>

              <!-- AI-only Section Cards (exclude duplicates) -->
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

              <div class="ai-refresh-bar">
                <t-button theme="primary" variant="outline" size="small" :loading="analysisLoading" @click="handleRefreshAnalysis">
                  <template #icon><t-icon name="refresh" /></template>
                  刷新AI分析
                </t-button>
              </div>
            </div>

            <div v-else class="ai-empty-section">
              <t-divider>AI 智能分析</t-divider>
              <div class="empty-container" style="height: 120px">
                <t-button theme="primary" @click="handleRefreshAnalysis">开始AI分析</t-button>
              </div>
            </div>
          </div>
        </t-tab-panel>

        <!-- Trend Charts Tab -->
        <t-tab-panel value="charts" label="趋势图表">
          <t-card title="数据可视化" :bordered="false">
            <div v-if="loading" class="loading-container">
              <t-loading size="large" text="加载图表数据..." />
            </div>
            <div v-else-if="!indicatorData.length && !incomeData.length" class="empty-container">
              <t-empty description="暂无趋势数据" />
            </div>
            <div v-else class="charts-grid">
              <div class="chart-item">
                <div ref="profitabilityChartRef" class="chart-container" />
              </div>
              <div class="chart-item">
                <div ref="marginChartRef" class="chart-container" />
              </div>
              <div class="chart-item">
                <div ref="epsChartRef" class="chart-container" />
              </div>
              <div class="chart-item">
                <div ref="valuationChartRef" class="chart-container" />
              </div>
              <div v-if="incomeData.length" class="chart-item">
                <div ref="incomeChartRef" class="chart-container" />
              </div>
              <div v-if="balanceData.length" class="chart-item">
                <div ref="balanceChartRef" class="chart-container" />
              </div>
              <div v-if="cashflowData.length" class="chart-item full-width-chart">
                <div ref="cashflowChartRef" class="chart-container" />
              </div>
            </div>
          </t-card>
        </t-tab-panel>

        <!-- Financial Statements Tab -->
        <t-tab-panel value="statements" label="三大报表">
          <t-card :bordered="false">
            <div class="statements-header">
              <t-radio-group v-model="statementSubTab" variant="default-filled" size="small">
                <t-radio-button value="income">利润表</t-radio-button>
                <t-radio-button value="balance">资产负债表</t-radio-button>
                <t-radio-button value="cashflow">现金流量表</t-radio-button>
              </t-radio-group>
            </div>

            <!-- Income Statement -->
            <div v-if="statementSubTab === 'income'">
              <div v-if="!incomeData.length" class="empty-container" style="height: 200px">
                <t-empty description="暂无利润表数据" />
              </div>
              <t-table
                v-else
                :data="incomeTable.rows"
                :columns="incomeTable.columns"
                :loading="loading"
                row-key="indicator"
                :scroll="{ x: 900 }"
                :pagination="false"
                size="small"
                stripe
              />
            </div>

            <!-- Balance Sheet -->
            <div v-if="statementSubTab === 'balance'">
              <div v-if="!balanceData.length" class="empty-container" style="height: 200px">
                <t-empty description="暂无资产负债表数据" />
              </div>
              <t-table
                v-else
                :data="balanceTable.rows"
                :columns="balanceTable.columns"
                :loading="loading"
                row-key="indicator"
                :scroll="{ x: 900 }"
                :pagination="false"
                size="small"
                stripe
              />
            </div>

            <!-- Cash Flow -->
            <div v-if="statementSubTab === 'cashflow'">
              <div v-if="!cashflowData.length" class="empty-container" style="height: 200px">
                <t-empty description="暂无现金流量表数据" />
              </div>
              <t-table
                v-else
                :data="cashflowTable.rows"
                :columns="cashflowTable.columns"
                :loading="loading"
                row-key="indicator"
                :scroll="{ x: 900 }"
                :pagination="false"
                size="small"
                stripe
              />
            </div>
          </t-card>
        </t-tab-panel>

        <!-- Indicators Table Tab -->
        <t-tab-panel value="indicators" label="财务指标">
          <t-card title="港股财务指标明细" :bordered="false">
            <t-table
              :data="indicatorData"
              :columns="indicatorColumns"
              :loading="loading"
              row-key="end_date"
              :scroll="{ x: 900 }"
              :pagination="false"
              size="small"
            >
              <template #roe_avg="{ row }">
                <span class="number-cell" :class="{ positive: parseFloat(row.roe_avg) > 15, negative: parseFloat(row.roe_avg) < 5 }">
                  {{ formatValue(row.roe_avg) }}
                </span>
              </template>
              <template #roa="{ row }">
                <span class="number-cell">{{ formatValue(row.roa) }}</span>
              </template>
              <template #gross_profit_ratio="{ row }">
                <span class="number-cell">{{ formatValue(row.gross_profit_ratio) }}</span>
              </template>
              <template #net_profit_ratio="{ row }">
                <span class="number-cell">{{ formatValue(row.net_profit_ratio) }}</span>
              </template>
              <template #basic_eps="{ row }">
                <span class="number-cell">{{ formatValue(row.basic_eps) }}</span>
              </template>
              <template #pe_ttm="{ row }">
                <span class="number-cell">{{ formatValue(row.pe_ttm) }}</span>
              </template>
              <template #pb_ttm="{ row }">
                <span class="number-cell">{{ formatValue(row.pb_ttm) }}</span>
              </template>
              <template #debt_asset_ratio="{ row }">
                <span class="number-cell" :class="{ negative: parseFloat(row.debt_asset_ratio) > 70 }">{{ formatValue(row.debt_asset_ratio) }}</span>
              </template>
              <template #current_ratio="{ row }">
                <span class="number-cell" :class="{ positive: parseFloat(row.current_ratio) > 2 }">{{ formatValue(row.current_ratio) }}</span>
              </template>
              <template #equity_multiplier="{ row }">
                <span class="number-cell">{{ formatValue(row.equity_multiplier) }}</span>
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
      <p>无法获取 {{ stockCode }} 的港股财务数据</p>
      <t-button theme="primary" @click="handleSearch">重试</t-button>
    </div>
  </div>
</template>

<style scoped>
.hk-financial-panel {
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

/* Analysis Content - matches AIInsight.vue */
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
.icon-default { color: var(--td-text-color-secondary); }

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

/* Number cells in table */
.number-cell {
  font-family: 'Monaco', 'Menlo', monospace;
  text-align: right;
}

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

.chart-item.full-width-chart {
  grid-column: 1 / -1;
}

.chart-container {
  width: 100%;
  height: 320px;
}

/* Statements */
.statements-header {
  margin-bottom: 16px;
}

.loading-container,
.empty-container {
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

.positive {
  color: var(--td-success-color);
  font-weight: 500;
}

.negative {
  color: var(--td-error-color);
  font-weight: 500;
}

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

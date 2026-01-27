<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, computed, nextTick } from 'vue'
import * as echarts from 'echarts'
import type { KLineData } from '@/types/common'

const props = defineProps<{
  data: KLineData[]
  indicators?: Record<string, number[]>
  indicatorDates?: string[]
  selectedIndicators?: string[]
  loading?: boolean
  height?: number | string
}>()

const chartRef = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

// Indicator colors
const indicatorColors: Record<string, string> = {
  MA5: '#ff9500',   // 橙色 - 5日均线
  MA10: '#9b59b6',  // 紫色 - 10日均线
  MA20: '#1e3a5f',  // 深蓝色 - 20日均线
  MA60: '#4a4a4a',  // 深灰色 - 60日均线
  EMA12: '#ffaa00',
  EMA26: '#00aaff',
  DIF: '#ff6b6b',
  DEA: '#4ecdc4',
  MACD: '#95a5a6',
  RSI14: '#9b59b6',
  K: '#e74c3c',
  D: '#3498db',
  J: '#f1c40f',
  BOLL_UPPER: '#e74c3c',
  BOLL_MIDDLE: '#3498db',
  BOLL_LOWER: '#2ecc71',
  CCI14: '#e67e22',
  // DMI
  PDI: '#e74c3c',
  MDI: '#2ecc71',
  ADX: '#3498db',
  // OBV
  OBV: '#9b59b6',
  // ATR
  ATR14: '#e67e22',
}

const chartHeight = computed(() => {
  if (typeof props.height === 'string') {
    return props.height
  }
  return props.height ? `${props.height}px` : '600px'
})

// Determine which indicators go in main chart vs sub charts
const mainChartIndicators = ['MA5', 'MA10', 'MA20', 'MA60', 'EMA12', 'EMA26', 'BOLL_UPPER', 'BOLL_MIDDLE', 'BOLL_LOWER']
const macdIndicators = ['DIF', 'DEA', 'MACD']
const rsiIndicators = ['RSI14', 'RSI']
const kdjIndicators = ['K', 'D', 'J']
const cciIndicators = ['CCI14', 'CCI']
const dmiIndicators = ['PDI', 'MDI', 'ADX']

const hasMACD = computed(() => {
  if (!props.indicators) return false
  return macdIndicators.some(k => props.indicators![k]?.length > 0)
})

const hasRSI = computed(() => {
  if (!props.indicators) return false
  return Object.keys(props.indicators).some(k => k.startsWith('RSI') && props.indicators![k]?.length > 0)
})

const hasKDJ = computed(() => {
  if (!props.indicators) return false
  return kdjIndicators.some(k => props.indicators![k]?.length > 0)
})

const hasCCI = computed(() => {
  if (!props.indicators) return false
  return Object.keys(props.indicators).some(k => k.startsWith('CCI') && props.indicators![k]?.length > 0)
})

const hasDMI = computed(() => {
  if (!props.indicators) return false
  return dmiIndicators.some(k => props.indicators![k]?.length > 0)
})

const hasOBV = computed(() => {
  if (!props.indicators) return false
  return props.indicators.OBV?.length > 0
})

const hasATR = computed(() => {
  if (!props.indicators) return false
  return Object.keys(props.indicators).some(k => k.startsWith('ATR') && props.indicators![k]?.length > 0)
})

const initChart = () => {
  if (!chartRef.value) return
  
  // 确保容器有实际尺寸
  const rect = chartRef.value.getBoundingClientRect()
  if (rect.width === 0 || rect.height === 0) {
    // 延迟初始化，等待容器尺寸确定
    requestAnimationFrame(initChart)
    return
  }
  
  chart = echarts.init(chartRef.value)
  updateChart()
}

const updateChart = () => {
  if (!chart || !props.data.length) return

  const dates = props.data.map(d => d.date)
  const klineData = props.data.map(d => [d.open, d.close, d.low, d.high])
  const volumeData = props.data.map((d, i) => ({
    value: d.volume,
    itemStyle: {
      color: d.close >= d.open ? '#ec0000' : '#228B22'
    }
  }))

  // 计算缩放参数
  const totalBars = dates.length
  const minBars = 15   // 最少显示15根柱子
  const maxBars = 180  // 最多显示180根柱子
  
  // 计算 minSpan 和 maxSpan (百分比)
  const minSpanPercent = Math.min(100, (minBars / totalBars) * 100)
  const maxSpanPercent = Math.min(100, (maxBars / totalBars) * 100)
  
  // 默认显示全部柱子
  const zoomStart = 0
  const zoomEnd = 100

  // Create a date-to-index mapping for aligning indicator data with kline data
  const dateToKlineIndex = new Map<string, number>()
  dates.forEach((date, index) => {
    dateToKlineIndex.set(date, index)
  })

  // Function to align indicator data with kline dates
  const alignIndicatorData = (indicatorValues: number[], indicatorDates?: string[]): (number | null)[] => {
    if (!indicatorDates || indicatorDates.length === 0) {
      // If no indicator dates provided, assume data is already aligned
      return indicatorValues
    }
    
    // Create aligned array with nulls for missing data
    const aligned: (number | null)[] = new Array(dates.length).fill(null)
    
    indicatorDates.forEach((date, i) => {
      const klineIndex = dateToKlineIndex.get(date)
      if (klineIndex !== undefined && i < indicatorValues.length) {
        aligned[klineIndex] = indicatorValues[i]
      }
    })
    
    return aligned
  }

  // Calculate grid layout based on sub-indicators
  const grids: any[] = []
  const xAxes: any[] = []
  const yAxes: any[] = []
  const series: any[] = []
  
  // Count how many sub-charts we need
  const subCharts: string[] = []
  if (hasMACD.value) subCharts.push('MACD')
  if (hasKDJ.value) subCharts.push('KDJ')
  if (hasRSI.value) subCharts.push('RSI')
  if (hasCCI.value) subCharts.push('CCI')
  if (hasDMI.value) subCharts.push('DMI')
  if (hasOBV.value) subCharts.push('OBV')
  if (hasATR.value) subCharts.push('ATR')
  
  const subChartCount = subCharts.length
  const hasSubCharts = subChartCount > 0
  
  // ========== 动态布局参数 ==========
  // 主图占 50%，成交量和其他子图均分剩余 50%
  const totalAvailable = 99  // 100% - 1% 顶部边距
  const mainSubGap = 6       // 主图和子图区域之间的间距（增大以避免坐标重合）
  const subChartGapVal = 2   // 子图之间的间距
  
  // 主图固定占 48%
  const mainHeightVal = 48
  
  // 成交量也算作子图，和 MACD/KDJ/RSI/CCI 等一起均分剩余空间
  // 子图总数 = 成交量(1) + 其他子图数量
  const totalSubChartCount = 1 + subChartCount  // 成交量 + 其他指标子图
  
  // 计算子图高度（包括成交量）
  // 剩余空间 = 总可用 - 主图高度 - 主图与子图间距 - 子图之间的间距
  const totalSubGaps = subChartGapVal * (totalSubChartCount - 1)  // 子图之间的间距数量
  const remainingForSubs = totalAvailable - mainHeightVal - mainSubGap - totalSubGaps
  const subChartHeightVal = Math.floor(remainingForSubs / totalSubChartCount)
  
  // 成交量和其他子图使用相同高度
  const volumeHeightVal = subChartHeightVal
  
  const mainHeight = `${mainHeightVal}%`
  const volumeHeight = `${volumeHeightVal}%`
  const subChartHeight = `${subChartHeightVal}%`
  const subChartGap = subChartGapVal
  
  // Chart background colors - distinct colors for each chart type
  const chartColors = {
    main: { bg: 'rgba(255, 255, 255, 0.95)', border: '#a0a8b0' },
    volume: { bg: 'rgba(230, 240, 255, 0.95)', border: '#8098b8' },
    macd: { bg: 'rgba(255, 245, 235, 0.95)', border: '#c89868' },
    kdj: { bg: 'rgba(235, 255, 245, 0.95)', border: '#68b888' },
    rsi: { bg: 'rgba(245, 235, 255, 0.95)', border: '#9878b8' },
    default: { bg: 'rgba(245, 248, 252, 0.95)', border: '#a0a8b0' }
  }
  
  const mainHeightNum = mainHeightVal
  const volumeHeightNum = volumeHeightVal
  const subChartHeightNum = subChartHeightVal
  
  // Main chart grid - with distinct border and shadow
  const mainTopVal = 1 // Start at 1%
  grids.push({ 
    left: '8%', 
    right: '8%', 
    top: `${mainTopVal}%`, 
    height: mainHeight, 
    containLabel: false,
    backgroundColor: chartColors.main.bg,
    borderColor: chartColors.main.border,
    borderWidth: 2,
    shadowBlur: 8,
    shadowColor: 'rgba(0, 0, 0, 0.15)',
    shadowOffsetX: 0,
    shadowOffsetY: 3
  })
  xAxes.push({ type: 'category', data: dates, gridIndex: 0, boundaryGap: true, axisLine: { onZero: false, lineStyle: { color: '#ccc' } } })
  yAxes.push({ type: 'value', gridIndex: 0, scale: true, splitArea: { show: true, areaStyle: { color: ['rgba(255,255,255,0.5)', 'rgba(245,245,245,0.5)'] } }, boundaryGap: ['5%', '5%'], axisLine: { lineStyle: { color: '#ccc' } } })
  
  // Graphic elements for chart titles
  const graphicElements: any[] = []
  
  // K-line chart title - placed on left side, vertically centered
  const mainChartCenterTop = `${mainTopVal + mainHeightNum / 2}%`
  graphicElements.push({
    type: 'text',
    left: '1%',
    top: mainChartCenterTop,
    style: { text: 'K线图', fontSize: 12, fontWeight: 'bold', fill: '#333', verticalAlign: 'middle' }
  })
  
  // K-line series
  series.push({
    name: 'K线',
    type: 'candlestick',
    data: klineData,
    xAxisIndex: 0,
    yAxisIndex: 0,
    barMaxWidth: 20,  // 最大柱宽20px，保持协调比例
    barMinWidth: 1,   // 最小柱宽1px
    itemStyle: {
      color: '#ec0000',
      color0: '#228B22',
      borderColor: '#ec0000',
      borderColor0: '#228B22'
    }
  })

  // Add main chart indicators (MA, BOLL, etc.)
  if (props.indicators) {
    for (const [key, values] of Object.entries(props.indicators)) {
      if (mainChartIndicators.includes(key) && values?.length > 0) {
        const alignedData = alignIndicatorData(values, props.indicatorDates)
        series.push({
          name: key,
          type: 'line',
          data: alignedData,
          xAxisIndex: 0,
          yAxisIndex: 0,
          smooth: true,
          showSymbol: false,
          connectNulls: true,
          lineStyle: { width: 1.5, color: indicatorColors[key] || '#888' }
        })
      }
    }
  }

  // Volume grid - distinct blue-tinted background
  // Volume top = main top + main height + mainSubGap (间距)
  const volumeTopVal = mainTopVal + mainHeightNum + mainSubGap
  const volumeTop = `${volumeTopVal}%`
  grids.push({ 
    left: '8%', 
    right: '8%', 
    top: volumeTop, 
    height: volumeHeight, 
    containLabel: false,
    backgroundColor: chartColors.volume.bg,
    borderColor: chartColors.volume.border,
    borderWidth: 2,
    shadowBlur: 6,
    shadowColor: 'rgba(0, 0, 0, 0.12)',
    shadowOffsetX: 0,
    shadowOffsetY: 3
  })
  xAxes.push({ type: 'category', data: dates, gridIndex: 1, boundaryGap: true, axisLine: { onZero: false, lineStyle: { color: '#ccc' } }, axisTick: { show: false }, axisLabel: { show: false } })
  yAxes.push({ type: 'value', gridIndex: 1, scale: true, splitNumber: 2, boundaryGap: ['5%', '5%'], splitLine: { lineStyle: { color: '#eee' } }, axisLine: { lineStyle: { color: '#ccc' } } })
  
  // Volume chart title - placed on left side, vertically centered
  graphicElements.push({
    type: 'text',
    left: '1%',
    top: `${volumeTopVal + volumeHeightNum / 2}%`,
    style: { text: '成交量', fontSize: 12, fontWeight: 'bold', fill: '#333', verticalAlign: 'middle' }
  })
  
  series.push({
    name: '成交量',
    type: 'bar',
    data: volumeData,
    xAxisIndex: 1,
    yAxisIndex: 1,
    barMaxWidth: 20,  // 与K线保持一致
    barMinWidth: 1
  })

  // Add sub-charts dynamically - start after volume chart
  let subChartTop = volumeTopVal + volumeHeightNum + subChartGap
  
  // Helper function to create grid with distinct background color for each sub-chart type
  const createSubChartGrid = (top: string, chartType: string) => {
    const colors = chartType === 'MACD' ? chartColors.macd :
                   chartType === 'KDJ' ? chartColors.kdj :
                   chartType === 'RSI' ? chartColors.rsi :
                   chartColors.default
    return {
      left: '8%',
      right: '8%',
      top: top,
      height: subChartHeight,
      containLabel: false,
      backgroundColor: colors.bg,
      borderColor: colors.border,
      borderWidth: 2,
      shadowBlur: 6,
      shadowColor: 'rgba(0, 0, 0, 0.12)',
      shadowOffsetX: 0,
      shadowOffsetY: 3
    }
  }

  // MACD sub-chart
  if (hasMACD.value && props.indicators) {
    grids.push(createSubChartGrid(`${subChartTop}%`, 'MACD'))
    const axisIndex = grids.length - 1
    xAxes.push({ type: 'category', data: dates, gridIndex: axisIndex, boundaryGap: true, axisLine: { onZero: false, lineStyle: { color: '#ccc' } }, axisTick: { show: false }, axisLabel: { show: false } })
    yAxes.push({ type: 'value', gridIndex: axisIndex, scale: true, splitNumber: 2, boundaryGap: ['5%', '5%'], splitLine: { lineStyle: { color: '#eee' } }, axisLine: { lineStyle: { color: '#ccc' } } })
    
    graphicElements.push({
      type: 'text',
      left: '1%',
      top: `${subChartTop + subChartHeightNum / 2}%`,
      style: { text: 'MACD', fontSize: 12, fontWeight: 'bold', fill: '#333', verticalAlign: 'middle' }
    })
    
    if (props.indicators.DIF?.length > 0) {
      const alignedData = alignIndicatorData(props.indicators.DIF, props.indicatorDates)
      series.push({
        name: 'DIF',
        type: 'line',
        data: alignedData,
        xAxisIndex: axisIndex,
        yAxisIndex: axisIndex,
        smooth: true,
        showSymbol: false,
        connectNulls: true,
        lineStyle: { width: 1.5, color: indicatorColors.DIF }
      })
    }
    if (props.indicators.DEA?.length > 0) {
      const alignedData = alignIndicatorData(props.indicators.DEA, props.indicatorDates)
      series.push({
        name: 'DEA',
        type: 'line',
        data: alignedData,
        xAxisIndex: axisIndex,
        yAxisIndex: axisIndex,
        smooth: true,
        showSymbol: false,
        connectNulls: true,
        lineStyle: { width: 1.5, color: indicatorColors.DEA }
      })
    }
    if (props.indicators.MACD?.length > 0) {
      const alignedData = alignIndicatorData(props.indicators.MACD, props.indicatorDates)
      series.push({
        name: 'MACD',
        type: 'bar',
        data: alignedData.map(v => v === null ? null : ({
          value: v,
          itemStyle: { color: v >= 0 ? '#ec0000' : '#228B22' }
        })),
        xAxisIndex: axisIndex,
        yAxisIndex: axisIndex,
        barMaxWidth: 20,  // 与K线保持一致
        barMinWidth: 1
      })
    }
    subChartTop += subChartHeightNum + subChartGap
  }

  // KDJ sub-chart
  if (hasKDJ.value && props.indicators) {
    grids.push(createSubChartGrid(`${subChartTop}%`, 'KDJ'))
    const axisIndex = grids.length - 1
    xAxes.push({ type: 'category', data: dates, gridIndex: axisIndex, boundaryGap: true, axisLine: { onZero: false, lineStyle: { color: '#ccc' } }, axisTick: { show: false }, axisLabel: { show: false } })
    yAxes.push({ type: 'value', gridIndex: axisIndex, scale: true, splitNumber: 2, boundaryGap: ['5%', '5%'], splitLine: { lineStyle: { color: '#eee' } }, axisLine: { lineStyle: { color: '#ccc' } } })
    
    graphicElements.push({
      type: 'text',
      left: '1%',
      top: `${subChartTop + subChartHeightNum / 2}%`,
      style: { text: 'KDJ', fontSize: 12, fontWeight: 'bold', fill: '#333', verticalAlign: 'middle' }
    })
    
    for (const key of kdjIndicators) {
      if (props.indicators[key]?.length > 0) {
        const alignedData = alignIndicatorData(props.indicators[key], props.indicatorDates)
        series.push({
          name: key,
          type: 'line',
          data: alignedData,
          xAxisIndex: axisIndex,
          yAxisIndex: axisIndex,
          smooth: true,
          showSymbol: false,
          connectNulls: true,
          lineStyle: { width: 1.5, color: indicatorColors[key] }
        })
      }
    }
    subChartTop += subChartHeightNum + subChartGap
  }

  // RSI sub-chart
  if (hasRSI.value && props.indicators) {
    grids.push(createSubChartGrid(`${subChartTop}%`, 'RSI'))
    const axisIndex = grids.length - 1
    xAxes.push({ type: 'category', data: dates, gridIndex: axisIndex, boundaryGap: true, axisLine: { onZero: false, lineStyle: { color: '#ccc' } }, axisTick: { show: false }, axisLabel: { show: false } })
    yAxes.push({ type: 'value', gridIndex: axisIndex, scale: true, splitNumber: 2, boundaryGap: ['5%', '5%'], splitLine: { lineStyle: { color: '#eee' } }, axisLine: { lineStyle: { color: '#ccc' } } })
    
    graphicElements.push({
      type: 'text',
      left: '1%',
      top: `${subChartTop + subChartHeightNum / 2}%`,
      style: { text: 'RSI', fontSize: 12, fontWeight: 'bold', fill: '#333', verticalAlign: 'middle' }
    })
    
    for (const [key, values] of Object.entries(props.indicators)) {
      if (key.startsWith('RSI') && values?.length > 0) {
        const alignedData = alignIndicatorData(values, props.indicatorDates)
        series.push({
          name: key,
          type: 'line',
          data: alignedData,
          xAxisIndex: axisIndex,
          yAxisIndex: axisIndex,
          smooth: true,
          showSymbol: false,
          connectNulls: true,
          lineStyle: { width: 1.5, color: indicatorColors.RSI14 || '#9b59b6' }
        })
      }
    }
    subChartTop += subChartHeightNum + subChartGap
  }

  // CCI sub-chart
  if (hasCCI.value && props.indicators) {
    grids.push(createSubChartGrid(`${subChartTop}%`, 'CCI'))
    const axisIndex = grids.length - 1
    xAxes.push({ type: 'category', data: dates, gridIndex: axisIndex, boundaryGap: true, axisLine: { onZero: false, lineStyle: { color: '#ccc' } }, axisTick: { show: false }, axisLabel: { show: false } })
    yAxes.push({ type: 'value', gridIndex: axisIndex, scale: true, splitNumber: 2, boundaryGap: ['5%', '5%'], splitLine: { lineStyle: { color: '#eee' } }, axisLine: { lineStyle: { color: '#ccc' } } })
    
    graphicElements.push({
      type: 'text',
      left: '1%',
      top: `${subChartTop + subChartHeightNum / 2}%`,
      style: { text: 'CCI', fontSize: 12, fontWeight: 'bold', fill: '#333', verticalAlign: 'middle' }
    })
    
    for (const [key, values] of Object.entries(props.indicators)) {
      if (key.startsWith('CCI') && values?.length > 0) {
        const alignedData = alignIndicatorData(values, props.indicatorDates)
        series.push({
          name: key,
          type: 'line',
          data: alignedData,
          xAxisIndex: axisIndex,
          yAxisIndex: axisIndex,
          smooth: true,
          showSymbol: false,
          connectNulls: true,
          lineStyle: { width: 1.5, color: indicatorColors.CCI14 || '#e67e22' }
        })
      }
    }
    subChartTop += subChartHeightNum + subChartGap
  }

  // DMI sub-chart
  if (hasDMI.value && props.indicators) {
    grids.push(createSubChartGrid(`${subChartTop}%`, 'DMI'))
    const axisIndex = grids.length - 1
    xAxes.push({ type: 'category', data: dates, gridIndex: axisIndex, boundaryGap: true, axisLine: { onZero: false, lineStyle: { color: '#ccc' } }, axisTick: { show: false }, axisLabel: { show: false } })
    yAxes.push({ type: 'value', gridIndex: axisIndex, scale: true, splitNumber: 2, boundaryGap: ['5%', '5%'], splitLine: { lineStyle: { color: '#eee' } }, axisLine: { lineStyle: { color: '#ccc' } } })
    
    graphicElements.push({
      type: 'text',
      left: '1%',
      top: `${subChartTop + subChartHeightNum / 2}%`,
      style: { text: 'DMI', fontSize: 12, fontWeight: 'bold', fill: '#333', verticalAlign: 'middle' }
    })
    
    for (const key of dmiIndicators) {
      if (props.indicators[key]?.length > 0) {
        const alignedData = alignIndicatorData(props.indicators[key], props.indicatorDates)
        series.push({
          name: key,
          type: 'line',
          data: alignedData,
          xAxisIndex: axisIndex,
          yAxisIndex: axisIndex,
          smooth: true,
          showSymbol: false,
          connectNulls: true,
          lineStyle: { width: 1.5, color: indicatorColors[key] }
        })
      }
    }
    subChartTop += subChartHeightNum + subChartGap
  }

  // OBV sub-chart
  if (hasOBV.value && props.indicators) {
    grids.push(createSubChartGrid(`${subChartTop}%`, 'OBV'))
    const axisIndex = grids.length - 1
    xAxes.push({ type: 'category', data: dates, gridIndex: axisIndex, boundaryGap: true, axisLine: { onZero: false, lineStyle: { color: '#ccc' } }, axisTick: { show: false }, axisLabel: { show: false } })
    yAxes.push({ type: 'value', gridIndex: axisIndex, scale: true, splitNumber: 2, boundaryGap: ['5%', '5%'], splitLine: { lineStyle: { color: '#eee' } }, axisLine: { lineStyle: { color: '#ccc' } } })
    
    graphicElements.push({
      type: 'text',
      left: '1%',
      top: `${subChartTop + subChartHeightNum / 2}%`,
      style: { text: 'OBV', fontSize: 12, fontWeight: 'bold', fill: '#333', verticalAlign: 'middle' }
    })
    
    if (props.indicators.OBV?.length > 0) {
      const alignedData = alignIndicatorData(props.indicators.OBV, props.indicatorDates)
      series.push({
        name: 'OBV',
        type: 'line',
        data: alignedData,
        xAxisIndex: axisIndex,
        yAxisIndex: axisIndex,
        smooth: true,
        showSymbol: false,
        connectNulls: true,
        lineStyle: { width: 1.5, color: indicatorColors.OBV }
      })
    }
    subChartTop += subChartHeightNum + subChartGap
  }

  // ATR sub-chart
  if (hasATR.value && props.indicators) {
    grids.push(createSubChartGrid(`${subChartTop}%`, 'ATR'))
    const axisIndex = grids.length - 1
    xAxes.push({ type: 'category', data: dates, gridIndex: axisIndex, boundaryGap: true, axisLine: { onZero: false, lineStyle: { color: '#ccc' } }, axisTick: { show: false }, axisLabel: { show: false } })
    yAxes.push({ type: 'value', gridIndex: axisIndex, scale: true, splitNumber: 2, boundaryGap: ['5%', '5%'], splitLine: { lineStyle: { color: '#eee' } }, axisLine: { lineStyle: { color: '#ccc' } } })
    
    graphicElements.push({
      type: 'text',
      left: '1%',
      top: `${subChartTop + subChartHeightNum / 2}%`,
      style: { text: 'ATR', fontSize: 12, fontWeight: 'bold', fill: '#333', verticalAlign: 'middle' }
    })
    
    for (const [key, values] of Object.entries(props.indicators)) {
      if (key.startsWith('ATR') && values?.length > 0) {
        const alignedData = alignIndicatorData(values, props.indicatorDates)
        series.push({
          name: key,
          type: 'line',
          data: alignedData,
          xAxisIndex: axisIndex,
          yAxisIndex: axisIndex,
          smooth: true,
          showSymbol: false,
          connectNulls: true,
          lineStyle: { width: 1.5, color: indicatorColors.ATR14 || '#e67e22' }
        })
      }
    }
  }

  // Calculate dataZoom slider position - not used (inside zoom only)
  // const sliderTop = `${Math.min(subChartTop + subChartHeightNum, 92)}%`

  const option: echarts.EChartsOption = {
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross'
      },
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#ccc',
      borderWidth: 1,
      textStyle: { color: '#333' },
      formatter: (params: any) => {
        if (!params || params.length === 0) return ''
        const dataIndex = params[0].dataIndex
        const kline = props.data[dataIndex]
        if (!kline) return ''
        
        let html = `<div style="font-size:12px;"><strong>${kline.date}</strong><br/>`
        html += `开: ${kline.open.toFixed(2)} 高: ${kline.high.toFixed(2)}<br/>`
        html += `低: ${kline.low.toFixed(2)} 收: ${kline.close.toFixed(2)}<br/>`
        html += `成交量: ${(kline.volume / 10000).toFixed(2)}万手<br/>`
        
        // Add indicator values
        if (props.indicators) {
          for (const [key, values] of Object.entries(props.indicators)) {
            if (values && values[dataIndex] != null) {
              html += `${key}: ${values[dataIndex].toFixed(2)}<br/>`
            }
          }
        }
        html += '</div>'
        return html
      }
    },
    legend: {
      show: false, // 隐藏图例以节省空间
      data: ['K线', '成交量', ...series.filter(s => !['K线', '成交量'].includes(s.name)).map(s => s.name)],
      top: 10,
      textStyle: { fontSize: 11 }
    },
    axisPointer: {
      link: [{ xAxisIndex: 'all' }],
      label: { backgroundColor: '#777' }
    },
    grid: grids,
    xAxis: xAxes,
    yAxis: yAxes,
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: xAxes.map((_, i) => i),
        start: zoomStart,
        end: zoomEnd,
        minSpan: minSpanPercent,
        maxSpan: maxSpanPercent,
        zoomOnMouseWheel: true,
        moveOnMouseMove: true,
        preventDefaultMouseMove: true
      }
    ],
    graphic: graphicElements,
    series
  }

  chart.setOption(option, true)
}

const handleResize = () => {
  if (chart) {
    chart.resize()
  }
}

// 监听数据和指标变化
watch([() => props.data, () => props.indicators], () => {
  if (chart) {
    updateChart()
  } else if (props.data.length > 0) {
    // 如果图表还没初始化但有数据了，尝试初始化
    initChart()
  }
}, { deep: true })

onMounted(() => {
  // 使用 nextTick 确保 DOM 完全渲染
  nextTick(() => {
    initChart()
  })
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  chart?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>

<template>
  <div class="kline-chart-container" :style="{ height: chartHeight }">
    <!-- 加载状态：居中显示加载动画 -->
    <div v-if="loading" class="loading-state">
      <t-loading size="large" text="数据加载中..." />
    </div>
    <!-- 无数据状态 -->
    <div v-else-if="!data.length" class="empty-state">
      <t-icon name="chart-line" size="48px" style="color: #ddd" />
      <p>暂无数据</p>
    </div>
    <!-- 图表：只有在有数据且不在加载时才显示 -->
    <div v-show="!loading && data.length > 0" ref="chartRef" class="chart" />
  </div>
</template>

<style scoped>
.kline-chart-container {
  position: relative;
  width: 100%;
  min-height: 400px;
}

.loading-state {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  background: rgba(255, 255, 255, 0.9);
  z-index: 10;
}

.chart {
  width: 100%;
  height: 100%;
}

.empty-state {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  color: #999;
}
</style>

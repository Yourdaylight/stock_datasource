<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, computed } from 'vue'
import * as echarts from 'echarts'
import type { KLineData } from '@/types/common'

const props = defineProps<{
  data: KLineData[]
  indicators?: Record<string, number[]>
  indicatorDates?: string[]
  selectedIndicators?: string[]
  loading?: boolean
  height?: number
}>()

const chartRef = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

// Indicator colors
const indicatorColors: Record<string, string> = {
  MA5: '#ffaa00',
  MA10: '#00aaff',
  MA20: '#ff00aa',
  MA60: '#00ff88',
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

const chartHeight = computed(() => props.height || 600)

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
      color: d.close >= d.open ? '#ec0000' : '#00da3c'
    }
  }))

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
  
  // Calculate heights dynamically - adjusted for better spacing between indicator charts
  const mainHeight = hasSubCharts ? (subChartCount > 2 ? '18%' : subChartCount > 1 ? '24%' : '28%') : '55%'
  const volumeHeight = subChartCount > 2 ? '5%' : '7%'
  const subChartHeight = subChartCount > 2 ? '7%' : subChartCount > 1 ? '9%' : '11%'
  const subChartGap = subChartCount > 2 ? 5 : 6 // Gap percentage between sub-charts (increased for clearer separation)
  
  // Main chart grid
  grids.push({ left: '8%', right: '8%', top: 60, height: mainHeight, containLabel: false })
  xAxes.push({ type: 'category', data: dates, gridIndex: 0, boundaryGap: true, axisLine: { onZero: false } })
  yAxes.push({ type: 'value', gridIndex: 0, scale: true, splitArea: { show: true }, boundaryGap: ['5%', '5%'] })
  
  // K-line series
  series.push({
    name: 'K线',
    type: 'candlestick',
    data: klineData,
    xAxisIndex: 0,
    yAxisIndex: 0,
    itemStyle: {
      color: '#ec0000',
      color0: '#00da3c',
      borderColor: '#ec0000',
      borderColor0: '#00da3c'
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
          lineStyle: { width: 1, color: indicatorColors[key] || '#888' }
        })
      }
    }
  }

  // Volume grid
  const volumeTop = hasSubCharts ? (subChartCount > 1 ? '45%' : '50%') : '70%'
  grids.push({ left: '8%', right: '8%', top: volumeTop, height: volumeHeight, containLabel: false })
  xAxes.push({ type: 'category', data: dates, gridIndex: 1, boundaryGap: true, axisLine: { onZero: false }, axisTick: { show: false }, axisLabel: { show: false } })
  yAxes.push({ type: 'value', gridIndex: 1, scale: true, splitNumber: 2, boundaryGap: ['5%', '5%'] })
  
  series.push({
    name: '成交量',
    type: 'bar',
    data: volumeData,
    xAxisIndex: 1,
    yAxisIndex: 1
  })

  // Add sub-charts dynamically
  let subChartTop = hasSubCharts ? (subChartCount > 1 ? 56 : 65) : 85
  
  // Graphic elements for sub-chart titles and separators
  const graphicElements: any[] = []

  // Helper function to add separator line
  const addSeparator = (topPercent: number) => {
    graphicElements.push({
      type: 'rect',
      left: '8%',
      right: '8%',
      top: `${topPercent - 2}%`,
      shape: { width: 10000, height: 1 },
      style: { fill: '#e0e0e0' }
    })
  }

  // MACD sub-chart
  if (hasMACD.value && props.indicators) {
    addSeparator(subChartTop)
    
    grids.push({ left: '8%', right: '8%', top: `${subChartTop}%`, height: subChartHeight, containLabel: false })
    const axisIndex = grids.length - 1
    xAxes.push({ type: 'category', data: dates, gridIndex: axisIndex, boundaryGap: true, axisLine: { onZero: false }, axisTick: { show: false }, axisLabel: { show: false } })
    yAxes.push({ type: 'value', gridIndex: axisIndex, scale: true, splitNumber: 2, boundaryGap: ['5%', '5%'] })
    
    graphicElements.push({
      type: 'text',
      left: '9%',
      top: `${subChartTop}%`,
      style: { text: 'MACD', fontSize: 11, fontWeight: 'bold', fill: '#666' }
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
        lineStyle: { width: 1, color: indicatorColors.DIF }
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
        lineStyle: { width: 1, color: indicatorColors.DEA }
      })
    }
    if (props.indicators.MACD?.length > 0) {
      const alignedData = alignIndicatorData(props.indicators.MACD, props.indicatorDates)
      series.push({
        name: 'MACD',
        type: 'bar',
        data: alignedData.map(v => v === null ? null : ({
          value: v,
          itemStyle: { color: v >= 0 ? '#ec0000' : '#00da3c' }
        })),
        xAxisIndex: axisIndex,
        yAxisIndex: axisIndex
      })
    }
    subChartTop += parseInt(subChartHeight) + subChartGap
  }

  // KDJ sub-chart
  if (hasKDJ.value && props.indicators) {
    addSeparator(subChartTop)
    
    grids.push({ left: '8%', right: '8%', top: `${subChartTop}%`, height: subChartHeight, containLabel: false })
    const axisIndex = grids.length - 1
    xAxes.push({ type: 'category', data: dates, gridIndex: axisIndex, boundaryGap: true, axisLine: { onZero: false }, axisTick: { show: false }, axisLabel: { show: false } })
    yAxes.push({ type: 'value', gridIndex: axisIndex, scale: true, splitNumber: 2, min: 0, max: 100 })
    
    graphicElements.push({
      type: 'text',
      left: '9%',
      top: `${subChartTop}%`,
      style: { text: 'KDJ', fontSize: 11, fontWeight: 'bold', fill: '#666' }
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
          lineStyle: { width: 1, color: indicatorColors[key] }
        })
      }
    }
    subChartTop += parseInt(subChartHeight) + subChartGap
  }

  // RSI sub-chart
  if (hasRSI.value && props.indicators) {
    addSeparator(subChartTop)
    
    grids.push({ left: '8%', right: '8%', top: `${subChartTop}%`, height: subChartHeight, containLabel: false })
    const axisIndex = grids.length - 1
    xAxes.push({ type: 'category', data: dates, gridIndex: axisIndex, boundaryGap: true, axisLine: { onZero: false }, axisTick: { show: false }, axisLabel: { show: false } })
    yAxes.push({ type: 'value', gridIndex: axisIndex, scale: true, splitNumber: 2, min: 0, max: 100 })
    
    graphicElements.push({
      type: 'text',
      left: '9%',
      top: `${subChartTop}%`,
      style: { text: 'RSI', fontSize: 11, fontWeight: 'bold', fill: '#666' }
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
          lineStyle: { width: 1, color: indicatorColors.RSI14 || '#9b59b6' }
        })
      }
    }
    subChartTop += parseInt(subChartHeight) + subChartGap
  }

  // CCI sub-chart
  if (hasCCI.value && props.indicators) {
    addSeparator(subChartTop)
    
    grids.push({ left: '8%', right: '8%', top: `${subChartTop}%`, height: subChartHeight, containLabel: false })
    const axisIndex = grids.length - 1
    xAxes.push({ type: 'category', data: dates, gridIndex: axisIndex, boundaryGap: true, axisLine: { onZero: false }, axisTick: { show: false }, axisLabel: { show: false } })
    yAxes.push({ type: 'value', gridIndex: axisIndex, scale: true, splitNumber: 2, boundaryGap: ['5%', '5%'] })
    
    graphicElements.push({
      type: 'text',
      left: '9%',
      top: `${subChartTop}%`,
      style: { text: 'CCI', fontSize: 11, fontWeight: 'bold', fill: '#666' }
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
          lineStyle: { width: 1, color: indicatorColors.CCI14 || '#e67e22' }
        })
      }
    }
    subChartTop += parseInt(subChartHeight) + subChartGap
  }

  // DMI sub-chart
  if (hasDMI.value && props.indicators) {
    addSeparator(subChartTop)
    
    grids.push({ left: '8%', right: '8%', top: `${subChartTop}%`, height: subChartHeight, containLabel: false })
    const axisIndex = grids.length - 1
    xAxes.push({ type: 'category', data: dates, gridIndex: axisIndex, boundaryGap: true, axisLine: { onZero: false }, axisTick: { show: false }, axisLabel: { show: false } })
    yAxes.push({ type: 'value', gridIndex: axisIndex, scale: true, splitNumber: 2, boundaryGap: ['5%', '5%'] })
    
    graphicElements.push({
      type: 'text',
      left: '9%',
      top: `${subChartTop}%`,
      style: { text: 'DMI', fontSize: 11, fontWeight: 'bold', fill: '#666' }
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
          lineStyle: { width: 1, color: indicatorColors[key] }
        })
      }
    }
    subChartTop += parseInt(subChartHeight) + subChartGap
  }

  // OBV sub-chart
  if (hasOBV.value && props.indicators) {
    addSeparator(subChartTop)
    
    grids.push({ left: '8%', right: '8%', top: `${subChartTop}%`, height: subChartHeight, containLabel: false })
    const axisIndex = grids.length - 1
    xAxes.push({ type: 'category', data: dates, gridIndex: axisIndex, boundaryGap: true, axisLine: { onZero: false }, axisTick: { show: false }, axisLabel: { show: false } })
    yAxes.push({ type: 'value', gridIndex: axisIndex, scale: true, splitNumber: 2, boundaryGap: ['5%', '5%'] })
    
    graphicElements.push({
      type: 'text',
      left: '9%',
      top: `${subChartTop}%`,
      style: { text: 'OBV', fontSize: 11, fontWeight: 'bold', fill: '#666' }
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
        lineStyle: { width: 1, color: indicatorColors.OBV }
      })
    }
    subChartTop += parseInt(subChartHeight) + subChartGap
  }

  // ATR sub-chart
  if (hasATR.value && props.indicators) {
    addSeparator(subChartTop)
    
    grids.push({ left: '8%', right: '8%', top: `${subChartTop}%`, height: subChartHeight, containLabel: false })
    const axisIndex = grids.length - 1
    xAxes.push({ type: 'category', data: dates, gridIndex: axisIndex, boundaryGap: true, axisLine: { onZero: false }, axisTick: { show: false }, axisLabel: { show: false } })
    yAxes.push({ type: 'value', gridIndex: axisIndex, scale: true, splitNumber: 2, boundaryGap: ['5%', '5%'] })
    
    graphicElements.push({
      type: 'text',
      left: '9%',
      top: `${subChartTop}%`,
      style: { text: 'ATR', fontSize: 11, fontWeight: 'bold', fill: '#666' }
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
          lineStyle: { width: 1, color: indicatorColors.ATR14 || '#e67e22' }
        })
      }
    }
  }

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
        start: 50,
        end: 100,
        minSpan: 5,
        maxSpan: 100,
        zoomOnMouseWheel: true,
        moveOnMouseMove: true,
        preventDefaultMouseMove: true
      },
      {
        type: 'slider',
        xAxisIndex: xAxes.map((_, i) => i),
        start: 50,
        end: 100,
        top: '90%',
        height: 20,
        minSpan: 5,
        maxSpan: 100
      }
    ],
    graphic: graphicElements,
    series
  }

  chart.setOption(option, true)
}

const handleResize = () => {
  chart?.resize()
}

watch([() => props.data, () => props.indicators], updateChart, { deep: true })

onMounted(() => {
  initChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  chart?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>

<template>
  <div class="kline-chart-container" :style="{ height: `${chartHeight}px` }">
    <t-loading v-if="loading" size="large" />
    <div v-if="!data.length && !loading" class="empty-state">
      <t-icon name="chart-line" size="48px" style="color: #ddd" />
      <p>暂无数据</p>
    </div>
    <div ref="chartRef" class="chart" />
  </div>
</template>

<style scoped>
.kline-chart-container {
  position: relative;
  width: 100%;
  min-height: 400px;
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

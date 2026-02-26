<template>
  <div class="return-distribution-chart-container">
    <div class="chart-header">
      <h3 class="chart-title">收益率分布</h3>
      <div class="chart-controls">
        <el-select v-model="binCount" size="small" @change="updateChart">
          <el-option label="20组" :value="20" />
          <el-option label="30组" :value="30" />
          <el-option label="50组" :value="50" />
        </el-select>
        <el-tooltip content="导出图表" placement="top">
          <el-button size="small" @click="exportChart">
            <el-icon><Download /></el-icon>
          </el-button>
        </el-tooltip>
      </div>
    </div>
    <div 
      ref="chartRef" 
      class="return-distribution-chart"
      v-loading="loading"
    ></div>
    <div v-if="!loading && (!returnData || returnData.length === 0)" class="empty-chart">
      <el-empty description="暂无收益率数据" />
    </div>
    
    <!-- 统计信息 -->
    <div v-if="!loading && returnData?.length" class="stats-panel">
      <div class="stat-item">
        <span class="stat-label">均值:</span>
        <span class="stat-value">{{ mean.toFixed(3) }}%</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">标准差:</span>
        <span class="stat-value">{{ stdDev.toFixed(3) }}%</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">偏度:</span>
        <span class="stat-value" :class="{ 'negative': skewness < 0, 'positive': skewness > 0 }">
          {{ skewness.toFixed(3) }}
        </span>
      </div>
      <div class="stat-item">
        <span class="stat-label">峰度:</span>
        <span class="stat-value" :class="{ 'negative': kurtosis < 3, 'positive': kurtosis > 3 }">
          {{ kurtosis.toFixed(3) }}
        </span>
      </div>
      <div class="stat-item">
        <span class="stat-label">VaR(95%):</span>
        <span class="stat-value negative">{{ var95.toFixed(3) }}%</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">VaR(99%):</span>
        <span class="stat-value negative">{{ var99.toFixed(3) }}%</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue';
import * as echarts from 'echarts';
import { Download } from '@element-plus/icons-vue';

interface Props {
  returnData: number[];
  loading?: boolean;
  height?: string;
  showNormalCurve?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  height: '400px',
  showNormalCurve: true
});

const chartRef = ref<HTMLElement | null>(null);
const binCount = ref<number>(30);
let chartInstance: echarts.ECharts | null = null;

// 统计计算函数
function calculateMean(data: number[]): number {
  return data.reduce((sum, val) => sum + val, 0) / data.length;
}

function calculateStdDev(data: number[], mean: number): number {
  const variance = data.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / data.length;
  return Math.sqrt(variance);
}

function calculateSkewness(data: number[], mean: number, stdDev: number): number {
  const n = data.length;
  const sum = data.reduce((sum, val) => sum + Math.pow((val - mean) / stdDev, 3), 0);
  return (n / ((n - 1) * (n - 2))) * sum;
}

function calculateKurtosis(data: number[], mean: number, stdDev: number): number {
  const n = data.length;
  const sum = data.reduce((sum, val) => sum + Math.pow((val - mean) / stdDev, 4), 0);
  return ((n * (n + 1)) / ((n - 1) * (n - 2) * (n - 3))) * sum - (3 * Math.pow(n - 1, 2)) / ((n - 2) * (n - 3));
}

function calculateVaR(data: number[], confidence: number): number {
  const sorted = [...data].sort((a, b) => a - b);
  const index = Math.floor((1 - confidence) * sorted.length);
  return sorted[index];
}

function normalPDF(x: number, mean: number, stdDev: number): number {
  return (1 / (stdDev * Math.sqrt(2 * Math.PI))) * Math.exp(-0.5 * Math.pow((x - mean) / stdDev, 2));
}

// 计算统计指标
const mean = computed(() => {
  return props.returnData?.length ? calculateMean(props.returnData) : 0;
});

const stdDev = computed(() => {
  return props.returnData?.length ? calculateStdDev(props.returnData, mean.value) : 0;
});

const skewness = computed(() => {
  return props.returnData?.length > 2 ? calculateSkewness(props.returnData, mean.value, stdDev.value) : 0;
});

const kurtosis = computed(() => {
  return props.returnData?.length > 3 ? calculateKurtosis(props.returnData, mean.value, stdDev.value) : 0;
});

const var95 = computed(() => {
  return props.returnData?.length ? calculateVaR(props.returnData, 0.95) : 0;
});

const var99 = computed(() => {
  return props.returnData?.length ? calculateVaR(props.returnData, 0.99) : 0;
});

// 创建直方图数据
function createHistogramData(data: number[], bins: number) {
  if (!data.length) return { binCenters: [], frequencies: [], binWidth: 0 };

  const min = Math.min(...data);
  const max = Math.max(...data);
  const binWidth = (max - min) / bins;
  
  const frequencies = new Array(bins).fill(0);
  const binCenters = [];
  
  // 计算每个bin的中心点
  for (let i = 0; i < bins; i++) {
    binCenters.push(min + (i + 0.5) * binWidth);
  }
  
  // 统计每个bin的频数
  data.forEach(value => {
    let binIndex = Math.floor((value - min) / binWidth);
    if (binIndex >= bins) binIndex = bins - 1; // 处理边界情况
    frequencies[binIndex]++;
  });
  
  // 转换为频率密度
  const totalCount = data.length;
  const densities = frequencies.map(freq => freq / (totalCount * binWidth));
  
  return { binCenters, frequencies: densities, binWidth };
}

// 初始化图表
function initChart() {
  if (!chartRef.value) return;
  
  chartInstance = echarts.init(chartRef.value);
  updateChart();
  
  // 监听窗口大小变化
  window.addEventListener('resize', handleResize);
}

// 更新图表
function updateChart() {
  if (!chartInstance || !props.returnData?.length) return;

  const { binCenters, frequencies, binWidth } = createHistogramData(props.returnData, binCount.value);
  
  const series: echarts.SeriesOption[] = [
    {
      name: '收益率分布',
      type: 'bar',
      data: frequencies,
      barWidth: '90%',
      itemStyle: {
        color: '#1890ff',
        opacity: 0.7
      }
    }
  ];

  // 如果显示正态分布曲线
  if (props.showNormalCurve && props.returnData.length > 1) {
    const min = Math.min(...props.returnData);
    const max = Math.max(...props.returnData);
    const step = (max - min) / 100;
    const normalX = [];
    const normalY = [];
    
    for (let x = min; x <= max; x += step) {
      normalX.push(x);
      normalY.push(normalPDF(x, mean.value, stdDev.value));
    }
    
    series.push({
      name: '正态分布',
      type: 'line',
      data: normalX.map((x, i) => [x, normalY[i]]),
      smooth: true,
      symbol: 'none',
      lineStyle: {
        color: '#ff4d4f',
        width: 2,
        type: 'dashed'
      }
    });
  }

  const option: echarts.EChartsOption = {
    title: {
      text: '收益率概率分布',
      left: 'center',
      textStyle: {
        fontSize: 16,
        fontWeight: 'bold'
      }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross'
      },
      formatter: (params: any) => {
        const data = params[0];
        const binCenter = binCenters[data.dataIndex];
        const frequency = data.value;
        const binStart = binCenter - binWidth / 2;
        const binEnd = binCenter + binWidth / 2;
        
        return `
          <div style="text-align: left;">
            <div><strong>收益率区间</strong></div>
            <div>[${binStart.toFixed(3)}%, ${binEnd.toFixed(3)}%)</div>
            <div>频率密度: ${frequency.toFixed(4)}</div>
          </div>
        `;
      }
    },
    legend: {
      data: props.showNormalCurve ? ['收益率分布', '正态分布'] : ['收益率分布'],
      top: 30
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '15%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: binCenters.map(center => center.toFixed(2)),
      name: '收益率 (%)',
      nameLocation: 'middle',
      nameGap: 30,
      axisLabel: {
        formatter: '{value}%'
      }
    },
    yAxis: {
      type: 'value',
      name: '频率密度',
      nameLocation: 'middle',
      nameGap: 50,
      splitLine: {
        lineStyle: {
          type: 'dashed'
        }
      }
    },
    series: series
  };

  chartInstance.setOption(option);
}

// 导出图表
function exportChart() {
  if (!chartInstance) return;
  
  const url = chartInstance.getDataURL({
    type: 'png',
    pixelRatio: 2,
    backgroundColor: '#fff'
  });
  
  const link = document.createElement('a');
  link.download = `收益率分布_${new Date().toISOString().split('T')[0]}.png`;
  link.href = url;
  link.click();
}

// 处理窗口大小变化
function handleResize() {
  if (chartInstance) {
    chartInstance.resize();
  }
}

// 监听数据变化
watch(() => props.returnData, () => {
  nextTick(() => {
    updateChart();
  });
}, { deep: true });

watch(() => props.loading, (newVal) => {
  if (!newVal) {
    nextTick(() => {
      updateChart();
    });
  }
});

onMounted(() => {
  nextTick(() => {
    initChart();
  });
});

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
  window.removeEventListener('resize', handleResize);
});
</script>

<style scoped>
.return-distribution-chart-container {
  width: 100%;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #f0f0f0;
  background: #fafafa;
}

.chart-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #262626;
}

.chart-controls {
  display: flex;
  gap: 8px;
  align-items: center;
}

.return-distribution-chart {
  width: 100%;
  height: v-bind(height);
  min-height: 300px;
}

.empty-chart {
  height: v-bind(height);
  display: flex;
  align-items: center;
  justify-content: center;
}

.stats-panel {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  padding: 16px 20px;
  background: #f8f9fa;
  border-top: 1px solid #f0f0f0;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 100px;
}

.stat-label {
  font-size: 12px;
  color: #8c8c8c;
  margin-bottom: 4px;
}

.stat-value {
  font-size: 14px;
  font-weight: 600;
  color: #262626;
}

.stat-value.positive {
  color: #ff4d4f;
}

.stat-value.negative {
  color: #52c41a;
}

@media (max-width: 768px) {
  .chart-header {
    padding: 12px 16px;
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
  }
  
  .chart-title {
    font-size: 14px;
  }
  
  .return-distribution-chart {
    height: 300px;
  }
  
  .stats-panel {
    padding: 12px 16px;
    gap: 12px;
  }
  
  .stat-item {
    min-width: 80px;
  }
}
</style>
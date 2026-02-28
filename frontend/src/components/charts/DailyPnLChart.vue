<template>
  <div class="daily-pnl-chart-container">
    <div class="chart-header">
      <h3 class="chart-title">每日盈亏分布</h3>
      <div class="chart-controls">
        <el-select v-model="chartType" size="small" @change="updateChart">
          <el-option label="柱状图" value="bar" />
          <el-option label="线图" value="line" />
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
      class="daily-pnl-chart"
      v-loading="loading"
    ></div>
    <div v-if="!loading && (!dailyPnLData || dailyPnLData.length === 0)" class="empty-chart">
      <el-empty description="暂无每日盈亏数据" />
    </div>
    
    <!-- 统计信息 -->
    <div v-if="!loading && dailyPnLData?.length" class="stats-panel">
      <div class="stat-item">
        <span class="stat-label">盈利天数:</span>
        <span class="stat-value positive">{{ profitDays }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">亏损天数:</span>
        <span class="stat-value negative">{{ lossDays }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">胜率:</span>
        <span class="stat-value">{{ winRate }}%</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">最大单日盈利:</span>
        <span class="stat-value positive">{{ maxProfit.toFixed(2) }}%</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">最大单日亏损:</span>
        <span class="stat-value negative">{{ maxLoss.toFixed(2) }}%</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue';
import * as echarts from 'echarts';
import { Download } from '@element-plus/icons-vue';

interface DailyPnLDataPoint {
  date: string;
  pnl: number;
  pnlPercent: number;
  cumulativePnL: number;
}

interface Props {
  dailyPnLData: DailyPnLDataPoint[];
  loading?: boolean;
  height?: string;
  showCumulative?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  height: '400px',
  showCumulative: true
});

const chartRef = ref<HTMLElement | null>(null);
const chartType = ref<'bar' | 'line'>('bar');
let chartInstance: echarts.ECharts | null = null;

// 计算统计信息
const profitDays = computed(() => {
  return props.dailyPnLData?.filter(item => item.pnlPercent > 0).length || 0;
});

const lossDays = computed(() => {
  return props.dailyPnLData?.filter(item => item.pnlPercent < 0).length || 0;
});

const winRate = computed(() => {
  const total = props.dailyPnLData?.length || 0;
  return total > 0 ? ((profitDays.value / total) * 100).toFixed(1) : '0.0';
});

const maxProfit = computed(() => {
  return Math.max(...(props.dailyPnLData?.map(item => item.pnlPercent) || [0]));
});

const maxLoss = computed(() => {
  return Math.min(...(props.dailyPnLData?.map(item => item.pnlPercent) || [0]));
});

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
  if (!chartInstance || !props.dailyPnLData?.length) return;

  const dates = props.dailyPnLData.map(item => item.date);
  const pnlPercents = props.dailyPnLData.map(item => item.pnlPercent);
  const cumulativePnL = props.dailyPnLData.map(item => item.cumulativePnL);

  // 为正负值设置不同颜色
  const itemColors = pnlPercents.map(value => value >= 0 ? '#52c41a' : '#ff4d4f');

  const series: echarts.SeriesOption[] = []

  if (chartType.value === 'bar') {
    const positiveData = pnlPercents.map(value => (value >= 0 ? value : null))
    const negativeData = pnlPercents.map(value => (value < 0 ? value : null))

    series.push({
      name: '每日收益率',
      type: 'bar',
      data: positiveData,
      itemStyle: {
        color: '#ff4d4f'
      },
      barWidth: '60%'
    })

    series.push({
      name: '每日收益率',
      type: 'bar',
      data: negativeData,
      itemStyle: {
        color: '#52c41a'
      },
      barWidth: '60%'
    })
  } else {
    const trendColor = pnlPercents.length && pnlPercents[pnlPercents.length - 1] >= 0 ? '#ff4d4f' : '#52c41a'
    series.push({
      name: '每日收益率',
      type: 'line',
      data: pnlPercents,
      symbol: 'circle',
      symbolSize: 4,
      smooth: true,
      itemStyle: {
        color: trendColor
      },
      lineStyle: {
        width: 2,
        color: trendColor
      }
    })
  }

  // 如果显示累计收益，添加累计收益线
  if (props.showCumulative) {
    series.push({
      name: '累计收益率',
      type: 'line',
      yAxisIndex: 1,
      data: cumulativePnL,
      smooth: true,
      symbol: 'none',
      lineStyle: {
        color: '#1890ff',
        width: 2
      }
    });
  }

  const option: echarts.EChartsOption = {
    title: {
      text: '每日盈亏分布',
      left: 'center',
      textStyle: {
        fontSize: 16,
        fontWeight: 'bold'
      }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        label: {
          backgroundColor: '#6a7985'
        }
      },
      formatter: (params: any) => {
        const data = params[0];
        const index = data.dataIndex;
        const point = props.dailyPnLData[index];
        let result = `
          <div style="text-align: left;">
            <div><strong>${data.axisValue}</strong></div>
            <div>每日收益: <span style="color: ${point.pnlPercent >= 0 ? '#ff4d4f' : '#52c41a'};">${point.pnlPercent.toFixed(2)}%</span></div>
            <div>盈亏金额: ¥${point.pnl.toFixed(2)}</div>
        `;
        
        if (props.showCumulative && params.length > 1) {
          result += `<div>累计收益: ${point.cumulativePnL.toFixed(2)}%</div>`;
        }
        
        result += '</div>';
        return result;
      }
    },
    legend: {
      data: props.showCumulative ? ['每日收益率', '累计收益率'] : ['每日收益率'],
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
      data: dates,
      axisLabel: {
        formatter: (value: string) => {
          const date = new Date(value);
          return `${date.getMonth() + 1}/${date.getDate()}`;
        },
        rotate: 45
      }
    },
    yAxis: [
      {
        type: 'value',
        name: '每日收益率 (%)',
        nameLocation: 'middle',
        nameGap: 50,
        axisLabel: {
          formatter: '{value}%'
        },
        splitLine: {
          lineStyle: {
            type: 'dashed'
          }
        }
      }
    ],
    series: series,
    dataZoom: [
      {
        type: 'inside',
        start: 0,
        end: 100
      },
      {
        start: 0,
        end: 100,
        height: 30,
        bottom: 20
      }
    ]
  };

  // 如果显示累计收益，添加右侧Y轴
  if (props.showCumulative) {
    option.yAxis = [
      option.yAxis![0],
      {
        type: 'value',
        name: '累计收益率 (%)',
        nameLocation: 'middle',
        nameGap: 50,
        position: 'right',
        axisLabel: {
          formatter: '{value}%'
        },
        splitLine: {
          show: false
        }
      }
    ];
  }

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
  link.download = `每日盈亏分布_${new Date().toISOString().split('T')[0]}.png`;
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
watch(() => props.dailyPnLData, () => {
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
.daily-pnl-chart-container {
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

.daily-pnl-chart {
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
  
  .daily-pnl-chart {
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
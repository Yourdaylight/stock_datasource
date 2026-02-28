<template>
  <div class="drawdown-chart-container">
    <div class="chart-header">
      <h3 class="chart-title">回撤曲线</h3>
      <div class="chart-controls">
        <el-tooltip content="导出图表" placement="top">
          <el-button size="small" @click="exportChart">
            <el-icon><Download /></el-icon>
          </el-button>
        </el-tooltip>
      </div>
    </div>
    <div 
      ref="chartRef" 
      class="drawdown-chart"
      v-loading="loading"
    ></div>
    <div v-if="!loading && (!drawdownData || drawdownData.length === 0)" class="empty-chart">
      <el-empty description="暂无回撤数据" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue';
import * as echarts from 'echarts';
import { Download } from '@element-plus/icons-vue';

interface DrawdownDataPoint {
  date: string;
  drawdown: number;
  equity: number;
}

interface Props {
  drawdownData: DrawdownDataPoint[];
  loading?: boolean;
  height?: string;
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  height: '400px'
});

const chartRef = ref<HTMLElement | null>(null);
let chartInstance: echarts.ECharts | null = null;

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
  if (!chartInstance || !props.drawdownData?.length) return;

  const dates = props.drawdownData.map(item => item.date);
  const drawdowns = props.drawdownData.map(item => item.drawdown * 100); // 转换为百分比
  const equities = props.drawdownData.map(item => item.equity);

  // 找到最大回撤点
  const maxDrawdownIndex = drawdowns.findIndex(dd => dd === Math.min(...drawdowns));
  const maxDrawdownPoint = props.drawdownData[maxDrawdownIndex];

  const option: echarts.EChartsOption = {
    title: {
      text: '净值回撤曲线',
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
        const point = props.drawdownData[index];
        return `
          <div style="text-align: left;">
            <div><strong>${data.axisValue}</strong></div>
            <div>回撤: <span style="color: #ff4d4f;">${data.value.toFixed(2)}%</span></div>
            <div>净值: ${point.equity.toFixed(4)}</div>
          </div>
        `;
      }
    },
    legend: {
      data: ['回撤曲线'],
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
      boundaryGap: false,
      data: dates,
      axisLabel: {
        formatter: (value: string) => {
          const date = new Date(value);
          return `${date.getMonth() + 1}/${date.getDate()}`;
        }
      }
    },
    yAxis: {
      type: 'value',
      name: '回撤 (%)',
      nameLocation: 'middle',
      nameGap: 50,
      max: 0,
      axisLabel: {
        formatter: '{value}%'
      },
      splitLine: {
        lineStyle: {
          type: 'dashed'
        }
      }
    },
    series: [
      {
        name: '回撤曲线',
        type: 'line',
        data: drawdowns,
        smooth: true,
        symbol: 'none',
        lineStyle: {
          color: '#ff4d4f',
          width: 2
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              {
                offset: 0,
                color: 'rgba(255, 77, 79, 0.3)'
              },
              {
                offset: 1,
                color: 'rgba(255, 77, 79, 0.1)'
              }
            ]
          }
        },
        markPoint: {
          data: [
            {
              name: '最大回撤',
              coord: [maxDrawdownIndex, drawdowns[maxDrawdownIndex]],
              value: `${drawdowns[maxDrawdownIndex].toFixed(2)}%`,
              itemStyle: {
                color: '#ff4d4f'
              },
              label: {
                show: true,
                position: 'bottom',
                formatter: '最大回撤\n{c}'
              }
            }
          ],
          symbolSize: 60,
          itemStyle: {
            color: '#ff4d4f'
          }
        }
      }
    ],
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
  link.download = `回撤曲线_${new Date().toISOString().split('T')[0]}.png`;
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
watch(() => props.drawdownData, () => {
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
.drawdown-chart-container {
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
}

.drawdown-chart {
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

@media (max-width: 768px) {
  .chart-header {
    padding: 12px 16px;
  }
  
  .chart-title {
    font-size: 14px;
  }
  
  .drawdown-chart {
    height: 300px;
  }
}
</style>
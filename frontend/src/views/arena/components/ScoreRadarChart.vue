<template>
  <div ref="chartRef" class="radar-chart"></div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue';
import * as echarts from 'echarts';

interface ScoreData {
  name: string;
  profitability: number;
  risk_control: number;
  stability: number;
  adaptability: number;
}

const props = defineProps<{
  data: ScoreData[];
}>();

const chartRef = ref<HTMLElement | null>(null);
let chartInstance: echarts.ECharts | null = null;

const colors = [
  '#5470c6', '#91cc75', '#fac858', '#ee6666',
  '#73c0de', '#3ba272', '#fc8452', '#9a60b4'
];

function initChart() {
  if (!chartRef.value) return;
  
  chartInstance = echarts.init(chartRef.value);
  updateChart();
}

function updateChart() {
  if (!chartInstance || !props.data.length) return;

  const indicator = [
    { name: '收益性', max: 100 },
    { name: '风险控制', max: 100 },
    { name: '稳定性', max: 100 },
    { name: '适应性', max: 100 },
  ];

  const seriesData = props.data.map((item, index) => ({
    value: [
      item.profitability,
      item.risk_control,
      item.stability,
      item.adaptability,
    ],
    name: item.name,
    itemStyle: {
      color: colors[index % colors.length],
    },
    areaStyle: {
      opacity: 0.2,
    },
  }));

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'item',
    },
    legend: {
      data: props.data.map((d) => d.name),
      bottom: 0,
      left: 'center',
      type: 'scroll',
    },
    radar: {
      indicator,
      center: ['50%', '45%'],
      radius: '60%',
      splitNumber: 4,
      axisName: {
        color: '#666',
        fontSize: 12,
      },
      splitArea: {
        areaStyle: {
          color: ['rgba(64, 158, 255, 0.05)', 'rgba(64, 158, 255, 0.1)'],
        },
      },
      splitLine: {
        lineStyle: {
          color: '#ddd',
        },
      },
      axisLine: {
        lineStyle: {
          color: '#ddd',
        },
      },
    },
    series: [
      {
        type: 'radar',
        data: seriesData,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: {
          width: 2,
        },
        emphasis: {
          lineStyle: {
            width: 3,
          },
        },
      },
    ],
  };

  chartInstance.setOption(option);
}

function handleResize() {
  chartInstance?.resize();
}

watch(() => props.data, updateChart, { deep: true });

onMounted(() => {
  initChart();
  window.addEventListener('resize', handleResize);
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  chartInstance?.dispose();
});
</script>

<style scoped>
.radar-chart {
  width: 100%;
  height: 300px;
}
</style>

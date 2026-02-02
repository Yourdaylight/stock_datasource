<template>
  <div ref="chartRef" class="return-chart"></div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue';
import * as echarts from 'echarts';

interface ReturnData {
  name: string;
  dates: string[];
  returns: number[];
}

const props = defineProps<{
  data: ReturnData[];
  benchmark?: ReturnData;
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

  // Merge all dates and sort
  const allDates = new Set<string>();
  props.data.forEach((d) => d.dates.forEach((date) => allDates.add(date)));
  if (props.benchmark) {
    props.benchmark.dates.forEach((date) => allDates.add(date));
  }
  const dates = Array.from(allDates).sort();

  // Create series data
  const series: echarts.SeriesOption[] = props.data.map((item, index) => {
    const dataMap = new Map(item.dates.map((d, i) => [d, item.returns[i]]));
    return {
      name: item.name,
      type: 'line',
      smooth: true,
      symbol: 'none',
      data: dates.map((d) => dataMap.get(d) ?? null),
      itemStyle: {
        color: colors[index % colors.length],
      },
      lineStyle: {
        width: 2,
      },
    };
  });

  // Add benchmark if exists
  if (props.benchmark) {
    const benchmarkMap = new Map(
      props.benchmark.dates.map((d, i) => [d, props.benchmark!.returns[i]])
    );
    series.push({
      name: props.benchmark.name,
      type: 'line',
      smooth: true,
      symbol: 'none',
      data: dates.map((d) => benchmarkMap.get(d) ?? null),
      itemStyle: {
        color: '#999',
      },
      lineStyle: {
        width: 2,
        type: 'dashed',
      },
    });
  }

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
      },
      formatter: (params: unknown) => {
        const arr = params as Array<{ axisValue?: string; value?: number; marker?: string; seriesName?: string }>;
        if (!arr.length) return '';
        let result = `<div style="font-weight: bold">${arr[0].axisValue || ''}</div>`;
        arr.forEach((item) => {
          if (item.value !== null && item.value !== undefined) {
            const value = Number(item.value);
            const color = value >= 0 ? '#67c23a' : '#f56c6c';
            result += `
              <div style="display: flex; justify-content: space-between; gap: 20px;">
                <span>${item.marker}${item.seriesName}</span>
                <span style="color: ${color}; font-weight: bold;">${value.toFixed(2)}%</span>
              </div>
            `;
          }
        });
        return result;
      },
    },
    legend: {
      data: [...props.data.map((d) => d.name), ...(props.benchmark ? [props.benchmark.name] : [])],
      bottom: 0,
      left: 'center',
      type: 'scroll',
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      top: '10%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: false,
      axisLine: {
        lineStyle: {
          color: '#ddd',
        },
      },
      axisLabel: {
        color: '#666',
      },
    },
    yAxis: {
      type: 'value',
      name: '累计收益率 (%)',
      nameTextStyle: {
        color: '#666',
      },
      axisLine: {
        show: false,
      },
      splitLine: {
        lineStyle: {
          color: '#eee',
        },
      },
      axisLabel: {
        color: '#666',
        formatter: '{value}%',
      },
    },
    series,
    dataZoom: [
      {
        type: 'inside',
        start: 0,
        end: 100,
      },
      {
        type: 'slider',
        start: 0,
        end: 100,
        height: 20,
        bottom: 30,
      },
    ],
  };

  chartInstance.setOption(option);
}

function handleResize() {
  chartInstance?.resize();
}

watch(() => [props.data, props.benchmark], updateChart, { deep: true });

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
.return-chart {
  width: 100%;
  height: 350px;
}
</style>

<script setup lang="ts">
import { ref } from 'vue'
import EtfScreenerContent from './EtfScreenerContent.vue'
import EtfBenchmarkIndexPanel from './components/EtfBenchmarkIndexPanel.vue'

const activeTab = ref('screener')

const tabList = [
  { value: 'screener', label: 'ETF行情' },
  { value: 'benchmark', label: '基准指数' },
]
</script>

<template>
  <div class="etf-view">
    <t-tabs v-model="activeTab" theme="card" class="etf-tabs">
      <t-tab-panel
        v-for="tab in tabList"
        :key="tab.value"
        :value="tab.value"
        :label="tab.label"
      >
        <template v-if="tab.value === 'screener'">
          <EtfScreenerContent />
        </template>
        <template v-else-if="tab.value === 'benchmark'">
          <EtfBenchmarkIndexPanel />
        </template>
      </t-tab-panel>
    </t-tabs>
  </div>
</template>

<style scoped>
.etf-view {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.etf-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.etf-tabs :deep(.t-tabs__content) {
  flex: 1;
  overflow: auto;
  padding: 16px;
}
</style>

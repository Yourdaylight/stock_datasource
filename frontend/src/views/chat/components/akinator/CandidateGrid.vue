<script setup lang="ts">
import type { StockDTO } from '@/api/akinator'

interface Props {
  candidates: StockDTO[]
}

defineProps<Props>()

const emit = defineEmits<{
  (e: 'pick', ts_code: string): void
  (e: 'abandon'): void
  (e: 'retry'): void
}>()

const formatMarketCap = (mv?: number) => {
  if (!mv) return '-'
  // mv in 万元
  const yi = mv / 10000
  if (yi >= 10000) return `${(yi / 10000).toFixed(1)}万亿`
  if (yi >= 100) return `${yi.toFixed(0)}亿`
  return `${yi.toFixed(1)}亿`
}
</script>

<template>
  <div class="candidate-grid">
    <div class="cg-header">
      <h3 class="cg-title">
        <t-icon name="sparkles" /> 我觉得可能是这些股票
      </h3>
      <p class="cg-subtitle">点击选择你想的那只，如果都不对请点"都不对"</p>
    </div>

    <div class="cg-cards">
      <div
        v-for="stock in candidates"
        :key="stock.ts_code"
        class="cg-card"
        @click="emit('pick', stock.ts_code)"
      >
        <div class="cg-card-header">
          <span class="cg-name">{{ stock.name || stock.ts_code }}</span>
          <span class="cg-code">{{ stock.ts_code }}</span>
        </div>
        <div class="cg-card-meta">
          <t-tag v-if="stock.industry" size="small" variant="light" theme="primary">
            {{ stock.industry }}
          </t-tag>
          <span class="cg-mv">市值 {{ formatMarketCap(stock.total_mv) }}</span>
        </div>
        <div v-if="stock.concepts?.length" class="cg-concepts">
          <t-tag
            v-for="c in stock.concepts.slice(0, 3)"
            :key="c"
            size="small"
            variant="outline"
          >
            {{ c }}
          </t-tag>
          <span v-if="stock.concepts.length > 3" class="cg-more">
            +{{ stock.concepts.length - 3 }}
          </span>
        </div>
      </div>
    </div>

    <div class="cg-actions">
      <t-button theme="default" variant="outline" @click="emit('abandon')">
        都不对 🤔
      </t-button>
      <t-button theme="primary" variant="outline" @click="emit('retry')">
        <template #icon><t-icon name="refresh" /></template>
        再玩一次
      </t-button>
    </div>
  </div>
</template>

<style scoped>
.candidate-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.cg-header {
  text-align: center;
}

.cg-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 4px;
  color: var(--td-text-color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.cg-subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--td-text-color-secondary);
}

.cg-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}

.cg-card {
  padding: 12px 14px;
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-component-stroke);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.cg-card:hover {
  border-color: var(--td-brand-color);
  background: var(--td-brand-color-light);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 82, 217, 0.12);
}

.cg-card-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 8px;
}

.cg-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--td-text-color-primary);
}

.cg-code {
  font-size: 11px;
  color: var(--td-text-color-placeholder);
  font-family: monospace;
}

.cg-card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--td-text-color-secondary);
  margin-bottom: 6px;
}

.cg-concepts {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

.cg-more {
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}

.cg-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-top: 8px;
}
</style>

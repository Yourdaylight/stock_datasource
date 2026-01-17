<script setup lang="ts">
import { computed } from 'vue'
import type { IndexData, MarketStats } from '@/types/common'

const props = defineProps<{
  indices: IndexData[]
  stats: MarketStats | null
  loading?: boolean
}>()

const formatAmount = (amount: number) => {
  if (amount >= 10000) {
    return (amount / 10000).toFixed(2) + '万亿'
  }
  return amount.toFixed(2) + '亿'
}

const formatPctChg = (pctChg: number) => {
  const prefix = pctChg >= 0 ? '+' : ''
  return prefix + pctChg.toFixed(2) + '%'
}
</script>

<template>
  <div class="market-overview">
    <t-loading v-if="loading" size="medium" />
    
    <template v-else>
      <!-- Index Cards -->
      <div class="index-cards">
        <div 
          v-for="index in indices" 
          :key="index.code" 
          class="index-card"
          :class="{ 'up': index.pct_chg > 0, 'down': index.pct_chg < 0 }"
        >
          <div class="index-name">{{ index.name }}</div>
          <div class="index-close">{{ index.close.toFixed(2) }}</div>
          <div class="index-change">{{ formatPctChg(index.pct_chg) }}</div>
        </div>
      </div>
      
      <!-- Market Stats -->
      <div v-if="stats" class="market-stats">
        <div class="stat-item up">
          <span class="stat-label">上涨</span>
          <span class="stat-value">{{ stats.up_count }}</span>
        </div>
        <div class="stat-item down">
          <span class="stat-label">下跌</span>
          <span class="stat-value">{{ stats.down_count }}</span>
        </div>
        <div class="stat-item flat">
          <span class="stat-label">平盘</span>
          <span class="stat-value">{{ stats.flat_count }}</span>
        </div>
        <div class="stat-item limit-up">
          <span class="stat-label">涨停</span>
          <span class="stat-value">{{ stats.limit_up_count }}</span>
        </div>
        <div class="stat-item limit-down">
          <span class="stat-label">跌停</span>
          <span class="stat-value">{{ stats.limit_down_count }}</span>
        </div>
        <div class="stat-item amount">
          <span class="stat-label">成交额</span>
          <span class="stat-value">{{ formatAmount(stats.total_amount) }}</span>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.market-overview {
  padding: 16px;
  background: #fff;
  border-radius: 8px;
}

.index-cards {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.index-card {
  flex: 1;
  min-width: 120px;
  padding: 12px;
  background: #f5f5f5;
  border-radius: 8px;
  text-align: center;
}

.index-card.up {
  background: #fff0f0;
}

.index-card.down {
  background: #f0fff0;
}

.index-name {
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
}

.index-close {
  font-size: 18px;
  font-weight: 600;
}

.index-card.up .index-close,
.index-card.up .index-change {
  color: #ec0000;
}

.index-card.down .index-close,
.index-card.down .index-change {
  color: #00da3c;
}

.index-change {
  font-size: 13px;
  margin-top: 4px;
}

.market-stats {
  display: flex;
  justify-content: space-around;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px;
  background: #fafafa;
  border-radius: 8px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 60px;
}

.stat-label {
  font-size: 11px;
  color: #666;
}

.stat-value {
  font-size: 16px;
  font-weight: 600;
  margin-top: 2px;
}

.stat-item.up .stat-value { color: #ec0000; }
.stat-item.down .stat-value { color: #00da3c; }
.stat-item.flat .stat-value { color: #999; }
.stat-item.limit-up .stat-value { color: #ff4d4f; }
.stat-item.limit-down .stat-value { color: #52c41a; }
.stat-item.amount .stat-value { color: #1890ff; }
</style>

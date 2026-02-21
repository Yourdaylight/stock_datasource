<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useScreenerStore } from '@/stores/screener'
import type { Recommendation } from '@/api/screener'

const screenerStore = useScreenerStore()

const emit = defineEmits(['view-detail', 'add-watchlist'])

// A股分类标签
const aShareCategoryLabels: Record<string, string> = {
  low_valuation: '低估值精选',
  strong_momentum: '强势股',
  high_activity: '活跃股',
}

// 港股分类标签
const hkCategoryLabels: Record<string, string> = {
  strong_momentum: '强势港股',
  oversold: '超跌港股',
  high_volume: '高成交港股',
}

// 根据市场类型获取分类标签
const categoryLabels = computed(() => {
  return screenerStore.marketType === 'hk_stock' ? hkCategoryLabels : aShareCategoryLabels
})

const categoryIcons: Record<string, string> = {
  low_valuation: 'chart-pie',
  strong_momentum: 'arrow-up',
  high_activity: 'swap',
  oversold: 'arrow-down',
  high_volume: 'money-circle',
}

const handleViewDetail = (tsCode: string) => {
  emit('view-detail', tsCode)
}

const handleAddWatchlist = (rec: Recommendation) => {
  emit('add-watchlist', rec)
}

// 监听市场类型变化，重新获取推荐
watch(() => screenerStore.marketType, () => {
  screenerStore.fetchRecommendations()
}, { immediate: false })

onMounted(() => {
  screenerStore.fetchRecommendations()
})
</script>

<template>
  <div class="recommendation-panel">
    <t-loading :loading="screenerStore.recommendationsLoading" text="加载推荐...">
      <div v-if="screenerStore.recommendations">
        <div class="trade-date">
          {{ screenerStore.recommendations.trade_date }} 推荐
        </div>
        
        <div 
          v-for="(recs, category) in screenerStore.recommendations.categories" 
          :key="category"
          class="recommendation-category"
        >
          <div class="category-header">
            <t-icon :name="categoryIcons[category] || 'star'" />
            <span>{{ categoryLabels[category] || category }}</span>
          </div>
          
          <div class="recommendation-list">
            <div 
              v-for="rec in recs" 
              :key="rec.ts_code"
              class="recommendation-item"
            >
              <div class="rec-main">
                <div class="rec-stock">
                  <span class="rec-name">{{ rec.stock_name }}</span>
                  <span class="rec-code">{{ rec.ts_code }}</span>
                </div>
                <div class="rec-reason">{{ rec.reason }}</div>
              </div>
              <div class="rec-actions">
                <t-link theme="primary" @click="handleViewDetail(rec.ts_code)">
                  详情
                </t-link>
                <t-link theme="primary" @click="handleAddWatchlist(rec)">
                  加自选
                </t-link>
              </div>
            </div>
          </div>
        </div>
        
        <t-empty 
          v-if="Object.keys(screenerStore.recommendations.categories).length === 0"
          description="暂无推荐"
        />
      </div>
      
      <t-empty v-else description="暂无推荐数据" />
    </t-loading>
  </div>
</template>

<style scoped>
.recommendation-panel {
  padding: 8px 0;
}

.trade-date {
  text-align: center;
  color: var(--td-text-color-secondary);
  font-size: 12px;
  margin-bottom: 16px;
}

.recommendation-category {
  margin-bottom: 20px;
}

.category-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
  font-size: 14px;
  margin-bottom: 12px;
  color: var(--td-brand-color);
}

.recommendation-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.recommendation-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: var(--td-bg-color-container);
  border-radius: 8px;
  transition: background 0.2s;
}

.recommendation-item:hover {
  background: var(--td-bg-color-container-hover);
}

.rec-main {
  flex: 1;
  min-width: 0;
}

.rec-stock {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 4px;
}

.rec-name {
  font-weight: 500;
  font-size: 14px;
}

.rec-code {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.rec-reason {
  font-size: 12px;
  color: var(--td-text-color-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rec-actions {
  display: flex;
  gap: 12px;
  flex-shrink: 0;
  margin-left: 12px;
}
</style>

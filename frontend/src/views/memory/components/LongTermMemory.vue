<script setup lang="ts">
import { computed, ref } from 'vue'
import { useMemoryStore } from '@/stores/memory'
import type { FactOutput } from '@/api/memory'
import { CATEGORY_MAP, getCategoryInfo } from './categoryMap'

const memoryStore = useMemoryStore()
const activeCategory = ref<string>('all')

const emit = defineEmits<{
  (e: 'delete-fact', factId: string): void
}>()

const LONG_TERM_KEYS = ['risk_preference', 'sector_focus', 'stock_opinion', 'trading_style']

const categories = computed(() => {
  const counts: Record<string, number> = {}
  memoryStore.longTermFacts.forEach(f => {
    counts[f.category] = (counts[f.category] || 0) + 1
  })
  return [
    { key: 'all', label: '全部', count: memoryStore.longTermFacts.length },
    ...LONG_TERM_KEYS.map(key => ({
      key,
      label: CATEGORY_MAP[key]?.label ?? key,
      count: counts[key] || 0
    }))
  ]
})

const filteredFacts = computed(() => {
  if (activeCategory.value === 'all') return memoryStore.longTermFacts
  return memoryStore.longTermFacts.filter(f => f.category === activeCategory.value)
})

function getConfidencePercent(confidence: number): number {
  return Math.round(confidence * 100)
}

function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.9) return 'var(--td-success-color)'
  if (confidence >= 0.7) return 'var(--td-brand-color)'
  if (confidence >= 0.5) return 'var(--td-warning-color)'
  return 'var(--td-error-color)'
}

function formatDate(ts: number): string {
  if (!ts) return '--'
  const date = new Date(ts * 1000)
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

function handleDelete(fact: FactOutput) {
  emit('delete-fact', fact.id)
}
</script>

<template>
  <t-card class="longterm-memory-card" :bordered="false">
    <template #header>
      <div class="card-header">
        <div class="card-header__left">
          <t-icon name="root-list" class="header-icon longterm-icon" />
          <span class="header-title">长期记忆</span>
          <t-tag size="small" theme="success" variant="light">高置信</t-tag>
        </div>
        <span class="card-count">{{ memoryStore.longTermFacts.length }} 条累积记忆</span>
      </div>
    </template>

    <!-- Category filter tabs -->
    <div class="category-tabs">
      <div
        v-for="cat in categories"
        :key="cat.key"
        class="category-tab"
        :class="{ active: activeCategory === cat.key }"
        @click="activeCategory = cat.key"
      >
        <span class="tab-label">{{ cat.label }}</span>
        <span class="tab-count">{{ cat.count }}</span>
      </div>
    </div>

    <!-- Facts grid -->
    <div class="facts-grid" v-if="filteredFacts.length > 0">
      <div
        v-for="fact in filteredFacts"
        :key="fact.id"
        class="memory-card"
      >
        <div class="memory-card__header">
          <t-tag
            :theme="getCategoryInfo(fact.category).theme as any"
            size="small"
            variant="light"
          >
            {{ getCategoryInfo(fact.category).label }}
          </t-tag>
          <t-popconfirm content="确定删除此记忆？" @confirm="handleDelete(fact)">
            <t-link theme="danger" size="small" class="delete-btn">
              <t-icon name="delete" size="14px" />
            </t-link>
          </t-popconfirm>
        </div>

        <p class="memory-card__text">{{ fact.content }}</p>

        <!-- Confidence bar -->
        <div class="memory-card__confidence">
          <div class="confidence-bar">
            <div
              class="confidence-fill"
              :style="{
                width: getConfidencePercent(fact.confidence) + '%',
                background: getConfidenceColor(fact.confidence)
              }"
            />
          </div>
          <span class="confidence-label">{{ getConfidencePercent(fact.confidence) }}%</span>
        </div>

        <!-- Reinforce / Contradict counts -->
        <div class="memory-card__footer">
          <div class="reinforce-info">
            <span class="reinforce-count" v-if="fact.reinforced_at?.length">
              <t-icon name="check-circle" size="12px" style="color: var(--td-success-color)" />
              强化 {{ fact.reinforced_at.length }}次
            </span>
            <span class="contradict-count" v-if="fact.contradicted_at?.length">
              <t-icon name="close-circle" size="12px" style="color: var(--td-error-color)" />
              矛盾 {{ fact.contradicted_at.length }}次
            </span>
          </div>
          <span class="memory-date">{{ formatDate(fact.created_at) }}</span>
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <t-empty
      v-if="filteredFacts.length === 0"
      description="暂无该类别的长期记忆"
    />
  </t-card>
</template>

<style scoped>
.longterm-memory-card {
  height: 100%;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-header__left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-icon {
  font-size: 18px;
}

.longterm-icon {
  color: var(--td-success-color);
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--td-text-color-primary);
}

.card-count {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

/* Category tabs */
.category-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 16px;
  overflow-x: auto;
  padding-bottom: 4px;
}

.category-tab {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-radius: 16px;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
  background: var(--td-bg-color-secondarycontainer);
  color: var(--td-text-color-secondary);
  transition: all 0.2s;
}

.category-tab:hover {
  background: var(--td-brand-color-light);
}

.category-tab.active {
  background: var(--td-brand-color);
  color: #fff;
}

.tab-count {
  font-size: 11px;
  opacity: 0.8;
}

/* Facts grid */
.facts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}

.memory-card {
  padding: 14px;
  border-radius: 10px;
  background: var(--td-bg-color-secondarycontainer);
  border: 1px solid var(--td-component-border);
  transition: box-shadow 0.2s, transform 0.2s;
}

.memory-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transform: translateY(-1px);
}

.memory-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.delete-btn {
  opacity: 0;
  transition: opacity 0.2s;
}

.memory-card:hover .delete-btn {
  opacity: 1;
}

.memory-card__text {
  margin: 0 0 10px 0;
  font-size: 13px;
  color: var(--td-text-color-primary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.memory-card__confidence {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.confidence-bar {
  flex: 1;
  height: 4px;
  border-radius: 2px;
  background: var(--td-bg-color-component);
  overflow: hidden;
}

.confidence-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s;
}

.confidence-label {
  font-size: 11px;
  color: var(--td-text-color-secondary);
  min-width: 28px;
  text-align: right;
}

.memory-card__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.reinforce-info {
  display: flex;
  gap: 8px;
}

.reinforce-count,
.contradict-count {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  color: var(--td-text-color-secondary);
}

.memory-date {
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}
</style>

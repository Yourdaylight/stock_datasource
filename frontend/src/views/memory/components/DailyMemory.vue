<script setup lang="ts">
import { computed } from 'vue'
import { useMemoryStore } from '@/stores/memory'
import type { FactOutput } from '@/api/memory'
import { getCategoryInfo } from './categoryMap'

const memoryStore = useMemoryStore()

const emit = defineEmits<{
  (e: 'delete-fact', factId: string): void
}>()

const todayFacts = computed(() => memoryStore.dailyFacts)

const recentConclusions = computed(() => memoryStore.dailyConclusions)

const recentHistory = computed(() => {
  return memoryStore.history.slice(0, 8)
})

function formatTimestamp(ts: number): string {
  if (!ts) return '--'
  const date = new Date(ts * 1000)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function getConfidencePercent(confidence: number): number {
  return Math.round(confidence * 100)
}

function getConfidenceStatus(confidence: number): string {
  if (confidence >= 0.8) return 'success'
  if (confidence >= 0.6) return 'warning'
  return 'error'
}

function handleDelete(fact: FactOutput) {
  emit('delete-fact', fact.id)
}
</script>

<template>
  <t-card class="daily-memory-card" :bordered="false">
    <template #header>
      <div class="card-header">
        <div class="card-header__left">
          <t-icon name="time" class="header-icon daily-icon" />
          <span class="header-title">每日记忆</span>
          <t-tag size="small" theme="primary" variant="light">今日</t-tag>
        </div>
        <span class="card-count">{{ todayFacts.length }} 条新记忆</span>
      </div>
    </template>

    <!-- Today's extracted facts timeline -->
    <div class="daily-section" v-if="todayFacts.length > 0">
      <div class="section-label">今日提取的事实</div>
      <div class="fact-timeline">
        <div
          v-for="fact in todayFacts"
          :key="fact.id"
          class="fact-item"
        >
          <div class="fact-item__time">{{ formatTimestamp(fact.created_at) }}</div>
          <div class="fact-item__content">
            <div class="fact-item__top">
              <t-tag
                :theme="getCategoryInfo(fact.category).theme as any"
                size="small"
                variant="light"
              >
                {{ getCategoryInfo(fact.category).label }}
              </t-tag>
              <div class="fact-item__confidence">
                <t-progress
                  :percentage="getConfidencePercent(fact.confidence)"
                  :status="getConfidenceStatus(fact.confidence) as any"
                  size="small"
                  :stroke-width="4"
                  style="width: 60px"
                />
                <span class="conf-text">{{ getConfidencePercent(fact.confidence) }}%</span>
              </div>
            </div>
            <p class="fact-text">{{ fact.content }}</p>
            <div class="fact-item__meta">
              <span v-if="fact.source" class="fact-source">来源: {{ fact.source }}</span>
              <t-popconfirm content="确定删除此记忆？" @confirm="handleDelete(fact)">
                <t-link theme="danger" size="small">删除</t-link>
              </t-popconfirm>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Recent interaction feed -->
    <div class="daily-section" v-if="recentHistory.length > 0">
      <div class="section-label">近期交互</div>
      <div class="history-feed">
        <div
          v-for="item in recentHistory"
          :key="item.id"
          class="history-item"
        >
          <div class="history-item__intent">
            <t-icon name="chat" size="14px" />
            <span>{{ item.intent }}</span>
          </div>
          <p class="history-item__input">{{ item.user_input }}</p>
          <div class="history-item__stocks" v-if="item.stocks_mentioned?.length">
            <t-tag
              v-for="stock in item.stocks_mentioned"
              :key="stock"
              size="small"
              variant="outline"
            >
              {{ stock }}
            </t-tag>
          </div>
          <span class="history-item__time">{{ item.timestamp }}</span>
        </div>
      </div>
    </div>

    <!-- Recent conclusions -->
    <div class="daily-section" v-if="recentConclusions.length > 0">
      <div class="section-label">今日结论</div>
      <div class="conclusions-list">
        <div
          v-for="concl in recentConclusions"
          :key="concl.id"
          class="conclusion-item"
        >
          <t-icon name="lightbulb" class="concl-icon" />
          <div class="conclusion-content">
            <p v-if="concl.data.summary">{{ concl.data.summary }}</p>
            <p v-else-if="concl.data.intent">{{ concl.data.intent }}: {{ concl.data.user_message }}</p>
            <p v-else>{{ JSON.stringify(concl.data).slice(0, 120) }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <t-empty
      v-if="todayFacts.length === 0 && recentHistory.length === 0 && recentConclusions.length === 0"
      description="今日暂无新记忆，与AI对话后将自动提取"
    />
  </t-card>
</template>

<style scoped>
.daily-memory-card {
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

.daily-icon {
  color: var(--td-brand-color);
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

.daily-section {
  margin-bottom: 20px;
}

.daily-section:last-child {
  margin-bottom: 0;
}

.section-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--td-text-color-secondary);
  margin-bottom: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* Fact timeline */
.fact-timeline {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.fact-item {
  display: flex;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--td-bg-color-secondarycontainer);
  transition: background 0.2s;
}

.fact-item:hover {
  background: var(--td-bg-color-container-hover);
}

.fact-item__time {
  font-size: 11px;
  color: var(--td-text-color-placeholder);
  white-space: nowrap;
  padding-top: 2px;
  min-width: 42px;
}

.fact-item__content {
  flex: 1;
  min-width: 0;
}

.fact-item__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 4px;
}

.fact-item__confidence {
  display: flex;
  align-items: center;
  gap: 4px;
}

.conf-text {
  font-size: 11px;
  color: var(--td-text-color-secondary);
  min-width: 28px;
}

.fact-text {
  margin: 0;
  font-size: 13px;
  color: var(--td-text-color-primary);
  line-height: 1.5;
}

.fact-item__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 4px;
}

.fact-source {
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}

/* History feed */
.history-feed {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.history-item {
  padding: 8px 12px;
  border-radius: 6px;
  border-left: 3px solid var(--td-brand-color-light);
  background: var(--td-bg-color-secondarycontainer);
}

.history-item__intent {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;
  color: var(--td-brand-color);
  margin-bottom: 4px;
}

.history-item__input {
  margin: 0 0 4px 0;
  font-size: 13px;
  color: var(--td-text-color-primary);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-item__stocks {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}

.history-item__time {
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}

/* Conclusions */
.conclusions-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.conclusion-item {
  display: flex;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  background: var(--td-bg-color-secondarycontainer);
}

.concl-icon {
  color: var(--td-warning-color);
  margin-top: 2px;
  flex-shrink: 0;
}

.conclusion-content p {
  margin: 0;
  font-size: 13px;
  color: var(--td-text-color-primary);
  line-height: 1.4;
}
</style>

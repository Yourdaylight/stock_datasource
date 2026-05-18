<script setup lang="ts">
import { computed } from 'vue'
import { useMemoryStore } from '@/stores/memory'
import type { FactOutput } from '@/api/memory'
import { getCategoryInfo } from './categoryMap'

const memoryStore = useMemoryStore()

const emit = defineEmits<{
  (e: 'delete-fact', factId: string): void
}>()

// Group scenario facts by stock/topic
const groupedScenarios = computed(() => {
  const groups: Record<string, { topic: string; facts: FactOutput[]; conclusions: any[] }> = {}

  // Group facts by stock code or category
  memoryStore.scenarioFacts.forEach(fact => {
    const codeMatch = fact.content.match(/(\d{6}\.[A-Z]{2}|\d{6})/)
    const key = codeMatch ? codeMatch[1] : fact.category

    if (!groups[key]) {
      groups[key] = { topic: key, facts: [], conclusions: [] }
    }
    groups[key].facts.push(fact)
  })

  // Add conclusions
  memoryStore.conclusions.forEach(concl => {
    const stocks = concl.data.stocks || []
    if (stocks.length > 0) {
      const key = stocks[0]
      if (!groups[key]) {
        groups[key] = { topic: key, facts: [], conclusions: [] }
      }
      groups[key].conclusions.push(concl)
    } else {
      const key = concl.data.intent || 'general'
      if (!groups[key]) {
        groups[key] = { topic: key, facts: [], conclusions: [] }
      }
      groups[key].conclusions.push(concl)
    }
  })

  return Object.values(groups)
    .filter(g => g.facts.length > 0 || g.conclusions.length > 0)
    .sort((a, b) => (b.facts.length + b.conclusions.length) - (a.facts.length + a.conclusions.length))
})

function formatTimestamp(ts: number): string {
  if (!ts) return '--'
  const date = new Date(ts * 1000)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

function getTopicLabel(topic: string): string {
  if (/\d{6}/.test(topic)) return topic
  const labels: Record<string, string> = {
    market_signal: '市场信号汇总',
    capital_flow: '资金流向分析',
    conclusion: '综合分析',
    general: '通用讨论'
  }
  return labels[topic] || topic
}

function getTopicIcon(topic: string): string {
  if (/\d{6}/.test(topic)) return 'chart-line'
  const icons: Record<string, string> = {
    market_signal: 'alarm',
    capital_flow: 'swap',
    conclusion: 'lightbulb'
  }
  return icons[topic] || 'folder'
}

function handleDelete(fact: FactOutput) {
  emit('delete-fact', fact.id)
}
</script>

<template>
  <t-card class="scenario-memory-card" :bordered="false">
    <template #header>
      <div class="card-header">
        <div class="card-header__left">
          <t-icon name="layers" class="header-icon scenario-icon" />
          <span class="header-title">场景记忆</span>
          <t-tag size="small" theme="warning" variant="light">Agent协作</t-tag>
        </div>
        <span class="card-count">{{ groupedScenarios.length }} 个场景</span>
      </div>
    </template>

    <!-- Scenario groups -->
    <div class="scenario-list" v-if="groupedScenarios.length > 0">
      <div
        v-for="(group, index) in groupedScenarios"
        :key="index"
        class="scenario-group"
      >
        <div class="scenario-group__header">
          <div class="group-topic">
            <t-icon :name="getTopicIcon(group.topic)" size="16px" />
            <span class="topic-label">{{ getTopicLabel(group.topic) }}</span>
          </div>
          <t-tag size="small" variant="outline">
            {{ group.facts.length + group.conclusions.length }} 条
          </t-tag>
        </div>

        <!-- Facts in this scenario -->
        <div class="scenario-facts">
          <div
            v-for="fact in group.facts.slice(0, 5)"
            :key="fact.id"
            class="scenario-fact-item"
          >
            <div class="scenario-fact-item__left">
              <t-tag
                :theme="getCategoryInfo(fact.category).theme as any"
                size="small"
                variant="light"
              >
                {{ getCategoryInfo(fact.category).label }}
              </t-tag>
              <span class="fact-text">{{ fact.content }}</span>
            </div>
            <div class="scenario-fact-item__right">
              <span class="fact-time">{{ formatTimestamp(fact.created_at) }}</span>
              <t-link theme="danger" size="small" @click.stop="handleDelete(fact)">
                <t-icon name="close" size="12px" />
              </t-link>
            </div>
          </div>

          <!-- Conclusions in this scenario -->
          <div
            v-for="concl in group.conclusions.slice(0, 3)"
            :key="concl.id"
            class="scenario-conclusion-item"
          >
            <t-icon name="lightbulb" size="14px" class="concl-bullet" />
            <div class="conclusion-body">
              <span class="conclusion-text" v-if="concl.data.summary">
                {{ concl.data.summary }}
              </span>
              <span class="conclusion-text" v-else-if="concl.data.intent">
                {{ concl.data.intent }}
              </span>
              <span class="conclusion-time">{{ formatTimestamp(concl.stored_at) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <t-empty
      v-if="groupedScenarios.length === 0"
      description="暂无场景记忆，Agent协作讨论后将自动生成"
    />
  </t-card>
</template>

<style scoped>
.scenario-memory-card {
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

.scenario-icon {
  color: var(--td-warning-color);
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

/* Scenario groups */
.scenario-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.scenario-group {
  padding: 14px;
  border-radius: 10px;
  background: var(--td-bg-color-secondarycontainer);
  border: 1px solid var(--td-component-border);
}

.scenario-group__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--td-component-border);
}

.group-topic {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--td-text-color-primary);
  font-weight: 500;
  font-size: 14px;
}

.topic-label {
  font-weight: 600;
}

.scenario-facts {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.scenario-fact-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  border-radius: 6px;
  background: var(--td-bg-color-container);
  gap: 8px;
}

.scenario-fact-item__left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.scenario-fact-item__left .fact-text {
  font-size: 13px;
  color: var(--td-text-color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.scenario-fact-item__right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.fact-time {
  font-size: 11px;
  color: var(--td-text-color-placeholder);
  white-space: nowrap;
}

.scenario-conclusion-item {
  display: flex;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  background: var(--td-bg-color-container);
  border-left: 3px solid var(--td-warning-color-light);
}

.concl-bullet {
  color: var(--td-warning-color);
  margin-top: 2px;
  flex-shrink: 0;
}

.conclusion-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.conclusion-text {
  font-size: 13px;
  color: var(--td-text-color-primary);
  line-height: 1.4;
}

.conclusion-time {
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}
</style>

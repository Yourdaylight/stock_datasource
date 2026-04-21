<script setup lang="ts">
import { ref } from 'vue'
import type { QAHistoryEntry } from '@/stores/akinator'

interface Props {
  history: QAHistoryEntry[]
}

defineProps<Props>()

const expanded = ref(false)

const answerLabel = (ans: string) => {
  const map: Record<string, string> = { yes: '是', no: '不是', unknown: '不确定' }
  return map[ans] || ans
}

const answerTheme = (ans: string) => {
  const map: Record<string, string> = { yes: 'success', no: 'danger', unknown: 'default' }
  return map[ans] || 'default'
}
</script>

<template>
  <div v-if="history.length" class="qa-history">
    <div class="qa-header" @click="expanded = !expanded">
      <span class="qa-title">
        <t-icon name="history" /> 历史问答 ({{ history.length }})
      </span>
      <t-icon :name="expanded ? 'chevron-up' : 'chevron-down'" />
    </div>
    <transition name="slide">
      <div v-if="expanded" class="qa-list">
        <div
          v-for="(entry, idx) in history"
          :key="idx"
          class="qa-item"
        >
          <div class="qa-item-header">
            <span class="qa-round">Q{{ idx + 1 }}</span>
            <span class="qa-question">{{ entry.question }}</span>
            <t-tag :theme="answerTheme(entry.answer)" size="small" variant="light">
              {{ answerLabel(entry.answer) }}
            </t-tag>
          </div>
          <div class="qa-item-stats">
            候选: {{ entry.candidatesBefore }} → {{ entry.candidatesAfter }}
            <span v-if="entry.candidatesBefore > entry.candidatesAfter" class="qa-reduced">
              (-{{ entry.candidatesBefore - entry.candidatesAfter }})
            </span>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.qa-history {
  padding: 8px 12px;
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-component-stroke);
  border-radius: 8px;
}

.qa-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  font-size: 13px;
  color: var(--td-text-color-secondary);
  padding: 4px 0;
}

.qa-title {
  display: flex;
  align-items: center;
  gap: 6px;
}

.qa-list {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 240px;
  overflow-y: auto;
}

.qa-item {
  padding: 8px 10px;
  background: var(--td-bg-color-component);
  border-radius: 6px;
  font-size: 12px;
}

.qa-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.qa-round {
  font-weight: 600;
  color: var(--td-brand-color);
  min-width: 28px;
}

.qa-question {
  flex: 1;
  color: var(--td-text-color-primary);
}

.qa-item-stats {
  margin-top: 4px;
  color: var(--td-text-color-placeholder);
  font-size: 11px;
  padding-left: 36px;
}

.qa-reduced {
  color: var(--td-success-color);
  margin-left: 6px;
}

.slide-enter-active, .slide-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}

.slide-enter-from, .slide-leave-to {
  max-height: 0;
  opacity: 0;
}

.slide-enter-to, .slide-leave-from {
  max-height: 400px;
  opacity: 1;
}
</style>

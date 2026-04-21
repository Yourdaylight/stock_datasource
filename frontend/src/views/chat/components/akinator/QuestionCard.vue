<script setup lang="ts">
import { ref } from 'vue'
import type { QuestionDTO } from '@/api/akinator'
import type { AnswerType } from '@/api/akinator'

interface Props {
  question: QuestionDTO
  loading?: boolean
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  disabled: false,
})

const emit = defineEmits<{
  (e: 'answer', ans: AnswerType): void
}>()

const showReasoning = ref(false)

const handle = (ans: AnswerType) => {
  if (props.loading || props.disabled) return
  emit('answer', ans)
}
</script>

<template>
  <div class="question-card">
    <div class="qc-title">
      <t-icon name="help-circle" class="qc-icon" />
      {{ question.question }}
    </div>

    <div class="qc-actions">
      <t-button
        theme="success"
        size="large"
        :loading="loading"
        :disabled="disabled"
        class="qc-btn"
        @click="handle('yes')"
      >
        <template #icon><t-icon name="check" /></template>
        是
      </t-button>
      <t-button
        theme="danger"
        size="large"
        variant="outline"
        :loading="loading"
        :disabled="disabled"
        class="qc-btn"
        @click="handle('no')"
      >
        <template #icon><t-icon name="close" /></template>
        不是
      </t-button>
      <t-button
        theme="default"
        size="large"
        variant="outline"
        :loading="loading"
        :disabled="disabled"
        class="qc-btn"
        @click="handle('unknown')"
      >
        <template #icon><t-icon name="help" /></template>
        不确定
      </t-button>
    </div>

    <div v-if="question.reasoning" class="qc-reasoning">
      <t-button
        theme="default"
        variant="text"
        size="small"
        @click="showReasoning = !showReasoning"
      >
        <template #icon><t-icon :name="showReasoning ? 'chevron-up' : 'chevron-down'" /></template>
        {{ showReasoning ? '隐藏' : '查看' }}提问思路
      </t-button>
      <div v-if="showReasoning" class="qc-reasoning-text">
        💡 {{ question.reasoning }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.question-card {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 28px 24px;
  background: linear-gradient(135deg, var(--td-bg-color-container) 0%, var(--td-brand-color-light) 100%);
  border: 1px solid var(--td-component-stroke);
  border-radius: 12px;
}

.qc-title {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 20px;
  font-weight: 600;
  color: var(--td-text-color-primary);
  line-height: 1.5;
}

.qc-icon {
  color: var(--td-brand-color);
  font-size: 24px;
  flex-shrink: 0;
}

.qc-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.qc-btn {
  flex: 1;
  max-width: 140px;
  min-height: 44px;
  font-size: 15px;
}

.qc-reasoning {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.qc-reasoning-text {
  padding: 10px 12px;
  background: var(--td-bg-color-component);
  border-radius: 6px;
  color: var(--td-text-color-secondary);
  font-size: 13px;
  line-height: 1.5;
}
</style>

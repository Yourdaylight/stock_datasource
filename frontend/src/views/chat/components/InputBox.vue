<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  disabled?: boolean
}>()

const emit = defineEmits<{
  send: [content: string]
}>()

const inputValue = ref('')

const handleSend = () => {
  const content = inputValue.value.trim()
  if (content && !props.disabled) {
    emit('send', content)
    inputValue.value = ''
  }
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}
</script>

<template>
  <div class="input-box">
    <t-textarea
      v-model="inputValue"
      placeholder="输入您的问题，例如：分析贵州茅台的走势 / 分析腾讯 00700.HK 技术指标"
      :autosize="{ minRows: 1, maxRows: 4 }"
      :disabled="disabled"
      @keydown="handleKeydown"
    />
    <t-button
      theme="primary"
      :disabled="!inputValue.trim() || disabled"
      @click="handleSend"
    >
      <template #icon><t-icon name="send" /></template>
      发送
    </t-button>
  </div>
</template>

<style scoped>
.input-box {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.input-box :deep(.t-textarea__inner) {
  flex: 1;
}
</style>

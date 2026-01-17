<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { useOverviewStore } from '@/stores/overview'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

const overviewStore = useOverviewStore()

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

const question = ref('')
const messagesRef = ref<HTMLElement>()

// Preset questions for market analysis
const presetQuestions = [
  '今日市场整体表现如何？',
  '哪些板块表现最强？',
  '今日热门ETF有哪些？',
  '当前市场情绪如何？',
  '今日涨停板有多少家？',
  '哪些行业板块领涨？',
]

interface Message {
  role: 'user' | 'assistant'
  content: string
}

const messages = ref<Message[]>([])

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

const handleSend = async () => {
  if (!question.value.trim() || overviewStore.analysisLoading) return

  const userQuestion = question.value.trim()
  messages.value.push({ role: 'user', content: userQuestion })
  question.value = ''
  scrollToBottom()

  try {
    await overviewStore.runAIAnalysis(userQuestion)
    if (overviewStore.aiAnalysisResult) {
      messages.value.push({ role: 'assistant', content: overviewStore.aiAnalysisResult })
      scrollToBottom()
    }
  } catch (e) {
    messages.value.push({ role: 'assistant', content: '抱歉，分析失败，请稍后重试。' })
    scrollToBottom()
  }
}

const handlePresetClick = (q: string) => {
  question.value = q
  handleSend()
}

const handleClear = async () => {
  messages.value = []
  await overviewStore.clearConversation()
}

const handleKeyDown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

// Reset messages when dialog opens
watch(() => props.visible, (val) => {
  if (val && messages.value.length === 0) {
    // Show welcome message
    messages.value.push({
      role: 'assistant',
      content: '您好！我是行情分析助手，可以帮您分析今日市场表现、板块走势、热门ETF等。请选择下方的问题或直接输入您想了解的内容。'
    })
  }
})
</script>

<template>
  <t-drawer
    v-model:visible="dialogVisible"
    header="行情分析助手"
    size="400px"
    :footer="false"
    :close-on-overlay-click="true"
  >
    <div class="ai-dialog">
      <!-- Preset Questions -->
      <div class="preset-section">
        <div class="preset-title">快捷问题</div>
        <div class="preset-list">
          <t-tag
            v-for="(q, idx) in presetQuestions"
            :key="idx"
            class="preset-tag"
            @click="handlePresetClick(q)"
          >
            {{ q }}
          </t-tag>
        </div>
      </div>

      <!-- Messages -->
      <div ref="messagesRef" class="messages-container">
        <div
          v-for="(msg, idx) in messages"
          :key="idx"
          :class="['message', msg.role]"
        >
          <div class="message-avatar">
            <t-icon :name="msg.role === 'user' ? 'user' : 'service'" />
          </div>
          <div class="message-content">
            <div class="message-text" v-html="msg.content.replace(/\n/g, '<br>')"></div>
          </div>
        </div>

        <!-- Loading indicator -->
        <div v-if="overviewStore.analysisLoading" class="message assistant">
          <div class="message-avatar">
            <t-icon name="service" />
          </div>
          <div class="message-content">
            <t-loading size="small" text="分析中..." />
          </div>
        </div>
      </div>

      <!-- Input Area -->
      <div class="input-area">
        <div class="input-wrapper">
          <t-textarea
            v-model="question"
            placeholder="输入您的问题..."
            :autosize="{ minRows: 1, maxRows: 3 }"
            @keydown="handleKeyDown"
          />
          <div class="input-actions">
            <t-button
              theme="primary"
              size="small"
              :loading="overviewStore.analysisLoading"
              :disabled="!question.trim()"
              @click="handleSend"
            >
              发送
            </t-button>
            <t-button
              variant="text"
              size="small"
              @click="handleClear"
            >
              清空
            </t-button>
          </div>
        </div>
        <div class="history-info" v-if="overviewStore.historyLength > 0">
          对话轮次: {{ overviewStore.historyLength }}
        </div>
      </div>
    </div>
  </t-drawer>
</template>

<style scoped>
.ai-dialog {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.preset-section {
  flex-shrink: 0;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--td-component-stroke);
  margin-bottom: 12px;
}

.preset-title {
  font-size: 12px;
  color: var(--td-text-color-secondary);
  margin-bottom: 8px;
}

.preset-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.preset-tag {
  cursor: pointer;
  transition: all 0.2s;
}

.preset-tag:hover {
  color: var(--td-brand-color);
  border-color: var(--td-brand-color);
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.message {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--td-bg-color-container-hover);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.message.user .message-avatar {
  background: var(--td-brand-color-light);
  color: var(--td-brand-color);
}

.message.assistant .message-avatar {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.message-content {
  max-width: 80%;
}

.message-text {
  padding: 10px 14px;
  border-radius: 12px;
  line-height: 1.5;
  font-size: 14px;
}

.message.user .message-text {
  background: var(--td-brand-color);
  color: white;
  border-bottom-right-radius: 4px;
}

.message.assistant .message-text {
  background: var(--td-bg-color-container-hover);
  border-bottom-left-radius: 4px;
}

.input-area {
  flex-shrink: 0;
  padding-top: 12px;
  border-top: 1px solid var(--td-component-stroke);
}

.input-wrapper {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

.input-wrapper :deep(.t-textarea__inner) {
  border-radius: 8px;
}

.input-actions {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.history-info {
  font-size: 11px;
  color: var(--td-text-color-placeholder);
  margin-top: 8px;
  text-align: right;
}
</style>

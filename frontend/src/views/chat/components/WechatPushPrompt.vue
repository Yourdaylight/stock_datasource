<template>
  <div class="wechat-push-prompt" v-if="visible">
    <div class="prompt-card">
      <button class="prompt-close" @click="dismiss">×</button>
      <div class="prompt-icon">📱</div>
      <div class="prompt-content">
        <div class="prompt-title">开启微信推送</div>
        <div class="prompt-desc">
          你已完成 {{ analysisCount }} 次分析。连接微信后，AI分析师的买卖信号和异动提醒会自动推送到你的微信。
        </div>
      </div>
      <div class="prompt-actions">
        <button class="prompt-btn prompt-btn-primary" @click="goSetup">
          <t-icon name="logo-wechat" size="16px" />
          <span>去设置</span>
        </button>
        <button class="prompt-btn prompt-btn-secondary" @click="remindLater">
          以后再说
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '@/stores/chat'

const router = useRouter()
const chatStore = useChatStore()

const STORAGE_KEY = 'wechat_push_prompt'
const ANALYSIS_THRESHOLD = 3

const dismissed = ref(false)
const remindLaterUntil = ref(0)

// Track analysis count from session messages (count assistant messages with stock_codes)
const analysisCount = computed(() => {
  return chatStore.messages.filter(
    m => m.role === 'assistant' && m.metadata?.stock_codes?.length
  ).length
})

const visible = computed(() => {
  if (dismissed.value) return false
  if (Date.now() < remindLaterUntil.value) return false
  return analysisCount.value >= ANALYSIS_THRESHOLD
})

onMounted(() => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      const data = JSON.parse(stored)
      if (data.dismissed) dismissed.value = true
      if (data.remindLaterUntil) remindLaterUntil.value = data.remindLaterUntil
    }
  } catch { /* ignore */ }
})

const dismiss = () => {
  dismissed.value = true
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ dismissed: true }))
}

const remindLater = () => {
  // Don't show again for 24 hours
  const until = Date.now() + 24 * 60 * 60 * 1000
  remindLaterUntil.value = until
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ remindLaterUntil: until }))
}

const goSetup = () => {
  router.push('/wechat-bridge')
}
</script>

<style scoped>
.wechat-push-prompt {
  position: fixed;
  bottom: 100px;
  right: 24px;
  z-index: 1000;
  animation: slideUp 0.3s ease-out;
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

.prompt-card {
  position: relative;
  width: 300px;
  padding: 20px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
  border: 1px solid var(--td-component-border, #e7e7e7);
}

.prompt-close {
  position: absolute;
  top: 8px;
  right: 12px;
  background: none;
  border: none;
  font-size: 18px;
  color: var(--td-text-color-placeholder);
  cursor: pointer;
  line-height: 1;
}

.prompt-close:hover {
  color: var(--td-text-color-primary);
}

.prompt-icon {
  font-size: 32px;
  margin-bottom: 8px;
}

.prompt-content {
  margin-bottom: 16px;
}

.prompt-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--td-text-color-primary);
  margin-bottom: 6px;
}

.prompt-desc {
  font-size: 13px;
  color: var(--td-text-color-secondary);
  line-height: 1.5;
}

.prompt-actions {
  display: flex;
  gap: 8px;
}

.prompt-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.prompt-btn-primary {
  background: #07c160;
  color: white;
  font-weight: 500;
}

.prompt-btn-primary:hover {
  background: #06ad56;
}

.prompt-btn-secondary {
  background: var(--td-bg-color-secondarycontainer, #f5f5f5);
  color: var(--td-text-color-secondary);
}

.prompt-btn-secondary:hover {
  background: var(--td-bg-color-container-hover, #eee);
}
</style>

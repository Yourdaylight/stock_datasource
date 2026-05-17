<template>
  <div class="post-analysis-actions" v-if="visible">
    <div class="actions-divider">
      <span>接下来</span>
    </div>
    <div class="actions-row">
      <button class="action-btn action-follow" @click="handleFollowUp">
        <t-icon name="chat" size="18px" />
        <span>深入追问</span>
        <span class="action-hint">{{ followUpHint }}</span>
      </button>
      <button class="action-btn action-watchlist" :class="{ done: addedToWatchlist }" :disabled="watchlistLoading || addedToWatchlist" @click="handleAddWatchlist">
        <t-icon :name="addedToWatchlist ? 'check' : 'star'" size="18px" />
        <span>{{ addedToWatchlist ? '已加自选' : '加入自选' }}</span>
      </button>
      <button class="action-btn action-alert" :class="{ done: alertSet }" :disabled="alertLoading || alertSet" @click="handleSetAlert">
        <t-icon :name="alertSet ? 'check' : 'notification'" size="18px" />
        <span>{{ alertSet ? '已设提醒' : '设置提醒' }}</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { request } from '@/utils/request'

const props = defineProps<{
  signal?: string         // BUY / SELL / HOLD
  stockCode?: string      // 600519.SH
  confidence?: number     // 0.0 ~ 1.0
}>()

const emit = defineEmits<{
  (e: 'followUp', query: string): void
}>()

const visible = computed(() => !!props.signal || !!props.stockCode)
const watchlistLoading = ref(false)
const alertLoading = ref(false)
const addedToWatchlist = ref(false)
const alertSet = ref(false)

const followUpHint = computed(() => {
  if (props.signal === 'BUY' || props.signal === 'buy') return '"为什么看多？"'
  if (props.signal === 'SELL' || props.signal === 'sell') return '"主要风险是什么？"'
  return '"能详细说说吗？"'
})

function handleFollowUp() {
  const stock = props.stockCode || ''
  let query = '能详细说说分析理由吗？'
  if (props.signal === 'BUY' || props.signal === 'buy') {
    query = `${stock}为什么看多？主要支撑逻辑是什么？`
  } else if (props.signal === 'SELL' || props.signal === 'sell') {
    query = `${stock}看空的主要风险点有哪些？`
  }
  emit('followUp', query)
}

async function handleAddWatchlist() {
  if (!props.stockCode || addedToWatchlist.value) return
  watchlistLoading.value = true
  try {
    const params = new URLSearchParams({ ts_code: props.stockCode, source: 'chat' })
    await request.post(`/api/portfolio/watchlist?${params}`)
    addedToWatchlist.value = true
    MessagePlugin.success(`已加入自选: ${props.stockCode}`)
  } catch (e) {
    MessagePlugin.error('加入自选失败')
  } finally {
    watchlistLoading.value = false
  }
}

async function handleSetAlert() {
  if (!props.stockCode || alertSet.value) return
  alertLoading.value = true
  try {
    const params = new URLSearchParams({
      ts_code: props.stockCode,
      alert_type: 'price',
      message: `${props.stockCode} 异动提醒`,
    })
    await request.post(`/api/portfolio/alerts/quick?${params}`)
    alertSet.value = true
    MessagePlugin.success(`已设置提醒: ${props.stockCode}`)
  } catch (e) {
    MessagePlugin.error('设置提醒失败')
  } finally {
    alertLoading.value = false
  }
}
</script>

<style scoped>
.post-analysis-actions {
  margin-top: 12px;
}

.actions-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
  font-size: 12px;
  color: var(--td-text-color-placeholder);
}

.actions-divider::before,
.actions-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--td-component-border);
}

.actions-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 8px;
  border: 1px solid var(--td-component-border);
  background: var(--td-bg-color-container);
  color: var(--td-text-color-primary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover {
  border-color: var(--td-brand-color);
  color: var(--td-brand-color);
  background: var(--td-brand-color-light);
}

.action-btn.done {
  border-color: var(--td-success-color);
  color: var(--td-success-color);
  background: var(--td-success-color-light);
  cursor: default;
}

.action-btn:disabled {
  opacity: 0.7;
  cursor: default;
}

.action-hint {
  font-size: 12px;
  color: var(--td-text-color-placeholder);
}

.action-follow {
  flex: 1;
  min-width: 180px;
}

@media (max-width: 768px) {
  .actions-row {
    flex-direction: column;
  }
  .action-btn {
    justify-content: center;
  }
}
</style>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import request from '@/utils/request'

const authStore = useAuthStore()

const balance = ref<{
  total_quota: number
  used_tokens: number
  remaining_tokens: number
  usage_percent: number
} | null>(null)

const loading = ref(false)

const tierLabel = computed(() => {
  const map: Record<string, string> = { free: '体验版', pro: '专业版', admin: '管理员' }
  return map[authStore.userTier] || '体验版'
})

const tierTheme = computed(() => {
  const map: Record<string, string> = { free: 'default', pro: 'primary', admin: 'warning' }
  return map[authStore.userTier] || 'default'
})

const usagePercent = computed(() => {
  if (!balance.value) return 0
  return Math.min(balance.value.usage_percent, 100)
})

const usageColor = computed(() => {
  const pct = usagePercent.value
  if (pct >= 90) return '#d54941'
  if (pct >= 70) return '#e37318'
  return '#0052d9'
})

const formatTokens = (n: number) => {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
  return String(n)
}

const fetchBalance = async () => {
  if (!authStore.isAuthenticated) return
  loading.value = true
  try {
    const resp = await request.get('/api/token/balance')
    balance.value = resp as any
  } catch {
    balance.value = null
  } finally {
    loading.value = false
  }
}

onMounted(fetchBalance)
</script>

<template>
  <div class="quota-indicator" v-if="authStore.isAuthenticated">
    <t-popup placement="bottom" trigger="hover">
      <div class="quota-trigger">
        <t-tag :theme="tierTheme" size="small" variant="light">
          {{ tierLabel }}
        </t-tag>
        <div v-if="balance" class="quota-bar-mini">
          <div
            class="quota-bar-fill"
            :style="{ width: usagePercent + '%', background: usageColor }"
          />
        </div>
      </div>
      <template #content>
        <div class="quota-popup">
          <div class="quota-header">
            <span>账户等级：{{ tierLabel }}</span>
          </div>
          <div v-if="balance" class="quota-detail">
            <div class="quota-row">
              <span>已用</span>
              <span>{{ formatTokens(balance.used_tokens) }} / {{ formatTokens(balance.total_quota) }}</span>
            </div>
            <t-progress
              :percentage="usagePercent"
              :color="usageColor"
              size="small"
              :label="usagePercent.toFixed(0) + '%'"
            />
            <div class="quota-row remaining">
              <span>剩余</span>
              <span :style="{ color: usageColor }">{{ formatTokens(balance.remaining_tokens) }} tokens</span>
            </div>
          </div>
          <div v-else class="quota-empty">
            暂无用量数据
          </div>
        </div>
      </template>
    </t-popup>
  </div>
</template>

<style scoped>
.quota-indicator {
  display: flex;
  align-items: center;
}

.quota-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.quota-bar-mini {
  width: 40px;
  height: 4px;
  background: var(--td-bg-color-component);
  border-radius: 2px;
  overflow: hidden;
}

.quota-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s;
}

.quota-popup {
  padding: 8px;
  min-width: 200px;
}

.quota-header {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--td-text-color-primary);
}

.quota-detail {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.quota-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.quota-row.remaining {
  font-weight: 500;
}

.quota-empty {
  font-size: 12px;
  color: var(--td-text-color-placeholder);
}
</style>

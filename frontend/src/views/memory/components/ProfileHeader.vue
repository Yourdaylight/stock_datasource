<script setup lang="ts">
import { computed } from 'vue'
import { useMemoryStore } from '@/stores/memory'

const memoryStore = useMemoryStore()

const riskLevelMap: Record<string, { label: string; theme: string }> = {
  conservative: { label: '保守型', theme: 'warning' },
  moderate: { label: '稳健型', theme: 'primary' },
  aggressive: { label: '激进型', theme: 'danger' }
}

const styleMap: Record<string, string> = {
  value: '价值投资',
  growth: '成长投资',
  balanced: '均衡投资',
  momentum: '动量投资'
}

const activeLevelMap: Record<string, { label: string; theme: string }> = {
  high: { label: '高活跃', theme: 'success' },
  medium: { label: '中等活跃', theme: 'primary' },
  low: { label: '低活跃', theme: 'default' }
}

const riskInfo = computed(() => {
  return riskLevelMap[memoryStore.preference.risk_level] || { label: '未知', theme: 'default' }
})

const activeInfo = computed(() => {
  return activeLevelMap[memoryStore.profile?.active_level || 'medium'] || { label: '未知', theme: 'default' }
})

const totalFacts = computed(() => memoryStore.memoryCounts.facts)
const totalConclusions = computed(() => memoryStore.memoryCounts.conclusions)
const totalInteractions = computed(() => memoryStore.memoryCounts.interactions)
const highConfidenceFacts = computed(() => memoryStore.facts.filter(f => f.confidence >= 0.8).length)
</script>

<template>
  <div class="profile-header">
    <div class="profile-header__left">
      <div class="profile-avatar">
        <t-icon name="user-circle" size="48px" />
      </div>
      <div class="profile-info">
        <h2 class="profile-title">用户记忆系统</h2>
        <p class="profile-subtitle">
          AI 从对话中自动提取并维护的用户画像 · 共
          <strong>{{ totalFacts }}</strong> 条记忆 ·
          <strong>{{ totalConclusions }}</strong> 条结论 ·
          <strong>{{ totalInteractions }}</strong> 次交互
          <span class="high-conf" v-if="highConfidenceFacts">({{ highConfidenceFacts }} 条高置信)</span>
        </p>
      </div>
    </div>
    <div class="profile-header__stats">
      <div class="stat-item">
        <span class="stat-label">风险偏好</span>
        <t-tag :theme="riskInfo.theme as any" variant="light" size="medium">
          {{ riskInfo.label }}
        </t-tag>
      </div>
      <div class="stat-item">
        <span class="stat-label">投资风格</span>
        <t-tag theme="primary" variant="outline" size="medium">
          {{ styleMap[memoryStore.preference.investment_style] || '未知' }}
        </t-tag>
      </div>
      <div class="stat-item">
        <span class="stat-label">活跃度</span>
        <t-tag :theme="activeInfo.theme as any" variant="light" size="medium">
          {{ activeInfo.label }}
        </t-tag>
      </div>
      <div class="stat-item">
        <span class="stat-label">专业度</span>
        <t-tag theme="default" variant="light" size="medium">
          {{ memoryStore.profile?.expertise_level || '中级' }}
        </t-tag>
      </div>
      <div class="stat-item" v-if="memoryStore.profile?.focus_industries?.length">
        <span class="stat-label">关注板块</span>
        <div class="tags-inline">
          <t-tag
            v-for="ind in memoryStore.profile.focus_industries.slice(0, 4)"
            :key="ind"
            size="small"
            variant="light"
            theme="primary"
          >
            {{ ind }}
          </t-tag>
          <t-tag v-if="memoryStore.profile.focus_industries.length > 4" size="small" variant="outline">
            +{{ memoryStore.profile.focus_industries.length - 4 }}
          </t-tag>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.profile-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px 28px;
  background: var(--td-bg-color-container);
  border-radius: 12px;
  border: 1px solid var(--td-component-border);
  margin-bottom: 20px;
  gap: 24px;
  flex-wrap: wrap;
}

.profile-header__left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.profile-avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--td-brand-color), var(--td-brand-color-light));
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}

.profile-title {
  margin: 0 0 4px 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--td-text-color-primary);
}

.profile-subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--td-text-color-secondary);
}

.profile-subtitle strong {
  color: var(--td-brand-color);
}

.high-conf {
  color: var(--td-success-color);
}

.profile-header__stats {
  display: flex;
  align-items: center;
  gap: 20px;
  flex-wrap: wrap;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.stat-label {
  font-size: 11px;
  color: var(--td-text-color-placeholder);
  white-space: nowrap;
}

.tags-inline {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
</style>

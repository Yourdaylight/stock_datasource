<script setup lang="ts">
import { computed, ref } from 'vue'
import type { DebugMessage } from '@/stores/chat'
import { useChatStore } from '@/stores/chat'

const props = defineProps<{
  message: DebugMessage
}>()

const chatStore = useChatStore()
const expanded = ref(false)

const roleConfig = computed(() => {
  const configs: Record<string, { icon: string; color: string; label: string }> = {
    orchestrator: { icon: 'control-platform', color: '#0052d9', label: '调度器' },
    agent: { icon: 'user-circle', color: '#2ba471', label: 'Agent' },
    tool: { icon: 'tools', color: '#e37318', label: '工具' },
    system: { icon: 'info-circle', color: '#888', label: '系统' },
    handoff: { icon: 'swap', color: '#7b61ff', label: '交接' },
  }
  return configs[props.message.role] || configs.system
})

const agentName = computed(() => {
  return chatStore.getAgentDisplayName(props.message.agent)
})

const title = computed(() => {
  const d = props.message.data
  switch (props.message.debugType) {
    case 'classification':
      return `识别意图: ${d.intent || '未知'}`
    case 'routing':
      return d.is_parallel
        ? `并行分发 → ${chatStore.getAgentDisplayName(d.to_agent || '')}`
        : `路由 → ${chatStore.getAgentDisplayName(d.to_agent || '')}`
    case 'agent_start':
      return `${agentName.value} 开始执行`
    case 'agent_end':
      return d.success
        ? `${agentName.value} 完成 (${d.duration_ms}ms)`
        : `${agentName.value} 失败`
    case 'tool_result':
      return `调用工具: ${chatStore.getToolDisplayName(d.tool || '')}`
    case 'handoff':
      return `${chatStore.getAgentDisplayName(d.from_agent || '')} → ${chatStore.getAgentDisplayName(d.to_agent || '')}`
    case 'data_sharing':
      return `数据共享: ${chatStore.getAgentDisplayName(d.from_agent || '')} → ${chatStore.getAgentDisplayName(d.to_agent || '')}`
    default:
      return props.message.debugType
  }
})

const timeStr = computed(() => {
  const ts = props.message.timestamp
  if (!ts) return ''
  const d = new Date(ts * 1000)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
})

const hasDetails = computed(() => {
  const d = props.message.data
  return d.args || d.result_summary || d.rationale || d.tools_available || d.data_summary || d.shared_data_summary || d.error
})

const formatJson = (obj: any): string => {
  if (!obj) return ''
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
  }
}
</script>

<template>
  <div
    :class="[
      'debug-msg',
      `debug-msg--${message.role}`,
      `debug-msg--${message.debugType}`,
      { 'debug-msg--nested': message.parentAgent },
    ]"
    :style="message.parentAgent ? { marginLeft: '20px' } : {}"
  >
    <div class="debug-msg__avatar" :style="{ color: roleConfig.color }">
      <t-icon :name="roleConfig.icon" size="16px" />
    </div>
    <div class="debug-msg__body">
      <div class="debug-msg__header">
        <span class="debug-msg__agent" :style="{ color: roleConfig.color }">{{ agentName }}</span>
        <span class="debug-msg__time">{{ timeStr }}</span>
      </div>
      <div class="debug-msg__title">{{ title }}</div>

      <!-- Rationale for classification -->
      <div v-if="message.debugType === 'classification' && message.data.rationale" class="debug-msg__rationale">
        {{ message.data.rationale }}
      </div>

      <!-- Routing arrow for handoff -->
      <div v-if="message.debugType === 'handoff'" class="debug-msg__arrow">
        <span>{{ chatStore.getAgentDisplayName(message.data.from_agent || '') }}</span>
        <t-icon name="arrow-right" />
        <span>{{ chatStore.getAgentDisplayName(message.data.to_agent || '') }}</span>
      </div>

      <!-- Error badge -->
      <div v-if="message.data.error" class="debug-msg__error">
        {{ message.data.error }}
      </div>

      <!-- Expand/collapse details -->
      <div v-if="hasDetails" class="debug-msg__toggle" @click="expanded = !expanded">
        <t-icon :name="expanded ? 'chevron-up' : 'chevron-down'" size="14px" />
        <span>{{ expanded ? '收起详情' : '查看详情' }}</span>
      </div>

      <div v-if="expanded && hasDetails" class="debug-msg__details">
        <div v-if="message.data.tools_available" class="detail-row">
          <span class="detail-label">可用工具:</span>
          <span class="detail-value">{{ message.data.tools_available.join(', ') }}</span>
        </div>
        <div v-if="message.data.args" class="detail-row">
          <span class="detail-label">参数:</span>
          <pre class="detail-code">{{ formatJson(message.data.args) }}</pre>
        </div>
        <div v-if="message.data.result_summary" class="detail-row">
          <span class="detail-label">结果:</span>
          <pre class="detail-code">{{ message.data.result_summary }}</pre>
        </div>
        <div v-if="message.data.data_summary" class="detail-row">
          <span class="detail-label">共享数据:</span>
          <pre class="detail-code">{{ formatJson(message.data.data_summary) }}</pre>
        </div>
        <div v-if="message.data.input_summary" class="detail-row">
          <span class="detail-label">输入:</span>
          <pre class="detail-code">{{ message.data.input_summary }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.debug-msg {
  display: flex;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  transition: background 0.2s;
}

.debug-msg:hover {
  background: var(--td-bg-color-secondarycontainer, #f5f5f5);
}

.debug-msg--nested {
  border-left: 2px solid var(--td-component-stroke, #e7e7e7);
}

.debug-msg__avatar {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--td-bg-color-secondarycontainer, #f5f5f5);
  display: flex;
  align-items: center;
  justify-content: center;
}

.debug-msg__body {
  flex: 1;
  min-width: 0;
}

.debug-msg__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 2px;
}

.debug-msg__agent {
  font-size: 12px;
  font-weight: 600;
}

.debug-msg__time {
  font-size: 11px;
  color: var(--td-text-color-placeholder, #aaa);
}

.debug-msg__title {
  font-size: 13px;
  color: var(--td-text-color-primary, #333);
  line-height: 1.4;
}

.debug-msg__rationale {
  font-size: 12px;
  color: var(--td-text-color-secondary, #666);
  margin-top: 4px;
  padding: 4px 8px;
  background: var(--td-bg-color-secondarycontainer, #f5f5f5);
  border-radius: 4px;
}

.debug-msg__arrow {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
  font-size: 12px;
  color: #7b61ff;
  font-weight: 500;
}

.debug-msg__error {
  margin-top: 4px;
  padding: 4px 8px;
  background: var(--td-error-color-1, #fff0ed);
  color: var(--td-error-color, #d54941);
  border-radius: 4px;
  font-size: 12px;
}

.debug-msg__toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 4px;
  font-size: 11px;
  color: var(--td-brand-color, #0052d9);
  cursor: pointer;
}

.debug-msg__toggle:hover {
  text-decoration: underline;
}

.debug-msg__details {
  margin-top: 6px;
  padding: 8px;
  background: var(--td-bg-color-page, #fafafa);
  border-radius: 6px;
  font-size: 12px;
}

.detail-row {
  margin-bottom: 6px;
}

.detail-row:last-child {
  margin-bottom: 0;
}

.detail-label {
  font-weight: 500;
  color: var(--td-text-color-secondary, #666);
  display: block;
  margin-bottom: 2px;
}

.detail-value {
  color: var(--td-text-color-primary, #333);
  word-break: break-all;
}

.detail-code {
  margin: 0;
  padding: 6px 8px;
  background: var(--td-bg-color-container, #fff);
  border: 1px solid var(--td-component-stroke, #e7e7e7);
  border-radius: 4px;
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 11px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
}

/* Type-specific colors */
.debug-msg--agent_end .debug-msg__title {
  color: var(--td-text-color-secondary, #666);
}

.debug-msg--tool_result .debug-msg__avatar {
  background: #fff7e6;
}

.debug-msg--handoff .debug-msg__avatar {
  background: #f0ebff;
}
</style>

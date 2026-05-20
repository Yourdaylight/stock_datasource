<script setup lang="ts">
import { computed } from 'vue'

export interface NodeState {
  id: string
  label: string
  type: string
  status: 'pending' | 'running' | 'completed' | 'error'
  output: string
  durationMs: number
  error: string
}

const props = defineProps<{
  nodes: NodeState[]
  isRunning: boolean
  isComplete: boolean
}>()

const expandedNode = defineModel<string>('expandedNode', { default: '' })

const completedCount = computed(() => props.nodes.filter(n => n.status === 'completed' && n.type === 'agent').length)
const totalAgents = computed(() => props.nodes.filter(n => n.type === 'agent').length)
const progressPercent = computed(() => {
  if (!totalAgents.value) return 0
  return Math.round((completedCount.value / totalAgents.value) * 100)
})

const statusIcon = (status: string) => {
  switch (status) {
    case 'completed': return '✅'
    case 'running': return '⏳'
    case 'error': return '❌'
    default: return '⏸'
  }
}

const statusLabel = (status: string) => {
  switch (status) {
    case 'completed': return '完成'
    case 'running': return '运行中'
    case 'error': return '失败'
    default: return '等待'
  }
}

const nodeTypeIcon = (type: string) => {
  switch (type) {
    case 'input': return '📥'
    case 'output': return '📤'
    case 'agent': return '🤖'
    case 'aggregator': return '🔀'
    default: return '⚙️'
  }
}

function toggleExpand(nodeId: string) {
  expandedNode.value = expandedNode.value === nodeId ? '' : nodeId
}

function formatDuration(ms: number) {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}
</script>

<template>
  <div class="execution-panel" :class="{ running: isRunning, complete: isComplete }">
    <!-- Progress bar -->
    <div class="progress-section" v-if="isRunning || isComplete">
      <div class="progress-header">
        <span class="progress-label">
          {{ isComplete ? '执行完成' : '执行中' }}
        </span>
        <span class="progress-stats">{{ completedCount }}/{{ totalAgents }} Agent 完成</span>
      </div>
      <div class="progress-bar">
        <div
          class="progress-fill"
          :class="{ complete: isComplete }"
          :style="{ width: progressPercent + '%' }"
        />
      </div>
    </div>

    <!-- Node cards flow -->
    <div class="nodes-flow">
      <div
        v-for="(node, index) in nodes"
        :key="node.id"
        class="node-wrapper"
      >
        <div
          class="node-card"
          :class="[`status-${node.status}`, `type-${node.type}`]"
          @click="toggleExpand(node.id)"
        >
          <div class="node-card__header">
            <span class="node-icon">{{ nodeTypeIcon(node.type) }}</span>
            <span class="node-label">{{ node.label }}</span>
            <span class="node-status-badge" :class="node.status">
              {{ statusIcon(node.status) }} {{ statusLabel(node.status) }}
            </span>
          </div>

          <!-- Duration shown for completed nodes -->
          <div class="node-card__meta" v-if="node.durationMs > 0">
            <span class="duration">{{ formatDuration(node.durationMs) }}</span>
          </div>

          <!-- Running pulse indicator -->
          <div class="running-indicator" v-if="node.status === 'running'">
            <div class="pulse-dot" />
            <span>正在思考...</span>
          </div>

          <!-- Error display -->
          <div class="node-error" v-if="node.status === 'error' && node.error">
            {{ node.error }}
          </div>
        </div>

        <!-- Connector arrow -->
        <div class="connector" v-if="index < nodes.length - 1">→</div>
      </div>
    </div>

    <!-- Expanded output area -->
    <div class="expanded-output" v-if="expandedNode">
      <div class="expanded-header">
        <span>{{ nodes.find(n => n.id === expandedNode)?.label }} 输出</span>
        <t-button variant="text" size="small" @click="expandedNode = ''">收起</t-button>
      </div>
      <div class="output-content">
        {{ nodes.find(n => n.id === expandedNode)?.output || '暂无输出' }}
      </div>
    </div>

    <!-- Empty state -->
    <div class="empty-hint" v-if="!isRunning && !isComplete && !nodes.length">
      点击"运行团队"开始执行
    </div>
  </div>
</template>

<style scoped>
.execution-panel {
  border: 1px solid var(--td-component-border, #e7e7e7);
  border-radius: 10px;
  padding: 16px;
  background: var(--td-bg-color-container, #fff);
  min-height: 200px;
}

.execution-panel.running {
  border-color: var(--td-brand-color, #0052d9);
}

.execution-panel.complete {
  border-color: var(--td-success-color, #00a870);
}

/* Progress */
.progress-section {
  margin-bottom: 16px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.progress-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--td-text-color-primary);
}

.progress-stats {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.progress-bar {
  height: 6px;
  background: var(--td-bg-color-component, #f0f0f0);
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--td-brand-color, #0052d9);
  border-radius: 3px;
  transition: width 0.5s ease;
}

.progress-fill.complete {
  background: var(--td-success-color, #00a870);
}

/* Nodes flow */
.nodes-flow {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
  margin-bottom: 12px;
}

.node-wrapper {
  display: flex;
  align-items: center;
  gap: 4px;
}

.connector {
  font-size: 16px;
  color: var(--td-text-color-placeholder, #bbb);
  flex-shrink: 0;
}

/* Node card */
.node-card {
  border: 1px solid var(--td-component-border, #e7e7e7);
  border-radius: 8px;
  padding: 10px 14px;
  cursor: pointer;
  transition: all 0.2s;
  min-width: 120px;
  background: var(--td-bg-color-secondarycontainer, #fafafa);
}

.node-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transform: translateY(-1px);
}

.node-card.status-running {
  border-color: var(--td-brand-color, #0052d9);
  background: var(--td-brand-color-light, #f0f5ff);
  animation: breathe 2s ease-in-out infinite;
}

.node-card.status-completed {
  border-color: var(--td-success-color, #00a870);
  background: var(--td-success-color-1, #f0faf5);
}

.node-card.status-error {
  border-color: var(--td-error-color, #d54941);
  background: var(--td-error-color-1, #fff0f0);
}

@keyframes breathe {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.85; }
}

.node-card__header {
  display: flex;
  align-items: center;
  gap: 6px;
}

.node-icon {
  font-size: 16px;
}

.node-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--td-text-color-primary);
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.node-status-badge {
  font-size: 10px;
  white-space: nowrap;
}

.node-card__meta {
  margin-top: 4px;
}

.duration {
  font-size: 10px;
  color: var(--td-text-color-secondary);
  font-family: monospace;
}

/* Running indicator */
.running-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  font-size: 11px;
  color: var(--td-brand-color);
}

.pulse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--td-brand-color);
  animation: pulse 1.2s infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.8); opacity: 0.4; }
}

.node-error {
  margin-top: 6px;
  font-size: 11px;
  color: var(--td-error-color);
  line-height: 1.3;
}

/* Expanded output */
.expanded-output {
  border-top: 1px solid var(--td-component-border, #e7e7e7);
  padding-top: 12px;
  margin-top: 12px;
}

.expanded-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--td-text-color-primary);
}

.output-content {
  background: var(--td-bg-color-secondarycontainer, #f5f7fa);
  border-radius: 6px;
  padding: 12px;
  font-size: 12px;
  line-height: 1.6;
  max-height: 300px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--td-text-color-primary);
}

.empty-hint {
  text-align: center;
  color: var(--td-text-color-placeholder);
  font-size: 13px;
  padding: 40px 0;
}
</style>

<template>
  <div class="discussion-viewer">
    <div class="header">
      <h3>🎤 多智能体讨论记录</h3>
      <button class="close-btn" @click="$emit('close')">×</button>
    </div>

    <div class="events-container">
      <div
        v-for="(event, index) in discussionEvents"
        :key="event.id"
        class="event-item"
        :class="eventTypeClass(event.debugType)"
      >
        <!-- Agent Discussion Event -->
        <template v-if="event.debugType === 'discussion_argument'">
          <div class="event-agent-badge">{{ event.data.agent_role || event.agent }}</div>
          <div class="event-message">
            <strong>{{ event.agent }}</strong>
            <p>{{ event.data.content || '发表观点...' }}</p>
            <div class="event-meta">
              <span class="message-type">{{ event.data.message_type }}</span>
              <span class="timestamp">{{ formatTime(event.timestamp) }}</span>
            </div>
          </div>
        </template>

        <!-- Decision Summary Event -->
        <template v-else-if="event.debugType === 'decision_summary'">
          <div class="event-decision">
            <div class="decision-header">
              <span class="badge decision">💡 决策总结</span>
            </div>
            <div class="decision-content">
              <div class="decision-signal" :class="signalClass(event.data.signal as string || '')">
                {{ signalEmoji(event.data.signal as string || '') }} {{ event.data.signal }}
              </div>
              <div class="decision-stats">
                <span>置信度: {{ ((event.data.confidence || 0) * 100).toFixed(0) }}%</span>
                <span>赞同: {{ event.data.bull_count || 0 }}</span>
                <span>反对: {{ event.data.bear_count || 0 }}</span>
                <span>中立: {{ event.data.neutral_count || 0 }}</span>
              </div>
              <p v-if="event.data.suggested_action" class="action">
                建议: {{ event.data.suggested_action }}
              </p>
            </div>
          </div>
        </template>

        <!-- Arena Error Event -->
        <template v-else-if="event.debugType === 'arena_error'">
          <div class="event-error">
            <div class="error-badge">⚠️ 错误</div>
            <div class="error-content">{{ event.data.content || event.agent }}</div>
          </div>
        </template>
      </div>

      <div v-if="discussionEvents.length === 0" class="empty-state">
        <p>暂无讨论记录</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { DebugMessage } from '@/stores/chat'

const props = defineProps<{
  debugMessages: DebugMessage[]
}>()

const emit = defineEmits<{
  close: []
}>()

const discussionEvents = computed(() => {
  return props.debugMessages.filter(
    msg => msg.role === 'discussion' || 
            msg.debugType === 'discussion_argument' ||
            msg.debugType === 'decision_summary' ||
            msg.debugType === 'arena_error'
  )
})

const eventTypeClass = (debugType: string) => {
  if (debugType === 'discussion_argument') return 'argument'
  if (debugType === 'decision_summary') return 'decision'
  if (debugType === 'arena_error') return 'error'
  return 'other'
}

const signalClass = (signal: string) => {
  switch (signal) {
    case 'BUY':
      return 'buy'
    case 'SELL':
      return 'sell'
    case 'HOLD':
      return 'hold'
    default:
      return 'none'
  }
}

const signalEmoji = (signal: string) => {
  const map: Record<string, string> = {
    'BUY': '🚀',
    'SELL': '⬇️',
    'HOLD': '⏸️',
    'NONE': '❓'
  }
  return map[signal] || '❓'
}

const formatTime = (timestamp: number) => {
  const date = new Date(timestamp * 1000)
  return date.toLocaleTimeString('zh-CN', { 
    hour: '2-digit', 
    minute: '2-digit', 
    second: '2-digit' 
  })
}
</script>

<style scoped>
.discussion-viewer {
  background: white;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  max-height: 600px;
  display: flex;
  flex-direction: column;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 2px solid #f0f0f0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.close-btn {
  background: rgba(255, 255, 255, 0.2);
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: white;
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: all 0.2s;
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.3);
}

.events-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #999;
}

.event-item {
  padding: 12px;
  border-radius: 8px;
  border-left: 4px solid transparent;
}

.event-item.argument {
  background: #f8f9fa;
  border-left-color: #667eea;
}

.event-item.decision {
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  border-left-color: #2ecc71;
}

.event-item.error {
  background: #fff5f5;
  border-left-color: #e74c3c;
}

.event-agent-badge {
  display: inline-block;
  background: #667eea;
  color: white;
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 8px;
}

.event-message {
  font-size: 13px;
}

.event-message strong {
  color: #333;
  display: block;
  margin-bottom: 4px;
}

.event-message p {
  margin: 8px 0;
  color: #555;
  line-height: 1.5;
}

.event-meta {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: #999;
  margin-top: 8px;
}

.message-type {
  background: rgba(102, 126, 234, 0.1);
  padding: 2px 6px;
  border-radius: 4px;
  color: #667eea;
  font-weight: 500;
}

.event-decision {
  padding: 12px;
  background: white;
  border-radius: 8px;
  border: 2px solid #2ecc71;
}

.decision-header {
  margin-bottom: 12px;
}

.badge {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.badge.decision {
  background: linear-gradient(135deg, #2ecc71, #27ae60);
  color: white;
}

.decision-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.decision-signal {
  font-size: 14px;
  font-weight: 700;
  padding: 8px 12px;
  border-radius: 6px;
  text-align: center;
}

.decision-signal.buy {
  background: #84fab0;
  color: #27ae60;
}

.decision-signal.sell {
  background: #fa709a;
  color: #c0392b;
}

.decision-signal.hold {
  background: #a8edea;
  color: #f39c12;
}

.decision-signal.none {
  background: #d4d4d4;
  color: #666;
}

.decision-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: #666;
}

.decision-stats span {
  background: rgba(0, 0, 0, 0.05);
  padding: 4px 8px;
  border-radius: 4px;
}

.action {
  margin: 0;
  font-size: 12px;
  color: #333;
  padding: 8px;
  background: rgba(46, 204, 113, 0.1);
  border-radius: 4px;
  border-left: 3px solid #2ecc71;
}

.event-error {
  padding: 12px;
  background: white;
  border-radius: 8px;
  border: 2px solid #e74c3c;
}

.error-badge {
  display: inline-block;
  color: #e74c3c;
  font-weight: 600;
  font-size: 12px;
  margin-bottom: 8px;
}

.error-content {
  font-size: 13px;
  color: #666;
}

@media (max-width: 768px) {
  .discussion-viewer {
    max-height: 400px;
  }

  .header h3 {
    font-size: 14px;
  }

  .events-container {
    padding: 12px;
    gap: 8px;
  }

  .event-item {
    padding: 10px;
  }
}
</style>

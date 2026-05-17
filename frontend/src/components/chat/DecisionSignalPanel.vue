<template>
  <div v-if="summary" class="decision-panel">
    <div class="header">
      <h3>💡 多智能体决策信号</h3>
      <button class="close-btn" @click="$emit('close')">×</button>
    </div>

    <div class="signal-container">
      <div class="signal-box" :class="signalClass">
        <div class="signal-label">决策信号</div>
        <div class="signal-value">{{ signalDisplay }}</div>
        <div class="confidence-bar">
          <div class="confidence-fill" :style="{ width: confidence + '%' }"></div>
        </div>
        <div class="confidence-text">置信度: {{ (confidence).toFixed(0) }}%</div>
      </div>
    </div>

    <div class="votes-section">
      <div class="vote-item bull">
        <div class="vote-icon">🔴</div>
        <div class="vote-count">{{ summary.bull_count }}</div>
        <div class="vote-label">看多</div>
      </div>
      <div class="vote-item bear">
        <div class="vote-icon">🟢</div>
        <div class="vote-count">{{ summary.bear_count }}</div>
        <div class="vote-label">看空</div>
      </div>
      <div class="vote-item neutral">
        <div class="vote-icon">⚪</div>
        <div class="vote-count">{{ summary.neutral_count }}</div>
        <div class="vote-label">中性</div>
      </div>
    </div>

    <div v-if="summary.suggested_action" class="action-section">
      <div class="action-label">建议行动</div>
      <div class="action-text">{{ summary.suggested_action }}</div>
    </div>

    <div class="discussion-note">
      <p>💬 多智能体讨论已完成</p>
      <p>市场分析：{{ totalAgents }}个分析师</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface DecisionSummary {
  signal: 'BUY' | 'SELL' | 'HOLD' | 'NONE'
  confidence: number
  bull_count: number
  bear_count: number
  neutral_count: number
  suggested_action?: string
}

const props = defineProps<{
  summary: DecisionSummary | null
}>()

const emit = defineEmits<{
  close: []
}>()

const signalDisplay = computed(() => {
  const map: Record<string, string> = {
    'BUY': '🚀 买入',
    'SELL': '⬇️ 卖出',
    'HOLD': '⏸️ 持有',
    'NONE': '❓ 待议'
  }
  return map[props.summary?.signal || 'NONE'] || '❓ 待议'
})

const signalClass = computed(() => {
  const baseClass = 'signal'
  const signal = props.summary?.signal
  switch (signal) {
    case 'BUY':
      return baseClass + ' buy'
    case 'SELL':
      return baseClass + ' sell'
    case 'HOLD':
      return baseClass + ' hold'
    default:
      return baseClass + ' none'
  }
})

const confidence = computed(() => {
  return (props.summary?.confidence || 0) * 100
})

const totalAgents = computed(() => {
  return (props.summary?.bull_count || 0) + 
         (props.summary?.bear_count || 0) + 
         (props.summary?.neutral_count || 0)
})
</script>

<style scoped>
.decision-panel {
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  border-radius: 12px;
  padding: 20px;
  margin: 16px 0;
  border-left: 4px solid #007bff;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 2px solid rgba(0, 0, 0, 0.1);
}

.header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #666;
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
  background: rgba(0, 0, 0, 0.1);
  color: #333;
}

.signal-container {
  margin-bottom: 20px;
}

.signal-box {
  padding: 16px;
  border-radius: 8px;
  text-align: center;
  transition: all 0.3s;
}

.signal-box.buy {
  background: linear-gradient(135deg, #84fab0 0%, #8fd3f4 100%);
  border: 2px solid #2ecc71;
}

.signal-box.sell {
  background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
  border: 2px solid #e74c3c;
}

.signal-box.hold {
  background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
  border: 2px solid #f39c12;
}

.signal-box.none {
  background: linear-gradient(135deg, #d4d4d4 0%, #a8a8a8 100%);
  border: 2px solid #95a5a6;
}

.signal-label {
  font-size: 12px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.6);
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 8px;
}

.signal-value {
  font-size: 28px;
  font-weight: 700;
  margin-bottom: 12px;
  color: #333;
}

.confidence-bar {
  background: rgba(255, 255, 255, 0.5);
  height: 8px;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 8px;
}

.confidence-fill {
  background: linear-gradient(90deg, #2ecc71, #27ae60);
  height: 100%;
  transition: width 0.5s ease;
}

.signal-box.sell .confidence-fill {
  background: linear-gradient(90deg, #e74c3c, #c0392b);
}

.signal-box.hold .confidence-fill {
  background: linear-gradient(90deg, #f39c12, #e67e22);
}

.confidence-text {
  font-size: 12px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.7);
}

.votes-section {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}

.vote-item {
  background: white;
  border-radius: 8px;
  padding: 12px;
  text-align: center;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  transition: all 0.2s;
}

.vote-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
}

.vote-item.bull {
  border-top: 3px solid #2ecc71;
}

.vote-item.bear {
  border-top: 3px solid #e74c3c;
}

.vote-item.neutral {
  border-top: 3px solid #f39c12;
}

.vote-icon {
  font-size: 20px;
  margin-bottom: 4px;
}

.vote-count {
  font-size: 20px;
  font-weight: 700;
  color: #333;
  margin-bottom: 4px;
}

.vote-label {
  font-size: 12px;
  color: #666;
  font-weight: 500;
}

.action-section {
  background: white;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.action-label {
  font-size: 12px;
  font-weight: 600;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
}

.action-text {
  font-size: 14px;
  color: #333;
  line-height: 1.5;
}

.discussion-note {
  background: rgba(255, 255, 255, 0.6);
  border-radius: 8px;
  padding: 12px;
  font-size: 12px;
  color: #666;
  line-height: 1.6;
}

.discussion-note p {
  margin: 4px 0;
}

@media (max-width: 768px) {
  .decision-panel {
    padding: 16px;
    margin: 12px 0;
  }

  .signal-value {
    font-size: 24px;
  }

  .votes-section {
    gap: 8px;
  }
}
</style>

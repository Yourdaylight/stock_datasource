<script setup lang="ts">
import { computed } from 'vue'
import type { TechnicalSignal } from '@/types/common'

const props = defineProps<{
  trend?: string
  support?: number
  resistance?: number
  signals?: TechnicalSignal[]
  summary?: string
  disclaimer?: string
  loading?: boolean
}>()

const trendClass = computed(() => {
  if (!props.trend) return ''
  if (props.trend.includes('上涨')) return 'up'
  if (props.trend.includes('下跌')) return 'down'
  return 'neutral'
})

const bullishSignals = computed(() => 
  props.signals?.filter(s => s.type === 'bullish') || []
)

const bearishSignals = computed(() => 
  props.signals?.filter(s => s.type === 'bearish') || []
)
</script>

<template>
  <div class="trend-analysis">
    <t-loading v-if="loading" size="medium" />
    
    <template v-else-if="trend">
      <!-- Trend Direction -->
      <div class="trend-section">
        <div class="section-title">趋势判断</div>
        <div class="trend-badge" :class="trendClass">
          {{ trend }}
        </div>
      </div>
      
      <!-- Support/Resistance -->
      <div v-if="support && resistance" class="levels-section">
        <div class="section-title">关键位置</div>
        <div class="levels">
          <div class="level-item">
            <span class="level-label">支撑位</span>
            <span class="level-value support">{{ support.toFixed(2) }}</span>
          </div>
          <div class="level-item">
            <span class="level-label">压力位</span>
            <span class="level-value resistance">{{ resistance.toFixed(2) }}</span>
          </div>
        </div>
      </div>
      
      <!-- Signals -->
      <div v-if="signals && signals.length > 0" class="signals-section">
        <div class="section-title">技术信号</div>
        
        <div v-if="bullishSignals.length > 0" class="signal-group">
          <div class="signal-group-title bullish">
            <t-icon name="arrow-up" /> 看多信号
          </div>
          <div class="signal-list">
            <t-tag 
              v-for="signal in bullishSignals" 
              :key="signal.signal"
              theme="success"
              variant="light"
            >
              <t-tooltip :content="signal.description">
                {{ signal.signal }}
              </t-tooltip>
            </t-tag>
          </div>
        </div>
        
        <div v-if="bearishSignals.length > 0" class="signal-group">
          <div class="signal-group-title bearish">
            <t-icon name="arrow-down" /> 看空信号
          </div>
          <div class="signal-list">
            <t-tag 
              v-for="signal in bearishSignals" 
              :key="signal.signal"
              theme="danger"
              variant="light"
            >
              <t-tooltip :content="signal.description">
                {{ signal.signal }}
              </t-tooltip>
            </t-tag>
          </div>
        </div>
      </div>
      
      <!-- Summary -->
      <div v-if="summary" class="summary-section">
        <div class="section-title">分析摘要</div>
        <div class="summary-text">{{ summary }}</div>
      </div>
      
      <!-- Disclaimer -->
      <div v-if="disclaimer" class="disclaimer">
        <t-icon name="info-circle" />
        {{ disclaimer }}
      </div>
    </template>
    
    <div v-else class="empty-state">
      <t-icon name="analysis" size="32px" style="color: #ddd" />
      <p>点击「AI 智能分析」获取技术分析报告</p>
    </div>
  </div>
</template>

<style scoped>
.trend-analysis {
  padding: 16px;
  background: #fff;
  border-radius: 8px;
}

.section-title {
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
}

.trend-section,
.levels-section,
.signals-section,
.summary-section {
  margin-bottom: 16px;
}

.trend-badge {
  display: inline-block;
  padding: 8px 16px;
  border-radius: 4px;
  font-size: 15px;
  font-weight: 600;
}

.trend-badge.up {
  background: #fff0f0;
  color: #ec0000;
}

.trend-badge.down {
  background: #f0fff0;
  color: #00da3c;
}

.trend-badge.neutral {
  background: #f5f5f5;
  color: #666;
}

.levels {
  display: flex;
  gap: 24px;
}

.level-item {
  display: flex;
  flex-direction: column;
}

.level-label {
  font-size: 12px;
  color: #999;
}

.level-value {
  font-size: 18px;
  font-weight: 600;
  margin-top: 4px;
}

.level-value.support { color: #00da3c; }
.level-value.resistance { color: #ec0000; }

.signal-group {
  margin-bottom: 12px;
}

.signal-group-title {
  font-size: 12px;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.signal-group-title.bullish { color: #52c41a; }
.signal-group-title.bearish { color: #ff4d4f; }

.signal-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.summary-text {
  font-size: 14px;
  line-height: 1.6;
  color: #333;
  padding: 12px;
  background: #f9f9f9;
  border-radius: 4px;
}

.disclaimer {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 11px;
  color: #999;
  padding: 8px;
  background: #fffbe6;
  border-radius: 4px;
  margin-top: 12px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: #999;
  text-align: center;
}
</style>

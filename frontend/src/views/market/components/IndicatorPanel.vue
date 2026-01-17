<script setup lang="ts">
import { ref, computed } from 'vue'

const emit = defineEmits<{
  (e: 'change', indicators: string[]): void
}>()

const props = defineProps<{
  selectedIndicators?: string[]
}>()

// Available indicators grouped by category
const indicatorGroups = [
  {
    name: '均线指标',
    items: [
      { value: 'MA', label: 'MA 移动平均线', desc: '5/10/20/60日均线' },
      { value: 'EMA', label: 'EMA 指数均线', desc: '12/26日指数均线' },
      { value: 'BOLL', label: 'BOLL 布林带', desc: '20日布林带' },
    ]
  },
  {
    name: '趋势指标',
    items: [
      { value: 'MACD', label: 'MACD', desc: 'DIF/DEA/柱状图' },
      { value: 'DMI', label: 'DMI 趋向指标', desc: '+DI/-DI/ADX' },
    ]
  },
  {
    name: '超买超卖',
    items: [
      { value: 'RSI', label: 'RSI 相对强弱', desc: '14日RSI' },
      { value: 'KDJ', label: 'KDJ 随机指标', desc: '9日KDJ' },
      { value: 'CCI', label: 'CCI 顺势指标', desc: '14日CCI' },
    ]
  },
  {
    name: '量能指标',
    items: [
      { value: 'OBV', label: 'OBV 能量潮', desc: '累积成交量' },
      { value: 'ATR', label: 'ATR 真实波幅', desc: '14日波动幅度' },
    ]
  }
]

const selected = ref<string[]>(props.selectedIndicators || ['MACD', 'MA'])

const handleChange = () => {
  emit('change', selected.value)
}

// Preset configurations
const presets = [
  { name: '简洁', indicators: ['MA'] },
  { name: '标准', indicators: ['MA', 'MACD'] },
  { name: '专业', indicators: ['MA', 'BOLL', 'MACD', 'RSI'] },
]

const applyPreset = (preset: { name: string; indicators: string[] }) => {
  selected.value = [...preset.indicators]
  handleChange()
}
</script>

<template>
  <div class="indicator-panel">
    <div class="panel-header">
      <span class="title">技术指标</span>
      <t-space size="small">
        <t-tag
          v-for="preset in presets"
          :key="preset.name"
          theme="default"
          variant="outline"
          style="cursor: pointer"
          @click="applyPreset(preset)"
        >
          {{ preset.name }}
        </t-tag>
      </t-space>
    </div>
    
    <div class="indicator-groups">
      <div v-for="group in indicatorGroups" :key="group.name" class="indicator-group">
        <div class="group-name">{{ group.name }}</div>
        <t-checkbox-group v-model="selected" @change="handleChange">
          <div class="indicator-items">
            <t-checkbox
              v-for="item in group.items"
              :key="item.value"
              :value="item.value"
              class="indicator-item"
            >
              <div class="indicator-info">
                <span class="indicator-label">{{ item.label }}</span>
                <span class="indicator-desc">{{ item.desc }}</span>
              </div>
            </t-checkbox>
          </div>
        </t-checkbox-group>
      </div>
    </div>
  </div>
</template>

<style scoped>
.indicator-panel {
  padding: 12px;
  background: #fafafa;
  border-radius: 8px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.title {
  font-weight: 600;
  font-size: 14px;
}

.indicator-groups {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.indicator-group {
  background: #fff;
  padding: 10px;
  border-radius: 6px;
}

.group-name {
  font-size: 12px;
  color: #666;
  margin-bottom: 8px;
}

.indicator-items {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.indicator-item {
  min-width: 140px;
}

.indicator-info {
  display: flex;
  flex-direction: column;
}

.indicator-label {
  font-size: 13px;
}

.indicator-desc {
  font-size: 11px;
  color: #999;
}
</style>

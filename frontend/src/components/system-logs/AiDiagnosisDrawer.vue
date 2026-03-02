<script setup lang="ts">
import type { LogAnalysisResponse } from '@/api/systemLogs'

const props = defineProps<{
  visible: boolean
  loading: boolean
  result: LogAnalysisResponse | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

const close = () => emit('update:visible', false)

const riskTheme = (level?: string) => {
  if (level === 'critical' || level === 'high') return 'danger'
  if (level === 'medium') return 'warning'
  return 'success'
}
</script>

<template>
  <t-drawer :visible="props.visible" header="AI日志诊断" size="760px" @close="close">
    <t-loading :loading="props.loading">
      <t-empty v-if="!props.result" description="暂无诊断结果" />
      <div v-else class="result-wrap">
        <div class="result-top">
          <t-tag :theme="riskTheme(props.result.risk_level)" variant="light">
            风险：{{ props.result.risk_level || 'low' }}
          </t-tag>
          <span class="source">来源：{{ props.result.analysis_source || 'rule_based' }}</span>
          <span class="confidence">置信度：{{ ((props.result.confidence || 0) * 100).toFixed(1) }}%</span>
        </div>

        <t-alert theme="info" :message="props.result.summary || '未生成摘要'" />

        <t-collapse class="mt-3">
          <t-collapse-panel header="根因定位">
            <ul class="ul-list">
              <li v-for="(item, idx) in props.result.root_causes || []" :key="idx">
                {{ item.title }}
                <span v-if="item.module">（{{ item.module }}）</span>
              </li>
            </ul>
          </t-collapse-panel>
          <t-collapse-panel header="修复建议">
            <ul class="ul-list">
              <li v-for="(item, idx) in props.result.suggested_fixes || []" :key="idx">{{ item }}</li>
            </ul>
          </t-collapse-panel>
          <t-collapse-panel header="影响范围">
            <div>{{ props.result.impact_scope || '未识别' }}</div>
          </t-collapse-panel>
        </t-collapse>
      </div>
    </t-loading>
  </t-drawer>
</template>

<style scoped>
.result-wrap {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.result-top {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #6b7280;
  font-size: 12px;
}
.source,
.confidence {
  white-space: nowrap;
}
.ul-list {
  margin: 0;
  padding-left: 18px;
  line-height: 1.7;
}
</style>

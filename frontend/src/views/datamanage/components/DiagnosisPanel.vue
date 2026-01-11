<script setup lang="ts">
import { ref, computed } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { datamanageApi, type DiagnosisResult, type DiagnosisSuggestion } from '@/api/datamanage'

const loading = ref(false)
const diagnosis = ref<DiagnosisResult | null>(null)
const logLines = ref(100)
const errorsOnly = ref(false)
const expandedSuggestion = ref<number | null>(null)

const runDiagnosis = async () => {
  loading.value = true
  try {
    diagnosis.value = await datamanageApi.getDiagnosis(logLines.value, errorsOnly.value)
    if (diagnosis.value.suggestions.length === 0) {
      MessagePlugin.success('诊断完成，未发现问题')
    } else {
      MessagePlugin.warning(`诊断完成，发现 ${diagnosis.value.suggestions.length} 个问题`)
    }
  } catch (e) {
    MessagePlugin.error('诊断失败')
  } finally {
    loading.value = false
  }
}

const getSeverityTheme = (severity: string) => {
  const themes: Record<string, string> = {
    critical: 'danger',
    warning: 'warning',
    info: 'primary'
  }
  return themes[severity] || 'default'
}

const getSeverityText = (severity: string) => {
  const texts: Record<string, string> = {
    critical: '严重',
    warning: '警告',
    info: '提示'
  }
  return texts[severity] || severity
}

const getCategoryText = (category: string) => {
  const texts: Record<string, string> = {
    config: '配置问题',
    data: '数据问题',
    connection: '连接问题',
    plugin: '插件问题',
    system: '系统问题'
  }
  return texts[category] || category
}

const toggleSuggestion = (index: number) => {
  expandedSuggestion.value = expandedSuggestion.value === index ? null : index
}

const criticalCount = computed(() => 
  diagnosis.value?.suggestions.filter(s => s.severity === 'critical').length || 0
)

const warningCount = computed(() => 
  diagnosis.value?.suggestions.filter(s => s.severity === 'warning').length || 0
)
</script>

<template>
  <t-card title="AI 诊断" :bordered="false" style="margin-bottom: 16px">
    <template #actions>
      <t-space>
        <t-input-number 
          v-model="logLines" 
          :min="10" 
          :max="500" 
          :step="50"
          style="width: 120px"
        >
          <template #label>日志行数</template>
        </t-input-number>
        <t-checkbox v-model="errorsOnly">仅错误日志</t-checkbox>
        <t-button theme="primary" :loading="loading" @click="runDiagnosis">
          开始诊断
        </t-button>
      </t-space>
    </template>

    <div v-if="diagnosis" class="diagnosis-result">
      <!-- Summary -->
      <t-alert 
        :theme="criticalCount > 0 ? 'error' : warningCount > 0 ? 'warning' : 'success'"
        :message="diagnosis.summary"
        style="margin-bottom: 16px"
      >
        <template #operation>
          <t-space>
            <t-tag theme="default">分析 {{ diagnosis.log_lines_analyzed }} 行日志</t-tag>
            <t-tag v-if="diagnosis.error_count > 0" theme="danger">{{ diagnosis.error_count }} 错误</t-tag>
            <t-tag v-if="diagnosis.warning_count > 0" theme="warning">{{ diagnosis.warning_count }} 警告</t-tag>
          </t-space>
        </template>
      </t-alert>

      <!-- Suggestions -->
      <div v-if="diagnosis.suggestions.length > 0" class="suggestions">
        <div 
          v-for="(suggestion, index) in diagnosis.suggestions" 
          :key="index"
          class="suggestion-item"
          :class="{ expanded: expandedSuggestion === index }"
        >
          <div class="suggestion-header" @click="toggleSuggestion(index)">
            <t-space>
              <t-tag :theme="getSeverityTheme(suggestion.severity)" size="small">
                {{ getSeverityText(suggestion.severity) }}
              </t-tag>
              <t-tag theme="default" variant="outline" size="small">
                {{ getCategoryText(suggestion.category) }}
              </t-tag>
              <span class="suggestion-title">{{ suggestion.title }}</span>
            </t-space>
            <t-icon :name="expandedSuggestion === index ? 'chevron-up' : 'chevron-down'" />
          </div>
          
          <div v-if="expandedSuggestion === index" class="suggestion-content">
            <t-descriptions :column="1" bordered size="small">
              <t-descriptions-item label="问题描述">
                {{ suggestion.description }}
              </t-descriptions-item>
              <t-descriptions-item label="修复建议">
                <span style="color: #0052d9; font-weight: 500">{{ suggestion.suggestion }}</span>
              </t-descriptions-item>
              <t-descriptions-item v-if="suggestion.related_logs.length > 0" label="相关日志">
                <div class="related-logs">
                  <code v-for="(log, i) in suggestion.related_logs" :key="i">{{ log }}</code>
                </div>
              </t-descriptions-item>
            </t-descriptions>
          </div>
        </div>
      </div>

      <!-- No issues -->
      <t-empty v-else description="未发现问题，系统运行正常" />
    </div>

    <t-empty v-else description="点击「开始诊断」分析系统日志" />
  </t-card>
</template>

<style scoped>
.diagnosis-result {
  min-height: 100px;
}

.suggestions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.suggestion-item {
  border: 1px solid #e7e7e7;
  border-radius: 6px;
  overflow: hidden;
}

.suggestion-item.expanded {
  border-color: #0052d9;
}

.suggestion-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  cursor: pointer;
  background: #fafafa;
}

.suggestion-header:hover {
  background: #f0f0f0;
}

.suggestion-title {
  font-weight: 500;
}

.suggestion-content {
  padding: 16px;
  border-top: 1px solid #e7e7e7;
}

.related-logs {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.related-logs code {
  display: block;
  padding: 4px 8px;
  background: #f5f5f5;
  border-radius: 4px;
  font-size: 12px;
  word-break: break-all;
  white-space: pre-wrap;
}
</style>

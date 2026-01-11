<script setup lang="ts">
import { ref, computed } from 'vue'
import { marked } from 'marked'
import type { AnalysisResponse } from '@/api/report'

interface Props {
  analysis?: AnalysisResponse
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false
})

const emit = defineEmits<{
  refresh: []
  changeType: [type: string]
}>()

const analysisType = ref('comprehensive')

// Analysis type options
const analysisTypes = [
  { value: 'comprehensive', label: '全面分析' },
  { value: 'peer_comparison', label: '同业对比' },
  { value: 'investment_insights', label: '投资洞察' }
]

// Get insights data
const insights = computed(() => {
  return props.analysis?.insights
})

// Process markdown content
const processedContent = computed(() => {
  if (!props.analysis?.content) return ''
  
  // Remove the main title (## xxx 财务分析报告)
  let content = props.analysis.content
  content = content.replace(/^##\s+[^\n]+财务分析报告\s*\n*/m, '')
  
  // Configure marked options
  marked.setOptions({
    breaks: true,
    gfm: true
  })
  
  return marked(content)
})

// Get competitive position color
const getPositionColor = (position: string) => {
  if (position.includes('领先')) return 'success'
  if (position.includes('中上游')) return 'warning'
  if (position.includes('中游')) return 'default'
  return 'error'
}

// Get strength level color
const getStrengthColor = (level: string) => {
  if (level === '强') return 'success'
  if (level.includes('中等')) return 'warning'
  return 'error'
}

// Get prospects color
const getProspectsColor = (prospects: string) => {
  if (prospects === '优秀') return 'success'
  if (prospects === '良好') return 'warning'
  if (prospects === '一般') return 'default'
  return 'error'
}

// Handle analysis type change
const handleTypeChange = (type: string) => {
  analysisType.value = type
  emit('changeType', type)
}

// Handle refresh
const handleRefresh = () => {
  emit('refresh')
}
</script>

<template>
  <div class="ai-insight">
    <t-card title="AI 智能分析">
      <template #actions>
        <t-space>
          <t-select
            v-model="analysisType"
            :options="analysisTypes"
            style="width: 120px"
            @change="handleTypeChange"
          />
          <t-button theme="primary" variant="outline" @click="handleRefresh">
            <template #icon><t-icon name="refresh" /></template>
            刷新分析
          </t-button>
        </t-space>
      </template>

      <div v-if="loading" class="loading-container">
        <t-loading size="large" text="AI 正在分析中..." />
      </div>

      <div v-else-if="!analysis" class="empty-container">
        <t-empty description="暂无分析结果">
          <template #action>
            <t-button theme="primary" @click="handleRefresh">
              开始分析
            </t-button>
          </template>
        </t-empty>
      </div>

      <div v-else class="analysis-content">
        <!-- Analysis Content -->
        <div class="analysis-text">
          <t-card title="分析报告" size="small" :bordered="false">
            <div class="markdown-content" v-html="processedContent"></div>
          </t-card>
        </div>

        <!-- Structured Insights -->
        <div v-if="insights" class="insights-section">
          <t-row :gutter="16">
            <!-- Investment Thesis -->
            <t-col :span="6">
              <t-card title="投资要点" size="small">
                <div class="insight-list">
                  <div v-for="(point, index) in insights.investment_thesis" :key="index" class="insight-item">
                    <t-icon name="check-circle" class="insight-icon success" />
                    <span>{{ point }}</span>
                  </div>
                </div>
              </t-card>
            </t-col>

            <!-- Risk Factors -->
            <t-col :span="6">
              <t-card title="风险因素" size="small">
                <div class="insight-list">
                  <div v-for="(risk, index) in insights.risk_factors" :key="index" class="insight-item">
                    <t-icon name="error-circle" class="insight-icon error" />
                    <span>{{ risk }}</span>
                  </div>
                </div>
              </t-card>
            </t-col>

            <!-- Competitive Position -->
            <t-col :span="6">
              <t-card title="竞争地位" size="small">
                <div class="position-info">
                  <t-tag 
                    :theme="getPositionColor(insights.competitive_position.position)"
                    size="large"
                  >
                    {{ insights.competitive_position.position }}
                  </t-tag>
                  <div class="position-details">
                    <p>优秀指标: {{ insights.competitive_position.excellent_metrics }}/{{ insights.competitive_position.total_metrics }}</p>
                  </div>
                </div>
              </t-card>
            </t-col>

            <!-- Financial Strength -->
            <t-col :span="6">
              <t-card title="财务实力" size="small">
                <div class="strength-info">
                  <t-tag 
                    :theme="getStrengthColor(insights.financial_strength.level)"
                    size="large"
                  >
                    {{ insights.financial_strength.level }}
                  </t-tag>
                  <div class="strength-details">
                    <t-progress 
                      :percentage="insights.financial_strength.score" 
                      :theme="getStrengthColor(insights.financial_strength.level)"
                      size="small"
                    />
                    <div class="key-strengths">
                      <span v-for="strength in insights.financial_strength.key_strengths" :key="strength" class="strength-tag">
                        {{ strength }}
                      </span>
                    </div>
                  </div>
                </div>
              </t-card>
            </t-col>
          </t-row>

          <!-- Growth Prospects -->
          <t-row :gutter="16" style="margin-top: 16px">
            <t-col :span="24">
              <t-card title="成长前景" size="small">
                <div class="growth-info">
                  <div class="growth-header">
                    <t-tag 
                      :theme="getProspectsColor(insights.growth_prospects.prospects)"
                      size="large"
                    >
                      {{ insights.growth_prospects.prospects }}
                    </t-tag>
                  </div>
                  <div class="growth-metrics">
                    <div class="growth-metric">
                      <span class="metric-label">营收增长率</span>
                      <span class="metric-value" :class="{ 'positive': insights.growth_prospects.revenue_growth > 0 }">
                        {{ insights.growth_prospects.revenue_growth?.toFixed(2) }}%
                      </span>
                    </div>
                    <div class="growth-metric">
                      <span class="metric-label">利润增长率</span>
                      <span class="metric-value" :class="{ 'positive': insights.growth_prospects.profit_growth > 0 }">
                        {{ insights.growth_prospects.profit_growth?.toFixed(2) }}%
                      </span>
                    </div>
                  </div>
                </div>
              </t-card>
            </t-col>
          </t-row>
        </div>
      </div>
    </t-card>
  </div>
</template>

<style scoped>
.ai-insight {
  height: 100%;
}

.loading-container,
.empty-container {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 300px;
}

.analysis-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.analysis-text {
  margin-bottom: 16px;
}

.markdown-content {
  line-height: 1.6;
  font-size: 14px;
}

/* Markdown styles */
.markdown-content h1,
.markdown-content h2,
.markdown-content h3,
.markdown-content h4,
.markdown-content h5,
.markdown-content h6 {
  margin: 16px 0 8px 0;
  font-weight: 600;
  color: var(--td-text-color-primary);
}

.markdown-content h1 { font-size: 24px; }
.markdown-content h2 { font-size: 20px; }
.markdown-content h3 { 
  font-size: 16px; 
  color: var(--td-brand-color);
  border-left: 3px solid var(--td-brand-color);
  padding-left: 8px;
}
.markdown-content h4 { font-size: 14px; }

.markdown-content p {
  margin: 8px 0;
  color: var(--td-text-color-primary);
}

.markdown-content ul,
.markdown-content ol {
  margin: 8px 0;
  padding-left: 20px;
}

.markdown-content li {
  margin: 4px 0;
  color: var(--td-text-color-primary);
}

.markdown-content strong {
  font-weight: 600;
  color: var(--td-text-color-primary);
}

.markdown-content em {
  font-style: italic;
  color: var(--td-text-color-secondary);
}

.markdown-content code {
  background: var(--td-bg-color-container-select);
  padding: 2px 4px;
  border-radius: 3px;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 13px;
}

.markdown-content blockquote {
  border-left: 4px solid var(--td-border-level-2-color);
  margin: 16px 0;
  padding: 8px 16px;
  background: var(--td-bg-color-container);
  color: var(--td-text-color-secondary);
}

.insights-section {
  margin-top: 16px;
}

.insight-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.insight-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 4px 0;
  font-size: 13px;
  line-height: 1.4;
}

.insight-icon {
  margin-top: 2px;
  flex-shrink: 0;
}

.insight-icon.success {
  color: var(--td-success-color);
}

.insight-icon.error {
  color: var(--td-error-color);
}

.position-info,
.strength-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.position-details,
.strength-details {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.key-strengths {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 8px;
}

.strength-tag {
  background: var(--td-bg-color-container-select);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
}

.growth-info {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.growth-header {
  display: flex;
  align-items: center;
}

.growth-metrics {
  display: flex;
  gap: 24px;
}

.growth-metric {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.metric-label {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.metric-value {
  font-size: 16px;
  font-weight: 500;
  font-family: 'Monaco', 'Menlo', monospace;
}

.metric-value.positive {
  color: var(--td-success-color);
}

:deep(.t-card__body) {
  padding: 12px;
}
</style>
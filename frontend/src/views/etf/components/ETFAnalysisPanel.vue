<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useETFStore } from '@/stores/etf'

const props = defineProps<{
  indexCode: string
  indexName: string
}>()

const etfStore = useETFStore()
const activeTab = ref('quick')
const aiQuestion = ref('')

// Score color based on value
const getScoreColor = (score: number) => {
  if (score >= 70) return '#00a870'
  if (score >= 55) return '#0052d9'
  if (score >= 45) return '#e37318'
  return '#e34d59'
}

// Suggestion tag theme
const getSuggestionTheme = (suggestion: string) => {
  if (suggestion === '积极') return 'success'
  if (suggestion === '谨慎乐观') return 'primary'
  if (suggestion === '观望') return 'warning'
  return 'danger'
}

// Risk level theme
const getRiskLevelTheme = (level: string) => {
  if (level === '低') return 'success'
  if (level === '中') return 'warning'
  return 'danger'
}

// Format dimension scores for display
const dimensionScores = computed(() => {
  const analysis = etfStore.quickAnalysis
  if (!analysis?.dimension_scores) return []
  
  const ds = analysis.dimension_scores
  return [
    { name: '趋势', score: ds.trend.score, weight: ds.trend.weight, detail: ds.trend.direction },
    { name: '动量', score: ds.momentum.score, weight: ds.momentum.weight, detail: ds.momentum.status },
    { name: '波动', score: ds.volatility.score, weight: ds.volatility.weight, detail: ds.volatility.status },
    { name: '量能', score: ds.volume.score, weight: ds.volume.weight, detail: ds.volume.status },
    { name: '情绪', score: ds.sentiment.score, weight: ds.sentiment.weight, detail: ds.sentiment.status },
  ]
})

// Load quick analysis on mount
onMounted(() => {
  etfStore.fetchQuickAnalysis(props.indexCode)
})

// Handlers
const handleRunAIAnalysis = () => {
  etfStore.runAIAnalysis(props.indexCode, aiQuestion.value || undefined)
}

const handleRefreshQuickAnalysis = () => {
  etfStore.fetchQuickAnalysis(props.indexCode)
}
</script>

<template>
  <div class="analysis-panel">
    <t-tabs v-model="activeTab">
      <!-- Quick Analysis Tab -->
      <t-tab-panel value="quick" label="快速分析">
        <t-loading :loading="etfStore.analysisLoading">
          <div v-if="etfStore.quickAnalysis" class="quick-analysis">
            <!-- Overall Score -->
            <div class="score-section">
              <div class="score-card">
                <div class="score-label">多空评分</div>
                <div 
                  class="score-value" 
                  :style="{ color: getScoreColor(etfStore.quickAnalysis.overall_score) }"
                >
                  {{ etfStore.quickAnalysis.overall_score }}
                </div>
                <div class="score-hint">满分100，50为中性</div>
              </div>
              
              <div class="suggestion-card">
                <div class="suggestion-label">操作建议</div>
                <t-tag 
                  :theme="getSuggestionTheme(etfStore.quickAnalysis.suggestion)"
                  size="large"
                >
                  {{ etfStore.quickAnalysis.suggestion }}
                </t-tag>
                <div class="suggestion-detail">
                  {{ etfStore.quickAnalysis.suggestion_detail }}
                </div>
              </div>
            </div>
            
            <!-- Dimension Scores -->
            <div class="dimension-section">
              <div class="section-title">维度分析</div>
              <div class="dimension-list">
                <div 
                  v-for="dim in dimensionScores" 
                  :key="dim.name"
                  class="dimension-item"
                >
                  <div class="dimension-header">
                    <span class="dimension-name">{{ dim.name }}</span>
                    <span class="dimension-weight">{{ dim.weight }}</span>
                  </div>
                  <t-progress
                    :percentage="dim.score"
                    :color="getScoreColor(dim.score)"
                    size="small"
                  />
                  <div class="dimension-detail">{{ dim.detail }}</div>
                </div>
              </div>
            </div>
            
            <!-- Concentration Risk -->
            <div class="concentration-section" v-if="etfStore.quickAnalysis.concentration">
              <div class="section-title">集中度风险</div>
              <t-space>
                <t-tag>CR10: {{ etfStore.quickAnalysis.concentration.cr10 }}%</t-tag>
                <t-tag>HHI: {{ etfStore.quickAnalysis.concentration.hhi?.toFixed(0) }}</t-tag>
                <t-tag :theme="getRiskLevelTheme(etfStore.quickAnalysis.concentration.risk_level)">
                  风险等级: {{ etfStore.quickAnalysis.concentration.risk_level }}
                </t-tag>
              </t-space>
            </div>
            
            <!-- Risks -->
            <div class="risks-section">
              <div class="section-title">风险提示</div>
              <t-list :split="true">
                <t-list-item v-for="(risk, index) in etfStore.quickAnalysis.risks" :key="index">
                  <t-icon name="error-circle" style="color: #e37318; margin-right: 8px" />
                  {{ risk }}
                </t-list-item>
              </t-list>
            </div>
            
            <!-- Disclaimer -->
            <div class="disclaimer">
              {{ etfStore.quickAnalysis.disclaimer }}
            </div>
            
            <!-- Refresh Button -->
            <t-button 
              variant="outline" 
              block 
              style="margin-top: 16px"
              @click="handleRefreshQuickAnalysis"
            >
              刷新分析
            </t-button>
          </div>
          
          <div v-else class="no-data">
            <t-icon name="info-circle" size="48px" />
            <p>暂无分析数据</p>
            <t-button theme="primary" @click="handleRefreshQuickAnalysis">
              开始分析
            </t-button>
          </div>
        </t-loading>
      </t-tab-panel>
      
      <!-- AI Analysis Tab -->
      <t-tab-panel value="ai" label="AI深度分析">
        <div class="ai-analysis">
          <div class="ai-input-section">
            <t-textarea
              v-model="aiQuestion"
              placeholder="可选：输入您想了解的具体问题，如：该指数近期趋势如何？"
              :autosize="{ minRows: 2, maxRows: 4 }"
            />
            <t-button 
              theme="primary" 
              block 
              style="margin-top: 12px"
              :loading="etfStore.analysisLoading"
              @click="handleRunAIAnalysis"
            >
              开始AI分析
            </t-button>
          </div>
          
          <div class="ai-result-section" v-if="etfStore.aiAnalysisResult">
            <div class="section-title">AI分析结果</div>
            <div class="ai-result-content">
              <pre>{{ etfStore.aiAnalysisResult }}</pre>
            </div>
          </div>
          
          <div v-else-if="!etfStore.analysisLoading" class="ai-hint">
            <t-icon name="tips" size="24px" />
            <p>点击"开始AI分析"获取更详细的量化分析报告</p>
          </div>
        </div>
      </t-tab-panel>
    </t-tabs>
  </div>
</template>

<style scoped>
.analysis-panel {
  padding: 8px 0;
}

.quick-analysis {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.score-section {
  display: flex;
  gap: 24px;
}

.score-card {
  flex: 1;
  text-align: center;
  padding: 16px;
  background: var(--td-bg-color-container);
  border-radius: 8px;
}

.score-label {
  font-size: 14px;
  color: var(--td-text-color-secondary);
}

.score-value {
  font-size: 48px;
  font-weight: bold;
  margin: 8px 0;
}

.score-hint {
  font-size: 12px;
  color: var(--td-text-color-placeholder);
}

.suggestion-card {
  flex: 1;
  text-align: center;
  padding: 16px;
  background: var(--td-bg-color-container);
  border-radius: 8px;
}

.suggestion-label {
  font-size: 14px;
  color: var(--td-text-color-secondary);
  margin-bottom: 8px;
}

.suggestion-detail {
  font-size: 13px;
  color: var(--td-text-color-secondary);
  margin-top: 12px;
  line-height: 1.5;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--td-text-color-primary);
  margin-bottom: 12px;
}

.dimension-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.dimension-item {
  padding: 12px;
  background: var(--td-bg-color-container);
  border-radius: 6px;
}

.dimension-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.dimension-name {
  font-weight: 500;
}

.dimension-weight {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.dimension-detail {
  font-size: 12px;
  color: var(--td-text-color-secondary);
  margin-top: 8px;
}

.concentration-section {
  padding: 12px;
  background: var(--td-bg-color-container);
  border-radius: 6px;
}

.risks-section {
  padding: 12px;
  background: var(--td-bg-color-container);
  border-radius: 6px;
}

.disclaimer {
  font-size: 12px;
  color: var(--td-text-color-placeholder);
  text-align: center;
  padding: 12px;
  background: var(--td-bg-color-secondarycontainer);
  border-radius: 6px;
}

.no-data {
  text-align: center;
  padding: 48px 0;
  color: var(--td-text-color-secondary);
}

.no-data p {
  margin: 16px 0;
}

.ai-analysis {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.ai-result-content {
  padding: 16px;
  background: var(--td-bg-color-container);
  border-radius: 6px;
  max-height: 400px;
  overflow-y: auto;
}

.ai-result-content pre {
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: inherit;
  margin: 0;
  line-height: 1.6;
}

.ai-hint {
  text-align: center;
  padding: 48px 0;
  color: var(--td-text-color-secondary);
}

.ai-hint p {
  margin-top: 12px;
}
</style>

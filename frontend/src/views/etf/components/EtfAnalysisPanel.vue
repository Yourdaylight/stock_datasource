<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useEtfStore } from '@/stores/etf'

const props = defineProps<{
  etfCode: string
  etfName: string
}>()

const etfStore = useEtfStore()
const activeTab = ref('quick')
const aiQuestion = ref('')

// Preset questions for ETF analysis
const presetQuestions = [
  '这只ETF的跟踪效果如何？',
  '近期表现和风险如何？',
  '适合什么类型的投资者？',
  '与同类ETF相比有什么优势？',
]

// Load quick analysis on mount
onMounted(() => {
  etfStore.fetchQuickAnalysis(props.etfCode)
})

// Handlers
const handleRunAIAnalysis = () => {
  etfStore.runAIAnalysis(props.etfCode, aiQuestion.value || undefined)
}

const handlePresetQuestion = (question: string) => {
  aiQuestion.value = question
  handleRunAIAnalysis()
}

const handleRefreshQuickAnalysis = () => {
  etfStore.fetchQuickAnalysis(props.etfCode)
}

const handleClearHistory = () => {
  etfStore.clearConversation(props.etfCode)
}

// Format percentage
const formatPercent = (value?: number) => {
  if (value === undefined || value === null) return '-'
  return value > 0 ? `+${value.toFixed(2)}%` : `${value.toFixed(2)}%`
}

// Get color based on value
const getChangeColor = (value?: number) => {
  if (value === undefined || value === null) return 'inherit'
  return value > 0 ? '#e34d59' : value < 0 ? '#00a870' : 'inherit'
}
</script>

<template>
  <div class="analysis-panel">
    <t-tabs v-model="activeTab">
      <!-- Quick Analysis Tab -->
      <t-tab-panel value="quick" label="快速分析">
        <t-loading :loading="etfStore.analysisLoading">
          <div v-if="etfStore.quickAnalysis" class="quick-analysis">
            <!-- Basic Info -->
            <div class="info-section">
              <div class="section-title">基本信息</div>
              <div class="info-grid">
                <div class="info-item">
                  <span class="info-label">管理人</span>
                  <span class="info-value">{{ etfStore.quickAnalysis.basic_info.management || '-' }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">托管人</span>
                  <span class="info-value">{{ etfStore.quickAnalysis.basic_info.custodian || '-' }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">管理费率</span>
                  <span class="info-value">
                    {{ etfStore.quickAnalysis.basic_info.m_fee 
                       ? etfStore.quickAnalysis.basic_info.m_fee.toFixed(2) + '%' 
                       : '-' }}
                  </span>
                </div>
                <div class="info-item">
                  <span class="info-label">托管费率</span>
                  <span class="info-value">
                    {{ etfStore.quickAnalysis.basic_info.c_fee 
                       ? etfStore.quickAnalysis.basic_info.c_fee.toFixed(2) + '%' 
                       : '-' }}
                  </span>
                </div>
              </div>
            </div>
            
            <!-- Price Metrics -->
            <div class="metrics-section">
              <div class="section-title">行情指标</div>
              <div class="metrics-grid">
                <div class="metric-card">
                  <div class="metric-label">最新价</div>
                  <div class="metric-value">
                    {{ etfStore.quickAnalysis.price_metrics.latest_close?.toFixed(3) || '-' }}
                  </div>
                </div>
                <div class="metric-card">
                  <div class="metric-label">今日涨跌</div>
                  <div 
                    class="metric-value"
                    :style="{ color: getChangeColor(etfStore.quickAnalysis.price_metrics.latest_pct_chg) }"
                  >
                    {{ formatPercent(etfStore.quickAnalysis.price_metrics.latest_pct_chg) }}
                  </div>
                </div>
                <div class="metric-card">
                  <div class="metric-label">近5日</div>
                  <div 
                    class="metric-value"
                    :style="{ color: getChangeColor(etfStore.quickAnalysis.price_metrics.return_5d) }"
                  >
                    {{ formatPercent(etfStore.quickAnalysis.price_metrics.return_5d) }}
                  </div>
                </div>
                <div class="metric-card">
                  <div class="metric-label">近20日</div>
                  <div 
                    class="metric-value"
                    :style="{ color: getChangeColor(etfStore.quickAnalysis.price_metrics.return_20d) }"
                  >
                    {{ formatPercent(etfStore.quickAnalysis.price_metrics.return_20d) }}
                  </div>
                </div>
              </div>
            </div>
            
            <!-- Risk Metrics -->
            <div class="metrics-section">
              <div class="section-title">风险指标</div>
              <div class="metrics-grid">
                <div class="metric-card">
                  <div class="metric-label">年化波动率</div>
                  <div class="metric-value">
                    {{ etfStore.quickAnalysis.risk_metrics.annual_volatility?.toFixed(2) || '-' }}%
                  </div>
                </div>
                <div class="metric-card">
                  <div class="metric-label">最大回撤</div>
                  <div class="metric-value" style="color: #e34d59">
                    {{ etfStore.quickAnalysis.risk_metrics.max_drawdown?.toFixed(2) || '-' }}%
                  </div>
                </div>
                <div class="metric-card">
                  <div class="metric-label">日均成交额</div>
                  <div class="metric-value">
                    {{ etfStore.quickAnalysis.volume_metrics.avg_amount_wan?.toFixed(0) || '-' }}万
                  </div>
                </div>
              </div>
            </div>
            
            <!-- Tracking Info -->
            <div class="tracking-section">
              <div class="section-title">跟踪信息</div>
              <div class="tracking-content">
                <div class="tracking-item">
                  <span class="tracking-label">跟踪基准</span>
                  <span class="tracking-value">
                    {{ etfStore.quickAnalysis.tracking_info.benchmark || '-' }}
                  </span>
                </div>
                <div class="tracking-item" v-if="etfStore.quickAnalysis.tracking_info.tracking_diff !== undefined">
                  <span class="tracking-label">跟踪偏离</span>
                  <span 
                    class="tracking-value"
                    :style="{ color: Math.abs(etfStore.quickAnalysis.tracking_info.tracking_diff) > 1 ? '#e37318' : '#00a870' }"
                  >
                    {{ etfStore.quickAnalysis.tracking_info.tracking_diff?.toFixed(2) }}%
                  </span>
                </div>
                <div class="tracking-analysis" v-if="etfStore.quickAnalysis.tracking_info.analysis">
                  {{ etfStore.quickAnalysis.tracking_info.analysis }}
                </div>
              </div>
            </div>
            
            <!-- Signals -->
            <div class="signals-section" v-if="etfStore.quickAnalysis.signals.length > 0">
              <div class="section-title">分析信号</div>
              <div class="signals-list">
                <div 
                  v-for="(signal, index) in etfStore.quickAnalysis.signals" 
                  :key="index"
                  class="signal-item"
                  :class="{ warning: signal.includes('⚠️') }"
                >
                  {{ signal }}
                </div>
              </div>
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
          <!-- Preset Questions -->
          <div class="preset-questions">
            <div class="preset-label">快捷问题</div>
            <div class="preset-list">
              <t-tag
                v-for="q in presetQuestions"
                :key="q"
                theme="primary"
                variant="light"
                class="preset-tag"
                @click="handlePresetQuestion(q)"
              >
                {{ q }}
              </t-tag>
            </div>
          </div>
          
          <div class="ai-input-section">
            <t-textarea
              v-model="aiQuestion"
              placeholder="输入您想了解的问题，或点击上方快捷问题"
              :autosize="{ minRows: 2, maxRows: 4 }"
            />
            <div class="ai-actions">
              <t-button 
                theme="primary" 
                :loading="etfStore.analysisLoading"
                @click="handleRunAIAnalysis"
              >
                开始AI分析
              </t-button>
              <t-button 
                variant="outline"
                :disabled="etfStore.historyLength === 0"
                @click="handleClearHistory"
              >
                清除对话
              </t-button>
            </div>
            <div class="session-info" v-if="etfStore.historyLength > 0">
              对话轮数: {{ etfStore.historyLength }}
            </div>
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
  gap: 20px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--td-text-color-primary);
  margin-bottom: 12px;
}

.info-section {
  padding: 12px;
  background: var(--td-bg-color-container);
  border-radius: 6px;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.info-item {
  display: flex;
  justify-content: space-between;
}

.info-label {
  color: var(--td-text-color-secondary);
  font-size: 13px;
}

.info-value {
  font-size: 13px;
}

.metrics-section {
  padding: 12px;
  background: var(--td-bg-color-container);
  border-radius: 6px;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.metric-card {
  text-align: center;
  padding: 8px;
  background: var(--td-bg-color-secondarycontainer);
  border-radius: 4px;
}

.metric-label {
  font-size: 12px;
  color: var(--td-text-color-secondary);
  margin-bottom: 4px;
}

.metric-value {
  font-size: 18px;
  font-weight: 600;
}

.tracking-section {
  padding: 12px;
  background: var(--td-bg-color-container);
  border-radius: 6px;
}

.tracking-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tracking-item {
  display: flex;
  justify-content: space-between;
}

.tracking-label {
  color: var(--td-text-color-secondary);
  font-size: 13px;
}

.tracking-value {
  font-size: 13px;
}

.tracking-analysis {
  font-size: 13px;
  color: var(--td-text-color-secondary);
  padding-top: 8px;
  border-top: 1px solid var(--td-component-border);
}

.signals-section {
  padding: 12px;
  background: var(--td-bg-color-container);
  border-radius: 6px;
}

.signals-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.signal-item {
  padding: 8px 12px;
  background: var(--td-bg-color-secondarycontainer);
  border-radius: 4px;
  font-size: 13px;
}

.signal-item.warning {
  background: #fff3e0;
  color: #e37318;
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
  gap: 20px;
}

.preset-questions {
  padding: 12px;
  background: var(--td-bg-color-container);
  border-radius: 6px;
}

.preset-label {
  font-size: 13px;
  color: var(--td-text-color-secondary);
  margin-bottom: 8px;
}

.preset-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.preset-tag {
  cursor: pointer;
}

.preset-tag:hover {
  transform: scale(1.02);
}

.ai-actions {
  display: flex;
  gap: 12px;
  margin-top: 12px;
}

.session-info {
  font-size: 12px;
  color: var(--td-text-color-placeholder);
  margin-top: 8px;
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

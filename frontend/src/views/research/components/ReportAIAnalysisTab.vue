<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { useFinancialAnalysisStore } from '@/stores/financial-analysis'

const props = defineProps<{
  code: string
  period: string
  market: string
  companyName: string
}>()

const store = useFinancialAnalysisStore()
const historyVisible = ref(false)

// ========== Computed ==========

const hasAnalysis = computed(() => !!store.currentAnalysis)
const analysisContent = computed(() => store.currentAnalysis?.report_content || '')
const analysisScore = computed(() => store.currentAnalysis?.health_score || 0)
const analysisSections = computed(() => store.currentAnalysis?.analysis_sections || [])
const currentAnalysisType = computed(() => store.currentAnalysis?.analysis_type || 'comprehensive')
const analysisTime = computed(() => {
  const t = store.currentAnalysis?.created_at
  if (!t) return ''
  try {
    return new Date(t).toLocaleString('zh-CN')
  } catch {
    return t
  }
})

const scoreColor = computed(() => {
  if (analysisScore.value >= 70) return '#2ba471'
  if (analysisScore.value >= 50) return '#e37318'
  return '#d54941'
})

// ========== Markdown Rendering ==========

const renderedSections = computed(() => {
  if (analysisSections.value?.length > 0) {
    return analysisSections.value
  }
  if (!analysisContent.value) return []
  return parseMarkdownSections(analysisContent.value)
})

const parseMarkdownSections = (content: string) => {
  const sections: Array<{ title: string; content: string; icon: string }> = []
  const parts = content.split(/^(#{2,3}\s+.+)$/gm)

  let currentTitle = ''
  let currentContent = ''

  for (const part of parts) {
    const headingMatch = part.match(/^#{2,3}\s+(.+)$/)
    if (headingMatch) {
      if (currentTitle) {
        sections.push({
          title: currentTitle,
          content: currentContent.trim(),
          icon: getIconForTitle(currentTitle),
        })
      }
      currentTitle = headingMatch[1].trim()
      currentContent = ''
    } else {
      currentContent += part
    }
  }

  if (currentTitle) {
    sections.push({
      title: currentTitle,
      content: currentContent.trim(),
      icon: getIconForTitle(currentTitle),
    })
  }

  if (sections.length === 0 && content.trim()) {
    sections.push({
      title: '分析报告',
      content: content.trim(),
      icon: '📄',
    })
  }

  return sections
}

const getIconForTitle = (title: string): string => {
  if (title.includes('盈利')) return '📈'
  if (title.includes('偿债')) return '🏦'
  if (title.includes('营运') || title.includes('运营')) return '⚙️'
  if (title.includes('成长')) return '🚀'
  if (title.includes('现金流')) return '💰'
  if (title.includes('杜邦')) return '🔍'
  if (title.includes('同业') || title.includes('对比')) return '📊'
  if (title.includes('投资') || title.includes('建议') || title.includes('综合')) return '💡'
  if (title.includes('风险')) return '⚠️'
  if (title.includes('亮点')) return '✨'
  if (title.includes('AI') || title.includes('智能')) return '🤖'
  return '📋'
}

const parseContentItems = (content: string): Array<{ type: 'kv' | 'list' | 'text'; key?: string; value?: string; text: string }> => {
  if (!content) return []
  const lines = content.split('\n').filter(l => l.trim())
  const items: Array<{ type: 'kv' | 'list' | 'text'; key?: string; value?: string; text: string }> = []

  for (const line of lines) {
    const trimmed = line.trim()
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ') || trimmed.startsWith('• ')) {
      const text = trimmed.replace(/^[-*•]\s+/, '')
      const kvMatch = text.match(/^(.+?)[：:]\s*(.+)$/)
      if (kvMatch) {
        items.push({ type: 'kv', key: kvMatch[1], value: kvMatch[2], text })
      } else {
        items.push({ type: 'list', text })
      }
    } else if (trimmed.startsWith('#')) {
      continue
    } else {
      items.push({ type: 'text', text: trimmed })
    }
  }

  return items
}

// ========== Section Collapse ==========
const expandedSections = ref<Set<number>>(new Set())

const toggleSection = (idx: number) => {
  if (expandedSections.value.has(idx)) {
    expandedSections.value.delete(idx)
  } else {
    expandedSections.value.add(idx)
  }
  expandedSections.value = new Set(expandedSections.value)
}

const isSectionExpanded = (idx: number) => expandedSections.value.has(idx)

watch(
  () => store.currentAnalysis,
  () => {
    if (store.currentAnalysis) {
      const allIdx = new Set<number>()
      renderedSections.value.forEach((_, i) => allIdx.add(i))
      expandedSections.value = allIdx
    }
  },
  { immediate: true }
)

// ========== Actions ==========

const handleAnalyze = async () => {
  try {
    await store.runAnalysis({
      code: props.code,
      end_date: props.period,
      market: props.market,
      analysis_type: 'comprehensive',
    })
    MessagePlugin.success('AI分析完成')
    loadHistory()
  } catch (error: any) {
    MessagePlugin.error(error?.message || 'AI分析失败，请稍后重试')
  }
}

const handleAIDeepAnalyze = async () => {
  try {
    await store.runLLMAnalysis({
      code: props.code,
      end_date: props.period,
      market: props.market,
    })
    MessagePlugin.success('AI大模型深度分析完成')
    loadHistory()
  } catch (error: any) {
    MessagePlugin.error(error?.message || 'AI深度分析失败，请检查LLM配置或稍后重试')
  }
}

const isAnyRunning = computed(() => store.analyzeRunning || store.aiDeepRunning)

const loadHistory = async () => {
  try {
    await store.fetchAnalysisHistory(props.code, {
      end_date: props.period,
      market: props.market,
      limit: 20,
    })
    if (!store.currentAnalysis && store.analysisRecords.length > 0) {
      await store.fetchAnalysisRecord(store.analysisRecords[0].id)
    }
  } catch {
    // Silent fail for history
  }
}

const selectRecord = async (recordId: string) => {
  try {
    await store.fetchAnalysisRecord(recordId)
    historyVisible.value = false
  } catch {
    MessagePlugin.error('加载分析记录失败')
  }
}

const formatHistoryTime = (t: string): string => {
  if (!t) return ''
  try {
    return new Date(t).toLocaleString('zh-CN')
  } catch {
    return t
  }
}

onMounted(() => {
  loadHistory()
})

const analysisModules = [
  { icon: '📈', title: '盈利能力分析', desc: 'ROE、ROA、毛利率、净利率、EBITDA利润率' },
  { icon: '🏦', title: '偿债能力分析', desc: '资产负债率、流动比率、速动比率、利息保障倍数' },
  { icon: '⚙️', title: '营运能力分析', desc: '资产周转率、存货周转率、应收账款周转率' },
  { icon: '🚀', title: '成长能力分析', desc: '营收增长率、净利润增长率、经营现金流增长率' },
  { icon: '💰', title: '现金流分析', desc: '经营/投资/筹资现金流结构、自由现金流评估' },
  { icon: '🔍', title: '杜邦分析', desc: 'ROE三因素分解：利润率 × 资产周转率 × 权益乘数' },
  { icon: '📊', title: '同业对比', desc: '关键指标与行业中位数/均值对比分析' },
  { icon: '💡', title: '综合投资建议', desc: '风险提示、投资亮点、估值参考' },
]
</script>

<template>
  <div class="report-ai-analysis-tab">
    <!-- No Analysis Yet -->
    <div v-if="!hasAnalysis && !isAnyRunning" class="no-analysis">
      <div class="analysis-prompt">
        <div class="prompt-icon">🤖</div>
        <h3 class="prompt-title">AI 专业财报分析</h3>
        <p class="prompt-desc">
          使用AI对 <strong>{{ companyName }}</strong> {{ period }} 财报数据进行专业深度分析
        </p>
      </div>

      <div class="module-grid">
        <div v-for="mod in analysisModules" :key="mod.title" class="module-card">
          <span class="module-icon">{{ mod.icon }}</span>
          <div class="module-info">
            <div class="module-title">{{ mod.title }}</div>
            <div class="module-desc">{{ mod.desc }}</div>
          </div>
        </div>
      </div>

      <div class="start-action">
        <t-button
          theme="primary"
          size="large"
          :loading="store.analyzeRunning"
          @click="handleAnalyze"
        >
          <template #icon>
            <t-icon name="play-circle" />
          </template>
          快速规则分析
        </t-button>
        <t-button
          theme="warning"
          size="large"
          variant="outline"
          :loading="store.aiDeepRunning"
          @click="handleAIDeepAnalyze"
        >
          <template #icon>
            <t-icon name="rocket" />
          </template>
          🤖 AI大模型深度分析
        </t-button>
      </div>
      <p class="start-hint">
        <span class="hint-fast">⚡ 快速规则分析：基于预设规则引擎，秒级出结果</span>
        <span class="hint-deep">🤖 AI大模型分析：调用LLM深度分析，约10-60秒，洞察更深</span>
      </p>
    </div>

    <!-- Analysis Running -->
    <div v-if="isAnyRunning" class="analysis-running">
      <div class="running-animation">
        <t-loading size="large" />
      </div>
      <h3 class="running-title" v-if="store.aiDeepRunning">
        🤖 正在进行AI大模型深度分析...
      </h3>
      <h3 class="running-title" v-else>
        正在进行AI财报分析...
      </h3>
      <p class="running-desc" v-if="store.aiDeepRunning">
        AI大模型正在对 {{ companyName }} {{ period }} 财报数据进行深度分析和专业洞察，
        这可能需要10-60秒，请耐心等待
      </p>
      <p class="running-desc" v-else>
        AI正在对 {{ companyName }} {{ period }} 财报数据进行八大维度深度分析，
        这可能需要1-3分钟，请耐心等待
      </p>
      <div class="running-steps">
        <div v-for="(mod, idx) in analysisModules" :key="idx" class="running-step">
          <span class="step-icon">{{ mod.icon }}</span>
          <span class="step-text">{{ mod.title }}</span>
        </div>
      </div>
    </div>

    <!-- Analysis Result -->
    <div v-if="hasAnalysis && !isAnyRunning" class="analysis-result">
      <div class="result-header">
        <div class="result-meta">
          <div class="meta-left">
            <t-tag
              :theme="currentAnalysisType === 'ai_deep' ? 'warning' : 'success'"
              variant="light"
            >
              <template #icon><t-icon :name="currentAnalysisType === 'ai_deep' ? 'logo-android' : 'check-circle'" /></template>
              {{ currentAnalysisType === 'ai_deep' ? 'AI大模型分析' : '规则分析' }}
            </t-tag>
            <span class="meta-time" v-if="analysisTime">{{ analysisTime }}</span>
          </div>
          <div class="meta-actions">
            <t-button
              variant="outline"
              size="small"
              @click="historyVisible = true"
              v-if="store.analysisRecords.length > 1"
            >
              <template #icon><t-icon name="time" /></template>
              历史记录 ({{ store.analysisRecords.length }})
            </t-button>
            <t-button
              theme="primary"
              variant="outline"
              size="small"
              :loading="store.analyzeRunning"
              @click="handleAnalyze"
            >
              <template #icon><t-icon name="refresh" /></template>
              重新规则分析
            </t-button>
            <t-button
              theme="warning"
              size="small"
              :loading="store.aiDeepRunning"
              @click="handleAIDeepAnalyze"
            >
              <template #icon><t-icon name="rocket" /></template>
              🤖 AI深度分析
            </t-button>
          </div>
        </div>

        <div class="result-score" v-if="analysisScore > 0">
          <div class="score-badge" :style="{ borderColor: scoreColor }">
            <span class="score-val" :style="{ color: scoreColor }">{{ analysisScore }}</span>
            <span class="score-max">/100</span>
          </div>
          <span class="score-desc">健康度评分</span>
        </div>
      </div>

      <div class="analysis-sections">
        <div
          v-for="(section, idx) in renderedSections"
          :key="idx"
          class="analysis-section-card"
        >
          <div class="section-header" @click="toggleSection(idx)">
            <div class="section-header-left">
              <span class="section-icon">{{ section.icon || '📋' }}</span>
              <span class="section-title-text">{{ section.title }}</span>
            </div>
            <t-icon
              :name="isSectionExpanded(idx) ? 'chevron-up' : 'chevron-down'"
              class="expand-icon"
            />
          </div>
          <div v-show="isSectionExpanded(idx)" class="section-body">
            <div
              v-for="(item, jdx) in parseContentItems(section.content)"
              :key="jdx"
              :class="['content-item', `content-${item.type}`]"
            >
              <template v-if="item.type === 'kv'">
                <span class="item-key">{{ item.key }}</span>
                <span class="item-sep">：</span>
                <span class="item-value">{{ item.value }}</span>
              </template>
              <template v-else-if="item.type === 'list'">
                <span class="item-bullet">•</span>
                <span class="item-text">{{ item.text }}</span>
              </template>
              <template v-else>
                <p class="item-paragraph">{{ item.text }}</p>
              </template>
            </div>
            <div
              v-if="parseContentItems(section.content).length === 0 && section.content"
              class="raw-content"
            >
              {{ section.content }}
            </div>
          </div>
        </div>
      </div>

      <div v-if="renderedSections.length === 0 && analysisContent" class="raw-markdown">
        <pre class="markdown-pre">{{ analysisContent }}</pre>
      </div>
    </div>

    <!-- History Drawer -->
    <t-drawer
      v-model:visible="historyVisible"
      header="历史分析记录"
      :size="420"
      placement="right"
      :close-on-overlay-click="true"
    >
      <div class="history-list">
        <div
          v-for="record in store.analysisRecords"
          :key="record.id"
          class="history-item"
          :class="{ active: record.id === store.currentAnalysis?.id }"
          @click="selectRecord(record.id)"
        >
          <div class="history-item-header">
            <t-tag
              :theme="record.analysis_type === 'ai_deep' ? 'warning' : (record.id === store.currentAnalysis?.id ? 'primary' : 'default')"
              size="small"
              variant="light"
            >
              {{ record.analysis_type === 'ai_deep' ? '🤖 AI大模型' : (record.analysis_type === 'comprehensive' ? '规则分析' : record.analysis_type) }}
            </t-tag>
            <span class="history-score" v-if="record.health_score">
              {{ record.health_score }}分
            </span>
          </div>
          <div class="history-item-time">{{ formatHistoryTime(record.created_at) }}</div>
          <div class="history-item-preview">
            {{ (record.report_content || '').substring(0, 120) }}...
          </div>
        </div>

        <t-empty v-if="!store.analysisRecords.length" description="暂无历史分析记录" />
      </div>
    </t-drawer>
  </div>
</template>

<style scoped>
.report-ai-analysis-tab {
  padding: 4px 0;
}

/* ========== No Analysis ========== */
.no-analysis {
  text-align: center;
}

.analysis-prompt {
  padding: 30px 20px 20px;
}

.prompt-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.prompt-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--td-text-color-primary);
  margin: 0 0 8px;
}

.prompt-desc {
  font-size: 14px;
  color: var(--td-text-color-secondary);
  margin: 0;
}

.module-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  padding: 0 20px;
  margin-bottom: 24px;
  text-align: left;
}

@media (max-width: 640px) {
  .module-grid {
    grid-template-columns: 1fr;
  }
}

.module-card {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 14px 16px;
  border-radius: 10px;
  background: var(--td-bg-color-secondarycontainer);
  border: 1px solid var(--td-border-level-1-color);
  transition: all 0.2s ease;
}

.module-card:hover {
  border-color: var(--td-brand-color);
  box-shadow: 0 2px 8px rgba(0, 82, 217, 0.08);
  transform: translateY(-1px);
}

.module-icon {
  font-size: 22px;
  flex-shrink: 0;
  margin-top: 2px;
}

.module-info {
  flex: 1;
}

.module-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--td-text-color-primary);
  margin-bottom: 4px;
}

.module-desc {
  font-size: 12px;
  color: var(--td-text-color-secondary);
  line-height: 1.5;
}

.start-action {
  padding-bottom: 12px;
  display: flex;
  justify-content: center;
  gap: 12px;
  flex-wrap: wrap;
}

.start-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--td-text-color-placeholder);
  padding-bottom: 20px;
}

.hint-fast, .hint-deep {
  display: inline-block;
}

/* ========== Running ========== */
.analysis-running {
  text-align: center;
  padding: 40px 20px;
}

.running-animation {
  margin-bottom: 20px;
}

.running-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--td-text-color-primary);
  margin: 0 0 8px;
}

.running-desc {
  font-size: 14px;
  color: var(--td-text-color-secondary);
  margin: 0 auto 24px;
  max-width: 500px;
}

.running-steps {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px;
  max-width: 600px;
  margin: 0 auto;
}

.running-step {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 20px;
  background: var(--td-bg-color-secondarycontainer);
  font-size: 13px;
  color: var(--td-text-color-secondary);
  animation: pulse 2s ease-in-out infinite;
}

.running-step:nth-child(2) { animation-delay: 0.25s; }
.running-step:nth-child(3) { animation-delay: 0.5s; }
.running-step:nth-child(4) { animation-delay: 0.75s; }
.running-step:nth-child(5) { animation-delay: 1s; }
.running-step:nth-child(6) { animation-delay: 1.25s; }
.running-step:nth-child(7) { animation-delay: 1.5s; }
.running-step:nth-child(8) { animation-delay: 1.75s; }

@keyframes pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

.step-icon { font-size: 16px; }
.step-text { font-size: 13px; }

/* ========== Result ========== */
.analysis-result {
  padding: 0;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 0 18px;
  border-bottom: 1px solid var(--td-border-level-1-color);
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 12px;
}

.result-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.meta-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.meta-time {
  font-size: 13px;
  color: var(--td-text-color-placeholder);
}

.meta-actions {
  display: flex;
  gap: 8px;
}

.result-score {
  display: flex;
  align-items: center;
  gap: 8px;
}

.score-badge {
  display: flex;
  align-items: baseline;
  gap: 2px;
  padding: 6px 14px;
  border-radius: 24px;
  border: 2px solid;
  background: var(--td-bg-color-container);
}

.score-val {
  font-size: 24px;
  font-weight: 700;
  font-family: 'DIN Alternate', 'SF Mono', monospace;
}

.score-max {
  font-size: 13px;
  color: var(--td-text-color-secondary);
}

.score-desc {
  font-size: 13px;
  color: var(--td-text-color-secondary);
}

/* ========== Section Cards ========== */
.analysis-sections {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.analysis-section-card {
  border-radius: 10px;
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-border-level-1-color);
  overflow: hidden;
  transition: box-shadow 0.2s ease;
}

.analysis-section-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;
}

.section-header:hover {
  background: var(--td-bg-color-secondarycontainer);
}

.section-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-icon { font-size: 18px; }

.section-title-text {
  font-size: 15px;
  font-weight: 600;
  color: var(--td-text-color-primary);
}

.expand-icon {
  color: var(--td-text-color-secondary);
  transition: transform 0.2s;
}

.section-body {
  padding: 0 18px 16px;
  border-top: 1px solid var(--td-border-level-1-color);
  padding-top: 14px;
}

.content-item {
  margin-bottom: 6px;
  line-height: 1.7;
  font-size: 13px;
}

.content-kv {
  display: flex;
  flex-wrap: wrap;
  padding: 5px 0;
  border-bottom: 1px dashed var(--td-border-level-1-color);
}

.content-kv:last-child { border-bottom: none; }

.item-key {
  font-weight: 600;
  color: var(--td-text-color-primary);
}

.item-sep {
  color: var(--td-text-color-placeholder);
  margin: 0 2px;
}

.item-value {
  color: var(--td-text-color-secondary);
  flex: 1;
}

.content-list {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 3px 0;
}

.item-bullet {
  color: var(--td-brand-color);
  font-weight: 700;
  flex-shrink: 0;
  margin-top: 1px;
}

.item-text { color: var(--td-text-color-secondary); }

.item-paragraph {
  color: var(--td-text-color-secondary);
  margin: 0;
}

.raw-content {
  white-space: pre-wrap;
  font-size: 13px;
  color: var(--td-text-color-secondary);
  line-height: 1.7;
}

.raw-markdown {
  padding: 16px;
  background: var(--td-bg-color-secondarycontainer);
  border-radius: 8px;
}

.markdown-pre {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  color: var(--td-text-color-secondary);
  line-height: 1.7;
  margin: 0;
  font-family: inherit;
}

/* ========== History ========== */
.history-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.history-item {
  padding: 14px 16px;
  border-radius: 8px;
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-border-level-1-color);
  cursor: pointer;
  transition: all 0.2s;
}

.history-item:hover {
  border-color: var(--td-brand-color);
  box-shadow: 0 2px 8px rgba(0, 82, 217, 0.08);
}

.history-item.active {
  border-color: var(--td-brand-color);
  background: rgba(0, 82, 217, 0.03);
}

.history-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.history-score {
  font-size: 14px;
  font-weight: 700;
  font-family: 'DIN Alternate', 'SF Mono', monospace;
  color: var(--td-brand-color);
}

.history-item-time {
  font-size: 12px;
  color: var(--td-text-color-placeholder);
  margin-bottom: 6px;
}

.history-item-preview {
  font-size: 12px;
  color: var(--td-text-color-secondary);
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}
</style>

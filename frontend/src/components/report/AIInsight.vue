<script setup lang="ts">
import { computed } from 'vue'
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
}>()

// Parse structured sections from markdown content
const sections = computed(() => {
  if (!props.analysis?.content) return []
  
  const content = props.analysis.content
  const result: Array<{ title: string; icon: string; items: string[]; type: 'list' | 'kv' }> = []
  
  // Split by ### headers
  const parts = content.split(/^### /m).filter(Boolean)
  
  for (const part of parts) {
    const lines = part.trim().split('\n')
    const titleLine = lines[0].trim()
    
    // Extract icon and title
    const iconMatch = titleLine.match(/^([\p{Emoji}\u200d\ufe0f]+)\s*(.+)/u)
    const icon = iconMatch ? iconMatch[1] : ''
    const title = iconMatch ? iconMatch[2] : titleLine
    
    // Extract list items
    const items = lines.slice(1)
      .map(l => l.trim())
      .filter(l => l.startsWith('- '))
      .map(l => l.substring(2).trim())
      .filter(Boolean)
    
    if (items.length > 0) {
      // Check if items are key-value pairs (contain : or ：)
      const isKV = items.every(item => /[:：]/.test(item))
      result.push({ title, icon, items, type: isKV ? 'kv' : 'list' })
    }
  }
  
  return result
})

// Get health score from content
const healthScore = computed(() => {
  if (!props.analysis?.content) return null
  const match = props.analysis.content.match(/财务健康度评分[:：]\s*(\d+)\s*\/\s*100/)
  return match ? parseInt(match[1]) : null
})

// Get score theme
const scoreTheme = computed(() => {
  if (!healthScore.value) return 'warning'
  if (healthScore.value >= 70) return 'success'
  if (healthScore.value >= 50) return 'warning'
  return 'error'
})

// Get section card theme
const getSectionTheme = (title: string): string => {
  if (title.includes('优势')) return 'success'
  if (title.includes('关注')) return 'warning'
  if (title.includes('盈利')) return 'primary'
  if (title.includes('偿债')) return 'default'
  if (title.includes('成长')) return 'success'
  if (title.includes('投资建议')) return 'primary'
  if (title.includes('数据说明')) return 'default'
  return 'default'
}

// Parse KV item
const parseKV = (item: string): { key: string; value: string } => {
  const sep = item.indexOf('：') !== -1 ? '：' : ':'
  const idx = item.indexOf(sep)
  if (idx === -1) return { key: item, value: '' }
  return { key: item.substring(0, idx).trim(), value: item.substring(idx + 1).trim() }
}

// Get value color for KV items
const getValueColor = (value: string): string => {
  if (value === 'N/A') return 'var(--td-text-color-placeholder)'
  if (value.includes('%')) {
    const num = parseFloat(value)
    if (!isNaN(num)) {
      if (num > 20) return 'var(--td-success-color)'
      if (num < 0) return 'var(--td-error-color)'
    }
  }
  return 'var(--td-text-color-primary)'
}

// Get insights data
const insights = computed(() => {
  return props.analysis?.insights
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

// Handle refresh
const handleRefresh = () => {
  emit('refresh')
}
</script>

<template>
  <div class="ai-insight">
    <!-- Header -->
    <div class="insight-header">
      <h3 class="insight-title">AI 智能分析</h3>
      <t-button theme="primary" variant="outline" size="small" :loading="loading" @click="handleRefresh">
        <template #icon><t-icon name="refresh" /></template>
        刷新分析
      </t-button>
    </div>

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
      <!-- Health Score Card -->
      <div v-if="healthScore !== null" class="score-card" :class="'score-' + scoreTheme">
        <div class="score-circle">
          <t-progress
            theme="circle"
            :percentage="healthScore"
            :color="scoreTheme === 'success' ? '#2ba471' : scoreTheme === 'warning' ? '#e37318' : '#d54941'"
            :stroke-width="8"
            size="100px"
          >
            <div class="score-text">
              <span class="score-number">{{ healthScore }}</span>
              <span class="score-unit">/100</span>
            </div>
          </t-progress>
        </div>
        <div class="score-label">财务健康度评分</div>
      </div>

      <!-- Section Cards Grid -->
      <div class="section-grid">
        <template v-for="(section, idx) in sections" :key="idx">
          <!-- Skip health score section since we render it separately -->
          <div v-if="!section.title.includes('健康度评分')" class="section-card" :class="'theme-' + getSectionTheme(section.title)">
            <div class="section-title">
              <span class="section-icon">{{ section.icon }}</span>
              <span>{{ section.title }}</span>
            </div>
            
            <!-- KV Layout -->
            <div v-if="section.type === 'kv'" class="kv-list">
              <div v-for="(item, i) in section.items" :key="i" class="kv-item">
                <span class="kv-key">{{ parseKV(item).key }}</span>
                <span class="kv-value" :style="{ color: getValueColor(parseKV(item).value) }">
                  {{ parseKV(item).value }}
                </span>
              </div>
            </div>
            
            <!-- List Layout -->
            <div v-else class="item-list">
              <div v-for="(item, i) in section.items" :key="i" class="list-item">
                <t-icon
                  :name="section.title.includes('优势') ? 'check-circle-filled' :
                         section.title.includes('关注') ? 'error-circle-filled' :
                         section.title.includes('建议') ? 'lightbulb' : 'chevron-right'"
                  :class="section.title.includes('优势') ? 'icon-success' :
                          section.title.includes('关注') ? 'icon-warning' :
                          section.title.includes('建议') ? 'icon-primary' : 'icon-default'"
                  size="16px"
                />
                <span>{{ item }}</span>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- Structured Insights (if available) -->
      <div v-if="insights" class="insights-section">
        <t-divider>结构化洞察</t-divider>
        <div class="insights-grid">
          <!-- Investment Thesis -->
          <div v-if="insights.investment_thesis?.length" class="insight-card">
            <div class="insight-card-title">投资要点</div>
            <div v-for="(point, index) in insights.investment_thesis" :key="index" class="insight-point success">
              <t-icon name="check-circle-filled" size="14px" />
              <span>{{ point }}</span>
            </div>
          </div>

          <!-- Risk Factors -->
          <div v-if="insights.risk_factors?.length" class="insight-card">
            <div class="insight-card-title">风险因素</div>
            <div v-for="(risk, index) in insights.risk_factors" :key="index" class="insight-point error">
              <t-icon name="error-circle-filled" size="14px" />
              <span>{{ risk }}</span>
            </div>
          </div>

          <!-- Competitive Position -->
          <div v-if="insights.competitive_position" class="insight-card">
            <div class="insight-card-title">竞争地位</div>
            <div class="insight-metric">
              <t-tag :theme="getPositionColor(insights.competitive_position.position)" size="large">
                {{ insights.competitive_position.position }}
              </t-tag>
              <span class="metric-desc">
                优秀指标: {{ insights.competitive_position.excellent_metrics }}/{{ insights.competitive_position.total_metrics }}
              </span>
            </div>
          </div>

          <!-- Financial Strength -->
          <div v-if="insights.financial_strength" class="insight-card">
            <div class="insight-card-title">财务实力</div>
            <div class="insight-metric">
              <t-tag :theme="getStrengthColor(insights.financial_strength.level)" size="large">
                {{ insights.financial_strength.level }}
              </t-tag>
              <t-progress
                :percentage="insights.financial_strength.score"
                :color="getStrengthColor(insights.financial_strength.level) === 'success' ? '#2ba471' : '#e37318'"
                size="small"
                style="flex: 1; margin-left: 12px"
              />
            </div>
            <div v-if="insights.financial_strength.key_strengths?.length" class="strength-tags">
              <t-tag v-for="s in insights.financial_strength.key_strengths" :key="s" variant="light" theme="primary" size="small">
                {{ s }}
              </t-tag>
            </div>
          </div>

          <!-- Growth Prospects -->
          <div v-if="insights.growth_prospects" class="insight-card wide">
            <div class="insight-card-title">成长前景</div>
            <div class="growth-row">
              <div class="growth-item">
                <span class="growth-label">营收增长率</span>
                <span class="growth-value" :class="{ positive: (insights.growth_prospects.revenue_growth ?? 0) > 0, negative: (insights.growth_prospects.revenue_growth ?? 0) < 0 }">
                  {{ insights.growth_prospects.revenue_growth?.toFixed(2) ?? 'N/A' }}%
                </span>
              </div>
              <div class="growth-item">
                <span class="growth-label">利润增长率</span>
                <span class="growth-value" :class="{ positive: (insights.growth_prospects.profit_growth ?? 0) > 0, negative: (insights.growth_prospects.profit_growth ?? 0) < 0 }">
                  {{ insights.growth_prospects.profit_growth?.toFixed(2) ?? 'N/A' }}%
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ai-insight {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.insight-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.insight-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--td-text-color-primary);
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
  gap: 20px;
}

/* Health Score Card */
.score-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--td-bg-color-container) 0%, var(--td-bg-color-secondarycontainer) 100%);
  border: 1px solid var(--td-border-level-1-color);
}

.score-card.score-success { border-color: rgba(43, 164, 113, 0.3); }
.score-card.score-warning { border-color: rgba(227, 115, 24, 0.3); }
.score-card.score-error { border-color: rgba(213, 73, 65, 0.3); }

.score-text {
  display: flex;
  align-items: baseline;
  justify-content: center;
}

.score-number {
  font-size: 28px;
  font-weight: 700;
  font-family: 'Monaco', 'Menlo', monospace;
}

.score-unit {
  font-size: 12px;
  color: var(--td-text-color-secondary);
  margin-left: 2px;
}

.score-label {
  margin-top: 8px;
  font-size: 13px;
  color: var(--td-text-color-secondary);
}

/* Section Grid */
.section-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

@media (max-width: 768px) {
  .section-grid {
    grid-template-columns: 1fr;
  }
}

.section-card {
  padding: 16px;
  border-radius: 8px;
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-border-level-1-color);
  transition: box-shadow 0.2s;
}

.section-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.section-card.theme-success { border-left: 3px solid var(--td-success-color); }
.section-card.theme-warning { border-left: 3px solid var(--td-warning-color); }
.section-card.theme-primary { border-left: 3px solid var(--td-brand-color); }
.section-card.theme-default { border-left: 3px solid var(--td-border-level-2-color); }

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--td-text-color-primary);
  margin-bottom: 12px;
}

.section-icon {
  font-size: 16px;
}

/* KV List */
.kv-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.kv-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  border-bottom: 1px dashed var(--td-border-level-1-color);
}

.kv-item:last-child {
  border-bottom: none;
}

.kv-key {
  font-size: 13px;
  color: var(--td-text-color-secondary);
}

.kv-value {
  font-size: 14px;
  font-weight: 500;
  font-family: 'Monaco', 'Menlo', monospace;
}

/* List Items */
.item-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.list-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  line-height: 1.5;
  color: var(--td-text-color-primary);
}

.list-item .t-icon {
  margin-top: 3px;
  flex-shrink: 0;
}

.icon-success { color: var(--td-success-color); }
.icon-warning { color: var(--td-warning-color); }
.icon-primary { color: var(--td-brand-color); }
.icon-default { color: var(--td-text-color-placeholder); }

/* Insights Section */
.insights-section {
  margin-top: 4px;
}

.insights-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

@media (max-width: 768px) {
  .insights-grid {
    grid-template-columns: 1fr;
  }
}

.insight-card {
  padding: 14px;
  border-radius: 8px;
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-border-level-1-color);
}

.insight-card.wide {
  grid-column: 1 / -1;
}

.insight-card-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--td-text-color-secondary);
  margin-bottom: 10px;
}

.insight-point {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 13px;
  line-height: 1.4;
  padding: 3px 0;
}

.insight-point.success .t-icon { color: var(--td-success-color); }
.insight-point.error .t-icon { color: var(--td-error-color); }

.insight-point .t-icon {
  margin-top: 2px;
  flex-shrink: 0;
}

.insight-metric {
  display: flex;
  align-items: center;
  gap: 8px;
}

.metric-desc {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.strength-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 8px;
}

.growth-row {
  display: flex;
  gap: 24px;
}

.growth-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.growth-label {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.growth-value {
  font-size: 18px;
  font-weight: 600;
  font-family: 'Monaco', 'Menlo', monospace;
  color: var(--td-text-color-primary);
}

.growth-value.positive { color: var(--td-success-color); }
.growth-value.negative { color: var(--td-error-color); }
</style>

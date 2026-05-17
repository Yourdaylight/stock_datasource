<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { marked } from 'marked'
import type { ChatMessage } from '@/api/chat'
import { useChatStore } from '@/stores/chat'
import PostAnalysisActions from './PostAnalysisActions.vue'
import { datamanageApi } from '@/api/datamanage'
import KLineChart from '@/components/charts/KLineChart.vue'
import TrendChart from '@/components/report/TrendChart.vue'
import ProfitChart from '@/components/ProfitChart.vue'

// Configure marked for security
marked.setOptions({
  breaks: true,
  gfm: true
})

const props = defineProps<{
  messages: ChatMessage[]
  loading: boolean
}>()

const emit = defineEmits<{
  quickAction: [query: string]
}>()

const chatStore = useChatStore()
const router = useRouter()

// Knowledge base availability
const knowledgeEnabled = ref(false)

onMounted(async () => {
  try {
    const status = await datamanageApi.getKnowledgeStatus()
    knowledgeEnabled.value = status.status === 'healthy'
  } catch {
    knowledgeEnabled.value = false
  }
})

// Feature cards for welcome screen
const featureCards = [
  { icon: 'user-talk', title: 'AI分析师团队辩论', desc: '5个Agent实时辩论，看多看空理由全透明', example: '分析贵州茅台', highlight: true },
  { icon: 'chart-line', title: '技术面+基本面全解', desc: 'K线、财务、估值一次出', example: '帮我分析一下 600519 的技术指标' },
  { icon: 'notification', title: '消息面情绪扫描', desc: '新闻、研报、政策综合研判', example: '宁德时代最近有什么消息' },
  { icon: 'search', title: '智能选股', desc: '多条件筛选+量化评分', example: '推荐低估值高ROE的股票' },
]

// Quick-try chips (the "whoa" triggers)
const quickChips = [
  { label: '分析茅台', icon: '🍶' },
  { label: '分析比亚迪', icon: '🚗' },
  { label: '推荐低估值股票', icon: '🔍' },
  { label: '今日大盘走势', icon: '📊' },
]

// Example queries for quick start
const exampleQueries = [
  '帮我分析一下 600519 的技术指标',
  '分析腾讯控股 00700.HK 的技术面和财务情况',
  '推荐一些低PE高ROE的股票',
  '宁德时代最近有什么利好消息',
  '查看沪深300成分股',
  '分析我的持仓',
]

// Render markdown to HTML
const renderMarkdown = (content: string): string => {
  if (!content) return ''
  try {
    let cleanContent = content

    // Fix double-escaped newlines from ClickHouse storage
    // DB stores literal "\n" (two chars) instead of actual newline
    cleanContent = cleanContent.replace(/\\n/g, '\n')
    cleanContent = cleanContent.replace(/\\t/g, '\t')

    // Filter out obvious garbage/partial data (like incomplete JSON fragments)
    if (cleanContent.match(/^\s*\d+\s*[{\[]\s*$/)) {
      return '<span class="text-gray-400">正在生成回复...</span>'
    }
    
    // Remove control characters that might have slipped through
    cleanContent = cleanContent.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, '')
    
    // If content is too short and looks like partial JSON, don't render
    if (cleanContent.length < 10 && /^[\d\s{}\[\]"':,]+$/.test(cleanContent)) {
      return ''
    }
    
    return marked.parse(cleanContent) as string
  } catch (e) {
    console.warn('Markdown render error:', e)
    return content
  }
}

// Get visualizations for a specific message
const getMessageVisualizations = (msgId: string) => {
  return chatStore.messageVisualizations[msgId] || []
}

// Map visualization type to component
const vizComponentMap: Record<string, any> = {
  'kline': KLineChart,
  'financial_trend': TrendChart,
  'profit_curve': ProfitChart,
}

// Handle quick action click
const handleQuickAction = (query: string) => {
  emit('quickAction', query)
}

// Resume last session (for returning users)
const resumeLastSession = async () => {
  const ref = chatStore.lastSessionRef
  if (ref) {
    await chatStore.switchSession(ref.session_id)
    chatStore.lastSessionRef = null
  }
}

// Get agent tag color
const getAgentColor = (agent: string): string => {
  const colors: Record<string, string> = {
    'MarketAgent': 'primary',
    'ScreenerAgent': 'success',
    'ReportAgent': 'warning',
    'PortfolioAgent': 'danger',
    'BacktestAgent': 'default',
    'ChatAgent': 'primary',
    'StockDeepAgent': 'primary',
    'OrchestratorAgent': 'primary',
    'MCPFallback': 'warning'
  }
  return colors[agent] || 'default'
}

// Get tool tag color
const getToolColor = (tool: string): string => {
  const colors: Record<string, string> = {
    'get_stock_info': 'primary',
    'get_stock_kline': 'success',
    'get_stock_valuation': 'warning',
    'calculate_technical_indicators': 'danger',
    'screen_stocks': 'success',
    'get_market_overview': 'primary',
    'write_todos': 'default',
    'read_todos': 'default',
  }
  return colors[tool] || 'default'
}

// Get thinking step icon
const getThinkingStepIcon = (step: string): string => {
  if (step.includes('分析') || step.includes('理解')) return 'browse'
  if (step.includes('选择') || step.includes('路由')) return 'fork'
  if (step.includes('调用') || step.includes('执行')) return 'play-circle'
  if (step.includes('思考') || step.includes('推理')) return 'lightbulb'
  return 'time'
}
</script>

<template>
  <div class="message-list">
    <!-- Enhanced empty state with guidance -->
    <div v-if="messages.length === 0" class="welcome-state">
      <div class="welcome-header">
        <h2 class="welcome-title">A股AI投资助手</h2>
        <p class="welcome-subtitle">多Agent实时辩论 + 买卖信号<br>输入任意股票，看AI分析师团队如何协作决策</p>
      </div>

      <!-- Quick-try chips (primary CTA) -->
      <div class="quick-chips">
        <div class="quick-chips-label">试试输入:</div>
        <div class="quick-chips-row">
          <!-- Resume last conversation chip (for returning users) -->
          <button
            v-if="chatStore.lastSessionRef"
            class="quick-chip quick-chip--resume"
            @click="resumeLastSession"
          >
            <span class="chip-icon">💬</span>
            <span class="chip-text">继续上次: {{ chatStore.lastSessionRef.title }}</span>
            <t-icon name="arrow-right" size="14px" class="chip-arrow" />
          </button>

          <button
            v-for="chip in quickChips"
            :key="chip.label"
            class="quick-chip"
            @click="handleQuickAction(chip.label)"
          >
            <span class="chip-icon">{{ chip.icon }}</span>
            <span class="chip-text">{{ chip.label }}</span>
            <t-icon name="arrow-right" size="14px" class="chip-arrow" />
          </button>
        </div>
      </div>

      <!-- Feature cards -->
      <div class="feature-cards">
        <div
          v-for="feature in featureCards"
          :key="feature.title"
          class="feature-card"
          :class="{ 'feature-card--highlight': feature.highlight }"
          @click="handleQuickAction(feature.example)"
        >
          <div class="feature-icon">
            <t-icon :name="feature.icon" size="24px" />
          </div>
          <div class="feature-content">
            <div class="feature-title">{{ feature.title }}</div>
            <div class="feature-desc">{{ feature.desc }}</div>
          </div>
          <t-icon name="chevron-right" class="feature-arrow" />
        </div>

        <!-- Knowledge base card -->
        <div 
          class="feature-card"
          :class="{ 'feature-card--disabled': !knowledgeEnabled }"
          @click="knowledgeEnabled ? handleQuickAction('查看可用知识库') : router.push('/datamanage/knowledge')"
        >
          <div class="feature-icon" :class="{ 'feature-icon--disabled': !knowledgeEnabled }">
            <t-icon name="books" size="24px" />
          </div>
          <div class="feature-content">
            <div class="feature-title">知识库问答</div>
            <div class="feature-desc" v-if="knowledgeEnabled">引用研报公告进行深度分析</div>
            <div class="feature-desc feature-desc--guide" v-else>需部署知识库服务 · 点击前往配置</div>
          </div>
          <t-icon v-if="knowledgeEnabled" name="chevron-right" class="feature-arrow" />
          <t-icon v-else name="setting" class="feature-arrow feature-arrow--guide" />
        </div>
      </div>
      
      <!-- Quick start examples -->
      <div class="quick-start">
        <div class="quick-start-title">
          <t-icon name="lightbulb" />
          <span>试试这些问题</span>
        </div>
        <div class="quick-start-tags">
          <t-tag 
            v-for="query in exampleQueries" 
            :key="query"
            theme="primary"
            variant="outline"
            class="example-tag"
            @click="handleQuickAction(query)"
          >
            {{ query }}
          </t-tag>
        </div>
      </div>
      
      <!-- Usage tips -->
      <div class="usage-tips">
        <t-icon name="info-circle" style="color: #0052d9" />
        <span>提示：你可以直接输入股票代码（如 600519、00700.HK）或股票名称（如 贵州茅台、腾讯控股）进行分析</span>
      </div>
    </div>
    
    <!-- Message list -->
    <div
      v-for="msg in messages"
      :key="msg.id"
      :class="['message-item', msg.role]"
    >
      <div class="avatar">
        <t-avatar v-if="msg.role === 'user'" size="32px">U</t-avatar>
        <t-avatar v-else size="32px" style="background: #0052d9">AI</t-avatar>
      </div>
      <div class="message-content">
        <!-- Agent info for assistant messages -->
        <div v-if="msg.role === 'assistant' && msg.metadata?.agent" class="agent-info">
          <t-tag 
            :theme="getAgentColor(msg.metadata.agent)" 
            variant="light" 
            size="small"
          >
            {{ chatStore.getAgentDisplayName(msg.metadata.agent) }}
          </t-tag>
          <span v-if="msg.metadata?.intent" class="intent-badge">
            {{ chatStore.getIntentDisplayName(msg.metadata.intent) }}
          </span>
          <span v-if="msg.metadata.stock_codes?.length" class="stock-codes">
            <t-tag 
              v-for="code in msg.metadata.stock_codes" 
              :key="code"
              theme="default"
              variant="outline"
              size="small"
            >
              {{ code }}
            </t-tag>
          </span>
        </div>
        
        <!-- Message text with markdown rendering -->
        <div 
          v-if="msg.role === 'assistant'" 
          class="message-text markdown-body"
          v-html="renderMarkdown(msg.content)"
        ></div>
        <div v-else class="message-text">{{ msg.content }}</div>
        
        <!-- Dynamic visualization charts -->
        <div 
          v-if="msg.role === 'assistant' && getMessageVisualizations(msg.id).length > 0"
          class="message-visualizations"
        >
          <div 
            v-for="(viz, vizIdx) in getMessageVisualizations(msg.id)" 
            :key="`${msg.id}-viz-${vizIdx}`"
            class="visualization-container"
          >
            <div v-if="viz.title" class="viz-title">{{ viz.title }}</div>
            <component
              v-if="vizComponentMap[viz.type]"
              :is="vizComponentMap[viz.type]"
              v-bind="viz.props"
            />
            <div v-else class="viz-unsupported">
              <t-icon name="chart" />
              <span>不支持的图表类型: {{ viz.type }}</span>
            </div>
          </div>
        </div>

        <!-- Post-analysis action buttons (after agent analysis with signal) -->
        <PostAnalysisActions
          v-if="msg.role === 'assistant' && !loading && (msg.metadata?.signal || msg.metadata?.stock_codes?.length)"
          :signal="msg.metadata?.signal as string"
          :stock-code="msg.metadata?.stock_codes?.[0] as string"
          :confidence="msg.metadata?.confidence as number"
          @follow-up="(query: string) => emit('quickAction', query)"
        />

        <div class="message-time">
          {{ msg.timestamp }}
          <span
            v-if="msg.role === 'assistant' && msg.metadata?.debug_events"
            class="debug-btn"
            @click="chatStore.viewDebug(msg.id)"
          >
            🔍 查看调试
          </span>
        </div>
      </div>
    </div>
    
    <!-- Enhanced Thinking/Loading state with plan display -->
    <div v-if="loading" class="message-item assistant">
      <div class="avatar">
        <t-avatar size="32px" style="background: #0052d9">AI</t-avatar>
      </div>
      <div class="message-content">
        <div v-if="chatStore.thinking" class="thinking-state">
          <!-- Thinking header with animation -->
          <div class="thinking-header">
            <div class="thinking-pulse">
              <span class="pulse-dot"></span>
              <span class="pulse-dot"></span>
              <span class="pulse-dot"></span>
            </div>
            <span class="thinking-text">{{ chatStore.currentStatus || '正在分析您的需求...' }}</span>
          </div>
          
          <!-- Plan display (if available) -->
          <div v-if="chatStore.currentAgent || chatStore.currentIntent" class="thinking-plan">
            <div class="plan-step">
              <t-icon :name="getThinkingStepIcon('理解')" class="step-icon completed" />
              <div class="step-content">
                <span class="step-title">理解意图</span>
                <span v-if="chatStore.currentIntent" class="step-detail">
                  {{ chatStore.getIntentDisplayName(chatStore.currentIntent) }}
                </span>
              </div>
            </div>
            
            <div v-if="chatStore.currentAgent" class="plan-step">
              <t-icon :name="getThinkingStepIcon('选择')" class="step-icon" :class="{ active: !chatStore.currentTool }" />
              <div class="step-content">
                <span class="step-title">选择专家</span>
                <t-tag 
                  :theme="getAgentColor(chatStore.currentAgent)" 
                  variant="light" 
                  size="small"
                >
                  {{ chatStore.getAgentDisplayName(chatStore.currentAgent) }}
                </t-tag>
              </div>
            </div>
            
            <div v-if="chatStore.currentTool" class="plan-step">
              <t-icon :name="getThinkingStepIcon('执行')" class="step-icon active" />
              <div class="step-content">
                <span class="step-title">执行工具</span>
                <t-tag 
                  :theme="getToolColor(chatStore.currentTool)" 
                  variant="outline" 
                  size="small"
                >
                  🔧 {{ chatStore.getToolDisplayName(chatStore.currentTool) }}
                </t-tag>
              </div>
            </div>
          </div>
          
          <!-- Stock codes being analyzed -->
          <div v-if="chatStore.currentStockCodes.length" class="analyzing-stocks">
            <span class="analyzing-label">分析标的：</span>
            <t-tag 
              v-for="code in chatStore.currentStockCodes" 
              :key="code"
              theme="primary"
              variant="outline"
              size="small"
            >
              {{ code }}
            </t-tag>
          </div>
        </div>
        <t-loading v-else size="small" text="生成中..." />
      </div>
    </div>
  </div>
</template>

<style scoped>
.message-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Welcome State Styles */
.welcome-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px 20px;
}

.welcome-header {
  text-align: center;
  margin-bottom: 24px;
}

.welcome-title {
  font-size: 26px;
  font-weight: 700;
  color: var(--td-text-color-primary);
  margin: 0 0 8px 0;
}

.welcome-subtitle {
  font-size: 15px;
  color: var(--td-text-color-secondary);
  margin: 0;
  line-height: 1.6;
}

/* Quick-try chips (primary CTA) */
.quick-chips {
  width: 100%;
  max-width: 560px;
  margin-bottom: 28px;
}

.quick-chips-label {
  font-size: 13px;
  color: var(--td-text-color-placeholder);
  margin-bottom: 10px;
  text-align: center;
}

.quick-chips-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
}

.quick-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 18px;
  border-radius: 20px;
  border: 1px solid var(--td-brand-color);
  background: var(--td-brand-color-light);
  color: var(--td-brand-color);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.quick-chip:hover {
  background: var(--td-brand-color);
  color: white;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 82, 217, 0.25);
}

.chip-icon {
  font-size: 16px;
}

.chip-arrow {
  opacity: 0;
  margin-left: -4px;
  transition: all 0.2s;
}

.quick-chip:hover .chip-arrow {
  opacity: 1;
  margin-left: 0;
}

.quick-chip--resume {
  border-color: var(--td-success-color, #52c41a);
  background: var(--td-success-color-light, #e8f8e8);
  color: var(--td-success-color, #52c41a);
}

.quick-chip--resume:hover {
  background: var(--td-success-color, #52c41a);
  color: white;
  box-shadow: 0 4px 12px rgba(82, 196, 26, 0.25);
}

.quick-chip--resume .chip-text {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 768px) {
  .quick-chips-row {
    flex-direction: column;
    align-items: stretch;
  }
  .quick-chip {
    justify-content: center;
  }
}

/* Feature Cards */
.feature-cards {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  width: 100%;
  max-width: 600px;
  margin-bottom: 24px;
}

.feature-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.feature-card:hover {
  background: #fff;
  border-color: #0052d9;
  box-shadow: 0 4px 12px rgba(0, 82, 217, 0.1);
}

.feature-card--highlight {
  background: linear-gradient(135deg, #e8f0fe 0%, #f0e6ff 100%);
  border-color: var(--td-brand-color);
}

.feature-card--highlight .feature-icon {
  background: var(--td-brand-color);
  color: white;
}

.feature-icon {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #e8f4ff 0%, #d4e8ff 100%);
  border-radius: 10px;
  color: #0052d9;
}

.feature-content {
  flex: 1;
  min-width: 0;
}

.feature-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 2px;
}

.feature-desc {
  font-size: 12px;
  color: #888;
}

.feature-arrow {
  color: #ccc;
  transition: transform 0.2s;
}

.feature-card:hover .feature-arrow {
  color: #0052d9;
  transform: translateX(4px);
}

/* Knowledge card disabled state */
.feature-card--disabled {
  background: #f5f5f5;
  opacity: 0.75;
  border: 1px dashed #d9d9d9;
}

.feature-card--disabled:hover {
  background: #f0f0f0;
  border-color: #bbb;
  box-shadow: none;
}

.feature-icon--disabled {
  background: linear-gradient(135deg, #f0f0f0 0%, #e8e8e8 100%);
  color: #999;
}

.feature-desc--guide {
  color: #0052d9;
  font-size: 11px;
}

.feature-arrow--guide {
  color: #999;
}

.feature-card--disabled:hover .feature-arrow--guide {
  color: #666;
  transform: rotate(60deg);
}

/* Quick Start */
.quick-start {
  width: 100%;
  max-width: 600px;
  margin-bottom: 20px;
}

.quick-start-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #666;
  margin-bottom: 12px;
}

.quick-start-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.example-tag {
  cursor: pointer;
  transition: all 0.2s;
}

.example-tag:hover {
  background: #0052d9 !important;
  color: #fff !important;
}

/* Usage Tips */
.usage-tips {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #f0f7ff;
  border-radius: 8px;
  font-size: 12px;
  color: #666;
  max-width: 600px;
}

/* Message Item Styles */
.message-item {
  display: flex;
  gap: 12px;
}

.message-item.user {
  flex-direction: row-reverse;
}

.message-content {
  max-width: 80%;
}

.agent-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.intent-badge {
  font-size: 12px;
  color: #888;
  padding: 2px 8px;
  background: #f5f5f5;
  border-radius: 4px;
}

.stock-codes {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.message-text {
  padding: 12px 16px;
  border-radius: 8px;
  background: #f5f5f5;
  line-height: 1.6;
}

.message-item.user .message-text {
  background: #0052d9;
  color: #fff;
}

/* Visualization containers */
.message-visualizations {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 12px;
}

.visualization-container {
  border-radius: 8px;
  background: #fff;
  border: 1px solid #eee;
  overflow: hidden;
}

.viz-title {
  padding: 10px 16px 0;
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.viz-unsupported {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  color: #999;
  font-size: 13px;
}

/* Markdown styles */
.message-text.markdown-body {
  font-size: 14px;
}

.message-text.markdown-body :deep(h1),
.message-text.markdown-body :deep(h2),
.message-text.markdown-body :deep(h3),
.message-text.markdown-body :deep(h4) {
  margin-top: 16px;
  margin-bottom: 8px;
  font-weight: 600;
}

.message-text.markdown-body :deep(h1) { font-size: 1.5em; }
.message-text.markdown-body :deep(h2) { font-size: 1.3em; }
.message-text.markdown-body :deep(h3) { font-size: 1.1em; }
.message-text.markdown-body :deep(h4) { font-size: 1em; }

.message-text.markdown-body :deep(p) {
  margin: 8px 0;
}

.message-text.markdown-body :deep(ul),
.message-text.markdown-body :deep(ol) {
  padding-left: 20px;
  margin: 8px 0;
}

.message-text.markdown-body :deep(li) {
  margin: 4px 0;
}

.message-text.markdown-body :deep(code) {
  background: #e8e8e8;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 0.9em;
}

.message-text.markdown-body :deep(pre) {
  background: #2d2d2d;
  color: #f8f8f2;
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 8px 0;
}

.message-text.markdown-body :deep(pre code) {
  background: transparent;
  padding: 0;
  color: inherit;
}

.message-text.markdown-body :deep(blockquote) {
  border-left: 4px solid #0052d9;
  padding-left: 12px;
  margin: 8px 0;
  color: #666;
}

.message-text.markdown-body :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
}

.message-text.markdown-body :deep(th),
.message-text.markdown-body :deep(td) {
  border: 1px solid #ddd;
  padding: 8px 12px;
  text-align: left;
}

.message-text.markdown-body :deep(th) {
  background: #f5f5f5;
  font-weight: 600;
}

.message-text.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid #ddd;
  margin: 16px 0;
}

.message-text.markdown-body :deep(strong) {
  font-weight: 600;
}

.message-text.markdown-body :deep(em) {
  font-style: italic;
}

.message-time {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.debug-btn {
  font-size: 11px;
  color: var(--td-brand-color, #0052d9);
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.2s;
}

.message-item:hover .debug-btn {
  opacity: 1;
}

.debug-btn:hover {
  text-decoration: underline;
}

.message-item.user .message-time {
  text-align: right;
}

/* Enhanced Thinking State */
.thinking-state {
  padding: 16px;
  background: linear-gradient(135deg, #f8f9fa 0%, #fff 100%);
  border-radius: 12px;
  border: 1px solid #eee;
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.thinking-pulse {
  display: flex;
  gap: 4px;
}

.pulse-dot {
  width: 8px;
  height: 8px;
  background: #0052d9;
  border-radius: 50%;
  animation: pulse 1.4s ease-in-out infinite;
}

.pulse-dot:nth-child(2) { animation-delay: 0.2s; }
.pulse-dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes pulse {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}

.thinking-text {
  color: #333;
  font-size: 14px;
  font-weight: 500;
}

/* Plan Steps */
.thinking-plan {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  background: #fff;
  border-radius: 8px;
  margin-bottom: 12px;
}

.plan-step {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px dashed #eee;
}

.plan-step:last-child {
  border-bottom: none;
}

.step-icon {
  width: 24px;
  height: 24px;
  color: #ccc;
  transition: color 0.3s;
}

.step-icon.completed {
  color: #52c41a;
}

.step-icon.active {
  color: #0052d9;
  animation: iconPulse 1s ease-in-out infinite;
}

@keyframes iconPulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.1); }
}

.step-content {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.step-title {
  font-size: 13px;
  color: #666;
  min-width: 60px;
}

.step-detail {
  font-size: 12px;
  color: #999;
  padding: 2px 8px;
  background: #f5f5f5;
  border-radius: 4px;
}

/* Analyzing Stocks */
.analyzing-stocks {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.analyzing-label {
  font-size: 12px;
  color: #888;
}
</style>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'

const props = defineProps<{
  summary?: string
  disclaimer?: string
  loading?: boolean
  status?: string  // 流式分析状态
}>()

// Convert markdown summary to HTML
const renderedSummary = computed(() => {
  if (!props.summary) return ''
  try {
    // Configure marked for safe rendering
    marked.setOptions({
      breaks: true,  // Convert \n to <br>
      gfm: true,     // GitHub Flavored Markdown
    })
    return marked(props.summary) as string
  } catch (e) {
    console.error('Markdown parse error:', e)
    return props.summary
  }
})
</script>

<template>
  <div class="trend-analysis">
    <!-- Loading with status -->
    <div v-if="loading && !summary" class="loading-state">
      <t-loading size="medium" />
      <div v-if="status" class="status-text">{{ status }}</div>
    </div>
    
    <template v-else-if="summary">
      <!-- Status bar during streaming -->
      <div v-if="loading && status" class="streaming-status">
        <t-loading size="small" />
        <span>{{ status }}</span>
      </div>
      
      <!-- Summary -->
      <div class="summary-section">
        <div class="section-title">
          AI 分析报告
          <span v-if="loading" class="typing-indicator">
            <span></span><span></span><span></span>
          </span>
        </div>
        <div class="summary-text markdown-body" v-html="renderedSummary"></div>
      </div>
      
      <!-- Disclaimer -->
      <div v-if="disclaimer && !loading" class="disclaimer">
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
  padding: 12px;
  background: #fff;
  border-radius: 8px;
  height: 100%;
  overflow-y: auto;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 12px;
}

.status-text {
  color: #666;
  font-size: 13px;
}

.streaming-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #e6f7ff;
  border-radius: 4px;
  margin-bottom: 12px;
  font-size: 12px;
  color: #1890ff;
}

.summary-placeholder {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  background: #f9f9f9;
  border-radius: 4px;
  color: #666;
  font-size: 13px;
}

.typing-indicator {
  display: inline-flex;
  align-items: center;
  margin-left: 6px;
}

.typing-indicator span {
  width: 4px;
  height: 4px;
  background: #1890ff;
  border-radius: 50%;
  margin: 0 2px;
  animation: typing 1.4s infinite ease-in-out both;
}

.typing-indicator span:nth-child(1) {
  animation-delay: -0.32s;
}

.typing-indicator span:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes typing {
  0%, 80%, 100% {
    transform: scale(0);
  }
  40% {
    transform: scale(1);
  }
}

.section-title {
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
}

.summary-section {
  margin-bottom: 16px;
}

.summary-text {
  font-size: 14px;
  line-height: 1.6;
  color: #333;
  padding: 12px;
  background: #f9f9f9;
  border-radius: 4px;
}

/* Markdown content styles */
.summary-text.markdown-body {
  max-height: none;
  overflow-y: visible;
}

.summary-text.markdown-body :deep(h1),
.summary-text.markdown-body :deep(h2),
.summary-text.markdown-body :deep(h3),
.summary-text.markdown-body :deep(h4) {
  margin: 12px 0 8px 0;
  font-weight: 600;
  color: #1a1a1a;
}

.summary-text.markdown-body :deep(h1) { font-size: 18px; }
.summary-text.markdown-body :deep(h2) { font-size: 16px; }
.summary-text.markdown-body :deep(h3) { font-size: 15px; }
.summary-text.markdown-body :deep(h4) { font-size: 14px; }

.summary-text.markdown-body :deep(p) {
  margin: 8px 0;
}

.summary-text.markdown-body :deep(ul),
.summary-text.markdown-body :deep(ol) {
  margin: 8px 0;
  padding-left: 20px;
}

.summary-text.markdown-body :deep(li) {
  margin: 4px 0;
}

.summary-text.markdown-body :deep(strong) {
  font-weight: 600;
  color: #1a1a1a;
}

.summary-text.markdown-body :deep(em) {
  font-style: italic;
  color: #666;
}

.summary-text.markdown-body :deep(code) {
  background: #e8e8e8;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 13px;
}

.summary-text.markdown-body :deep(blockquote) {
  margin: 8px 0;
  padding: 8px 12px;
  border-left: 3px solid #667eea;
  background: #f0f2ff;
  color: #555;
}

.summary-text.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 13px;
}

.summary-text.markdown-body :deep(th),
.summary-text.markdown-body :deep(td) {
  border: 1px solid #e0e0e0;
  padding: 6px 10px;
  text-align: left;
}

.summary-text.markdown-body :deep(th) {
  background: #f5f5f5;
  font-weight: 600;
}

.summary-text.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid #e0e0e0;
  margin: 12px 0;
}

/* Highlight bullish/bearish keywords */
.summary-text.markdown-body :deep(strong:has(+ *:contains('看多'))),
.summary-text.markdown-body :deep(strong:contains('看多')),
.summary-text.markdown-body :deep(strong:contains('上涨')),
.summary-text.markdown-body :deep(strong:contains('买入')) {
  color: #cf1322;
}

.summary-text.markdown-body :deep(strong:contains('看空')),
.summary-text.markdown-body :deep(strong:contains('下跌')),
.summary-text.markdown-body :deep(strong:contains('卖出')) {
  color: #389e0d;
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
  height: 100%;
  color: #999;
  text-align: center;
}
</style>

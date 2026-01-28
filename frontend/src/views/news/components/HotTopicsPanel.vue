<script setup lang="ts">
import { computed } from 'vue'
import { ChartBubbleIcon, TrendingUpIcon, SearchIcon } from 'tdesign-icons-vue-next'
import type { HotTopic } from '@/types/news'

interface Props {
  hotTopics: HotTopic[]
  loading?: boolean
}

interface Emits {
  (e: 'topic-click', topic: HotTopic): void
}

const props = withDefaults(defineProps<Props>(), {
  loading: false
})

const emit = defineEmits<Emits>()

// 计算属性
const sortedTopics = computed(() => {
  return [...props.hotTopics]
    .sort((a, b) => b.heat_score - a.heat_score)
    .slice(0, 10)
})

// 获取热度等级
const getHeatLevel = (score: number) => {
  if (score >= 80) return 'hot'
  if (score >= 60) return 'warm'
  if (score >= 40) return 'normal'
  return 'cold'
}

// 获取热度颜色
const getHeatColor = (score: number) => {
  if (score >= 80) return 'var(--td-error-color)'
  if (score >= 60) return 'var(--td-warning-color)'
  if (score >= 40) return 'var(--td-brand-color)'
  return 'var(--td-text-color-secondary)'
}

// 格式化热度分数
const formatHeatScore = (score: number) => {
  return Math.round(score)
}

// 事件处理
const handleTopicClick = (topic: HotTopic) => {
  emit('topic-click', topic)
}
</script>

<template>
  <div class="hot-topics-panel">
    <t-card title="热点话题" size="small" :bordered="false" class="hot-topics-card">
      <template #actions>
        <t-button size="small" variant="text" :loading="loading">
          <template #icon>
            <TrendingUpIcon />
          </template>
          实时更新
        </t-button>
      </template>

      <div class="hot-topics-content">
        <!-- 热点话题列表 -->
        <div v-if="sortedTopics.length > 0" class="topics-list">
          <div
            v-for="(topic, index) in sortedTopics"
            :key="topic.topic"
            class="topic-item"
            :class="[`heat-${getHeatLevel(topic.heat_score)}`, { 'top-topic': index < 3 }]"
            @click="handleTopicClick(topic)"
          >
            <!-- 排名 -->
            <div class="topic-rank" :class="{ 'top-rank': index < 3 }">
              <ChartBubbleIcon v-if="index === 0" class="fire-icon" />
              <span v-else>{{ index + 1 }}</span>
            </div>

            <!-- 话题内容 -->
            <div class="topic-content">
              <div class="topic-name">
                {{ topic.topic }}
              </div>
              
              <!-- 关键词 -->
              <div class="topic-keywords" v-if="topic.keywords.length > 0">
                <t-tag
                  v-for="keyword in topic.keywords.slice(0, 3)"
                  :key="keyword"
                  size="small"
                  variant="outline"
                  class="keyword-tag"
                >
                  {{ keyword }}
                </t-tag>
                <span v-if="topic.keywords.length > 3" class="more-keywords">
                  +{{ topic.keywords.length - 3 }}
                </span>
              </div>

              <!-- 相关股票 -->
              <div class="topic-stocks" v-if="topic.related_stocks.length > 0">
              <SearchIcon size="12px" />
                <span class="stocks-text">
                  相关股票: {{ topic.related_stocks.slice(0, 2).join(', ') }}
                  <span v-if="topic.related_stocks.length > 2">
                    等{{ topic.related_stocks.length }}只
                  </span>
                </span>
              </div>
            </div>

            <!-- 热度指标 -->
            <div class="topic-metrics">
              <div class="heat-score" :style="{ color: getHeatColor(topic.heat_score) }">
                {{ formatHeatScore(topic.heat_score) }}
              </div>
              <div class="heat-label">热度</div>
              
              <div class="news-count">
                {{ topic.news_count }}
              </div>
              <div class="count-label">新闻</div>
            </div>

            <!-- 热度进度条 -->
            <div class="heat-progress">
              <t-progress
                :percentage="topic.heat_score"
                :theme="getHeatLevel(topic.heat_score) === 'hot' ? 'danger' : 
                       getHeatLevel(topic.heat_score) === 'warm' ? 'warning' : 'primary'"
                size="small"
                :show-info="false"
              />
            </div>
          </div>
        </div>

        <!-- 空状态 -->
        <div v-else-if="!loading" class="empty-topics">
          <div class="empty-topics-container">
            <div class="empty-topics-icon">
              <svg viewBox="0 0 48 48" width="56" height="56">
                <defs>
                  <linearGradient id="topicGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:#ff6b6b;stop-opacity:0.15" />
                    <stop offset="100%" style="stop-color:#ffa726;stop-opacity:0.1" />
                  </linearGradient>
                </defs>
                <circle cx="24" cy="24" r="20" fill="url(#topicGradient)" stroke="#ff6b6b" stroke-width="1"/>
                <path d="M24 12 L26 20 L34 20 L28 25 L30 34 L24 29 L18 34 L20 25 L14 20 L22 20 Z" 
                      fill="#ffa726" opacity="0.6"/>
                <circle cx="24" cy="24" r="6" fill="#ff6b6b" opacity="0.3"/>
              </svg>
            </div>
            <div class="empty-topics-text">
              <span class="empty-topics-title">暂无热点话题</span>
              <span class="empty-topics-desc">热点数据正在加载中</span>
            </div>
          </div>
        </div>

        <!-- 加载状态 -->
        <div v-if="loading" class="loading-topics">
          <t-skeleton 
            v-for="i in 5" 
            :key="i"
            theme="article"
            :row-col="[
              { width: '60%' },
              { width: '40%' }
            ]"
            style="margin-bottom: 12px;"
          />
        </div>
      </div>
    </t-card>
  </div>
</template>

<style scoped>
.hot-topics-panel {
  height: 50%;
  min-height: 300px;
}

.hot-topics-card {
  height: 100%;
  background: #ffffff;
  border: 1px solid #e8e8e8;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
}

.hot-topics-card :deep(.t-card__body) {
  flex: 1;
  padding: 8px;
  overflow: hidden;
}

.hot-topics-content {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.topics-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.topic-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px;
  border-radius: 6px;
  border: 1px solid var(--td-component-stroke);
  background: var(--td-bg-color-container);
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
}

.topic-item:hover {
  background: var(--td-bg-color-container-hover);
  border-color: var(--td-brand-color-light);
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.topic-item.top-topic {
  border-left: 3px solid var(--td-brand-color);
}

.topic-item.heat-hot {
  border-left-color: var(--td-error-color);
  background: linear-gradient(135deg, #fff5f5 0%, #ffffff 100%);
}

.topic-item.heat-warm {
  border-left-color: var(--td-warning-color);
  background: linear-gradient(135deg, #fffbf0 0%, #ffffff 100%);
}

.topic-rank {
  width: 20px;
  height: 20px;
  border-radius: 4px;
  background: var(--td-bg-color-component);
  color: var(--td-text-color-secondary);
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2px;
}

.topic-rank.top-rank {
  background: var(--td-brand-color);
  color: white;
}

.fire-icon {
  color: var(--td-error-color);
}

.topic-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.topic-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--td-text-color-primary);
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.topic-keywords {
  display: flex;
  align-items: center;
  gap: 3px;
  flex-wrap: wrap;
}

.keyword-tag {
  font-size: 10px;
  padding: 1px 4px;
  height: 16px;
  line-height: 14px;
}

.more-keywords {
  font-size: 10px;
  color: var(--td-text-color-placeholder);
}

.topic-stocks {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  color: var(--td-text-color-secondary);
}

.stocks-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topic-metrics {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
  min-width: 40px;
}

.heat-score {
  font-size: 16px;
  font-weight: 600;
  line-height: 1;
}

.heat-label,
.count-label {
  font-size: 9px;
  color: var(--td-text-color-placeholder);
  line-height: 1;
}

.news-count {
  font-size: 12px;
  font-weight: 500;
  color: var(--td-text-color-secondary);
  line-height: 1;
  margin-top: 4px;
}

.heat-progress {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 2px;
}

.heat-progress :deep(.t-progress__bar) {
  height: 2px;
  border-radius: 0 0 6px 6px;
}

.empty-topics {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.empty-topics-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 12px;
}

.empty-topics-icon {
  animation: floatSmall 2.5s ease-in-out infinite;
}

.empty-topics-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.empty-topics-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--td-text-color-primary);
}

.empty-topics-desc {
  font-size: 12px;
  color: var(--td-text-color-placeholder);
}

@keyframes floatSmall {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-5px);
  }
}

.loading-topics {
  flex: 1;
  padding: 8px 0;
}

/* 滚动条样式 */
.topics-list::-webkit-scrollbar {
  width: 4px;
}

.topics-list::-webkit-scrollbar-track {
  background: transparent;
}

.topics-list::-webkit-scrollbar-thumb {
  background: var(--td-bg-color-component-hover);
  border-radius: 2px;
}

.topics-list::-webkit-scrollbar-thumb:hover {
  background: var(--td-bg-color-component-active);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .hot-topics-panel {
    height: auto;
    min-height: 200px;
  }
  
  .topic-item {
    padding: 6px;
    gap: 6px;
  }
  
  .topic-name {
    font-size: 12px;
    -webkit-line-clamp: 1;
  }
  
  .topic-metrics {
    min-width: 35px;
  }
  
  .heat-score {
    font-size: 14px;
  }
}
</style>
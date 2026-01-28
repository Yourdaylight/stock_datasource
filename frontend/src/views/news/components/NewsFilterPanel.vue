<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import type { NewsFilters } from '@/types/news'

interface Props {
  filters: NewsFilters
  availableCategories: string[]
  availableSources: string[]
  loading?: boolean
}

interface Emits {
  (e: 'update:filters', filters: NewsFilters): void
  (e: 'filter-change', filters: NewsFilters): void
}

const props = withDefaults(defineProps<Props>(), {
  loading: false
})

const emit = defineEmits<Emits>()

// 防止初始化时触发 watch
const isInitialized = ref(false)

// 本地筛选状态
const localFilters = ref<NewsFilters>({ ...props.filters })

// 股票代码输入
const stockCodeInput = ref('')

// 预设的新闻类型选项
const categoryOptions = [
  { label: '公告', value: 'announcement' },
  { label: '快讯', value: 'news' },
  { label: '分析', value: 'analysis' },
  { label: '研报', value: 'research' }
]

// 情绪选项
const sentimentOptions = [
  { label: '利好', value: 'positive' },
  { label: '利空', value: 'negative' },
  { label: '中性', value: 'neutral' }
]

// 时间范围预设选项
const dateRangePresets = [
  { label: '今天', value: 0 },
  { label: '最近3天', value: 3 },
  { label: '最近7天', value: 7 },
  { label: '最近30天', value: 30 }
]

// 计算属性
const availableCategoryOptions = computed(() => {
  return categoryOptions.filter(option => 
    props.availableCategories.length === 0 || 
    props.availableCategories.includes(option.value)
  )
})

const availableSourceOptions = computed(() => {
  return props.availableSources.map(source => ({
    label: source,
    value: source
  }))
})

// 监听props变化
watch(() => props.filters, (newFilters) => {
  localFilters.value = { ...newFilters }
}, { deep: true })

// 添加股票代码
const addStockCode = () => {
  const code = stockCodeInput.value.trim().toUpperCase()
  if (code && !localFilters.value.stock_codes.includes(code)) {
    localFilters.value.stock_codes.push(code)
    stockCodeInput.value = ''
    applyFilters()
  }
}

// 移除股票代码
const removeStockCode = (code: string) => {
  const index = localFilters.value.stock_codes.indexOf(code)
  if (index > -1) {
    localFilters.value.stock_codes.splice(index, 1)
    applyFilters()
  }
}

// 设置时间范围预设
const setDateRangePreset = (days: number) => {
  const endDate = new Date()
  const startDate = new Date()
  startDate.setDate(endDate.getDate() - days)
  
  localFilters.value.date_range = [
    startDate.toISOString().split('T')[0],
    endDate.toISOString().split('T')[0]
  ]
  applyFilters()
}

// 应用筛选条件
const applyFilters = () => {
  emit('update:filters', { ...localFilters.value })
  emit('filter-change', { ...localFilters.value })
}

// 重置筛选条件
const resetFilters = () => {
  localFilters.value = {
    stock_codes: [],
    date_range: ['', ''],
    categories: [],
    sentiments: [],
    sources: [],
    keywords: ''
  }
  stockCodeInput.value = ''
  applyFilters()
}

// 监听筛选条件变化（只在初始化后才触发）
watch(localFilters, () => {
  if (isInitialized.value) {
    applyFilters()
  }
}, { deep: true })

// 组件挂载后标记为已初始化
onMounted(() => {
  // 延迟设置，避免首次渲染时触发
  setTimeout(() => {
    isInitialized.value = true
  }, 0)
})
</script>

<template>
  <div class="news-filter-panel">
    <t-card title="筛选条件" size="small" :bordered="false" class="filter-card">
      <template #actions>
        <t-button 
          size="small" 
          variant="text" 
          @click="resetFilters"
          :disabled="loading"
        >
          重置
        </t-button>
      </template>

      <div class="filter-content">
        <!-- 股票代码筛选 -->
        <div class="filter-section">
          <div class="filter-label">股票代码</div>
          <div class="stock-input-group">
            <t-input
              v-model="stockCodeInput"
              placeholder="输入股票代码"
              size="small"
              @enter="addStockCode"
              :disabled="loading"
            >
              <template #suffix>
                <t-button 
                  size="small" 
                  variant="text"
                  @click="addStockCode"
                  :disabled="!stockCodeInput.trim() || loading"
                >
                  添加
                </t-button>
              </template>
            </t-input>
          </div>
          <div class="stock-tags" v-if="localFilters.stock_codes.length > 0">
            <t-tag
              v-for="code in localFilters.stock_codes"
              :key="code"
              size="small"
              closable
              @close="removeStockCode(code)"
              :disabled="loading"
            >
              {{ code }}
            </t-tag>
          </div>
        </div>

        <!-- 时间范围筛选 -->
        <div class="filter-section">
          <div class="filter-label">时间范围</div>
          <div class="date-presets">
            <t-button
              v-for="preset in dateRangePresets"
              :key="preset.value"
              size="small"
              variant="outline"
              @click="setDateRangePreset(preset.value)"
              :disabled="loading"
            >
              {{ preset.label }}
            </t-button>
          </div>
          <t-date-range-picker
            v-model="localFilters.date_range"
            format="YYYY-MM-DD"
            size="small"
            placeholder="选择日期范围"
            :disabled="loading"
            style="margin-top: 8px;"
          />
        </div>

        <!-- 新闻类型筛选 -->
        <div class="filter-section">
          <div class="filter-label">新闻类型</div>
          <t-checkbox-group 
            v-model="localFilters.categories"
            :disabled="loading"
          >
            <t-checkbox
              v-for="option in availableCategoryOptions"
              :key="option.value"
              :value="option.value"
              size="small"
            >
              {{ option.label }}
            </t-checkbox>
          </t-checkbox-group>
        </div>

        <!-- 情绪倾向筛选 -->
        <div class="filter-section">
          <div class="filter-label">情绪倾向</div>
          <t-checkbox-group 
            v-model="localFilters.sentiments"
            :disabled="loading"
          >
            <t-checkbox
              v-for="option in sentimentOptions"
              :key="option.value"
              :value="option.value"
              size="small"
            >
              <span :class="`sentiment-${option.value}`">
                {{ option.label }}
              </span>
            </t-checkbox>
          </t-checkbox-group>
        </div>

        <!-- 新闻来源筛选 -->
        <div class="filter-section" v-if="availableSourceOptions.length > 0">
          <div class="filter-label">新闻来源</div>
          <t-select
            v-model="localFilters.sources"
            :options="availableSourceOptions"
            placeholder="选择新闻来源"
            multiple
            size="small"
            :disabled="loading"
            filterable
          />
        </div>

        <!-- 关键词搜索 -->
        <div class="filter-section">
          <div class="filter-label">关键词</div>
          <t-input
            v-model="localFilters.keywords"
            placeholder="输入关键词搜索"
            size="small"
            :disabled="loading"
            clearable
          />
        </div>
      </div>
    </t-card>

    <!-- 快速筛选 -->
    <t-card title="快速筛选" size="small" :bordered="false" class="filter-card quick-filter">
      <div class="quick-filter-content">
        <t-button
          size="small"
          variant="outline"
          @click="() => applyFilters()"
          :disabled="loading"
        >
          全部新闻
        </t-button>
        <t-button
          size="small"
          variant="outline"
          @click="() => { localFilters.sentiments = ['positive']; applyFilters() }"
          :disabled="loading"
        >
          利好消息
        </t-button>
        <t-button
          size="small"
          variant="outline"
          @click="() => { localFilters.sentiments = ['negative']; applyFilters() }"
          :disabled="loading"
        >
          利空消息
        </t-button>
        <t-button
          size="small"
          variant="outline"
          @click="() => { localFilters.categories = ['announcement']; applyFilters() }"
          :disabled="loading"
        >
          公司公告
        </t-button>
      </div>
    </t-card>
  </div>
</template>

<style scoped>
.news-filter-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
}

.filter-card {
  background: #ffffff;
  border: 1px solid #e8e8e8;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.filter-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.filter-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.filter-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--td-text-color-primary);
}

.stock-input-group {
  width: 100%;
}

.stock-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}

.date-presets {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
}

.sentiment-positive {
  color: var(--td-success-color);
}

.sentiment-negative {
  color: var(--td-error-color);
}

.sentiment-neutral {
  color: var(--td-text-color-secondary);
}

.quick-filter {
  flex-shrink: 0;
}

.quick-filter-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.quick-filter-content .t-button {
  justify-content: flex-start;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .news-filter-panel {
    gap: 8px;
  }
  
  .date-presets {
    grid-template-columns: 1fr 1fr 1fr 1fr;
  }
  
  .quick-filter-content {
    flex-direction: row;
    flex-wrap: wrap;
  }
}
</style>
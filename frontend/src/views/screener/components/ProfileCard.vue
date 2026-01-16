<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useScreenerStore } from '@/stores/screener'
import type { StockProfile, ProfileDimension } from '@/api/screener'

const props = defineProps<{
  tsCode: string
  visible: boolean
}>()

const emit = defineEmits(['update:visible', 'close'])

const screenerStore = useScreenerStore()

const profile = ref<StockProfile | null>(null)
const loading = ref(false)

// 雷达图数据
const radarData = computed(() => {
  if (!profile.value) return []
  return profile.value.dimensions.map(d => ({
    name: d.name,
    score: d.score,
  }))
})

// 评分等级颜色
const scoreColor = (score: number) => {
  if (score >= 80) return '#52c41a'
  if (score >= 60) return '#1890ff'
  if (score >= 40) return '#faad14'
  return '#ff4d4f'
}

// 获取等级标签颜色
const levelTheme = (level: string) => {
  switch (level) {
    case '优秀': return 'success'
    case '良好': return 'primary'
    case '中等': return 'warning'
    case '较差': return 'danger'
    default: return 'default'
  }
}

// 加载画像数据
const loadProfile = async () => {
  if (!props.tsCode) return
  
  loading.value = true
  try {
    const result = await screenerStore.fetchProfile(props.tsCode)
    profile.value = result
  } catch (e) {
    console.error('Failed to load profile:', e)
  } finally {
    loading.value = false
  }
}

// 监听 visible 变化
watch(() => props.visible, (val) => {
  if (val && props.tsCode) {
    loadProfile()
  }
})

// 监听 tsCode 变化
watch(() => props.tsCode, (val) => {
  if (val && props.visible) {
    loadProfile()
  }
})

const handleClose = () => {
  emit('update:visible', false)
  emit('close')
}
</script>

<template>
  <t-drawer
    :visible="visible"
    header="股票十维画像"
    :footer="false"
    size="large"
    @close="handleClose"
  >
    <t-loading :loading="loading" text="加载中...">
      <div v-if="profile" class="profile-container">
        <!-- 基本信息 -->
        <div class="profile-header">
          <div class="stock-info">
            <h2>{{ profile.stock_name }}</h2>
            <span class="stock-code">{{ profile.ts_code }}</span>
          </div>
          <div class="total-score">
            <div class="score-value" :style="{ color: scoreColor(profile.total_score) }">
              {{ profile.total_score.toFixed(1) }}
            </div>
            <div class="score-label">综合评分</div>
          </div>
        </div>
        
        <!-- 维度评分列表 -->
        <t-divider>十维评分</t-divider>
        
        <div class="dimensions-grid">
          <div 
            v-for="dim in profile.dimensions" 
            :key="dim.name"
            class="dimension-item"
          >
            <div class="dimension-header">
              <span class="dimension-name">{{ dim.name }}</span>
              <t-tag :theme="levelTheme(dim.level)" size="small">{{ dim.level }}</t-tag>
            </div>
            <t-progress
              :percentage="dim.score"
              :color="scoreColor(dim.score)"
              :stroke-width="8"
            />
            <div class="dimension-score">{{ dim.score.toFixed(1) }} 分</div>
          </div>
        </div>
        
        <!-- 投资建议 -->
        <t-divider>投资建议</t-divider>
        
        <t-alert theme="info" :message="profile.recommendation" />
        
        <!-- 数据日期 -->
        <div class="data-date">
          数据日期: {{ profile.trade_date }}
        </div>
      </div>
      
      <t-empty v-else description="暂无画像数据" />
    </t-loading>
  </t-drawer>
</template>

<style scoped>
.profile-container {
  padding: 0 16px;
}

.profile-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 0;
}

.stock-info h2 {
  margin: 0 0 4px 0;
  font-size: 24px;
}

.stock-code {
  color: var(--td-text-color-secondary);
  font-size: 14px;
}

.total-score {
  text-align: center;
}

.score-value {
  font-size: 48px;
  font-weight: bold;
  line-height: 1;
}

.score-label {
  color: var(--td-text-color-secondary);
  font-size: 12px;
  margin-top: 4px;
}

.dimensions-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.dimension-item {
  background: var(--td-bg-color-container);
  border-radius: 8px;
  padding: 12px;
}

.dimension-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.dimension-name {
  font-weight: 500;
}

.dimension-score {
  text-align: right;
  font-size: 12px;
  color: var(--td-text-color-secondary);
  margin-top: 4px;
}

.data-date {
  text-align: center;
  color: var(--td-text-color-placeholder);
  font-size: 12px;
  margin-top: 24px;
  padding-bottom: 16px;
}
</style>

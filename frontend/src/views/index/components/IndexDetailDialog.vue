<script setup lang="ts">
import { ref, watch } from 'vue'
import { useIndexStore } from '@/stores/index'

const props = defineProps<{
  visible: boolean
  indexCode: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'close'): void
  (e: 'analyze', row: any): void
}>()

const indexStore = useIndexStore()
const activeTab = ref('info')

// Constituent table columns
const constituentColumns = [
  { colKey: 'con_code', title: '成分股代码', width: 120 },
  { colKey: 'weight', title: '权重 (%)', width: 100 },
]

// Watch for index code changes
watch(() => props.indexCode, async (newCode) => {
  if (newCode) {
    await Promise.all([
      indexStore.fetchIndexDetail(newCode),
      indexStore.fetchConstituents(newCode),
    ])
  }
}, { immediate: true })

const handleClose = () => {
  emit('update:visible', false)
  emit('close')
}

const handleAnalyze = () => {
  if (indexStore.currentIndex) {
    emit('analyze', indexStore.currentIndex)
    handleClose()
  }
}

// Format weight
const formatWeight = (weight: number | undefined) => {
  if (weight === undefined || weight === null) return '-'
  return weight.toFixed(4)
}
</script>

<template>
  <t-dialog
    :visible="visible"
    :header="`${indexStore.currentIndex?.name || indexCode} 详情`"
    width="800px"
    :footer="false"
    @close="handleClose"
  >
    <t-loading :loading="indexStore.detailLoading">
      <t-tabs v-model="activeTab">
        <!-- Basic Info Tab -->
        <t-tab-panel value="info" label="基础信息">
          <div class="info-grid" v-if="indexStore.currentIndex">
            <div class="info-item">
              <span class="info-label">指数代码</span>
              <span class="info-value">{{ indexStore.currentIndex.ts_code }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">指数名称</span>
              <span class="info-value">{{ indexStore.currentIndex.name }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">全称</span>
              <span class="info-value">{{ indexStore.currentIndex.fullname || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">市场</span>
              <span class="info-value">{{ indexStore.currentIndex.market || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">发布方</span>
              <span class="info-value">{{ indexStore.currentIndex.publisher || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">指数类型</span>
              <span class="info-value">{{ indexStore.currentIndex.index_type || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">类别</span>
              <span class="info-value">{{ indexStore.currentIndex.category || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">加权方式</span>
              <span class="info-value">{{ indexStore.currentIndex.weight_rule || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">基期</span>
              <span class="info-value">{{ indexStore.currentIndex.base_date || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">基点</span>
              <span class="info-value">{{ indexStore.currentIndex.base_point || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">发布日期</span>
              <span class="info-value">{{ indexStore.currentIndex.list_date || '-' }}</span>
            </div>
            <div class="info-item full-width">
              <span class="info-label">描述</span>
              <span class="info-value desc">{{ indexStore.currentIndex.desc || '-' }}</span>
            </div>
          </div>
        </t-tab-panel>
        
        <!-- Constituents Tab -->
        <t-tab-panel value="constituents" label="成分股">
          <div class="constituents-header" v-if="indexStore.constituents">
            <t-space>
              <t-tag theme="primary">成分股数量: {{ indexStore.constituents.constituent_count }}</t-tag>
              <t-tag theme="success">总权重: {{ indexStore.constituents.total_weight?.toFixed(2) }}%</t-tag>
              <t-tag>数据日期: {{ indexStore.constituents.trade_date || '-' }}</t-tag>
            </t-space>
          </div>
          
          <t-table
            :data="indexStore.constituents?.constituents || []"
            :columns="constituentColumns"
            row-key="con_code"
            max-height="400px"
            style="margin-top: 16px"
          >
            <template #weight="{ row }">
              {{ formatWeight(row.weight) }}
            </template>
          </t-table>
        </t-tab-panel>
      </t-tabs>
      
      <div class="dialog-footer">
        <t-button theme="primary" @click="handleAnalyze">
          量化分析
        </t-button>
        <t-button variant="outline" @click="handleClose">
          关闭
        </t-button>
      </div>
    </t-loading>
  </t-dialog>
</template>

<style scoped>
.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-item.full-width {
  grid-column: span 2;
}

.info-label {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.info-value {
  font-size: 14px;
  color: var(--td-text-color-primary);
}

.info-value.desc {
  line-height: 1.6;
}

.constituents-header {
  margin-bottom: 8px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--td-component-stroke);
}
</style>

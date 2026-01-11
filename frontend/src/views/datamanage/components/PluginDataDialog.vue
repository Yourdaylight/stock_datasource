<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useDataManageStore } from '@/stores/datamanage'

const props = defineProps<{
  visible: boolean
  pluginName: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

const dataStore = useDataManageStore()
const filterDate = ref<string>('')
const currentPage = ref(1)
const pageSize = ref(100)

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

watch(() => props.visible, (val) => {
  if (val && props.pluginName) {
    currentPage.value = 1
    filterDate.value = ''
    loadData()
  }
})

const loadData = () => {
  dataStore.fetchPluginData(
    props.pluginName, 
    filterDate.value || undefined, 
    currentPage.value, 
    pageSize.value
  )
}

const handleSearch = () => {
  currentPage.value = 1
  loadData()
}

const handlePageChange = (page: number) => {
  currentPage.value = page
  loadData()
}

const preview = computed(() => dataStore.currentPluginData)

const tableColumns = computed(() => {
  if (!preview.value?.columns) return []
  return preview.value.columns.map(col => ({
    colKey: col,
    title: col,
    width: col.length > 10 ? 150 : 120,
    ellipsis: true
  }))
})
</script>

<template>
  <t-dialog
    v-model:visible="dialogVisible"
    :header="`数据预览 - ${pluginName}`"
    width="90%"
    :footer="false"
  >
    <div class="data-preview">
      <div class="filter-bar">
        <t-input
          v-model="filterDate"
          placeholder="按日期筛选 (YYYY-MM-DD)"
          style="width: 200px"
          clearable
          @clear="handleSearch"
        />
        <t-button theme="primary" @click="handleSearch">查询</t-button>
        <span v-if="preview" class="total-info">
          共 {{ preview.total_count.toLocaleString() }} 条记录
        </span>
      </div>

      <t-loading :loading="dataStore.dataLoading">
        <t-table
          v-if="preview"
          :data="preview.data"
          :columns="tableColumns"
          row-key="ts_code"
          size="small"
          bordered
          max-height="500"
          :pagination="{
            current: currentPage,
            pageSize: pageSize,
            total: preview.total_count,
            showJumper: true,
            onChange: handlePageChange
          }"
        />
        <t-empty v-else-if="!dataStore.dataLoading" description="暂无数据" />
      </t-loading>
    </div>
  </t-dialog>
</template>

<style scoped>
.data-preview {
  min-height: 300px;
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.total-info {
  color: var(--td-text-color-secondary);
  font-size: 14px;
}
</style>

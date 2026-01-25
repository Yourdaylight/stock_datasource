<template>
  <div class="data-explorer">
    <!-- 左侧：表列表 -->
    <div class="table-list-panel">
      <div class="panel-header">
        <h3>数据表</h3>
        <t-input
          v-model="tableSearchKeyword"
          placeholder="搜索表名..."
          clearable
          size="small"
        >
          <template #prefix-icon>
            <t-icon name="search" />
          </template>
        </t-input>
      </div>
      
      <!-- 分类筛选 -->
      <div class="category-filter">
        <t-radio-group v-model="selectedCategory" variant="default-filled" size="small">
          <t-radio-button value="">全部</t-radio-button>
          <t-radio-button 
            v-for="cat in categories" 
            :key="cat.key" 
            :value="cat.key"
          >
            {{ cat.label }}
          </t-radio-button>
        </t-radio-group>
      </div>
      
      <!-- 表列表 -->
      <div class="table-list" v-loading="loadingTables">
        <div 
          v-for="table in filteredTables" 
          :key="table.table_name"
          :class="['table-item', { active: selectedTable?.table_name === table.table_name, 'no-data': !table.row_count }]"
          @click="selectTable(table)"
        >
          <div class="table-name">
            <t-icon name="table" class="table-icon" />
            {{ table.table_name }}
          </div>
          <div class="table-meta">
            <span class="row-count" v-if="table.row_count">
              {{ formatNumber(table.row_count) }} 行
            </span>
            <t-tag v-else size="small" theme="warning" variant="light">暂无数据</t-tag>
            <t-tag size="small" variant="light">{{ getCategoryLabel(table.category) }}</t-tag>
          </div>
          <div class="table-desc" v-if="table.description">{{ table.description }}</div>
          <!-- 数据同步按钮 -->
          <div class="table-actions" v-if="!table.row_count" @click.stop>
            <t-button 
              size="small" 
              theme="primary" 
              variant="text"
              :loading="syncingPlugins.has(table.plugin_name)"
              @click="triggerDataSync(table)"
            >
              <template #icon><t-icon name="refresh" /></template>
              获取数据
            </t-button>
          </div>
        </div>
        
        <t-empty v-if="!loadingTables && filteredTables.length === 0" description="没有找到匹配的表" />
      </div>
    </div>
    
    <!-- 右侧：查询区域 -->
    <div class="query-panel">
      <!-- 模式切换 -->
      <t-tabs v-model="queryMode" class="mode-tabs">
        <t-tab-panel value="simple" label="简单筛选">
          <template #label>
            <t-icon name="filter" /> 简单筛选
          </template>
        </t-tab-panel>
        <t-tab-panel value="sql" label="SQL 查询">
          <template #label>
            <t-icon name="code" /> SQL 查询
          </template>
        </t-tab-panel>
      </t-tabs>
      
      <!-- 简单筛选模式 -->
      <div v-if="queryMode === 'simple'" class="simple-filter-section">
        <div class="filter-form" v-if="selectedTable">
          <t-form :label-width="80" layout="inline">
            <t-form-item label="日期范围">
              <t-date-range-picker 
                v-model="dateRange" 
                allow-input
                clearable
                :presets="datePresets"
              />
            </t-form-item>
            <t-form-item label="代码筛选">
              <t-input 
                v-model="codeFilter" 
                placeholder="输入代码（支持模糊匹配）"
                clearable
                style="width: 200px"
              />
            </t-form-item>
            <t-form-item label="排序">
              <t-select v-model="sortColumn" placeholder="选择排序列" clearable style="width: 150px">
                <t-option 
                  v-for="col in selectedTable.columns" 
                  :key="col.name" 
                  :value="col.name" 
                  :label="col.comment || col.name"
                />
              </t-select>
              <t-select v-model="sortOrder" style="width: 100px; margin-left: 8px">
                <t-option value="DESC" label="降序" />
                <t-option value="ASC" label="升序" />
              </t-select>
            </t-form-item>
            <t-form-item>
              <t-button theme="primary" @click="executeSimpleQuery" :loading="queryLoading">
                <template #icon><t-icon name="play" /></template>
                查询
              </t-button>
            </t-form-item>
          </t-form>
        </div>
        <t-empty v-else description="请先选择一个表" />
      </div>
      
      <!-- SQL 查询模式 -->
      <div v-else class="sql-editor-section">
        <SqlEditorTabs
          ref="sqlEditorRef"
          v-model:tabs="sqlTabs"
          v-model:activeTab="activeTabId"
          :tables="tables"
          @execute="handleSqlExecute"
        />
      </div>
      
      <!-- 查询结果 -->
      <div class="result-section" v-if="queryResult || queryLoading">
        <div class="result-header">
          <div class="result-info">
            <span v-if="queryResult">
              查询结果：{{ queryResult.row_count }} 行
              <template v-if="queryResult.total_count"> / 共 {{ formatNumber(queryResult.total_count) }} 行</template>
              <span class="execution-time">（耗时 {{ queryResult.execution_time_ms }} ms）</span>
            </span>
            <t-tag v-if="queryResult?.truncated" theme="warning" size="small">
              结果已截断
            </t-tag>
          </div>
          <div class="result-actions">
            <t-button variant="outline" size="small" @click="exportResult('csv')" :disabled="!queryResult || queryResult.row_count === 0">
              <template #icon><t-icon name="download" /></template>
              导出 CSV
            </t-button>
            <t-button variant="outline" size="small" @click="exportResult('xlsx')" :disabled="!queryResult || queryResult.row_count === 0">
              <template #icon><t-icon name="file-excel" /></template>
              导出 Excel
            </t-button>
          </div>
        </div>
        
        <!-- 表不存在提示 -->
        <div v-if="queryResult?.table_not_exists && selectedTable" class="empty-data-hint">
          <t-alert theme="warning">
            <template #message>
              <span>表 <code>{{ selectedTable.table_name }}</code> 尚未创建，需要先同步数据以自动创建表</span>
            </template>
            <template #operation>
              <t-button 
                theme="primary" 
                size="small"
                :loading="syncingPlugins.has(selectedTable.plugin_name)"
                @click="triggerDataSync(selectedTable)"
              >
                <template #icon><t-icon name="refresh" /></template>
                创建表并同步数据
              </t-button>
            </template>
          </t-alert>
        </div>
        
        <!-- 空数据提示与同步按钮 -->
        <div v-else-if="queryResult && queryResult.row_count === 0 && selectedTable" class="empty-data-hint">
          <t-alert theme="warning" :message="`表 ${selectedTable.table_name} 暂无数据`">
            <template #operation>
              <t-button 
                theme="primary" 
                size="small"
                :loading="syncingPlugins.has(selectedTable.plugin_name)"
                @click="triggerDataSync(selectedTable)"
              >
                <template #icon><t-icon name="refresh" /></template>
                立即同步数据
              </t-button>
            </template>
          </t-alert>
        </div>
        
        <!-- 同步失败错误提示 -->
        <div v-if="syncError && selectedTable?.plugin_name === syncError.pluginName" class="sync-error-hint">
          <t-alert theme="error" title="数据同步失败" close @close="syncError = null">
            <template #message>
              <div class="error-message-content">
                <pre class="error-pre">{{ syncError.errorMessage }}</pre>
              </div>
            </template>
            <template #operation>
              <t-button theme="primary" size="small" @click="triggerDataSync(selectedTable!)">
                <template #icon><t-icon name="refresh" /></template>
                重试同步
              </t-button>
            </template>
          </t-alert>
        </div>
        
        <div class="result-table-wrapper" v-if="!queryResult || (!queryResult.table_not_exists && queryResult.row_count > 0)">
          <t-table
            :data="queryResult?.data || []"
            :columns="resultColumns"
            :loading="queryLoading"
            :pagination="pagination"
            stripe
            hover
            size="small"
            table-layout="auto"
            @page-change="handlePageChange"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { datamanageApi, type ExplorerTableInfo, type ExplorerSqlExecuteResponse, type SyncTask } from '@/api/datamanage'
import SqlEditorTabs from './components/SqlEditorTabs.vue'

// Tab data structure
interface SqlTab {
  id: string
  title: string
  sql: string
  result?: ExplorerSqlExecuteResponse
}

// State
const loadingTables = ref(false)
const queryLoading = ref(false)
const tables = ref<ExplorerTableInfo[]>([])
const categories = ref<{ key: string; label: string }[]>([])
const syncingPlugins = ref<Set<string>>(new Set())
const syncError = ref<{ pluginName: string; errorMessage: string } | null>(null)
const selectedTable = ref<ExplorerTableInfo | null>(null)
const selectedCategory = ref('')
const tableSearchKeyword = ref('')
const queryMode = ref<'simple' | 'sql'>('simple')

// Simple filter state
const dateRange = ref<string[]>([])
const codeFilter = ref('')
const sortColumn = ref('')
const sortOrder = ref<'ASC' | 'DESC'>('DESC')

// SQL editor state
const sqlTabs = ref<SqlTab[]>([
  { id: 'tab_1', title: '查询 1', sql: '' }
])
const activeTabId = ref('tab_1')
const sqlEditorRef = ref()

// Query result
const queryResult = ref<ExplorerSqlExecuteResponse | null>(null)
const currentPage = ref(1)
const pageSize = ref(100)
const lastExecutedSql = ref('')

// Date presets
const datePresets = {
  '最近7天': [new Date(Date.now() - 7 * 24 * 3600 * 1000), new Date()],
  '最近30天': [new Date(Date.now() - 30 * 24 * 3600 * 1000), new Date()],
  '最近90天': [new Date(Date.now() - 90 * 24 * 3600 * 1000), new Date()],
  '今年': [new Date(new Date().getFullYear(), 0, 1), new Date()]
}

// Computed
const filteredTables = computed(() => {
  let result = tables.value
  
  // Filter by category
  if (selectedCategory.value) {
    result = result.filter(t => t.category === selectedCategory.value)
  }
  
  // Filter by search keyword
  if (tableSearchKeyword.value) {
    const keyword = tableSearchKeyword.value.toLowerCase()
    result = result.filter(t => 
      t.table_name.toLowerCase().includes(keyword) ||
      t.description?.toLowerCase().includes(keyword) ||
      t.plugin_name.toLowerCase().includes(keyword)
    )
  }
  
  return result
})

const resultColumns = computed(() => {
  if (!queryResult.value?.columns) return []
  return queryResult.value.columns.map(col => ({
    colKey: col,
    title: col,
    ellipsis: true,
    width: 150
  }))
})

const pagination = computed(() => ({
  current: currentPage.value,
  pageSize: pageSize.value,
  total: queryResult.value?.total_count || queryResult.value?.row_count || 0,
  showPageSize: true,
  pageSizeOptions: [50, 100, 200, 500]
}))

// Methods
const loadTables = async () => {
  loadingTables.value = true
  try {
    const response = await datamanageApi.getExplorerTables()
    tables.value = response.tables
    categories.value = response.categories
    
    // Auto select first table with data and load it
    if (response.tables.length > 0 && !selectedTable.value) {
      // Prefer a table with row_count > 0
      const tableWithData = response.tables.find(t => t.row_count && t.row_count > 0)
      selectTable(tableWithData || response.tables[0])
    }
  } catch (error: any) {
    MessagePlugin.error(error.message || '加载表列表失败')
  } finally {
    loadingTables.value = false
  }
}

const selectTable = (table: ExplorerTableInfo) => {
  selectedTable.value = table
  // Reset filters when selecting a new table
  dateRange.value = []
  codeFilter.value = ''
  sortColumn.value = ''
  queryResult.value = null
  // Auto load data when selecting a table
  executeSimpleQuery()
}

const executeSimpleQuery = async () => {
  if (!selectedTable.value) return
  
  queryLoading.value = true
  queryResult.value = null
  
  try {
    const filters: Record<string, any> = {}
    
    if (dateRange.value?.length === 2) {
      filters.start_date = dateRange.value[0]
      filters.end_date = dateRange.value[1]
    }
    
    if (codeFilter.value) {
      filters.code_pattern = codeFilter.value
    }
    
    const response = await datamanageApi.queryExplorerTable(selectedTable.value.table_name, {
      filters,
      sort_by: sortColumn.value || undefined,
      sort_order: sortOrder.value,
      page: currentPage.value,
      page_size: pageSize.value
    })
    
    queryResult.value = response
  } catch (error: any) {
    // Provide friendly error message
    const errMsg = error.message || '查询失败'
    if (errMsg.includes('RetryError') || errMsg.includes('ServerException')) {
      // Return empty result for database errors
      queryResult.value = {
        columns: [],
        data: [],
        row_count: 0,
        total_count: 0,
        execution_time_ms: 0,
        truncated: false,
        table_not_exists: true
      }
    } else {
      MessagePlugin.error(errMsg)
    }
  } finally {
    queryLoading.value = false
  }
}

const handleSqlExecute = async (sql: string, tabId: string) => {
  queryLoading.value = true
  queryResult.value = null
  lastExecutedSql.value = sql
  
  try {
    const response = await datamanageApi.executeExplorerSql({
      sql,
      max_rows: pageSize.value,
      timeout: 30
    })
    
    queryResult.value = response
    
    // Update tab with result
    const tab = sqlTabs.value.find(t => t.id === tabId)
    if (tab) {
      tab.result = response
    }
  } catch (error: any) {
    MessagePlugin.error(error.message || 'SQL 执行失败')
  } finally {
    queryLoading.value = false
  }
}

const handlePageChange = (pageInfo: { current: number; pageSize: number }) => {
  currentPage.value = pageInfo.current
  pageSize.value = pageInfo.pageSize
  
  if (queryMode.value === 'simple') {
    executeSimpleQuery()
  }
}

const exportResult = async (format: 'csv' | 'xlsx') => {
  if (!queryResult.value) return
  
  // Get the SQL that was executed
  let sql = lastExecutedSql.value
  if (!sql && selectedTable.value) {
    // Build SQL from simple query
    sql = `SELECT * FROM ${selectedTable.value.table_name}`
  }
  
  if (!sql) {
    MessagePlugin.warning('没有可导出的查询')
    return
  }
  
  try {
    const blob = await datamanageApi.exportExplorerSql(sql, format)
    
    // Download file
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `query_result_${new Date().toISOString().slice(0, 10)}.${format}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
    
    MessagePlugin.success('导出成功')
  } catch (error: any) {
    MessagePlugin.error(error.message || '导出失败')
  }
}

const formatNumber = (num?: number | null) => {
  if (num === null || num === undefined) return '-'
  return num.toLocaleString()
}

const getCategoryLabel = (key: string) => {
  const cat = categories.value.find(c => c.key === key)
  return cat?.label || key
}

// Data sync methods
const triggerDataSync = async (table: ExplorerTableInfo) => {
  const pluginName = table.plugin_name
  
  if (syncingPlugins.value.has(pluginName)) {
    return
  }
  
  syncingPlugins.value.add(pluginName)
  
  try {
    const task = await datamanageApi.triggerSync({
      plugin_name: pluginName,
      task_type: 'incremental'
    })
    
    MessagePlugin.success(`已启动 ${pluginName} 数据同步任务`)
    
    // Poll for task completion
    pollSyncTask(task.task_id, table)
  } catch (error: any) {
    MessagePlugin.error(error.message || '启动同步任务失败')
    syncingPlugins.value.delete(pluginName)
  }
}

const pollSyncTask = async (taskId: string, table: ExplorerTableInfo) => {
  const pluginName = table.plugin_name
  let attempts = 0
  const maxAttempts = 120 // 2 minutes max
  
  const poll = async () => {
    if (attempts >= maxAttempts) {
      syncingPlugins.value.delete(pluginName)
      MessagePlugin.warning('同步任务超时，请在数据管理页面查看进度')
      return
    }
    
    try {
      const status = await datamanageApi.getSyncStatus(taskId)
      
      if (status.status === 'completed') {
        syncingPlugins.value.delete(pluginName)
        MessagePlugin.success(`${pluginName} 数据同步完成，共处理 ${status.records_processed} 条记录`)
        
        // Refresh table list and re-query
        await loadTables()
        if (selectedTable.value?.plugin_name === pluginName) {
          executeSimpleQuery()
        }
      } else if (status.status === 'failed') {
        syncingPlugins.value.delete(pluginName)
        // Show full error message in notification and allow user to see details
        const errMsg = status.error_message || '未知错误'
        const briefMsg = errMsg.length > 80 ? errMsg.substring(0, 80) + '...' : errMsg
        MessagePlugin.error({
          content: `同步失败: ${briefMsg}`,
          duration: 5000,
          closeBtn: true
        })
        // Set sync error for display in UI
        syncError.value = { pluginName, errorMessage: errMsg }
      } else if (status.status === 'cancelled') {
        syncingPlugins.value.delete(pluginName)
        MessagePlugin.warning('同步任务已取消')
      } else {
        // Still running, poll again
        attempts++
        setTimeout(poll, 1000)
      }
    } catch (error) {
      syncingPlugins.value.delete(pluginName)
      MessagePlugin.error('获取同步状态失败')
    }
  }
  
  poll()
}

// Lifecycle
onMounted(() => {
  loadTables()
})

// Watch for category change to reload
watch(selectedCategory, () => {
  selectedTable.value = null
  queryResult.value = null
})
</script>

<style scoped>
.data-explorer {
  display: flex;
  height: calc(100vh - 120px);
  gap: 16px;
  padding: 16px;
  background: var(--td-bg-color-container);
}

.table-list-panel {
  width: 320px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--td-bg-color-secondarycontainer);
  border-radius: 8px;
  overflow: hidden;
}

.table-list-panel .panel-header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--td-component-border);
}

.table-list-panel .panel-header h3 {
  margin: 0 0 12px 0;
  font-size: 16px;
  font-weight: 500;
}

.table-list-panel .category-filter {
  padding: 12px 16px;
  border-bottom: 1px solid var(--td-component-border);
  overflow-x: auto;
}

.table-list-panel .category-filter :deep(.t-radio-group) {
  flex-wrap: nowrap;
}

.table-list-panel .table-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.table-list-panel .table-item {
  padding: 12px;
  margin-bottom: 8px;
  background: var(--td-bg-color-container);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.table-list-panel .table-item:hover {
  border-color: var(--td-brand-color);
}

.table-list-panel .table-item.active {
  border-color: var(--td-brand-color);
  background: var(--td-brand-color-light);
}

.table-list-panel .table-item.no-data {
  opacity: 0.8;
}

.table-list-panel .table-item.no-data .table-icon {
  color: var(--td-warning-color);
}

.table-list-panel .table-item .table-actions {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--td-component-border);
}

.table-list-panel .table-item .table-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
  margin-bottom: 4px;
}

.table-list-panel .table-item .table-name .table-icon {
  color: var(--td-brand-color);
}

.table-list-panel .table-item .table-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.table-list-panel .table-item .table-meta .row-count {
  color: var(--td-text-color-placeholder);
}

.table-list-panel .table-item .table-desc {
  font-size: 12px;
  color: var(--td-text-color-placeholder);
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.query-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--td-bg-color-secondarycontainer);
  border-radius: 8px;
  overflow: hidden;
}

.query-panel .mode-tabs {
  border-bottom: 1px solid var(--td-component-border);
}

.query-panel .mode-tabs :deep(.t-tabs__nav) {
  padding: 0 16px;
}

.query-panel .simple-filter-section {
  padding: 16px;
  border-bottom: 1px solid var(--td-component-border);
}

.query-panel .simple-filter-section .filter-form :deep(.t-form__item) {
  margin-bottom: 0;
}

.query-panel .sql-editor-section {
  flex: 1;
  min-height: 300px;
  border-bottom: 1px solid var(--td-component-border);
}

.query-panel .result-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 200px;
  padding: 16px;
  overflow: hidden;
}

.query-panel .result-section .result-table-wrapper {
  flex: 1;
  overflow: auto;
}

.query-panel .result-section .result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.query-panel .result-section .result-header .result-info {
  font-size: 14px;
}

.query-panel .result-section .result-header .result-info .execution-time {
  color: var(--td-text-color-placeholder);
  margin-left: 8px;
}

.query-panel .result-section .result-header .result-actions {
  display: flex;
  gap: 8px;
}

.query-panel .result-section .empty-data-hint {
  margin-bottom: 16px;
}

.query-panel .result-section .empty-data-hint :deep(.t-alert__operation) {
  margin-top: 0;
}

.query-panel .result-section .sync-error-hint {
  margin-bottom: 16px;
}

.query-panel .result-section .sync-error-hint .error-message-content {
  max-height: 150px;
  overflow: auto;
}

.query-panel .result-section .sync-error-hint .error-pre {
  margin: 0;
  padding: 8px;
  background: var(--td-bg-color-container);
  border-radius: 4px;
  font-family: monospace;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>

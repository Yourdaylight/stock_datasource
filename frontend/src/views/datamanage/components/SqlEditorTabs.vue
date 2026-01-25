<template>
  <div class="sql-editor-tabs">
    <!-- Tab 栏 -->
    <div class="tab-bar">
      <div 
        v-for="tab in tabs" 
        :key="tab.id" 
        :class="['tab-item', { active: tab.id === activeTab }]"
        @click="selectTab(tab.id)"
      >
        <span class="tab-title" @dblclick="startEditTitle(tab)">
          <template v-if="editingTabId === tab.id">
            <t-input
              ref="titleInputRef"
              v-model="editingTitle"
              size="small"
              @blur="finishEditTitle"
              @keyup.enter="finishEditTitle"
              @keyup.escape="cancelEditTitle"
              style="width: 100px"
            />
          </template>
          <template v-else>
            {{ tab.title || '未命名查询' }}
          </template>
        </span>
        <t-icon 
          name="close" 
          class="close-icon"
          @click.stop="closeTab(tab.id)" 
          v-if="tabs.length > 1"
        />
      </div>
      <t-button variant="text" size="small" @click="addTab" class="add-tab-btn">
        <t-icon name="add" />
      </t-button>
    </div>
    
    <!-- 工具栏 -->
    <div class="editor-toolbar">
      <t-button theme="primary" size="small" @click="handleExecute" :loading="executing">
        <template #icon><t-icon name="play-circle" /></template>
        运行 (Ctrl+Enter)
      </t-button>
      <t-button variant="outline" size="small" @click="handleFormat">
        <template #icon><t-icon name="format-horizontal-align-center" /></template>
        格式化
      </t-button>
      <t-divider layout="vertical" />
      <t-button variant="text" size="small" @click="showTemplateDialog = true">
        <template #icon><t-icon name="save" /></template>
        保存模板
      </t-button>
      <t-dropdown :options="templateDropdownOptions" @click="handleTemplateSelect">
        <t-button variant="text" size="small">
          <template #icon><t-icon name="folder-open" /></template>
          加载模板
          <template #suffix><t-icon name="chevron-down" /></template>
        </t-button>
      </t-dropdown>
      <t-divider layout="vertical" />
      <t-popover placement="bottom-right" trigger="click" :visible="showHistory" @visible-change="showHistory = $event">
        <t-button variant="text" size="small">
          <template #icon><t-icon name="history" /></template>
          历史
        </t-button>
        <template #content>
          <div class="history-panel">
            <div class="history-header">
              <span>查询历史</span>
              <t-button variant="text" size="small" @click="clearHistory" v-if="history.length > 0">
                清空
              </t-button>
            </div>
            <div class="history-list" v-if="history.length > 0">
              <div 
                v-for="item in history" 
                :key="item.id" 
                class="history-item"
                @click="loadFromHistory(item)"
              >
                <div class="history-sql">{{ item.sql.substring(0, 100) }}...</div>
                <div class="history-meta">
                  {{ formatTime(item.executedAt) }}
                  <span v-if="item.executionTime">· {{ item.executionTime }}ms</span>
                </div>
              </div>
            </div>
            <t-empty v-else description="暂无历史记录" size="small" />
          </div>
        </template>
      </t-popover>
    </div>
    
    <!-- 编辑器区域 -->
    <div class="editor-container">
      <div 
        v-for="tab in tabs" 
        :key="tab.id"
        :class="['editor-wrapper', { hidden: tab.id !== activeTab }]"
      >
        <textarea
          :ref="el => setEditorRef(tab.id, el)"
          v-model="tab.sql"
          class="sql-textarea"
          placeholder="输入 SQL 查询语句..."
          @keydown.ctrl.enter.prevent="handleExecute"
          @keydown.meta.enter.prevent="handleExecute"
        />
      </div>
    </div>
    
    <!-- 表信息提示 -->
    <div class="table-hint" v-if="tables.length > 0">
      <t-icon name="info-circle" />
      可查询的表：
      <span 
        v-for="(table, index) in tables.slice(0, 5)" 
        :key="table.table_name"
        class="table-name-hint"
        @click="insertTableName(table.table_name)"
      >
        {{ table.table_name }}<template v-if="index < Math.min(tables.length, 5) - 1">, </template>
      </span>
      <template v-if="tables.length > 5">
        ... 等 {{ tables.length }} 个表
      </template>
    </div>
    
    <!-- 保存模板对话框 -->
    <t-dialog
      v-model:visible="showTemplateDialog"
      header="保存查询模板"
      :confirm-btn="{ content: '保存', loading: savingTemplate }"
      @confirm="handleSaveTemplate"
    >
      <t-form :label-width="80">
        <t-form-item label="模板名称" required>
          <t-input v-model="templateForm.name" placeholder="输入模板名称" />
        </t-form-item>
        <t-form-item label="描述">
          <t-textarea v-model="templateForm.description" placeholder="可选的描述信息" :autosize="{ minRows: 2 }" />
        </t-form-item>
        <t-form-item label="分类">
          <t-input v-model="templateForm.category" placeholder="可选的分类标签" />
        </t-form-item>
      </t-form>
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { datamanageApi, type ExplorerTableInfo, type SqlTemplate } from '@/api/datamanage'
import { useQueryHistory, type QueryHistoryItem } from '@/composables/useQueryHistory'

// Types
interface SqlTab {
  id: string
  title: string
  sql: string
  result?: any
}

// Props & Emits
const props = defineProps<{
  tabs: SqlTab[]
  activeTab: string
  tables: ExplorerTableInfo[]
}>()

const emit = defineEmits<{
  (e: 'update:tabs', value: SqlTab[]): void
  (e: 'update:activeTab', value: string): void
  (e: 'execute', sql: string, tabId: string): void
}>()

// State
const executing = ref(false)
const showHistory = ref(false)
const showTemplateDialog = ref(false)
const savingTemplate = ref(false)
const editingTabId = ref<string | null>(null)
const editingTitle = ref('')
const titleInputRef = ref<any>(null)
const templates = ref<SqlTemplate[]>([])

// Template form
const templateForm = ref({
  name: '',
  description: '',
  category: ''
})

// Editor refs
const editorRefs = ref<Map<string, HTMLTextAreaElement>>(new Map())

// Query history
const { history, addToHistory, clearHistory: clearHistoryFn } = useQueryHistory()

// Computed
const templateDropdownOptions = computed(() => {
  if (templates.value.length === 0) {
    return [{ content: '暂无模板', value: 'none', disabled: true }]
  }
  return templates.value.map(t => ({
    content: t.name,
    value: t.id?.toString() || t.name
  }))
})

// Methods
const setEditorRef = (tabId: string, el: any) => {
  if (el) {
    editorRefs.value.set(tabId, el as HTMLTextAreaElement)
  }
}

const selectTab = (tabId: string) => {
  emit('update:activeTab', tabId)
}

const addTab = () => {
  const newTab: SqlTab = {
    id: `tab_${Date.now()}`,
    title: `查询 ${props.tabs.length + 1}`,
    sql: ''
  }
  emit('update:tabs', [...props.tabs, newTab])
  emit('update:activeTab', newTab.id)
}

const closeTab = (tabId: string) => {
  if (props.tabs.length <= 1) return
  
  const newTabs = props.tabs.filter(t => t.id !== tabId)
  emit('update:tabs', newTabs)
  
  if (props.activeTab === tabId) {
    emit('update:activeTab', newTabs[0].id)
  }
  
  editorRefs.value.delete(tabId)
}

const startEditTitle = (tab: SqlTab) => {
  editingTabId.value = tab.id
  editingTitle.value = tab.title
  nextTick(() => {
    titleInputRef.value?.[0]?.focus()
  })
}

const finishEditTitle = () => {
  if (editingTabId.value && editingTitle.value.trim()) {
    const newTabs = props.tabs.map(t => 
      t.id === editingTabId.value ? { ...t, title: editingTitle.value.trim() } : t
    )
    emit('update:tabs', newTabs)
  }
  editingTabId.value = null
  editingTitle.value = ''
}

const cancelEditTitle = () => {
  editingTabId.value = null
  editingTitle.value = ''
}

const handleExecute = async () => {
  const currentTab = props.tabs.find(t => t.id === props.activeTab)
  if (!currentTab?.sql.trim()) {
    MessagePlugin.warning('请输入 SQL 语句')
    return
  }
  
  executing.value = true
  
  // Add to history
  addToHistory({
    sql: currentTab.sql,
    executedAt: new Date().toISOString()
  })
  
  try {
    emit('execute', currentTab.sql, currentTab.id)
  } finally {
    executing.value = false
  }
}

const handleFormat = () => {
  const currentTab = props.tabs.find(t => t.id === props.activeTab)
  if (!currentTab?.sql.trim()) return
  
  // Simple SQL formatting (basic implementation)
  let sql = currentTab.sql
  
  // Add newlines before keywords
  const keywords = ['SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'ORDER BY', 'GROUP BY', 'HAVING', 'LIMIT', 'JOIN', 'LEFT JOIN', 'RIGHT JOIN', 'INNER JOIN', 'ON']
  keywords.forEach(kw => {
    const regex = new RegExp(`\\s+${kw}\\s+`, 'gi')
    sql = sql.replace(regex, `\n${kw} `)
  })
  
  // Update tab
  const newTabs = props.tabs.map(t => 
    t.id === props.activeTab ? { ...t, sql: sql.trim() } : t
  )
  emit('update:tabs', newTabs)
}

const loadFromHistory = (item: QueryHistoryItem) => {
  const currentTab = props.tabs.find(t => t.id === props.activeTab)
  if (currentTab) {
    const newTabs = props.tabs.map(t => 
      t.id === props.activeTab ? { ...t, sql: item.sql } : t
    )
    emit('update:tabs', newTabs)
  }
  showHistory.value = false
}

const clearHistory = () => {
  clearHistoryFn()
  MessagePlugin.success('历史记录已清空')
}

const insertTableName = (tableName: string) => {
  const currentTab = props.tabs.find(t => t.id === props.activeTab)
  if (currentTab) {
    const newSql = currentTab.sql 
      ? `${currentTab.sql} ${tableName}` 
      : `SELECT * FROM ${tableName} LIMIT 100`
    const newTabs = props.tabs.map(t => 
      t.id === props.activeTab ? { ...t, sql: newSql } : t
    )
    emit('update:tabs', newTabs)
  }
}

const loadTemplates = async () => {
  try {
    templates.value = await datamanageApi.getExplorerTemplates()
  } catch (error) {
    console.error('Failed to load templates:', error)
  }
}

const handleTemplateSelect = (data: { value: string }) => {
  const template = templates.value.find(t => 
    (t.id?.toString() === data.value) || (t.name === data.value)
  )
  if (template) {
    const currentTab = props.tabs.find(t => t.id === props.activeTab)
    if (currentTab) {
      const newTabs = props.tabs.map(t => 
        t.id === props.activeTab ? { ...t, sql: template.sql, title: template.name } : t
      )
      emit('update:tabs', newTabs)
      MessagePlugin.success(`已加载模板: ${template.name}`)
    }
  }
}

const handleSaveTemplate = async () => {
  const currentTab = props.tabs.find(t => t.id === props.activeTab)
  if (!currentTab?.sql.trim()) {
    MessagePlugin.warning('当前查询为空')
    return
  }
  
  if (!templateForm.value.name.trim()) {
    MessagePlugin.warning('请输入模板名称')
    return
  }
  
  savingTemplate.value = true
  try {
    await datamanageApi.createExplorerTemplate({
      name: templateForm.value.name,
      description: templateForm.value.description,
      sql: currentTab.sql,
      category: templateForm.value.category
    })
    
    MessagePlugin.success('模板保存成功')
    showTemplateDialog.value = false
    templateForm.value = { name: '', description: '', category: '' }
    loadTemplates()
  } catch (error: any) {
    MessagePlugin.error(error.message || '保存模板失败')
  } finally {
    savingTemplate.value = false
  }
}

const formatTime = (isoString: string) => {
  const date = new Date(isoString)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
  return date.toLocaleDateString()
}

// Lifecycle
onMounted(() => {
  loadTemplates()
})
</script>

<style scoped>
.sql-editor-tabs {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.sql-editor-tabs .tab-bar {
  display: flex;
  align-items: center;
  background: var(--td-bg-color-container);
  border-bottom: 1px solid var(--td-component-border);
  padding: 0 8px;
  overflow-x: auto;
}

.sql-editor-tabs .tab-bar .tab-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  white-space: nowrap;
}

.sql-editor-tabs .tab-bar .tab-item.active {
  border-bottom-color: var(--td-brand-color);
  background: var(--td-bg-color-secondarycontainer);
}

.sql-editor-tabs .tab-bar .tab-item:hover {
  background: var(--td-bg-color-secondarycontainer);
}

.sql-editor-tabs .tab-bar .tab-item .close-icon {
  font-size: 14px;
  opacity: 0.6;
}

.sql-editor-tabs .tab-bar .tab-item .close-icon:hover {
  opacity: 1;
  color: var(--td-error-color);
}

.sql-editor-tabs .tab-bar .add-tab-btn {
  margin-left: 4px;
}

.sql-editor-tabs .editor-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: var(--td-bg-color-container);
  border-bottom: 1px solid var(--td-component-border);
}

.sql-editor-tabs .editor-container {
  flex: 1;
  position: relative;
  min-height: 150px;
}

.sql-editor-tabs .editor-container .editor-wrapper {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
}

.sql-editor-tabs .editor-container .editor-wrapper.hidden {
  visibility: hidden;
  pointer-events: none;
}

.sql-editor-tabs .editor-container .sql-textarea {
  width: 100%;
  height: 100%;
  padding: 12px 16px;
  border: none;
  outline: none;
  resize: none;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 14px;
  line-height: 1.6;
  background: var(--td-bg-color-container);
  color: var(--td-text-color-primary);
}

.sql-editor-tabs .editor-container .sql-textarea::placeholder {
  color: var(--td-text-color-placeholder);
}

.sql-editor-tabs .table-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  font-size: 12px;
  color: var(--td-text-color-secondary);
  background: var(--td-bg-color-secondarycontainer);
  border-top: 1px solid var(--td-component-border);
}

.sql-editor-tabs .table-hint .table-name-hint {
  color: var(--td-brand-color);
  cursor: pointer;
}

.sql-editor-tabs .table-hint .table-name-hint:hover {
  text-decoration: underline;
}

.history-panel {
  width: 350px;
  max-height: 400px;
}

.history-panel .history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--td-component-border);
  margin-bottom: 8px;
}

.history-panel .history-list {
  max-height: 350px;
  overflow-y: auto;
}

.history-panel .history-item {
  padding: 8px;
  border-radius: 4px;
  cursor: pointer;
  margin-bottom: 4px;
}

.history-panel .history-item:hover {
  background: var(--td-bg-color-secondarycontainer);
}

.history-panel .history-item .history-sql {
  font-family: monospace;
  font-size: 12px;
  color: var(--td-text-color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-panel .history-item .history-meta {
  font-size: 11px;
  color: var(--td-text-color-placeholder);
  margin-top: 4px;
}
</style>

<template>
  <div class="workflow-editor-container">
    <!-- 顶部操作栏 -->
    <div class="editor-header">
      <div class="header-left">
        <t-button theme="default" variant="text" @click="goBack">
          <template #icon><t-icon name="chevron-left" /></template>
        </t-button>
        <t-input 
          v-model="workflow.name"
          class="workflow-name-input"
          placeholder="工作流名称"
          borderless
        />
      </div>
      <div class="header-actions">
        <t-button theme="default" @click="showRunDialog = true" :disabled="!canRun">
          <template #icon><t-icon name="play-circle" /></template>
          运行
        </t-button>
        <t-button theme="primary" :loading="saving" @click="handleSave">
          <template #icon><t-icon name="check" /></template>
          保存
        </t-button>
      </div>
    </div>

    <!-- 主编辑区域 -->
    <div class="editor-main">
      <!-- 左侧：工具选择面板 -->
      <div class="tools-panel">
        <div class="panel-header">
          <h3>可用工具</h3>
          <t-input
            v-model="toolSearch"
            placeholder="搜索工具..."
            clearable
            size="small"
          >
            <template #prefix-icon><t-icon name="search" /></template>
          </t-input>
        </div>
        
        <div class="tools-list">
          <div 
            v-for="(tools, category) in filteredToolsByCategory" 
            :key="category"
            class="tool-category"
          >
            <div class="category-header">{{ category }}</div>
            <div 
              v-for="tool in tools" 
              :key="tool.name"
              class="tool-item"
              :class="{ selected: isToolSelected(tool.name) }"
              @click="toggleTool(tool.name)"
            >
              <t-checkbox :checked="isToolSelected(tool.name)" />
              <div class="tool-info">
                <span class="tool-name">{{ formatToolName(tool.name) }}</span>
                <span class="tool-desc">{{ tool.description }}</span>
              </div>
            </div>
          </div>
        </div>
        
        <div class="selected-count">
          已选择 {{ workflow.selected_tools.length }} 个工具
        </div>
      </div>

      <!-- 中间：提示词和设置 -->
      <div class="config-panel">
        <t-tabs v-model="activeTab">
          <t-tab-panel value="prompts" label="提示词配置">
            <div class="prompts-section">
              <div class="form-item">
                <label>工作流描述</label>
                <t-textarea
                  v-model="workflow.description"
                  placeholder="简要描述工作流的用途..."
                  :autosize="{ minRows: 2, maxRows: 4 }"
                />
              </div>
              
              <div class="form-item">
                <label>
                  系统提示词
                  <t-tooltip content="定义AI的角色、分析方法和输出格式">
                    <t-icon name="help-circle" />
                  </t-tooltip>
                </label>
                <t-textarea
                  v-model="workflow.system_prompt"
                  placeholder="你是一位专业的股票分析师..."
                  :autosize="{ minRows: 6, maxRows: 12 }"
                />
              </div>
              
              <div class="form-item">
                <label>
                  用户提示词模板
                  <t-tooltip content="使用 {{变量名}} 插入变量">
                    <t-icon name="help-circle" />
                  </t-tooltip>
                </label>
                <t-textarea
                  v-model="workflow.user_prompt_template"
                  placeholder="请分析股票 {{stock_code}} 的..."
                  :autosize="{ minRows: 4, maxRows: 8 }"
                />
                <div class="template-vars">
                  <span>可用变量：</span>
                  <t-tag 
                    v-for="v in workflow.variables" 
                    :key="v.name"
                    size="small"
                    @click="insertVariable(v.name)"
                  >
                    {{ formatVariableTag(v.name) }}
                  </t-tag>
                </div>
              </div>
            </div>
          </t-tab-panel>
          
          <t-tab-panel value="variables" label="变量配置">
            <div class="variables-section">
              <div class="variables-header">
                <span>定义工作流变量，执行时由用户输入</span>
                <t-button size="small" @click="addVariable">
                  <template #icon><t-icon name="add" /></template>
                  添加变量
                </t-button>
              </div>
              
              <div v-if="workflow.variables.length === 0" class="empty-variables">
                <p>暂无变量，点击"添加变量"创建</p>
              </div>
              
              <div v-else class="variables-list">
                <div 
                  v-for="(variable, index) in workflow.variables" 
                  :key="index"
                  class="variable-card"
                >
                  <div class="variable-row">
                    <t-input 
                      v-model="variable.name" 
                      placeholder="变量名" 
                      size="small"
                    />
                    <t-input 
                      v-model="variable.label" 
                      placeholder="显示标签" 
                      size="small"
                    />
                    <t-select 
                      v-model="variable.type" 
                      size="small"
                      :options="variableTypes"
                    />
                    <t-checkbox v-model="variable.required">必填</t-checkbox>
                    <t-button 
                      theme="danger" 
                      variant="text" 
                      size="small"
                      @click="removeVariable(index)"
                    >
                      <t-icon name="delete" />
                    </t-button>
                  </div>
                  <div class="variable-row">
                    <t-input 
                      v-model="variable.default" 
                      placeholder="默认值（可选）" 
                      size="small"
                    />
                    <t-input 
                      v-model="variable.description" 
                      placeholder="说明（可选）" 
                      size="small"
                    />
                  </div>
                </div>
              </div>
            </div>
          </t-tab-panel>
          
          <t-tab-panel value="settings" label="其他设置">
            <div class="settings-section">
              <div class="form-item">
                <label>分类</label>
                <t-select v-model="workflow.category" :options="categoryOptions" />
              </div>
              
              <div class="form-item">
                <label>标签</label>
                <t-tag-input 
                  v-model="workflow.tags"
                  placeholder="输入标签后按回车"
                />
              </div>
            </div>
          </t-tab-panel>
        </t-tabs>
      </div>

      <!-- 右侧：预览面板 -->
      <div class="preview-panel">
        <div class="panel-header">
          <h3>预览</h3>
        </div>
        
        <div class="preview-content">
          <div class="preview-section">
            <h4>基本信息</h4>
            <p><strong>名称：</strong>{{ workflow.name || '未命名' }}</p>
            <p><strong>描述：</strong>{{ workflow.description || '无' }}</p>
            <p><strong>分类：</strong>{{ getCategoryLabel(workflow.category) }}</p>
          </div>
          
          <div class="preview-section">
            <h4>选中的工具 ({{ workflow.selected_tools.length }})</h4>
            <div class="preview-tools">
              <t-tag 
                v-for="tool in workflow.selected_tools" 
                :key="tool"
                size="small"
              >
                {{ formatToolName(tool) }}
              </t-tag>
            </div>
          </div>
          
          <div class="preview-section">
            <h4>变量 ({{ workflow.variables.length }})</h4>
            <div v-for="v in workflow.variables" :key="v.name" class="preview-var">
              <span class="var-name">{{ v.label || v.name }}</span>
              <span class="var-type">{{ v.type }}</span>
              <span v-if="v.required" class="var-required">必填</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 运行对话框 -->
    <t-dialog
      v-model:visible="showRunDialog"
      :header="`运行: ${workflow.name || '工作流'}`"
      :footer="false"
      width="700px"
      destroy-on-close
    >
      <div class="run-dialog">
        <div v-if="!executing && !executionContent" class="variable-inputs">
          <div v-for="variable in workflow.variables" :key="variable.name" class="variable-item">
            <label>
              {{ variable.label || variable.name }}
              <span v-if="variable.required" class="required">*</span>
            </label>
            <t-input 
              v-model="runVariables[variable.name]"
              :placeholder="variable.description || `请输入${variable.label}`"
            />
          </div>
          
          <div class="dialog-footer">
            <t-button theme="default" @click="showRunDialog = false">取消</t-button>
            <t-button theme="primary" @click="handleRun">开始执行</t-button>
          </div>
        </div>
        
        <div v-else class="execution-result">
          <div v-if="executionThinking" class="thinking-status">
            <t-loading size="small" />
            <span>{{ executionThinking }}</span>
          </div>
          
          <div v-if="executionContent" class="result-content">
            <div class="markdown-content" v-html="renderMarkdown(executionContent)"></div>
          </div>
          
          <div v-if="executionError" class="execution-error">
            <t-icon name="close-circle" color="var(--td-error-color)" />
            <span>{{ executionError }}</span>
          </div>
          
          <div v-if="!executing" class="dialog-footer">
            <t-button theme="default" @click="handleCloseRun">关闭</t-button>
            <t-button theme="primary" @click="handleRerun">重新执行</t-button>
          </div>
        </div>
      </div>
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { MessagePlugin } from 'tdesign-vue-next'
import { useWorkflowStore } from '@/stores/workflow'
import { marked } from 'marked'
import type { AIWorkflow, WorkflowVariable, ToolInfo } from '@/api/workflow'

const router = useRouter()
const route = useRoute()
const workflowStore = useWorkflowStore()

// 编辑模式判断
const isEditMode = computed(() => !!route.params.id)
const workflowId = computed(() => route.params.id as string)

// 工作流数据
const workflow = reactive<{
  name: string
  description: string
  system_prompt: string
  user_prompt_template: string
  selected_tools: string[]
  variables: WorkflowVariable[]
  category: string
  tags: string[]
}>({
  name: '',
  description: '',
  system_prompt: '',
  user_prompt_template: '',
  selected_tools: [],
  variables: [],
  category: 'custom',
  tags: []
})

// UI状态
const activeTab = ref('prompts')
const toolSearch = ref('')
const saving = ref(false)
const showRunDialog = ref(false)
const runVariables = reactive<Record<string, any>>({})

// 从Store获取状态
const executing = computed(() => workflowStore.executing)
const executionThinking = computed(() => workflowStore.executionThinking)
const executionContent = computed(() => workflowStore.executionContent)
const executionError = computed(() => workflowStore.executionError)

// 可用工具
const availableTools = computed(() => workflowStore.availableTools)
const toolsByCategory = computed(() => workflowStore.toolsByCategory)

// 过滤后的工具
const filteredToolsByCategory = computed(() => {
  if (!toolSearch.value) return toolsByCategory.value
  
  const search = toolSearch.value.toLowerCase()
  const result: Record<string, ToolInfo[]> = {}
  
  for (const [category, tools] of Object.entries(toolsByCategory.value)) {
    const filtered = tools.filter(t => 
      t.name.toLowerCase().includes(search) ||
      t.description.toLowerCase().includes(search)
    )
    if (filtered.length > 0) {
      result[category] = filtered
    }
  }
  
  return result
})

// 是否可以运行
const canRun = computed(() => 
  workflow.name && 
  workflow.selected_tools.length > 0 &&
  workflow.system_prompt
)

// 变量类型选项
const variableTypes = [
  { label: '文本', value: 'string' },
  { label: '数字', value: 'number' },
  { label: '日期', value: 'date' },
  { label: '股票代码', value: 'stock_code' },
  { label: '股票列表', value: 'stock_list' }
]

// 分类选项
const categoryOptions = [
  { label: '个股分析', value: 'analysis' },
  { label: '对比分析', value: 'comparison' },
  { label: '条件筛选', value: 'screening' },
  { label: '技术分析', value: 'technical' },
  { label: '板块分析', value: 'sector' },
  { label: '自定义', value: 'custom' }
]

// 初始化
onMounted(async () => {
  // 加载工具列表
  if (workflowStore.availableTools.length === 0) {
    await workflowStore.loadTools()
  }
  
  // 编辑模式：加载工作流
  if (isEditMode.value) {
    try {
      const data = await workflowStore.loadWorkflowDetail(workflowId.value)
      if (data) {
        Object.assign(workflow, {
          name: data.name,
          description: data.description,
          system_prompt: data.system_prompt,
          user_prompt_template: data.user_prompt_template,
          selected_tools: [...data.selected_tools],
          variables: data.variables.map(v => ({ ...v })),
          category: data.category,
          tags: [...data.tags]
        })
      }
    } catch (error) {
      console.error('Failed to load workflow:', error)
      MessagePlugin.error('加载工作流失败')
    }
  }
})

// 方法
function goBack() {
  router.push('/workflow')
}

function isToolSelected(toolName: string): boolean {
  return workflow.selected_tools.includes(toolName)
}

function toggleTool(toolName: string) {
  const index = workflow.selected_tools.indexOf(toolName)
  if (index === -1) {
    workflow.selected_tools.push(toolName)
  } else {
    workflow.selected_tools.splice(index, 1)
  }
}

function formatToolName(name: string): string {
  // 移除前缀，转换下划线为空格
  const parts = name.split('_')
  if (parts.length > 1) {
    // 跳过第一个前缀部分
    return parts.slice(1).join(' ')
  }
  return name
}

function addVariable() {
  workflow.variables.push({
    name: '',
    label: '',
    type: 'string',
    required: true,
    default: '',
    description: ''
  })
}

function removeVariable(index: number) {
  workflow.variables.splice(index, 1)
}

function insertVariable(varName: string) {
  workflow.user_prompt_template += `{{${varName}}}`
}

function formatVariableTag(varName: string): string {
  return `{{${varName}}}`
}

function getCategoryLabel(value: string): string {
  const opt = categoryOptions.find(o => o.value === value)
  return opt?.label || value
}

async function handleSave() {
  if (!workflow.name) {
    MessagePlugin.warning('请输入工作流名称')
    return
  }
  
  saving.value = true
  try {
    if (isEditMode.value) {
      await workflowStore.update(workflowId.value, {
        name: workflow.name,
        description: workflow.description,
        system_prompt: workflow.system_prompt,
        user_prompt_template: workflow.user_prompt_template,
        selected_tools: workflow.selected_tools,
        variables: workflow.variables,
        category: workflow.category,
        tags: workflow.tags
      })
      MessagePlugin.success('保存成功')
    } else {
      const created = await workflowStore.create({
        name: workflow.name,
        description: workflow.description,
        system_prompt: workflow.system_prompt,
        user_prompt_template: workflow.user_prompt_template,
        selected_tools: workflow.selected_tools,
        variables: workflow.variables,
        category: workflow.category,
        tags: workflow.tags
      })
      MessagePlugin.success('创建成功')
      router.replace(`/workflow/${created.id}/edit`)
    }
  } catch (error) {
    console.error('Save failed:', error)
    MessagePlugin.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function handleRun() {
  // 验证必填变量
  for (const variable of workflow.variables) {
    if (variable.required && !runVariables[variable.name]) {
      MessagePlugin.warning(`请填写 ${variable.label || variable.name}`)
      return
    }
  }
  
  // 先保存再执行
  if (isEditMode.value) {
    try {
      await workflowStore.execute(workflowId.value, { ...runVariables })
    } catch (error) {
      console.error('Execution failed:', error)
    }
  } else {
    MessagePlugin.warning('请先保存工作流')
  }
}

function handleCloseRun() {
  showRunDialog.value = false
  workflowStore.clearExecution()
}

function handleRerun() {
  workflowStore.clearExecution()
}

function renderMarkdown(content: string): string {
  try {
    return marked(content) as string
  } catch {
    return content
  }
}

// 打开运行对话框时初始化变量
watch(showRunDialog, (val) => {
  if (val) {
    workflowStore.clearExecution()
    for (const variable of workflow.variables) {
      runVariables[variable.name] = variable.default || ''
    }
  }
})
</script>

<style scoped>
.workflow-editor-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--td-bg-color-page);
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 24px;
  background: var(--td-bg-color-container);
  border-bottom: 1px solid var(--td-component-stroke);
}

.editor-header .header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.editor-header .header-left .workflow-name-input {
  width: 300px;
  font-size: 16px;
  font-weight: 500;
}

.editor-header .header-actions {
  display: flex;
  gap: 12px;
}

.editor-main {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* 工具面板 */
.tools-panel {
  width: 280px;
  display: flex;
  flex-direction: column;
  background: var(--td-bg-color-container);
  border-right: 1px solid var(--td-component-stroke);
}

.tools-panel .panel-header {
  padding: 16px;
  border-bottom: 1px solid var(--td-component-stroke);
}

.tools-panel .panel-header h3 {
  font-size: 14px;
  font-weight: 500;
  margin: 0 0 12px 0;
}

.tools-panel .tools-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.tools-panel .tool-category {
  margin-bottom: 16px;
}

.tools-panel .tool-category .category-header {
  font-size: 12px;
  color: var(--td-text-color-placeholder);
  padding: 8px;
  text-transform: uppercase;
}

.tools-panel .tool-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
}

.tools-panel .tool-item:hover {
  background: var(--td-bg-color-secondarycontainer);
}

.tools-panel .tool-item.selected {
  background: var(--td-brand-color-light);
}

.tools-panel .tool-item .tool-info {
  flex: 1;
  min-width: 0;
}

.tools-panel .tool-item .tool-info .tool-name {
  display: block;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 2px;
}

.tools-panel .tool-item .tool-info .tool-desc {
  display: block;
  font-size: 12px;
  color: var(--td-text-color-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tools-panel .selected-count {
  padding: 12px 16px;
  font-size: 12px;
  color: var(--td-text-color-secondary);
  border-top: 1px solid var(--td-component-stroke);
  text-align: center;
}

/* 配置面板 */
.config-panel {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.config-panel :deep(.t-tabs) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.config-panel :deep(.t-tabs .t-tabs__content) {
  flex: 1;
  overflow-y: auto;
}

.config-panel :deep(.t-tabs__nav) {
  padding: 0 24px;
  background: var(--td-bg-color-container);
}

.prompts-section,
.variables-section,
.settings-section {
  padding: 24px;
}

.form-item {
  margin-bottom: 20px;
}

.form-item label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 8px;
  color: var(--td-text-color-primary);
}

.template-vars {
  margin-top: 8px;
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.template-vars .t-tag {
  cursor: pointer;
  margin-left: 4px;
}

/* 变量配置 */
.variables-section .variables-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.variables-section .variables-header span {
  font-size: 13px;
  color: var(--td-text-color-secondary);
}

.variables-section .empty-variables {
  text-align: center;
  padding: 40px;
  color: var(--td-text-color-placeholder);
}

.variables-section .variable-card {
  padding: 16px;
  background: var(--td-bg-color-secondarycontainer);
  border-radius: 8px;
  margin-bottom: 12px;
}

.variables-section .variable-card .variable-row {
  display: flex;
  gap: 12px;
  align-items: center;
}

.variables-section .variable-card .variable-row:first-child {
  margin-bottom: 12px;
}

.variables-section .variable-card .variable-row .t-input {
  flex: 1;
}

.variables-section .variable-card .variable-row .t-select {
  width: 120px;
}

/* 预览面板 */
.preview-panel {
  width: 280px;
  background: var(--td-bg-color-container);
  border-left: 1px solid var(--td-component-stroke);
  display: flex;
  flex-direction: column;
}

.preview-panel .panel-header {
  padding: 16px;
  border-bottom: 1px solid var(--td-component-stroke);
}

.preview-panel .panel-header h3 {
  font-size: 14px;
  font-weight: 500;
  margin: 0;
}

.preview-panel .preview-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.preview-panel .preview-section {
  margin-bottom: 20px;
}

.preview-panel .preview-section h4 {
  font-size: 12px;
  color: var(--td-text-color-placeholder);
  text-transform: uppercase;
  margin: 0 0 8px 0;
}

.preview-panel .preview-section p {
  font-size: 13px;
  margin: 4px 0;
  word-break: break-all;
}

.preview-panel .preview-tools {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.preview-panel .preview-var {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  font-size: 13px;
}

.preview-panel .preview-var .var-name {
  flex: 1;
}

.preview-panel .preview-var .var-type {
  color: var(--td-text-color-secondary);
  font-size: 12px;
}

.preview-panel .preview-var .var-required {
  color: var(--td-error-color);
  font-size: 11px;
}

/* 运行对话框 */
.run-dialog .variable-inputs .variable-item {
  margin-bottom: 16px;
}

.run-dialog .variable-inputs .variable-item label {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
}

.run-dialog .variable-inputs .variable-item label .required {
  color: var(--td-error-color);
  margin-left: 2px;
}

.run-dialog .execution-result .thinking-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: var(--td-bg-color-secondarycontainer);
  border-radius: 6px;
  margin-bottom: 16px;
}

.run-dialog .execution-result .result-content {
  max-height: 400px;
  overflow-y: auto;
  padding: 16px;
  background: var(--td-bg-color-secondarycontainer);
  border-radius: 6px;
}

.run-dialog .execution-result .result-content .markdown-content {
  font-size: 14px;
  line-height: 1.6;
}

.run-dialog .execution-result .execution-error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: var(--td-error-color-1);
  border-radius: 6px;
  margin-top: 16px;
  color: var(--td-error-color);
}

.run-dialog .dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 24px;
}
</style>

<template>
  <div class="workflow-list-container">
    <!-- 页面标题和操作栏 -->
    <div class="page-header">
      <div class="header-left">
        <h1>AI工作流</h1>
        <span class="subtitle">创建自定义的股票分析工作流</span>
      </div>
      <div class="header-actions">
        <t-button theme="default" @click="showAIGenerateDialog = true">
          <template #icon><t-icon name="lightbulb" /></template>
          AI智能生成
        </t-button>
        <t-button theme="primary" @click="goToCreate">
          <template #icon><t-icon name="add" /></template>
          创建工作流
        </t-button>
      </div>
    </div>

    <!-- 模板区域 -->
    <div class="section templates-section">
      <div class="section-header">
        <h2>推荐模板</h2>
        <span class="section-desc">快速开始，从预置模板创建工作流</span>
      </div>
      <div class="template-grid">
        <div 
          v-for="template in templates" 
          :key="template.id"
          class="template-card"
          @click="handleUseTemplate(template)"
        >
          <div class="template-icon">
            <t-icon :name="getTemplateIcon(template.category)" size="24px" />
          </div>
          <div class="template-content">
            <h3>{{ template.name }}</h3>
            <p>{{ template.description }}</p>
            <div class="template-tags">
              <t-tag v-for="tag in template.tags.slice(0, 3)" :key="tag" size="small" variant="light">
                {{ tag }}
              </t-tag>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 我的工作流 -->
    <div class="section my-workflows-section">
      <div class="section-header">
        <h2>我的工作流</h2>
        <span class="section-desc">共 {{ userWorkflows.length }} 个工作流</span>
      </div>
      
      <t-loading :loading="loading">
        <div v-if="userWorkflows.length === 0" class="empty-state">
          <t-icon name="folder-open" size="48px" />
          <p>暂无工作流</p>
          <t-button theme="primary" variant="text" @click="goToCreate">创建第一个工作流</t-button>
        </div>
        
        <div v-else class="workflow-grid">
          <div 
            v-for="workflow in userWorkflows" 
            :key="workflow.id"
            class="workflow-card"
          >
            <div class="workflow-header">
              <h3>{{ workflow.name }}</h3>
              <t-dropdown :options="getWorkflowActions(workflow)" @click="handleAction">
                <t-button theme="default" variant="text" shape="square">
                  <t-icon name="more" />
                </t-button>
              </t-dropdown>
            </div>
            <p class="workflow-desc">{{ workflow.description || '暂无描述' }}</p>
            <div class="workflow-meta">
              <span class="meta-item">
                <t-icon name="tools" size="14px" />
                {{ workflow.selected_tools.length }} 个工具
              </span>
              <span class="meta-item">
                <t-icon name="time" size="14px" />
                {{ formatDate(workflow.updated_at) }}
              </span>
            </div>
            <div class="workflow-actions">
              <t-button size="small" @click="handleRun(workflow)">
                <template #icon><t-icon name="play-circle" /></template>
                运行
              </t-button>
              <t-button size="small" theme="default" @click="handleEdit(workflow)">
                <template #icon><t-icon name="edit" /></template>
                编辑
              </t-button>
            </div>
          </div>
        </div>
      </t-loading>
    </div>

    <!-- AI生成对话框 -->
    <t-dialog
      v-model:visible="showAIGenerateDialog"
      header="AI智能生成工作流"
      :footer="false"
      width="600px"
      destroy-on-close
    >
      <div class="ai-generate-dialog">
        <div class="generate-tip">
          <t-icon name="lightbulb-circle" />
          <span>描述你想要的分析策略或交易方式，AI将为你生成对应的工作流配置</span>
        </div>
        
        <t-textarea
          v-model="generateDescription"
          placeholder="例如：我想要一个能帮我筛选高股息低估值的股票的工作流，关注股息率>3%且PE<20的股票"
          :maxlength="500"
          :autosize="{ minRows: 4, maxRows: 8 }"
        />
        
        <div v-if="generating" class="generate-status">
          <t-loading size="small" />
          <span>{{ generatingContent ? '生成中...' : '分析需求中...' }}</span>
        </div>
        
        <div v-if="generatedWorkflow" class="generate-result">
          <div class="result-header">
            <t-icon name="check-circle" color="var(--td-success-color)" />
            <span>工作流生成成功</span>
          </div>
          <div class="result-preview">
            <p><strong>名称：</strong>{{ generatedWorkflow.name }}</p>
            <p><strong>描述：</strong>{{ generatedWorkflow.description }}</p>
            <p><strong>工具：</strong>{{ generatedWorkflow.selected_tools?.join(', ') }}</p>
          </div>
        </div>
        
        <div v-if="generateError" class="generate-error">
          <t-icon name="close-circle" color="var(--td-error-color)" />
          <span>{{ generateError }}</span>
        </div>
        
        <div class="dialog-footer">
          <t-button theme="default" @click="showAIGenerateDialog = false">取消</t-button>
          <t-button 
            v-if="!generatedWorkflow"
            theme="primary" 
            :loading="generating"
            :disabled="!generateDescription.trim()"
            @click="handleGenerate"
          >
            生成工作流
          </t-button>
          <t-button 
            v-else
            theme="primary" 
            @click="handleApplyGenerated"
          >
            应用并编辑
          </t-button>
        </div>
      </div>
    </t-dialog>

    <!-- 运行工作流对话框 -->
    <t-dialog
      v-model:visible="showRunDialog"
      :header="`运行: ${runningWorkflow?.name || ''}`"
      :footer="false"
      width="700px"
      destroy-on-close
    >
      <div class="run-dialog">
        <!-- 变量输入 -->
        <div v-if="!executing && !executionContent" class="variable-inputs">
          <div v-for="variable in runningWorkflow?.variables" :key="variable.name" class="variable-item">
            <label>
              {{ variable.label }}
              <span v-if="variable.required" class="required">*</span>
            </label>
            <t-input 
              v-model="variableValues[variable.name]"
              :placeholder="variable.description || `请输入${variable.label}`"
            />
          </div>
          
          <div class="dialog-footer">
            <t-button theme="default" @click="showRunDialog = false">取消</t-button>
            <t-button theme="primary" @click="handleExecute">开始执行</t-button>
          </div>
        </div>
        
        <!-- 执行状态和结果 -->
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

    <!-- 使用模板对话框 -->
    <t-dialog
      v-model:visible="showTemplateDialog"
      header="从模板创建工作流"
      width="400px"
      @confirm="handleConfirmTemplate"
    >
      <t-form>
        <t-form-item label="工作流名称">
          <t-input v-model="newWorkflowName" placeholder="请输入工作流名称" />
        </t-form-item>
      </t-form>
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { MessagePlugin } from 'tdesign-vue-next'
import { useWorkflowStore } from '@/stores/workflow'
import { marked } from 'marked'
import type { AIWorkflow } from '@/api/workflow'

const router = useRouter()
const workflowStore = useWorkflowStore()

// 状态
const showAIGenerateDialog = ref(false)
const showRunDialog = ref(false)
const showTemplateDialog = ref(false)
const generateDescription = ref('')
const runningWorkflow = ref<AIWorkflow | null>(null)
const variableValues = reactive<Record<string, any>>({})
const selectedTemplate = ref<AIWorkflow | null>(null)
const newWorkflowName = ref('')

// 从Store获取状态
const loading = computed(() => workflowStore.loading)
const templates = computed(() => workflowStore.templates)
const userWorkflows = computed(() => workflowStore.userWorkflows)
const generating = computed(() => workflowStore.generating)
const generatingContent = computed(() => workflowStore.generatingContent)
const generatedWorkflow = computed(() => workflowStore.generatedWorkflow)
const generateError = computed(() => workflowStore.generateError)
const executing = computed(() => workflowStore.executing)
const executionThinking = computed(() => workflowStore.executionThinking)
const executionContent = computed(() => workflowStore.executionContent)
const executionError = computed(() => workflowStore.executionError)

// 初始化
onMounted(async () => {
  try {
    await Promise.all([
      workflowStore.loadWorkflows(),
      workflowStore.loadTemplates(),
      workflowStore.loadTools()
    ])
  } catch (error) {
    console.error('Failed to load data:', error)
  }
})

// 方法
function goToCreate() {
  router.push('/workflow/create')
}

function handleEdit(workflow: AIWorkflow) {
  router.push(`/workflow/${workflow.id}/edit`)
}

function handleRun(workflow: AIWorkflow) {
  runningWorkflow.value = workflow
  // 初始化变量值
  for (const variable of workflow.variables) {
    variableValues[variable.name] = variable.default || ''
  }
  workflowStore.clearExecution()
  showRunDialog.value = true
}

async function handleExecute() {
  if (!runningWorkflow.value) return
  
  // 验证必填变量
  for (const variable of runningWorkflow.value.variables) {
    if (variable.required && !variableValues[variable.name]) {
      MessagePlugin.warning(`请填写 ${variable.label}`)
      return
    }
  }
  
  try {
    await workflowStore.execute(runningWorkflow.value.id, { ...variableValues })
  } catch (error) {
    console.error('Execution failed:', error)
  }
}

function handleCloseRun() {
  showRunDialog.value = false
  workflowStore.clearExecution()
}

function handleRerun() {
  workflowStore.clearExecution()
}

function handleUseTemplate(template: AIWorkflow) {
  selectedTemplate.value = template
  newWorkflowName.value = `${template.name} - 副本`
  showTemplateDialog.value = true
}

async function handleConfirmTemplate() {
  if (!selectedTemplate.value || !newWorkflowName.value.trim()) {
    MessagePlugin.warning('请输入工作流名称')
    return
  }
  
  try {
    const workflow = await workflowStore.cloneTemplate(selectedTemplate.value.id, newWorkflowName.value)
    showTemplateDialog.value = false
    MessagePlugin.success('创建成功')
    router.push(`/workflow/${workflow.id}/edit`)
  } catch (error) {
    console.error('Clone failed:', error)
    MessagePlugin.error('创建失败')
  }
}

async function handleGenerate() {
  if (!generateDescription.value.trim()) return
  
  workflowStore.clearGeneration()
  try {
    await workflowStore.generate(generateDescription.value)
  } catch (error) {
    console.error('Generate failed:', error)
  }
}

async function handleApplyGenerated() {
  if (!generatedWorkflow.value) return
  
  try {
    const workflow = await workflowStore.create({
      name: generatedWorkflow.value.name,
      description: generatedWorkflow.value.description,
      system_prompt: generatedWorkflow.value.system_prompt,
      user_prompt_template: generatedWorkflow.value.user_prompt_template,
      selected_tools: generatedWorkflow.value.selected_tools,
      variables: generatedWorkflow.value.variables,
      category: generatedWorkflow.value.category,
      tags: generatedWorkflow.value.tags
    })
    
    showAIGenerateDialog.value = false
    workflowStore.clearGeneration()
    generateDescription.value = ''
    
    MessagePlugin.success('工作流创建成功')
    router.push(`/workflow/${workflow.id}/edit`)
  } catch (error) {
    console.error('Create failed:', error)
    MessagePlugin.error('创建失败')
  }
}

function handleAction(data: { value: string; workflow: AIWorkflow }) {
  const { value, workflow } = data
  if (value === 'edit') {
    handleEdit(workflow)
  } else if (value === 'run') {
    handleRun(workflow)
  } else if (value === 'delete') {
    handleDelete(workflow)
  }
}

async function handleDelete(workflow: AIWorkflow) {
  try {
    await workflowStore.remove(workflow.id)
    MessagePlugin.success('删除成功')
  } catch (error) {
    console.error('Delete failed:', error)
    MessagePlugin.error('删除失败')
  }
}

function getWorkflowActions(workflow: AIWorkflow) {
  return [
    { content: '运行', value: 'run', workflow },
    { content: '编辑', value: 'edit', workflow },
    { content: '删除', value: 'delete', workflow, theme: 'error' }
  ]
}

function getTemplateIcon(category: string): string {
  const icons: Record<string, string> = {
    analysis: 'chart-line',
    comparison: 'chart-bar',
    screening: 'filter',
    technical: 'chart-bubble',
    sector: 'layers',
    custom: 'cpu'
  }
  return icons[category] || 'cpu'
}

function formatDate(date: string): string {
  if (!date) return ''
  const d = new Date(date)
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

function renderMarkdown(content: string): string {
  try {
    return marked(content) as string
  } catch {
    return content
  }
}
</script>

<style scoped>
.workflow-list-container {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
}

.page-header .header-left h1 {
  font-size: 24px;
  font-weight: 600;
  margin: 0;
}

.page-header .header-left .subtitle {
  color: var(--td-text-color-secondary);
  font-size: 14px;
}

.page-header .header-actions {
  display: flex;
  gap: 12px;
}

.section {
  margin-bottom: 40px;
}

.section .section-header {
  margin-bottom: 16px;
}

.section .section-header h2 {
  font-size: 18px;
  font-weight: 500;
  margin: 0 0 4px 0;
}

.section .section-header .section-desc {
  color: var(--td-text-color-secondary);
  font-size: 13px;
}

.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.template-card {
  display: flex;
  gap: 16px;
  padding: 20px;
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-component-stroke);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.template-card:hover {
  border-color: var(--td-brand-color);
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.template-card .template-icon {
  width: 48px;
  height: 48px;
  background: var(--td-brand-color-light);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--td-brand-color);
  flex-shrink: 0;
}

.template-card .template-content {
  flex: 1;
  min-width: 0;
}

.template-card .template-content h3 {
  font-size: 15px;
  font-weight: 500;
  margin: 0 0 6px 0;
}

.template-card .template-content p {
  font-size: 13px;
  color: var(--td-text-color-secondary);
  margin: 0 0 10px 0;
  line-height: 1.4;
}

.template-card .template-content .template-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.workflow-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.workflow-card {
  padding: 20px;
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-component-stroke);
  border-radius: 8px;
}

.workflow-card .workflow-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
}

.workflow-card .workflow-header h3 {
  font-size: 15px;
  font-weight: 500;
  margin: 0;
}

.workflow-card .workflow-desc {
  font-size: 13px;
  color: var(--td-text-color-secondary);
  margin: 0 0 12px 0;
  line-height: 1.4;
}

.workflow-card .workflow-meta {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}

.workflow-card .workflow-meta .meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--td-text-color-placeholder);
}

.workflow-card .workflow-actions {
  display: flex;
  gap: 8px;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: var(--td-text-color-placeholder);
}

.empty-state p {
  margin: 16px 0;
}

/* AI生成对话框 */
.ai-generate-dialog .generate-tip {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px 16px;
  background: var(--td-brand-color-light);
  border-radius: 6px;
  margin-bottom: 16px;
  font-size: 13px;
  color: var(--td-brand-color);
}

.ai-generate-dialog .generate-status {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
  color: var(--td-text-color-secondary);
}

.ai-generate-dialog .generate-result {
  margin-top: 16px;
  padding: 16px;
  background: var(--td-success-color-1);
  border-radius: 6px;
}

.ai-generate-dialog .generate-result .result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
  margin-bottom: 12px;
}

.ai-generate-dialog .generate-result .result-preview p {
  margin: 4px 0;
  font-size: 13px;
}

.ai-generate-dialog .generate-error {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
  color: var(--td-error-color);
}

.ai-generate-dialog .dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 24px;
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

.run-dialog .execution-result .result-content .markdown-content :deep(h1),
.run-dialog .execution-result .result-content .markdown-content :deep(h2),
.run-dialog .execution-result .result-content .markdown-content :deep(h3) {
  margin-top: 16px;
  margin-bottom: 8px;
}

.run-dialog .execution-result .result-content .markdown-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
}

.run-dialog .execution-result .result-content .markdown-content :deep(table) th,
.run-dialog .execution-result .result-content .markdown-content :deep(table) td {
  border: 1px solid var(--td-component-stroke);
  padding: 8px;
  text-align: left;
}

.run-dialog .execution-result .result-content .markdown-content :deep(table) th {
  background: var(--td-bg-color-container);
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

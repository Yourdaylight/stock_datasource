/**
 * AI工作流状态管理
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { AIWorkflow, ToolInfo, WorkflowCreateRequest, WorkflowUpdateRequest, WorkflowVariable } from '@/api/workflow'
import {
  getWorkflowList,
  getWorkflow,
  createWorkflow,
  updateWorkflow,
  deleteWorkflow,
  getWorkflowTemplates,
  getAvailableTools,
  cloneFromTemplate,
  executeWorkflowStream,
  generateWorkflowStream
} from '@/api/workflow'

export const useWorkflowStore = defineStore('workflow', () => {
  // 状态
  const workflows = ref<AIWorkflow[]>([])
  const templates = ref<AIWorkflow[]>([])
  const availableTools = ref<ToolInfo[]>([])
  const currentWorkflow = ref<AIWorkflow | null>(null)
  const loading = ref(false)
  const executing = ref(false)
  const generating = ref(false)
  
  // 执行状态
  const executionThinking = ref('')
  const executionContent = ref('')
  const executionError = ref('')
  
  // 生成状态
  const generatingContent = ref('')
  const generatedWorkflow = ref<any>(null)
  const generateError = ref('')

  // 计算属性
  const userWorkflows = computed(() => 
    workflows.value.filter(w => !w.is_template)
  )
  
  const workflowsByCategory = computed(() => {
    const result: Record<string, AIWorkflow[]> = {}
    for (const w of workflows.value) {
      const cat = w.category || 'custom'
      if (!result[cat]) {
        result[cat] = []
      }
      result[cat].push(w)
    }
    return result
  })
  
  const toolsByCategory = computed(() => {
    const result: Record<string, ToolInfo[]> = {}
    for (const tool of availableTools.value) {
      const cat = tool.category || '其他'
      if (!result[cat]) {
        result[cat] = []
      }
      result[cat].push(tool)
    }
    return result
  })

  // 操作方法
  
  /**
   * 加载工作流列表
   */
  async function loadWorkflows(includeTemplates: boolean = true) {
    loading.value = true
    try {
      const response = await getWorkflowList(includeTemplates)
      workflows.value = response.workflows
    } catch (error) {
      console.error('Failed to load workflows:', error)
      throw error
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 加载模板列表
   */
  async function loadTemplates() {
    loading.value = true
    try {
      templates.value = await getWorkflowTemplates()
    } catch (error) {
      console.error('Failed to load templates:', error)
      throw error
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 加载可用工具
   */
  async function loadTools() {
    try {
      availableTools.value = await getAvailableTools()
    } catch (error) {
      console.error('Failed to load tools:', error)
      throw error
    }
  }
  
  /**
   * 加载工作流详情
   */
  async function loadWorkflowDetail(workflowId: string) {
    loading.value = true
    try {
      currentWorkflow.value = await getWorkflow(workflowId)
      return currentWorkflow.value
    } catch (error) {
      console.error('Failed to load workflow:', error)
      throw error
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 创建新工作流
   */
  async function create(data: WorkflowCreateRequest) {
    loading.value = true
    try {
      const workflow = await createWorkflow(data)
      workflows.value.unshift(workflow)
      return workflow
    } catch (error) {
      console.error('Failed to create workflow:', error)
      throw error
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 更新工作流
   */
  async function update(workflowId: string, data: WorkflowUpdateRequest) {
    loading.value = true
    try {
      const workflow = await updateWorkflow(workflowId, data)
      const index = workflows.value.findIndex(w => w.id === workflowId)
      if (index !== -1) {
        workflows.value[index] = workflow
      }
      if (currentWorkflow.value?.id === workflowId) {
        currentWorkflow.value = workflow
      }
      return workflow
    } catch (error) {
      console.error('Failed to update workflow:', error)
      throw error
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 删除工作流
   */
  async function remove(workflowId: string) {
    loading.value = true
    try {
      await deleteWorkflow(workflowId)
      workflows.value = workflows.value.filter(w => w.id !== workflowId)
      if (currentWorkflow.value?.id === workflowId) {
        currentWorkflow.value = null
      }
    } catch (error) {
      console.error('Failed to delete workflow:', error)
      throw error
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 从模板克隆
   */
  async function cloneTemplate(templateId: string, name: string) {
    loading.value = true
    try {
      const workflow = await cloneFromTemplate(templateId, name)
      workflows.value.unshift(workflow)
      return workflow
    } catch (error) {
      console.error('Failed to clone template:', error)
      throw error
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 执行工作流（流式）
   */
  async function execute(workflowId: string, variables: Record<string, any>) {
    executing.value = true
    executionThinking.value = ''
    executionContent.value = ''
    executionError.value = ''
    
    try {
      await executeWorkflowStream(
        workflowId,
        variables,
        (thinking) => {
          executionThinking.value = thinking
        },
        (content) => {
          executionContent.value += content
        },
        () => {
          executing.value = false
        },
        (error) => {
          executionError.value = error
          executing.value = false
        }
      )
    } catch (error: any) {
      executionError.value = error.message || '执行失败'
      executing.value = false
      throw error
    }
  }
  
  /**
   * AI生成工作流（流式）
   */
  async function generate(description: string) {
    generating.value = true
    generatingContent.value = ''
    generatedWorkflow.value = null
    generateError.value = ''
    
    try {
      await generateWorkflowStream(
        description,
        (thinking) => {
          // 思考状态
        },
        (content) => {
          generatingContent.value += content
        },
        (workflow) => {
          generatedWorkflow.value = workflow
        },
        () => {
          generating.value = false
        },
        (error) => {
          generateError.value = error
          generating.value = false
        }
      )
    } catch (error: any) {
      generateError.value = error.message || '生成失败'
      generating.value = false
      throw error
    }
  }
  
  /**
   * 清除执行状态
   */
  function clearExecution() {
    executionThinking.value = ''
    executionContent.value = ''
    executionError.value = ''
  }
  
  /**
   * 清除生成状态
   */
  function clearGeneration() {
    generatingContent.value = ''
    generatedWorkflow.value = null
    generateError.value = ''
  }
  
  /**
   * 设置当前工作流
   */
  function setCurrentWorkflow(workflow: AIWorkflow | null) {
    currentWorkflow.value = workflow
  }

  return {
    // 状态
    workflows,
    templates,
    availableTools,
    currentWorkflow,
    loading,
    executing,
    generating,
    executionThinking,
    executionContent,
    executionError,
    generatingContent,
    generatedWorkflow,
    generateError,
    
    // 计算属性
    userWorkflows,
    workflowsByCategory,
    toolsByCategory,
    
    // 方法
    loadWorkflows,
    loadTemplates,
    loadTools,
    loadWorkflowDetail,
    create,
    update,
    remove,
    cloneTemplate,
    execute,
    generate,
    clearExecution,
    clearGeneration,
    setCurrentWorkflow,
  }
})

<script setup lang="ts">
import { ref, nextTick, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '@/stores/chat'
import { useWorkflowStore } from '@/stores/workflow'
import MessageList from './components/MessageList.vue'
import InputBox from './components/InputBox.vue'

const router = useRouter()
const chatStore = useChatStore()
const workflowStore = useWorkflowStore()
const messageListRef = ref<HTMLElement | null>(null)
const showWorkflowPanel = ref(false)

const scrollToBottom = () => {
  nextTick(() => {
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  })
}

const handleSend = async (content: string) => {
  await chatStore.sendMessage(content)
}

// 快捷建议列表
const suggestions = [
  '分析贵州茅台',
  '推荐低估值股票',
  '今日大盘走势',
  '查看我的工作流',
]

// 执行工作流
const handleExecuteWorkflow = async (workflow: any) => {
  showWorkflowPanel.value = false
  // 构建执行命令
  const varNames = workflow.variables?.map((v: any) => v.label).join('、') || ''
  const prompt = varNames 
    ? `执行工作流"${workflow.name}"，需要填写：${varNames}`
    : `执行工作流"${workflow.name}"`
  await chatStore.sendMessage(prompt)
}

// 跳转到工作流页面
const goToWorkflow = () => {
  router.push('/workflow')
}

// Auto scroll when messages change or streaming content updates
watch(
  () => [chatStore.messages.length, chatStore.streamingContent],
  () => scrollToBottom(),
  { deep: true }
)

onMounted(async () => {
  chatStore.initSession()
  // 预加载工作流列表
  try {
    if (workflowStore.workflows.length === 0) {
      await workflowStore.loadWorkflows()
    }
    if (workflowStore.templates.length === 0) {
      await workflowStore.loadTemplates()
    }
  } catch (e) {
    console.warn('Failed to preload workflows:', e)
  }
})
</script>

<template>
  <div class="chat-view">
    <div class="chat-container">
      <div ref="messageListRef" class="message-area">
        <MessageList :messages="chatStore.messages" :loading="chatStore.loading" />
      </div>
      
      <div class="input-area">
        <div class="suggestions-row">
          <div class="suggestions">
            <t-tag
              v-for="suggestion in suggestions"
              :key="suggestion"
              theme="primary"
              variant="light"
              class="suggestion-tag"
              @click="handleSend(suggestion)"
            >
              {{ suggestion }}
            </t-tag>
          </div>
          <t-button 
            size="small" 
            variant="outline"
            @click="showWorkflowPanel = !showWorkflowPanel"
          >
            <template #icon><t-icon name="queue" /></template>
            工作流
          </t-button>
        </div>
        
        <!-- 工作流快捷面板 -->
        <div v-if="showWorkflowPanel" class="workflow-panel">
          <div class="workflow-panel-header">
            <span>快捷执行工作流</span>
            <t-button size="small" variant="text" @click="goToWorkflow">管理工作流</t-button>
          </div>
          <div class="workflow-list">
            <div 
              v-for="workflow in workflowStore.templates.slice(0, 5)" 
              :key="workflow.id"
              class="workflow-item"
              @click="handleExecuteWorkflow(workflow)"
            >
              <t-icon name="play-circle" />
              <div class="workflow-info">
                <span class="workflow-name">{{ workflow.name }}</span>
                <span class="workflow-desc">{{ workflow.description }}</span>
              </div>
            </div>
            <div 
              v-for="workflow in workflowStore.userWorkflows.slice(0, 3)" 
              :key="workflow.id"
              class="workflow-item"
              @click="handleExecuteWorkflow(workflow)"
            >
              <t-icon name="play-circle" />
              <div class="workflow-info">
                <span class="workflow-name">{{ workflow.name }}</span>
                <span class="workflow-desc">{{ workflow.description || '自定义工作流' }}</span>
              </div>
            </div>
          </div>
        </div>
        
        <InputBox @send="handleSend" :disabled="chatStore.loading" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-view {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
}

.message-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.input-area {
  border-top: 1px solid #e7e7e7;
  padding: 16px 20px;
}

.suggestions-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.suggestions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.suggestion-tag {
  cursor: pointer;
}

.suggestion-tag:hover {
  opacity: 0.8;
}

/* 工作流面板 */
.workflow-panel {
  background: var(--td-bg-color-secondarycontainer, #f5f5f5);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}

.workflow-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--td-text-color-secondary);
}

.workflow-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.workflow-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: var(--td-bg-color-container, #fff);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.workflow-item:hover {
  background: var(--td-brand-color-light, #e8f4ff);
}

.workflow-info {
  flex: 1;
  min-width: 0;
}

.workflow-name {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: var(--td-text-color-primary);
}

.workflow-desc {
  display: block;
  font-size: 12px;
  color: var(--td-text-color-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>

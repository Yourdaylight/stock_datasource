<script setup lang="ts">
import { ref, nextTick, onMounted, watch, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { MessagePlugin, DialogPlugin } from 'tdesign-vue-next'
import { useChatStore } from '@/stores/chat'
import MessageList from './components/MessageList.vue'
import InputBox from './components/InputBox.vue'
import AgentDebugSidebar from './components/AgentDebugSidebar.vue'
import AgentDiscussionSidebar from './components/AgentDiscussionSidebar.vue'
import AkinatorPanel from './components/AkinatorPanel.vue'
import WechatPushPrompt from './components/WechatPushPrompt.vue'

const router = useRouter()
const route = useRoute()
const chatStore = useChatStore()
// Agent teams loaded on mount
const messageListRef = ref<HTMLElement | null>(null)
const showTeamPanel = ref(false)
const agentTeams = ref<any[]>([])

// Load agent teams from orchestration pipelines
const loadTeams = async () => {
  try {
    const { listPipelines } = await import('@/api/orchestration')
    const res = await listPipelines()
    agentTeams.value = Array.isArray(res) ? res : (res as any).data || []
  } catch { /* ignore */ }
}

const handleTeamChat = (team: any) => {
  // Send team name as message to trigger multi-agent collaboration
  const msg = `请使用"${team.name}"团队模式来协作处理我的下一个问题`
  showTeamPanel.value = false
  handleSend(msg)
}
const showSessionsSidebar = ref(false)
const editingSessionId = ref('')
const editingTitle = ref('')

const activeTab = ref<'chat' | 'akinator'>('chat')

// Discussion sidebar state — synced from store when arena events arrive
const showDiscussionSidebar = computed({
  get: () => chatStore.decisionSidebarOpen,
  set: (val: boolean) => { chatStore.decisionSidebarOpen = val }
})
const discussionStockCode = ref<string | null>(null)

// Extract stock code from latest messages for discussion sidebar
const extractStockFromMessages = () => {
  const recentMessages = chatStore.messages.slice(-5)
  const stockPattern = /(\d{6}\.(SH|SZ|HK)|\d{6})/
  for (const msg of recentMessages.reverse()) {
    const match = msg.content?.match(stockPattern)
    if (match) {
      return match[1]
    }
  }
  return null
}

// Toggle discussion sidebar
const toggleDiscussionSidebar = () => {
  showDiscussionSidebar.value = !showDiscussionSidebar.value
  if (showDiscussionSidebar.value) {
    discussionStockCode.value = extractStockFromMessages()
  }
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  })
}

const handleSend = async (content: string) => {
  try {
    await chatStore.sendMessage(content)
  } catch (e) {
    console.error('Failed to send chat message:', e)
    MessagePlugin.error('发送消息失败，请重新登录后重试')
  }
}

// Quick suggestions
const suggestions = [
  '分析贵州茅台',
  '分析腾讯控股 00700.HK',
  '推荐低估值股票',
  '今日大盘走势',
]

// Format session time
const formatSessionTime = (timeStr: string) => {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  
  if (days === 0) {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } else if (days === 1) {
    return '昨天'
  } else if (days < 7) {
    return `${days}天前`
  } else {
    return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
  }
}

// Get session display title
const getSessionTitle = (session: any) => {
  return session.title || `会话 ${session.session_id.slice(-6)}`
}

// Create new conversation
const handleNewConversation = async () => {
  try {
    await chatStore.newConversation()
    // Update URL to new session
    if (chatStore.sessionId) {
      router.replace({ params: { sessionId: chatStore.sessionId } })
    }
    MessagePlugin.success('已创建新对话')
  } catch (e) {
    console.error('Failed to create new conversation:', e)
    MessagePlugin.error('创建新对话失败，请检查登录状态')
  }
}

// Switch to a session
const handleSwitchSession = async (sessionId: string) => {
  if (sessionId === chatStore.sessionId) return
  const success = await chatStore.switchSession(sessionId)
  if (success) {
    showSessionsSidebar.value = false
    // Update URL to reflect current session
    router.replace({ params: { sessionId } })
  } else {
    MessagePlugin.error('切换历史对话失败，请检查登录状态或会话权限')
  }
}

// Delete a session
const handleDeleteSession = async (sessionId: string, e: Event) => {
  e.stopPropagation()
  
  const dialogInstance = DialogPlugin.confirm({
    header: '删除对话',
    body: '确定要删除这个对话吗？删除后无法恢复。',
    confirmBtn: { content: '删除', theme: 'danger' },
    cancelBtn: '取消',
    onConfirm: async () => {
      dialogInstance.hide()
      const success = await chatStore.deleteSession(sessionId)
      if (success) {
        MessagePlugin.success('已删除对话')
      } else {
        MessagePlugin.error('删除失败')
      }
    }
  })
}

// Start editing session title
const startEditTitle = (session: any, e: Event) => {
  e.stopPropagation()
  editingSessionId.value = session.session_id
  editingTitle.value = session.title || ''
}

// Save session title
const saveSessionTitle = async () => {
  if (editingSessionId.value && editingTitle.value.trim()) {
    await chatStore.updateSessionTitle(editingSessionId.value, editingTitle.value.trim())
  }
  editingSessionId.value = ''
  editingTitle.value = ''
}

// Cancel editing
const cancelEditTitle = () => {
  editingSessionId.value = ''
  editingTitle.value = ''
}

// Clear current conversation
const handleClearConversation = () => {
  const dialogInstance = DialogPlugin.confirm({
    header: '清空对话',
    body: '确定要清空当前对话的消息吗？',
    confirmBtn: '清空',
    cancelBtn: '取消',
    onConfirm: () => {
      dialogInstance.hide()
      chatStore.clearCurrentConversation()
      MessagePlugin.success('已清空当前对话')
    }
  })
}

// deprecated workflow handlers removed

// Computed: grouped sessions by date
const groupedSessions = computed(() => {
  const today: any[] = []
  const yesterday: any[] = []
  const thisWeek: any[] = []
  const earlier: any[] = []
  
  const now = new Date()
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterdayStart = new Date(todayStart.getTime() - 24 * 60 * 60 * 1000)
  const weekStart = new Date(todayStart.getTime() - 7 * 24 * 60 * 60 * 1000)
  
  chatStore.sessions.forEach(session => {
    const sessionDate = new Date(session.last_message_at || session.created_at)
    if (sessionDate >= todayStart) {
      today.push(session)
    } else if (sessionDate >= yesterdayStart) {
      yesterday.push(session)
    } else if (sessionDate >= weekStart) {
      thisWeek.push(session)
    } else {
      earlier.push(session)
    }
  })
  
  return { today, yesterday, thisWeek, earlier }
})

// Auto scroll when messages change
watch(
  () => [chatStore.messages.length, chatStore.streamingContent],
  () => scrollToBottom(),
  { deep: true }
)

onMounted(async () => {
  const urlSessionId = route.params.sessionId as string | undefined

  try {
    // Always load sessions list first
    await chatStore.loadSessions()

    if (urlSessionId && urlSessionId !== chatStore.sessionId) {
      // URL has a session ID — check if it's valid before switching
      const sessionExists = chatStore.sessions.some(s => s.session_id === urlSessionId)
      if (sessionExists) {
        await chatStore.switchSession(urlSessionId)
      } else {
        // Invalid session, silently fall back to normal init (no warning spam)
        await chatStore.restoreOrInitSession()
        syncUrlToSession()
      }
    } else if (!urlSessionId) {
      // No session in URL — restore normally, then update URL once
      await chatStore.restoreOrInitSession()
      syncUrlToSession()
    }
    // If urlSessionId === chatStore.sessionId, do nothing (already there)
  } catch (e) {
    console.error('Failed to restore chat session:', e)
    MessagePlugin.error('加载历史对话失败，请重新登录后重试')
  }

  // 加载Agent Teams
  loadTeams()
})

// Sync URL to current session (silent, no component remount)
const syncUrlToSession = () => {
  if (!chatStore.sessionId) return
  const currentUrlSession = route.params.sessionId
  if (currentUrlSession !== chatStore.sessionId) {
    router.replace({ params: { sessionId: chatStore.sessionId } })
  }
}
</script>

<template>
  <div class="chat-root">
    <div class="chat-tabs-bar">
      <t-tabs v-model="activeTab" size="medium">
        <t-tab-panel value="chat" label="智能对话" />
        <t-tab-panel value="akinator" label="🔮 猜你所想" />
      </t-tabs>
    </div>

    <!-- Akinator Tab -->
    <div v-show="activeTab === 'akinator'" class="chat-tab-content">
      <AkinatorPanel />
    </div>

    <!-- Chat Tab (原有内容) -->
    <div v-show="activeTab === 'chat'" class="chat-tab-content">
    <div class="chat-view">
    <!-- Sessions Sidebar -->
    <div :class="['sessions-sidebar', { expanded: showSessionsSidebar }]">
      <div class="sidebar-header">
        <h3>历史对话</h3>
        <t-button theme="primary" size="small" @click="handleNewConversation">
          <template #icon><t-icon name="add" /></template>
          新对话
        </t-button>
      </div>
      
      <div class="sessions-list">
        <t-loading v-if="chatStore.sessionsLoading" size="small" />
        <template v-else>
          <!-- Today -->
          <div v-if="groupedSessions.today.length" class="session-group">
            <div class="group-label">今天</div>
            <div
              v-for="session in groupedSessions.today"
              :key="session.session_id"
              :class="['session-item', { active: session.session_id === chatStore.sessionId }]"
              @click="handleSwitchSession(session.session_id)"
            >
              <div class="session-content">
                <template v-if="editingSessionId === session.session_id">
                  <t-input
                    v-model="editingTitle"
                    size="small"
                    placeholder="输入标题"
                    @blur="saveSessionTitle"
                    @keyup.enter="saveSessionTitle"
                    @keyup.escape="cancelEditTitle"
                    autofocus
                    @click.stop
                  />
                </template>
                <template v-else>
                  <div class="session-title">{{ getSessionTitle(session) }}</div>
                  <div class="session-meta">
                    <span>{{ session.message_count }}条消息</span>
                    <span>{{ formatSessionTime(session.last_message_at) }}</span>
                  </div>
                </template>
              </div>
              <div class="session-actions" v-if="editingSessionId !== session.session_id">
                <t-button theme="default" variant="text" size="small" @click="startEditTitle(session, $event)">
                  <t-icon name="edit" />
                </t-button>
                <t-button theme="danger" variant="text" size="small" @click="handleDeleteSession(session.session_id, $event)">
                  <t-icon name="delete" />
                </t-button>
              </div>
            </div>
          </div>

          <!-- Yesterday -->
          <div v-if="groupedSessions.yesterday.length" class="session-group">
            <div class="group-label">昨天</div>
            <div
              v-for="session in groupedSessions.yesterday"
              :key="session.session_id"
              :class="['session-item', { active: session.session_id === chatStore.sessionId }]"
              @click="handleSwitchSession(session.session_id)"
            >
              <div class="session-content">
                <template v-if="editingSessionId === session.session_id">
                  <t-input
                    v-model="editingTitle"
                    size="small"
                    placeholder="输入标题"
                    @blur="saveSessionTitle"
                    @keyup.enter="saveSessionTitle"
                    @keyup.escape="cancelEditTitle"
                    autofocus
                    @click.stop
                  />
                </template>
                <template v-else>
                  <div class="session-title">{{ getSessionTitle(session) }}</div>
                  <div class="session-meta">
                    <span>{{ session.message_count }}条消息</span>
                    <span>{{ formatSessionTime(session.last_message_at) }}</span>
                  </div>
                </template>
              </div>
              <div class="session-actions" v-if="editingSessionId !== session.session_id">
                <t-button theme="default" variant="text" size="small" @click="startEditTitle(session, $event)">
                  <t-icon name="edit" />
                </t-button>
                <t-button theme="danger" variant="text" size="small" @click="handleDeleteSession(session.session_id, $event)">
                  <t-icon name="delete" />
                </t-button>
              </div>
            </div>
          </div>

          <!-- This Week -->
          <div v-if="groupedSessions.thisWeek.length" class="session-group">
            <div class="group-label">本周</div>
            <div
              v-for="session in groupedSessions.thisWeek"
              :key="session.session_id"
              :class="['session-item', { active: session.session_id === chatStore.sessionId }]"
              @click="handleSwitchSession(session.session_id)"
            >
              <div class="session-content">
                <template v-if="editingSessionId === session.session_id">
                  <t-input
                    v-model="editingTitle"
                    size="small"
                    placeholder="输入标题"
                    @blur="saveSessionTitle"
                    @keyup.enter="saveSessionTitle"
                    @keyup.escape="cancelEditTitle"
                    autofocus
                    @click.stop
                  />
                </template>
                <template v-else>
                  <div class="session-title">{{ getSessionTitle(session) }}</div>
                  <div class="session-meta">
                    <span>{{ session.message_count }}条消息</span>
                    <span>{{ formatSessionTime(session.last_message_at) }}</span>
                  </div>
                </template>
              </div>
              <div class="session-actions" v-if="editingSessionId !== session.session_id">
                <t-button theme="default" variant="text" size="small" @click="startEditTitle(session, $event)">
                  <t-icon name="edit" />
                </t-button>
                <t-button theme="danger" variant="text" size="small" @click="handleDeleteSession(session.session_id, $event)">
                  <t-icon name="delete" />
                </t-button>
              </div>
            </div>
          </div>

          <!-- Earlier -->
          <div v-if="groupedSessions.earlier.length" class="session-group">
            <div class="group-label">更早</div>
            <div
              v-for="session in groupedSessions.earlier"
              :key="session.session_id"
              :class="['session-item', { active: session.session_id === chatStore.sessionId }]"
              @click="handleSwitchSession(session.session_id)"
            >
              <div class="session-content">
                <template v-if="editingSessionId === session.session_id">
                  <t-input
                    v-model="editingTitle"
                    size="small"
                    placeholder="输入标题"
                    @blur="saveSessionTitle"
                    @keyup.enter="saveSessionTitle"
                    @keyup.escape="cancelEditTitle"
                    autofocus
                    @click.stop
                  />
                </template>
                <template v-else>
                  <div class="session-title">{{ getSessionTitle(session) }}</div>
                  <div class="session-meta">
                    <span>{{ session.message_count }}条消息</span>
                    <span>{{ formatSessionTime(session.last_message_at) }}</span>
                  </div>
                </template>
              </div>
              <div class="session-actions" v-if="editingSessionId !== session.session_id">
                <t-button theme="default" variant="text" size="small" @click="startEditTitle(session, $event)">
                  <t-icon name="edit" />
                </t-button>
                <t-button theme="danger" variant="text" size="small" @click="handleDeleteSession(session.session_id, $event)">
                  <t-icon name="delete" />
                </t-button>
              </div>
            </div>
          </div>

          <!-- Empty State -->
          <div v-if="chatStore.sessions.length === 0" class="empty-sessions">
            <t-icon name="chat" size="32px" />
            <p>暂无历史对话</p>
          </div>
        </template>
      </div>
    </div>
    
    <!-- Main Chat Container -->
    <div class="chat-container">
      <!-- Chat Header -->
      <div class="chat-header">
        <div class="header-left">
          <t-button 
            theme="default" 
            variant="text"
            @click="showSessionsSidebar = !showSessionsSidebar"
          >
            <template #icon><t-icon :name="showSessionsSidebar ? 'chevron-left' : 'menu-fold'" /></template>
          </t-button>
          <span class="current-session-title">
            {{ chatStore.currentSessionTitle || '新对话' }}
          </span>
        </div>
        <div class="header-right">
          <t-button 
            theme="default" 
            variant="text"
            :disabled="chatStore.messages.length === 0"
            @click="handleClearConversation"
          >
            <template #icon><t-icon name="clear" /></template>
            清空
          </t-button>
          <t-button
            :theme="chatStore.debugSidebarOpen ? 'primary' : 'default'"
            variant="text"
            @click="chatStore.debugSidebarOpen = !chatStore.debugSidebarOpen"
            title="Agent 链路追踪"
          >
            <template #icon><t-icon name="flow" /></template>
            链路
          </t-button>
          <t-button
            :theme="showDiscussionSidebar ? 'primary' : 'default'"
            variant="text"
            @click="toggleDiscussionSidebar"
            title="多智能体决策"
          >
            <template #icon><t-icon name="user-talk" /></template>
            决策
          </t-button>
          <t-button
            theme="primary"
            variant="text"
            @click="handleNewConversation"
          >
            <template #icon><t-icon name="add" /></template>
            新对话
          </t-button>
        </div>
      </div>
      
      <div class="main-content-area">
        <div ref="messageListRef" class="message-area">
          <MessageList
            :messages="chatStore.messages"
            :loading="chatStore.loading"
            @quick-action="handleSend"
          />
        </div>
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
            @click="showTeamPanel = !showTeamPanel"
          >
            <template #icon><t-icon name="usergroup" /></template>
            Agent Teams
          </t-button>
        </div>

        <!-- Agent Teams Panel -->
        <div v-if="showTeamPanel" class="workflow-panel">
          <div class="workflow-panel-header">
            <span>Agent 团队</span>
            <t-button size="small" variant="text" @click="router.push('/orchestration')">管理团队</t-button>
          </div>
          <div class="workflow-list">
            <div
              v-for="team in agentTeams"
              :key="team.id"
              class="workflow-item"
              @click="handleTeamChat(team)"
            >
              <t-icon name="usergroup" />
              <div class="workflow-info">
                <span class="workflow-name">{{ team.name }}</span>
                <span class="workflow-desc">{{ team.description || '多Agent协作' }}</span>
              </div>
            </div>
            <div v-if="agentTeams.length === 0" class="workflow-item" style="color:#bbb;justify-content:center">
              暂无团队，去Agent中心创建
            </div>
          </div>
        </div>
        
        <InputBox @send="handleSend" :disabled="chatStore.loading" />
      </div>
    </div>

    <!-- Debug Sidebar -->
    <AgentDebugSidebar />

    <!-- Agent Discussion Sidebar -->
    <AgentDiscussionSidebar
      :visible="showDiscussionSidebar"
      :stock-code="discussionStockCode"
      @close="showDiscussionSidebar = false"
    />

    <!-- WeChat Push Prompt (shows after 3rd analysis) -->
    <WechatPushPrompt />
    </div>
    </div>
  </div>
</template>

<style scoped>
.chat-root {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-tabs-bar {
  flex-shrink: 0;
  padding: 0 16px;
  background: var(--td-bg-color-container);
  border-bottom: 1px solid var(--td-component-stroke);
}

.chat-tabs-bar :deep(.t-tabs__content) {
  display: none;
}

.chat-tab-content {
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

.chat-view {
  height: 100%;
  display: flex;
  position: relative;
}

/* Sessions Sidebar */
.sessions-sidebar {
  width: 0;
  overflow: hidden;
  background: var(--td-bg-color-container, #fff);
  border-right: 1px solid var(--td-component-stroke, #e7e7e7);
  transition: width 0.3s ease;
  display: flex;
  flex-direction: column;
}

.sessions-sidebar.expanded {
  width: 280px;
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--td-component-stroke, #e7e7e7);
}

.sidebar-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.sessions-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.session-group {
  margin-bottom: 16px;
}

.group-label {
  font-size: 12px;
  color: var(--td-text-color-secondary, #888);
  padding: 4px 8px;
  font-weight: 500;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.session-item:hover {
  background: var(--td-bg-color-secondarycontainer, #f5f5f5);
}

.session-item.active {
  background: var(--td-brand-color-light, #e8f4ff);
  border-left: 3px solid var(--td-brand-color, #0052d9);
}

.session-content {
  flex: 1;
  min-width: 0;
}

.session-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--td-text-color-primary, #333);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-meta {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: var(--td-text-color-secondary, #888);
  margin-top: 2px;
}

.session-actions {
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.2s;
}

.session-item:hover .session-actions {
  opacity: 1;
}

.empty-sessions {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: var(--td-text-color-secondary, #888);
}

.empty-sessions p {
  margin-top: 8px;
  font-size: 14px;
}

/* Chat Container */
.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #fff;
  overflow: hidden;
  min-width: 0;
}

/* Chat Header */
.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  border-bottom: 1px solid var(--td-component-stroke, #e7e7e7);
  background: var(--td-bg-color-container, #fff);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.current-session-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--td-text-color-primary, #333);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 4px;
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

/* Workflow Panel */
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

/* Main Content Area */
.main-content-area {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  background: var(--td-bg-color, #ffffff);
}

.message-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  min-height: 0;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

</style>

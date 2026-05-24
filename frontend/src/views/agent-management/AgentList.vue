<template>
  <div class="agent-list-page">
    <!-- Header -->
    <div class="page-header">
      <div class="header-left">
        <h2>AI Agent 投研</h2>
        <span class="subtitle">配置投研角色、团队协作和研究任务</span>
      </div>
      <t-button theme="primary" @click="handleCreate">
        <template #icon><add-icon /></template>
        创建投研 Agent
      </t-button>
    </div>

    <!-- Filters -->
    <div class="filter-bar">
      <t-input
        v-model="searchQuery"
        placeholder="搜索投研 Agent、覆盖领域或技能..."
        clearable
        style="width: 240px"
      >
        <template #prefix-icon><search-icon /></template>
      </t-input>
      <t-radio-group v-model="filterType" variant="default-filled">
        <t-radio-button value="all">全部</t-radio-button>
        <t-radio-button value="mine">我的角色</t-radio-button>
        <t-radio-button value="system">系统角色</t-radio-button>
      </t-radio-group>
    </div>

    <!-- Agent Grid -->
    <div class="agent-grid" v-if="!loading">
      <div
        v-for="agent in filteredAgents"
        :key="agent.id"
        class="agent-card"
        @click="handleEdit(agent.id)"
      >
        <div class="card-header">
          <span class="agent-avatar">{{ agent.avatar || '🤖' }}</span>
          <div class="card-badges">
            <t-tag v-if="agent.user_id === 'system'" size="small" theme="warning">系统</t-tag>
            <t-tag v-if="agent.is_public" size="small" theme="success">公开</t-tag>
          </div>
        </div>
        <div class="card-body">
          <h3 class="agent-name">{{ agent.name }}</h3>
          <p class="agent-desc">{{ agent.description || '暂无描述' }}</p>
        </div>
        <div class="agent-meta">
          <t-tag v-for="tag in getResearchTags(agent)" :key="tag" size="small" variant="light">
            {{ tag }}
          </t-tag>
        </div>
        <div class="card-footer">
          <span class="skill-count">
            <t-tag size="small" variant="light">{{ agent.skills.length }} 个数据/工具能力</t-tag>
          </span>
          <div class="card-actions" @click.stop>
            <t-dropdown
              :options="[
                { content: '编辑', value: 'edit' },
                { content: '复制', value: 'clone' },
                { content: '删除', value: 'delete', theme: 'error' }
              ]"
              @click="handleAction($event, agent)"
            >
              <t-button variant="text" size="small" shape="square">
                <template #icon><more-icon /></template>
              </t-button>
            </t-dropdown>
          </div>
        </div>
      </div>

      <!-- Empty state -->
      <div v-if="filteredAgents.length === 0" class="empty-state">
        <p>暂无投研 Agent</p>
        <t-button theme="primary" variant="base" @click="handleCreate">创建第一个投研 Agent</t-button>
      </div>
    </div>

    <!-- Loading -->
    <div v-else class="loading-state">
      <t-loading />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { MessagePlugin, DialogPlugin } from 'tdesign-vue-next'
import { AddIcon, SearchIcon, MoreIcon } from 'tdesign-icons-vue-next'
import { listAgents, deleteAgent, createAgent } from '@/api/agent'
import type { AgentConfig } from '@/api/agent'

const router = useRouter()
const route = useRoute()
const agents = ref<AgentConfig[]>([])
const loading = ref(true)
const searchQuery = ref('')
const filterType = ref('all')
const highlightAgentName = ref('')

const filteredAgents = computed(() => {
  let result = agents.value
  if (filterType.value === 'mine') {
    result = result.filter(a => a.user_id !== 'system')
  } else if (filterType.value === 'system') {
    result = result.filter(a => a.user_id === 'system')
  }
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    result = result.filter(
      a =>
        a.name.toLowerCase().includes(q) ||
        a.description.toLowerCase().includes(q) ||
        a.skills.some(skill => skill.toLowerCase().includes(q)) ||
        a.tags.some(tag => tag.toLowerCase().includes(q))
    )
  }
  return result
})

function getResearchTags(agent: AgentConfig) {
  const tags = [...(agent.tags || [])]
  const skillText = (agent.skills || []).join(' ')
  if (/portfolio|position|risk|组合|持仓/i.test(`${agent.name} ${agent.description} ${skillText}`)) {
    tags.unshift('组合/风控')
  } else if (/report|financial|fundamental|财报|基本面/i.test(`${agent.name} ${agent.description} ${skillText}`)) {
    tags.unshift('基本面')
  } else if (/market|technical|kline|行情|技术/i.test(`${agent.name} ${agent.description} ${skillText}`)) {
    tags.unshift('行情/技术')
  } else if (/news|sentiment|新闻|舆情/i.test(`${agent.name} ${agent.description} ${skillText}`)) {
    tags.unshift('新闻/舆情')
  }
  return Array.from(new Set(tags)).slice(0, 3)
}

async function loadAgents() {
  loading.value = true
  try {
    const res = await listAgents()
    agents.value = Array.isArray(res) ? res : (res as any).data || []
  } catch (e: any) {
    MessagePlugin.error('加载 Agent 列表失败')
  } finally {
    loading.value = false
  }
}

function handleCreate() {
  router.push('/agents/new/edit')
}

function handleEdit(id: string) {
  router.push(`/agents/${id}/edit`)
}

async function handleAction(data: { value: string }, agent: AgentConfig) {
  if (data.value === 'edit') {
    handleEdit(agent.id)
  } else if (data.value === 'clone') {
    try {
      await createAgent({
        name: agent.name + ' (投研副本)',
        description: agent.description,
        avatar: agent.avatar,
        system_prompt: agent.system_prompt,
        skills: agent.skills,
        model_config_data: agent.model_config_data,
        tags: agent.tags,
      })
      MessagePlugin.success('复制成功')
      await loadAgents()
    } catch (e: any) {
      MessagePlugin.error('复制失败')
    }
  } else if (data.value === 'delete') {
    const dialog = DialogPlugin.confirm({
      header: '确认删除',
      body: `确定删除投研 Agent "${agent.name}" 吗？`,
      confirmBtn: { theme: 'danger', content: '删除' },
      onConfirm: async () => {
        try {
          await deleteAgent(agent.id)
          MessagePlugin.success('删除成功')
          await loadAgents()
        } catch (e: any) {
          MessagePlugin.error('删除失败')
        }
        dialog.destroy()
      },
    })
  }
}

onMounted(async () => {
  await loadAgents()
  // 如果从chat调试面板跳过来，高亮对应agent
  const hl = route.query.highlight as string
  if (hl) {
    highlightAgentName.value = hl
    // 如果找到匹配的agent，直接跳转到编辑页
    const found = agents.value.find(a => a.name === hl)
    if (found) {
      router.push(`/agents/${found.id}/edit`)
    }
  }
})
</script>

<style scoped>
.agent-list-page {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header-left h2 {
  margin: 0;
  font-size: 20px;
}

.subtitle {
  color: #8c8c8c;
  font-size: 13px;
  margin-left: 12px;
}

.filter-bar {
  display: flex;
  gap: 16px;
  align-items: center;
  margin-bottom: 20px;
}

.agent-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 16px;
}

.agent-card {
  border: 1px solid #e7e7e7;
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s;
  background: white;
}

.agent-card:hover {
  border-color: #0052d9;
  box-shadow: 0 2px 8px rgba(0, 82, 217, 0.1);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.agent-avatar {
  font-size: 32px;
  line-height: 1;
}

.card-badges {
  display: flex;
  gap: 4px;
}

.card-body {
  margin-bottom: 12px;
}

.agent-name {
  font-size: 15px;
  font-weight: 600;
  margin: 0 0 4px 0;
  color: #1d2129;
}

.agent-desc {
  font-size: 12px;
  color: #8c8c8c;
  margin: 0;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.agent-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 8px 0 12px;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.empty-state {
  grid-column: 1 / -1;
  text-align: center;
  padding: 60px 0;
  color: #8c8c8c;
}

.loading-state {
  text-align: center;
  padding: 60px 0;
}
</style>

<template>
  <div class="agent-editor-page">
    <!-- Header -->
    <div class="page-header">
      <div class="header-left">
        <t-button variant="text" @click="goBack">
          <template #icon><chevron-left-icon /></template>
          返回
        </t-button>
        <h2>{{ isNew ? '创建投研 Agent' : `编辑投研 Agent: ${form.name}` }}</h2>
      </div>
      <t-space>
        <t-button variant="outline" @click="showTestPanel = !showTestPanel">测试</t-button>
        <t-button theme="primary" :loading="saving" @click="handleSave">保存</t-button>
      </t-space>
    </div>

    <!-- Main Content: 2 columns -->
    <div class="editor-layout">
      <!-- Left: Basic + Model + Runtime -->
      <div class="left-panel">
        <t-card title="基本信息" :bordered="true">
          <t-form :data="form" label-align="top">
            <t-form-item label="名称">
              <t-input v-model="form.name" placeholder="投研 Agent 名称，如 基本面研究员" maxlength="50" />
            </t-form-item>
            <t-form-item label="描述">
              <t-textarea v-model="form.description" placeholder="简要描述" :maxlength="500" :autosize="{ minRows: 2, maxRows: 3 }" />
            </t-form-item>
            <t-form-item label="图标">
              <t-input v-model="form.avatar" placeholder="🤖" maxlength="4" style="width: 80px" />
            </t-form-item>
            <t-form-item label="标签">
              <t-tag-input v-model="form.tags" placeholder="回车添加" />
            </t-form-item>
          </t-form>
        </t-card>

        <t-card title="模型配置" :bordered="true" class="mt-12">
          <t-form label-align="top">
            <t-form-item label="模型">
              <t-select v-model="form.model_config_data.model">
                <t-option value="DeepSeek-V4-Pro" label="DeepSeek-V4-Pro" />
                <t-option value="DeepSeek-V3" label="DeepSeek-V3" />
                <t-option value="DeepSeek-R1" label="DeepSeek-R1" />
                <t-option value="gpt-4o" label="GPT-4o" />
                <t-option value="gpt-4o-mini" label="GPT-4o Mini" />
              </t-select>
            </t-form-item>
            <t-form-item label="温度">
              <div class="slider-row">
                <t-slider v-model="form.model_config_data.temperature" :min="0" :max="2" :step="0.1" style="flex:1" />
                <span class="slider-val">{{ form.model_config_data.temperature }}</span>
              </div>
            </t-form-item>
            <t-form-item label="最大输出 Token">
              <t-input-number v-model="form.model_config_data.max_tokens" :min="64" :max="128000" :step="256" style="width:100%" />
            </t-form-item>
            <t-form-item label="最小输出 Token">
              <t-input-number v-model="form.model_config_data.min_tokens" :min="0" :max="16000" :step="64" style="width:100%" />
            </t-form-item>
          </t-form>
        </t-card>

        <t-card title="工具运行时" :bordered="true" class="mt-12">
          <t-form label-align="top">
            <t-form-item label="执行引擎">
              <t-select v-model="form.runtime_config.type">
                <t-option value="langgraph" label="LangGraph (本地LLM+MCP)" />
                <t-option value="claude" label="Claude CLI" />
                <t-option value="codebuddy" label="CodeBuddy CLI" />
              </t-select>
            </t-form-item>
            <template v-if="form.runtime_config.type !== 'langgraph'">
              <t-form-item label="命令路径">
                <t-input v-model="form.runtime_config.command" :placeholder="form.runtime_config.type === 'claude' ? '/usr/bin/claude' : '/usr/bin/codebuddy'" />
              </t-form-item>
              <t-form-item label="工作目录">
                <t-input v-model="form.runtime_config.working_dir" placeholder="/root/lzh/stock_datasource" />
              </t-form-item>
            </template>
          </t-form>
        </t-card>
      </div>

      <!-- Right: Prompt + Skills -->
      <div class="right-panel">
        <t-card title="系统提示词" :bordered="true">
          <t-textarea
            v-model="form.system_prompt"
            placeholder="定义投研角色、覆盖范围、证据要求、风险提示和输出格式..."
            :autosize="{ minRows: 8, maxRows: 16 }"
          />
        </t-card>

        <!-- Skills Tabs -->
        <t-card title="技能配置" :bordered="true" class="mt-12">
          <template #actions>
            <span class="skill-count-label">已选 {{ form.skills.length + form.user_skills.length }} 个</span>
          </template>
          <t-tabs v-model="skillTab">
            <t-tab-panel value="platform" label="平台工具">
              <t-input v-model="skillSearch" placeholder="搜索..." clearable size="small" style="margin-bottom:8px">
                <template #prefix-icon><search-icon /></template>
              </t-input>
              <div class="skill-list-scroll">
                <div v-for="(skills, category) in filteredPlatformSkills" :key="category" class="skill-category">
                  <div class="category-header">{{ category }} ({{ skills.length }})</div>
                  <div v-for="skill in skills" :key="skill.id" class="skill-item">
                    <t-checkbox :checked="form.skills.includes(skill.id)" @change="togglePlatformSkill(skill.id, $event)">
                      <span class="skill-name">{{ skill.name }}</span>
                      <span class="skill-desc" v-if="skill.description">{{ skill.description }}</span>
                    </t-checkbox>
                  </div>
                </div>
              </div>
            </t-tab-panel>

            <t-tab-panel value="user" label="用户 Skills">
              <div class="skill-list-scroll">
                <div v-for="skill in userSkills" :key="skill.id" class="skill-item skill-card">
                  <t-checkbox :checked="form.user_skills.includes(skill.id)" @change="toggleUserSkill(skill.id, $event)">
                    <span class="skill-emoji">{{ skill.emoji || '📦' }}</span>
                    <span class="skill-name">{{ skill.name }}</span>
                    <t-tag size="small" variant="light">{{ skill.source }}</t-tag>
                  </t-checkbox>
                  <div class="skill-desc">{{ skill.description }}</div>
                </div>
                <div v-if="userSkills.length === 0" class="empty-skills">暂无用户Skills</div>
              </div>
            </t-tab-panel>

            <t-tab-panel value="project" label="项目 Skills">
              <div class="skill-list-scroll">
                <div v-for="skill in projectSkills" :key="skill.id" class="skill-item skill-card">
                  <t-checkbox :checked="form.user_skills.includes(skill.id)" @change="toggleUserSkill(skill.id, $event)">
                    <span class="skill-name">{{ skill.name }}</span>
                  </t-checkbox>
                  <div class="skill-desc">{{ skill.description }}</div>
                </div>
                <div v-if="projectSkills.length === 0" class="empty-skills">暂无项目Skills</div>
              </div>
            </t-tab-panel>
          </t-tabs>
        </t-card>
      </div>
    </div>

    <!-- Call History -->
    <div class="history-section" v-if="!isNew">
      <t-card title="调用历史" :bordered="true">
        <template #actions>
          <t-tag size="small" variant="light">{{ callHistory.length }} 条</t-tag>
        </template>
        <t-table
          :data="callHistory"
          :columns="historyColumns"
          :max-height="300"
          row-key="time"
          size="small"
          stripe
          :empty="'暂无调用记录'"
        />
      </t-card>
    </div>

    <!-- Test Panel -->
    <div v-if="showTestPanel" class="test-panel">
        <t-card title="测试投研 Agent" :bordered="true" size="small">
        <template #actions>
          <t-button variant="text" size="small" @click="showTestPanel = false">关闭</t-button>
        </template>
        <div class="test-messages">
          <div v-for="(msg, idx) in testMessages" :key="idx" :class="['test-msg', msg.role]">
            <strong>{{ msg.role === 'user' ? '你' : '投研 Agent' }}:</strong>
            <span>{{ msg.content }}</span>
          </div>
        </div>
        <div class="test-input">
          <t-input v-model="testInput" placeholder="输入测试消息..." @keyup.enter="sendTest" />
          <t-button theme="primary" :loading="testing" @click="sendTest">发送</t-button>
        </div>
      </t-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { MessagePlugin } from 'tdesign-vue-next'
import { ChevronLeftIcon, SearchIcon } from 'tdesign-icons-vue-next'
import {
  getAgent, createAgent, updateAgent, listSkills, listUserSkills, listProjectSkills,
  getAgentHistory, getAgentTestUrl
} from '@/api/agent'
import { request } from '@/utils/request'
import type { SkillInfo, UserSkillInfo } from '@/api/agent'

const route = useRoute()
const router = useRouter()

const isNew = computed(() => route.params.id === 'new')
const saving = ref(false)
const testing = ref(false)
const showTestPanel = ref(false)
const skillSearch = ref('')
const skillTab = ref('platform')
const allPlatformSkills = ref<SkillInfo[]>([])
const userSkills = ref<UserSkillInfo[]>([])
const projectSkills = ref<UserSkillInfo[]>([])
const testMessages = ref<Array<{ role: string; content: string }>>([])
const testInput = ref('')
const callHistory = ref<any[]>([])

const form = ref({
  name: '',
  description: '',
  avatar: '🤖',
  system_prompt: '',
  skills: [] as string[],
  user_skills: [] as string[],
  model_config_data: {
    model: 'DeepSeek-V4-Pro',
    temperature: 0.7,
    max_tokens: 4096,
    min_tokens: 0,
  },
  runtime_config: {
    type: 'langgraph' as string,
    command: '',
    working_dir: '',
    env_vars: {} as Record<string, string>,
  },
  tags: [] as string[],
  is_public: false,
})

const historyColumns = [
  { colKey: 'time', title: '时间', width: 140, cell: (h: any, { row }: any) => row.time?.substring(5, 16) || '' },
  { colKey: 'agent', title: '触发投研角色', width: 120 },
  { colKey: 'tools_used', title: '使用工具', width: 200, cell: (h: any, { row }: any) => (row.tools_used || []).slice(0, 3).join(', ') || '—' },
  { colKey: 'input', title: '对话摘要', ellipsis: true },
]

// Platform skills grouped by category
const filteredPlatformSkills = computed(() => {
  const groups: Record<string, SkillInfo[]> = {}
  const q = skillSearch.value.toLowerCase()
  for (const skill of allPlatformSkills.value) {
    if (q && !skill.name.toLowerCase().includes(q) && !(skill.description || '').toLowerCase().includes(q)) continue
    const cat = skill.category || '其他'
    if (!groups[cat]) groups[cat] = []
    groups[cat].push(skill)
  }
  return groups
})

function togglePlatformSkill(id: string, checked: boolean) {
  if (checked) {
    if (!form.value.skills.includes(id)) form.value.skills.push(id)
  } else {
    form.value.skills = form.value.skills.filter(s => s !== id)
  }
}

function toggleUserSkill(id: string, checked: boolean) {
  if (checked) {
    if (!form.value.user_skills.includes(id)) form.value.user_skills.push(id)
  } else {
    form.value.user_skills = form.value.user_skills.filter(s => s !== id)
  }
}

async function loadAgent() {
  if (isNew.value) return
  try {
    const res = await getAgent(route.params.id as string)
    const agent = (res as any).id ? res : (res as any).data
    form.value = {
      name: agent.name,
      description: agent.description,
      avatar: agent.avatar || '🤖',
      system_prompt: agent.system_prompt,
      skills: agent.skills || [],
      user_skills: agent.user_skills || [],
      model_config_data: {
        model: agent.model_config_data?.model || 'DeepSeek-V4-Pro',
        temperature: agent.model_config_data?.temperature ?? 0.7,
        max_tokens: agent.model_config_data?.max_tokens || 4096,
        min_tokens: agent.model_config_data?.min_tokens || 0,
      },
      runtime_config: {
        type: agent.runtime_config?.type || 'langgraph',
        command: agent.runtime_config?.command || '',
        working_dir: agent.runtime_config?.working_dir || '',
        env_vars: agent.runtime_config?.env_vars || {},
      },
      tags: agent.tags || [],
      is_public: agent.is_public,
    }
  } catch (e: any) {
    MessagePlugin.error('加载投研 Agent 失败')
  }
}

async function loadSkills() {
  try {
    const [platform, user, project] = await Promise.allSettled([
      listSkills(),
      listUserSkills(),
      listProjectSkills(),
    ])
    if (platform.status === 'fulfilled') {
      const data = platform.value as any
      allPlatformSkills.value = Array.isArray(data) ? data : data?.data || []
    }
    if (user.status === 'fulfilled') {
      const data = user.value as any
      userSkills.value = Array.isArray(data) ? data : data?.data || []
    }
    if (project.status === 'fulfilled') {
      const data = project.value as any
      projectSkills.value = Array.isArray(data) ? data : data?.data || []
    }
  } catch (e: any) {
    console.warn('Load skills failed:', e)
  }
}

async function loadCallHistory() {
  try {
    const res = await getAgentHistory(route.params.id as string)
    callHistory.value = Array.isArray(res) ? res : (res as any).data || []
  } catch {
    callHistory.value = []
  }
}

async function handleSave() {
  if (!form.value.name.trim()) { MessagePlugin.warning('请输入名称'); return }
  if (!form.value.system_prompt.trim()) { MessagePlugin.warning('请输入提示词'); return }
  saving.value = true
  try {
    if (isNew.value) {
      const res = await createAgent(form.value as any)
      MessagePlugin.success('创建成功')
      const id = (res as any).id || (res as any).data?.id
      router.replace(`/agents/${id}/edit`)
    } else {
      await updateAgent(route.params.id as string, form.value as any)
      MessagePlugin.success('保存成功')
    }
  } catch (e: any) {
    MessagePlugin.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function sendTest() {
  if (!testInput.value.trim()) return
  const msg = testInput.value.trim()
  testInput.value = ''
  testMessages.value.push({ role: 'user', content: msg })
  testing.value = true
  try {
    if (isNew.value) { testMessages.value.push({ role: 'assistant', content: '请先保存' }); return }
    const url = getAgentTestUrl(route.params.id as string, msg)
    const eventSource = new EventSource(url)
    let text = ''
    testMessages.value.push({ role: 'assistant', content: '' })
    const idx = testMessages.value.length - 1
    eventSource.onmessage = (event) => {
      if (event.data === '[DONE]') { eventSource.close(); testing.value = false; return }
      if (event.data.startsWith('[ERROR]')) { testMessages.value[idx].content = event.data; eventSource.close(); testing.value = false; return }
      text += event.data
      testMessages.value[idx].content = text
    }
    eventSource.onerror = () => { eventSource.close(); testing.value = false }
  } catch { testing.value = false }
}

function goBack() { router.push('/agents') }

onMounted(async () => {
  await Promise.all([loadAgent(), loadSkills()])
  if (!isNew.value) loadCallHistory()
})
</script>

<style scoped>
.agent-editor-page { padding: 20px; max-width: 1400px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.header-left { display: flex; align-items: center; gap: 8px; }
.header-left h2 { margin: 0; font-size: 18px; }
.editor-layout { display: grid; grid-template-columns: 340px 1fr; gap: 16px; }
.mt-12 { margin-top: 12px; }
.slider-row { display: flex; align-items: center; gap: 12px; }
.slider-val { font-size: 13px; color: #666; min-width: 30px; }
.skill-count-label { font-size: 12px; color: #0052d9; }
.skill-list-scroll { max-height: 280px; overflow-y: auto; }
.skill-category { margin-bottom: 8px; }
.category-header { font-size: 12px; font-weight: 600; color: #666; padding: 4px 0; border-bottom: 1px solid #f0f0f0; }
.skill-item { padding: 3px 0; font-size: 12px; }
.skill-card { padding: 6px 0; border-bottom: 1px solid #f8f8f8; }
.skill-name { font-weight: 500; }
.skill-desc { font-size: 11px; color: #8c8c8c; margin-left: 24px; margin-top: 2px; }
.skill-emoji { margin-right: 4px; }
.empty-skills { text-align: center; color: #bbb; padding: 20px; font-size: 13px; }
.history-section { margin-top: 16px; }
.test-panel { margin-top: 16px; }
.test-messages { max-height: 200px; overflow-y: auto; margin-bottom: 8px; padding: 8px; background: #fafafa; border-radius: 4px; }
.test-msg { margin-bottom: 6px; padding: 4px 8px; border-radius: 4px; font-size: 12px; white-space: pre-wrap; }
.test-msg.user { background: #e6f7ff; }
.test-msg.assistant { background: #f6ffed; }
.test-input { display: flex; gap: 8px; }
@media (max-width: 1024px) { .editor-layout { grid-template-columns: 1fr; } }
</style>

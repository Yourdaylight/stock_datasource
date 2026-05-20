<template>
  <div class="team-editor">
    <!-- Header -->
    <div class="page-header">
      <div class="header-left">
        <t-button variant="text" @click="goBack"><template #icon><chevron-left-icon /></template></t-button>
        <t-input v-model="pipelineName" class="name-input" placeholder="团队名称" @blur="autoSave" />
      </div>
      <t-space>
        <t-button variant="outline" @click="handleSave" :loading="saving">保存</t-button>
        <t-button theme="primary" @click="handleRun" :loading="running">
          <template #icon><play-icon /></template>
          运行团队
        </t-button>
      </t-space>
    </div>

    <div class="editor-body">
      <!-- Left: Config -->
      <div class="config-section">
        <t-card title="团队描述" :bordered="true" size="small">
          <t-textarea v-model="pipelineDesc" placeholder="描述团队任务目标..." :autosize="{minRows:2,maxRows:3}" />
        </t-card>

        <!-- 层级配置 -->
        <t-card title="层级配置（最多3层）" :bordered="true" size="small" class="mt-12">
          <div v-for="tier in 3" :key="tier" class="tier-section">
            <div class="tier-header">
              <span class="tier-badge" :class="`tier-${tier}`">Tier {{ tier }}</span>
              <span class="tier-desc">{{ tierDescs[tier - 1] }}</span>
              <t-button size="small" variant="text" @click="addToTier(tier)">+ 添加</t-button>
            </div>
            <div class="tier-agents">
              <div v-for="agent in getTierAgents(tier)" :key="agent.id" class="tier-agent-item">
                <span class="agent-avatar">{{ getAgentAvatar(agent) }}</span>
                <span class="agent-name">{{ agent.label }}</span>
                <t-space size="small">
                  <t-button v-if="tier > 1" variant="text" size="small" @click="moveTier(agent.id, tier - 1)" title="上移一层">↑</t-button>
                  <t-button v-if="tier < 3" variant="text" size="small" @click="moveTier(agent.id, tier + 1)" title="下移一层">↓</t-button>
                  <t-button variant="text" size="small" theme="danger" @click="removeMember(agent.id)"><t-icon name="delete" size="14px" /></t-button>
                </t-space>
              </div>
              <div v-if="getTierAgents(tier).length === 0" class="tier-empty">空</div>
            </div>
          </div>
        </t-card>

        <!-- 汇总策略 -->
        <t-card title="汇报规则" :bordered="true" size="small" class="mt-12">
          <t-form label-align="top">
            <t-form-item label="层间传递">
              <t-select v-model="executionMode">
                <t-option value="hierarchical" label="层级汇报 — Tier1→Tier2→Tier3 逐层上报" />
                <t-option value="parallel_then_merge" label="层内并行 — 每层内部并行，层间顺序" />
                <t-option value="all_to_final" label="全部汇总 — 所有Agent结果直接给最终层" />
              </t-select>
            </t-form-item>
            <t-form-item label="最终决策">
              <t-select v-model="mergeStrategy">
                <t-option value="llm_summarize" label="LLM综合研判（推荐）" />
                <t-option value="last_tier" label="取最高层Agent输出" />
                <t-option value="vote" label="投票决策" />
              </t-select>
            </t-form-item>
          </t-form>
        </t-card>

        <!-- AI生成 -->
        <t-card title="AI 生成" :bordered="true" size="small" class="mt-12">
          <t-textarea v-model="aiPrompt" placeholder="描述团队需求，例如：&#10;'3层选股团队：底层看行情和板块，中层筛选和分析，顶层综合决策'" :autosize="{minRows:2,maxRows:5}" />
          <t-button theme="primary" variant="outline" block class="mt-12" :loading="generating" @click="handleAiGenerate">AI 生成</t-button>
        </t-card>
      </div>

      <!-- Right: Topology -->
      <div class="preview-section">
        <t-card title="层级拓扑" :bordered="true" size="small">
          <div class="topo-visual">
            <!-- Tier 3 (top) -->
            <div class="topo-tier" v-if="getTierAgents(3).length">
              <div class="topo-tier-label">Tier 3 · 决策层</div>
              <div class="topo-tier-agents">
                <div v-for="a in getTierAgents(3)" :key="a.id" class="topo-chip topo-t3">{{ getAgentAvatar(a) }} {{ a.label }}</div>
              </div>
            </div>
            <div class="topo-connector" v-if="getTierAgents(3).length && getTierAgents(2).length">▲ 汇报</div>

            <!-- Tier 2 (middle) -->
            <div class="topo-tier" v-if="getTierAgents(2).length">
              <div class="topo-tier-label">Tier 2 · 分析层</div>
              <div class="topo-tier-agents">
                <div v-for="a in getTierAgents(2)" :key="a.id" class="topo-chip topo-t2">{{ getAgentAvatar(a) }} {{ a.label }}</div>
              </div>
            </div>
            <div class="topo-connector" v-if="getTierAgents(2).length && getTierAgents(1).length">▲ 汇报</div>

            <!-- Tier 1 (bottom) -->
            <div class="topo-tier" v-if="getTierAgents(1).length">
              <div class="topo-tier-label">Tier 1 · 执行层</div>
              <div class="topo-tier-agents">
                <div v-for="a in getTierAgents(1)" :key="a.id" class="topo-chip topo-t1">{{ getAgentAvatar(a) }} {{ a.label }}</div>
              </div>
            </div>

            <!-- Input -->
            <div class="topo-connector" v-if="agentNodes.length">▲ 输入</div>
            <div class="topo-tier">
              <div class="topo-tier-agents">
                <div class="topo-chip topo-input">📥 用户指令</div>
              </div>
            </div>

            <div v-if="!agentNodes.length" class="topo-empty">添加Agent后显示拓扑</div>
          </div>
        </t-card>

        <!-- Execution Panel -->
        <ExecutionPanel
          v-if="executionNodes.length || isExecutionRunning || isExecutionComplete"
          :nodes="executionNodes"
          :is-running="isExecutionRunning"
          :is-complete="isExecutionComplete"
          v-model:expanded-node="expandedNode"
          class="mt-12"
        />
      </div>
    </div>

    <!-- Add Agent Dialog -->
    <t-dialog v-model:visible="showAddAgent" :header="`添加Agent到 Tier ${addingTier}`" width="500px" :footer="false">
      <div class="agent-picker">
        <div v-for="agent in availableAgents" :key="agent.id" class="pick-item" @click="confirmAdd(agent)">
          <span>{{ agent.avatar || '🤖' }}</span>
          <div>
            <div class="pick-name">{{ agent.name }}</div>
            <div class="pick-desc">{{ agent.description }}</div>
          </div>
        </div>
      </div>
    </t-dialog>

    <!-- Run Dialog -->
    <t-dialog v-model:visible="showRunDialog" header="运行团队" width="400px" :footer="false">
      <t-textarea v-model="runInput" placeholder="输入任务..." :autosize="{minRows:3}" />
      <t-button theme="primary" block class="mt-12" :loading="running" @click="executeTeam">执行</t-button>
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { MessagePlugin } from 'tdesign-vue-next'
import { ChevronLeftIcon, PlayIcon } from 'tdesign-icons-vue-next'
import { getPipeline, updatePipeline, getExecuteUrl } from '@/api/orchestration'
import { listAgents } from '@/api/agent'
import type { PipelineNode } from '@/api/orchestration'
import type { AgentConfig } from '@/api/agent'
import ExecutionPanel from './components/ExecutionPanel.vue'
import type { NodeState } from './components/ExecutionPanel.vue'

const route = useRoute()
const router = useRouter()

const pipelineName = ref('')
const pipelineDesc = ref('')
const pipelineId = ref('')
const nodes = ref<PipelineNode[]>([])
const edges = ref<any[]>([])
const availableAgents = ref<AgentConfig[]>([])
const saving = ref(false)
const running = ref(false)
const generating = ref(false)
const showAddAgent = ref(false)
const addingTier = ref(1)
const showRunDialog = ref(false)
const runInput = ref('')
const executionNodes = ref<NodeState[]>([])
const isExecutionRunning = ref(false)
const isExecutionComplete = ref(false)
const expandedNode = ref('')
const aiPrompt = ref('')
const executionMode = ref('hierarchical')
const mergeStrategy = ref('llm_summarize')
let execAbort: AbortController | null = null

onUnmounted(() => { if (execAbort) execAbort.abort() })

const tierDescs = ['执行层 — 数据采集、监控', '分析层 — 研判、筛选', '决策层 — 综合判断、输出']

const agentNodes = computed(() => nodes.value.filter(n => n.type === 'agent'))

function getTierAgents(tier: number): PipelineNode[] {
  return nodes.value.filter(n => n.type === 'agent' && (n.data?.tier || 1) === tier)
}

function getAgentAvatar(node: PipelineNode) {
  const agent = availableAgents.value.find(a => a.id === node.data?.agent_id)
  return agent?.avatar || '🤖'
}

function getAgentDesc(node: PipelineNode) {
  const agent = availableAgents.value.find(a => a.id === node.data?.agent_id)
  return agent?.description?.substring(0, 30) || ''
}

function addToTier(tier: number) {
  addingTier.value = tier
  showAddAgent.value = true
}

function confirmAdd(agent: AgentConfig) {
  nodes.value.push({
    id: `agent_${Date.now()}`,
    type: 'agent',
    label: agent.name,
    position: { x: 0, y: 0 },
    data: { agent_id: agent.id, tier: addingTier.value },
  })
  showAddAgent.value = false
  rebuildEdges()
}

function removeMember(nodeId: string) {
  nodes.value = nodes.value.filter(n => n.id !== nodeId)
  rebuildEdges()
}

function moveTier(nodeId: string, newTier: number) {
  const node = nodes.value.find(n => n.id === nodeId)
  if (node) {
    node.data = { ...node.data, tier: newTier }
    rebuildEdges()
  }
}

function rebuildEdges() {
  const newEdges: any[] = []
  // Ensure input/output exist
  if (!nodes.value.find(n => n.type === 'input')) {
    nodes.value.unshift({ id: 'input_1', type: 'input', label: '输入', position: { x: 0, y: 0 }, data: {} })
  }
  if (!nodes.value.find(n => n.type === 'output')) {
    nodes.value.push({ id: 'output_1', type: 'output', label: '输出', position: { x: 0, y: 0 }, data: {} })
  }

  const tier1 = getTierAgents(1)
  const tier2 = getTierAgents(2)
  const tier3 = getTierAgents(3)

  // Input → Tier 1
  for (const a of tier1) {
    newEdges.push({ id: `e_in_${a.id}`, source: 'input_1', target: a.id })
  }
  // If no tier1, input → tier2
  if (!tier1.length) {
    for (const a of tier2) {
      newEdges.push({ id: `e_in_${a.id}`, source: 'input_1', target: a.id })
    }
  }

  // Tier 1 → Tier 2
  for (const a1 of tier1) {
    for (const a2 of tier2) {
      newEdges.push({ id: `e_${a1.id}_${a2.id}`, source: a1.id, target: a2.id })
    }
  }
  // If no tier2, tier1 → tier3
  if (!tier2.length && tier3.length) {
    for (const a1 of tier1) {
      for (const a3 of tier3) {
        newEdges.push({ id: `e_${a1.id}_${a3.id}`, source: a1.id, target: a3.id })
      }
    }
  }

  // Tier 2 → Tier 3
  for (const a2 of tier2) {
    for (const a3 of tier3) {
      newEdges.push({ id: `e_${a2.id}_${a3.id}`, source: a2.id, target: a3.id })
    }
  }

  // Last tier → Output
  const lastTier = tier3.length ? tier3 : (tier2.length ? tier2 : tier1)
  for (const a of lastTier) {
    newEdges.push({ id: `e_${a.id}_out`, source: a.id, target: 'output_1' })
  }

  edges.value = newEdges
}

async function loadPipeline() {
  const id = route.params.id as string
  pipelineId.value = id
  try {
    const res = await getPipeline(id)
    const p = (res as any).nodes ? res : (res as any).data
    pipelineName.value = p.name
    pipelineDesc.value = p.description || ''
    nodes.value = p.nodes || []
    edges.value = p.edges || []
    // Restore execution config from output_config
    const oc = p.output_config || {}
    if (oc.execution_mode) executionMode.value = oc.execution_mode
    if (oc.merge_strategy) mergeStrategy.value = oc.merge_strategy
    // Infer tiers from existing edges if not set
    inferTiers()
  } catch { MessagePlugin.error('加载失败') }
}

function inferTiers() {
  // If nodes already have tier data, skip
  const hasAnyTier = nodes.value.some(n => n.type === 'agent' && n.data?.tier)
  if (hasAnyTier) return

  // Infer from DAG depth
  const agentList = nodes.value.filter(n => n.type === 'agent')
  if (!agentList.length) return

  // Build adjacency from edges
  const incoming: Record<string, string[]> = {}
  const outgoing: Record<string, string[]> = {}
  for (const e of edges.value) {
    if (!outgoing[e.source]) outgoing[e.source] = []
    outgoing[e.source].push(e.target)
    if (!incoming[e.target]) incoming[e.target] = []
    incoming[e.target].push(e.source)
  }

  // BFS from input to determine depth
  const depths: Record<string, number> = {}
  const queue = ['input_1']
  depths['input_1'] = 0
  while (queue.length) {
    const current = queue.shift()!
    for (const next of (outgoing[current] || [])) {
      if (!(next in depths)) {
        depths[next] = (depths[current] || 0) + 1
        queue.push(next)
      }
    }
  }

  // Map depths to tiers (1-3)
  const agentDepths = agentList.map(a => depths[a.id] || 1)
  const maxDepth = Math.max(...agentDepths, 1)

  for (const agent of agentList) {
    const d = depths[agent.id] || 1
    let tier = 1
    if (maxDepth <= 1) tier = 1
    else if (maxDepth === 2) tier = d <= 1 ? 1 : 2
    else tier = d <= 1 ? 1 : (d <= Math.ceil(maxDepth / 2) ? 2 : 3)
    agent.data = { ...agent.data, tier }
  }
}

async function loadAgents() {
  try {
    const res = await listAgents()
    availableAgents.value = (Array.isArray(res) ? res : (res as any).data || []).filter((a: AgentConfig) => a.status === 'active')
  } catch {}
}

async function handleSave() {
  saving.value = true
  try {
    await updatePipeline(pipelineId.value, {
      name: pipelineName.value,
      description: pipelineDesc.value,
      nodes: nodes.value,
      edges: edges.value,
      output_config: { execution_mode: executionMode.value, merge_strategy: mergeStrategy.value },
    })
    MessagePlugin.success('已保存')
  } catch { MessagePlugin.error('保存失败') }
  finally { saving.value = false }
}
function autoSave() { handleSave() }
function handleRun() { runInput.value = ''; showRunDialog.value = true }

async function executeTeam() {
  if (!runInput.value.trim()) return
  showRunDialog.value = false
  running.value = true
  isExecutionRunning.value = true
  isExecutionComplete.value = false
  expandedNode.value = ''

  // Initialize node states from pipeline nodes (include all)
  executionNodes.value = nodes.value.map(n => ({
    id: n.id,
    label: n.label,
    type: n.type,
    status: 'pending' as const,
    output: '',
    durationMs: 0,
    error: '',
  }))

  // Abort previous stream if any
  if (execAbort) execAbort.abort()
  execAbort = new AbortController()

  try {
    await handleSave()
    const url = getExecuteUrl(pipelineId.value)
    const base = import.meta.env.VITE_API_BASE_URL || ''
    const token = localStorage.getItem('token')
    const response = await fetch(`${base}${url}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ input_data: { message: runInput.value } }),
      signal: execAbort.signal,
    })
    if (!response.ok) {
      throw new Error(`服务端错误 (HTTP ${response.status})`)
    }
    const reader = response.body?.getReader()
    if (!reader) return
    const decoder = new TextDecoder()
    let firstNodeStartSeen = false
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const text = decoder.decode(value, { stream: true })
      for (const line of text.split('\n')) {
        if (line.startsWith('data: ')) {
          try {
            const event = JSON.parse(line.slice(6))
            const nodeState = executionNodes.value.find(n => n.id === event.node_id)
            if (event.type === 'node_start' && nodeState) {
              nodeState.status = 'running'
              // Only auto-expand on first node_start to avoid flicker
              if (!firstNodeStartSeen) { expandedNode.value = nodeState.id; firstNodeStartSeen = true }
            } else if (event.type === 'node_end' && nodeState) {
              nodeState.status = 'completed'
              nodeState.output = event.output || ''
              nodeState.durationMs = event.duration_ms || 0
              expandedNode.value = nodeState.id
            } else if (event.type === 'node_error' && nodeState) {
              nodeState.status = 'error'
              nodeState.error = event.error || '未知错误'
              expandedNode.value = nodeState.id
            } else if (event.type === 'complete') {
              isExecutionComplete.value = true
              isExecutionRunning.value = false
            } else if (event.type === 'error') {
              isExecutionComplete.value = true
              isExecutionRunning.value = false
              MessagePlugin.error(event.message || '执行出错')
            }
          } catch (parseErr) {
            console.warn('SSE parse error:', line, parseErr)
          }
        }
      }
    }
  } catch (e: any) {
    if (e.name === 'AbortError') return // User cancelled
    isExecutionRunning.value = false
    isExecutionComplete.value = true
    MessagePlugin.error(`执行失败: ${e.message}`)
  } finally {
    running.value = false
    isExecutionRunning.value = false
  }
}

async function handleAiGenerate() {
  if (!aiPrompt.value.trim()) { MessagePlugin.warning('请描述需求'); return }
  generating.value = true
  try {
    const prompt = aiPrompt.value
    // Keyword-based matching to assign tiers
    const tier1Keywords: Record<string, string[]> = { '行情': ['行情分析师'], '数据': ['行情分析师'], '监控': ['行情分析师'], '板块': ['板块轮动分析师'], '指数': ['指数分析师'], '新闻': ['新闻分析师'] }
    const tier2Keywords: Record<string, string[]> = { '选股': ['选股专家'], '筛选': ['选股专家'], '分析': ['财报分析师', '技术面专家'], '技术': ['技术面专家'], '财报': ['财报分析师'], '基本面': ['财报分析师'] }
    const tier3Keywords: Record<string, string[]> = { '决策': ['价值投资专家'], '汇总': ['价值投资专家'], '建议': ['价值投资专家'], '把关': ['价值投资专家'] }

    const matched: Record<number, Set<string>> = { 1: new Set(), 2: new Set(), 3: new Set() }
    for (const [kw, names] of Object.entries(tier1Keywords)) { if (prompt.includes(kw)) names.forEach(n => matched[1].add(n)) }
    for (const [kw, names] of Object.entries(tier2Keywords)) { if (prompt.includes(kw)) names.forEach(n => matched[2].add(n)) }
    for (const [kw, names] of Object.entries(tier3Keywords)) { if (prompt.includes(kw)) names.forEach(n => matched[3].add(n)) }

    // If nothing in tier3, move highest tier2 there
    if (!matched[3].size && matched[2].size > 1) {
      const last = [...matched[2]].pop()!
      matched[2].delete(last)
      matched[3].add(last)
    }
    // If nothing anywhere, add defaults
    if (!matched[1].size && !matched[2].size && !matched[3].size) {
      matched[1].add('行情分析师')
      matched[2].add('选股专家')
      matched[3].add('价值投资专家')
    }

    // Clear and rebuild
    nodes.value = nodes.value.filter(n => n.type !== 'agent')
    for (const [tier, names] of Object.entries(matched)) {
      for (const name of names) {
        const agent = availableAgents.value.find(a => a.name === name)
        if (agent) {
          nodes.value.push({
            id: `agent_${Date.now()}_${Math.random().toString(36).slice(2, 5)}`,
            type: 'agent', label: agent.name, position: { x: 0, y: 0 },
            data: { agent_id: agent.id, tier: parseInt(tier) },
          })
        }
      }
    }
    rebuildEdges()
    MessagePlugin.success(`已生成 ${agentNodes.value.length} 个Agent的分层团队`)
  } finally { generating.value = false }
}

function goBack() { router.push('/orchestration') }

onMounted(async () => { await Promise.all([loadPipeline(), loadAgents()]) })
</script>

<style scoped>
.team-editor { display: flex; flex-direction: column; height: calc(100vh - 64px); padding: 16px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.header-left { display: flex; align-items: center; gap: 8px; }
.name-input { width: 220px; }
.editor-body { flex: 1; display: grid; grid-template-columns: 400px 1fr; gap: 16px; overflow: auto; }
.config-section, .preview-section { overflow-y: auto; }
.mt-12 { margin-top: 12px; }

/* Tier sections */
.tier-section { margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid #f0f0f0; }
.tier-section:last-child { border-bottom: none; margin-bottom: 0; }
.tier-header { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.tier-badge { font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 10px; }
.tier-1 { background: #f0f9eb; color: #52c41a; }
.tier-2 { background: #fef0e0; color: #e6a23c; }
.tier-3 { background: #ecf5ff; color: #409eff; }
.tier-desc { font-size: 11px; color: #8c8c8c; flex: 1; }
.tier-agents { padding-left: 4px; }
.tier-agent-item { display: flex; align-items: center; gap: 6px; padding: 4px 8px; border-radius: 4px; margin-bottom: 3px; background: #fafafa; }
.tier-agent-item:hover { background: #f0f5ff; }
.agent-avatar { font-size: 16px; }
.agent-name { flex: 1; font-size: 12px; font-weight: 500; }
.tier-empty { font-size: 11px; color: #ccc; padding: 4px 8px; }

/* Topology */
.topo-visual { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 16px; }
.topo-tier { width: 100%; padding: 10px; border-radius: 8px; background: #fafafa; }
.topo-tier-label { font-size: 11px; font-weight: 600; color: #666; margin-bottom: 6px; text-align: center; }
.topo-tier-agents { display: flex; flex-wrap: wrap; gap: 6px; justify-content: center; }
.topo-chip { padding: 5px 12px; border-radius: 14px; font-size: 12px; border: 1px solid #e7e7e7; background: white; }
.topo-t1 { border-color: #b3e19d; background: #f6ffed; }
.topo-t2 { border-color: #f5dab1; background: #fef7e6; }
.topo-t3 { border-color: #91caff; background: #e6f4ff; font-weight: 600; }
.topo-input { border-color: #ddd; background: #f5f5f5; }
.topo-connector { font-size: 12px; color: #bbb; text-align: center; }
.topo-empty { color: #ccc; font-size: 13px; padding: 30px; }

.agent-picker { max-height: 400px; overflow-y: auto; }
.pick-item { display: flex; align-items: center; gap: 10px; padding: 10px; border-radius: 6px; cursor: pointer; border: 1px solid #f0f0f0; margin-bottom: 6px; }
.pick-item:hover { border-color: #0052d9; background: #f0f5ff; }
.pick-name { font-weight: 500; font-size: 13px; }
.pick-desc { font-size: 11px; color: #8c8c8c; }
</style>

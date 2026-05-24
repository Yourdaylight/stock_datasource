<template>
  <div class="orchestration-list-page">
    <!-- Header -->
    <div class="page-header">
      <div class="header-left">
        <h2>投研团队</h2>
        <span class="subtitle">按投研角色组织协作流程，沉淀研究结论、风险审查和行动建议</span>
      </div>
      <t-button theme="primary" @click="handleCreate">
        <template #icon><add-icon /></template>
        新建投研团队
      </t-button>
    </div>

    <!-- Research Team Templates -->
    <div class="template-section">
      <div class="section-title">专业投研团队模板</div>
      <div class="template-grid">
        <div v-for="template in researchTemplates" :key="template.key" class="template-card">
          <div class="template-title">{{ template.name }}</div>
          <p>{{ template.description }}</p>
          <div class="template-roles">
            <t-tag v-for="role in template.roles" :key="role" size="small" variant="light">{{ role }}</t-tag>
          </div>
          <t-button size="small" variant="outline" @click="handleCreate(template)">按模板新建</t-button>
        </div>
      </div>
    </div>

    <!-- Pipeline List -->
    <div class="pipeline-grid" v-if="!loading">
      <div
        v-for="pipeline in pipelines"
        :key="pipeline.id"
        class="pipeline-card"
        @click="handleEdit(pipeline.id)"
      >
        <div class="card-header">
          <h3>{{ pipeline.name }}</h3>
          <t-tag :theme="statusTheme(pipeline.status)" size="small">
            {{ statusLabel(pipeline.status) }}
          </t-tag>
        </div>
        <p class="pipeline-desc">{{ pipeline.description || '暂无描述' }}</p>
        <div class="card-meta">
        <span>{{ pipeline.nodes.length }} 个角色/节点</span>
        <span>{{ pipeline.edges.length }} 条协作链路</span>
          <span>v{{ pipeline.version }}</span>
        </div>
        <div class="card-footer">
          <span class="time">{{ formatTime(pipeline.updated_at) }}</span>
          <div class="card-actions" @click.stop>
            <t-button variant="text" size="small" @click="handleRun(pipeline)">
              运行
            </t-button>
            <t-dropdown
              :options="[
                { content: '编辑', value: 'edit' },
                { content: '删除', value: 'delete', theme: 'error' }
              ]"
              @click="handleAction($event, pipeline)"
            >
              <t-button variant="text" size="small" shape="square">
                <template #icon><more-icon /></template>
              </t-button>
            </t-dropdown>
          </div>
        </div>
      </div>

      <!-- Empty -->
      <div v-if="pipelines.length === 0" class="empty-state">
        <p>暂无投研团队</p>
        <t-button theme="primary" @click="handleCreate()">创建第一个投研团队</t-button>
      </div>
    </div>

    <div v-else class="loading-state"><t-loading /></div>

    <!-- Run Dialog -->
    <t-dialog v-model:visible="showRunDialog" header="运行投研团队" :footer="false" width="500px">
      <t-form v-if="runPipeline" label-align="top">
        <t-form-item label="投研任务">
          <t-textarea v-model="runInput" placeholder="例如：评估贵州茅台是否适合加仓，并给出反方观点和风险提示" :autosize="{ minRows: 3 }" />
        </t-form-item>
        <t-button theme="primary" :loading="running" @click="executeRun" block>
          执行
        </t-button>
      </t-form>
      <div v-if="runResult" class="run-result">
        <h4>执行结果</h4>
        <pre>{{ runResult }}</pre>
      </div>
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { MessagePlugin, DialogPlugin } from 'tdesign-vue-next'
import { AddIcon, MoreIcon } from 'tdesign-icons-vue-next'
import { listPipelines, createPipeline, deletePipeline, getExecuteUrl } from '@/api/orchestration'
import type { Pipeline } from '@/api/orchestration'

const router = useRouter()
const pipelines = ref<Pipeline[]>([])
const loading = ref(true)
const showRunDialog = ref(false)
const runPipeline = ref<Pipeline | null>(null)
const runInput = ref('')
const running = ref(false)
const runResult = ref('')

const researchTemplates = [
  {
    key: 'single-stock-research',
    name: '个股深度研究团队',
    description: '围绕单一标的输出基本面、技术面、新闻事件、风险和组合经理结论。',
    roles: ['基本面', '技术面', '新闻事件', '风险', 'PM 汇总'],
  },
  {
    key: 'portfolio-rebalance',
    name: '组合调仓团队',
    description: '从持仓、风险预算、行业暴露和交易执行角度生成调仓建议。',
    roles: ['组合经理', '量化', '风控', '交易', '投顾'],
  },
  {
    key: 'event-impact',
    name: '事件冲击分析团队',
    description: '针对公告、财报、政策或突发新闻评估影响路径和应对预案。',
    roles: ['事件解读', '行业影响', '个股影响', '风险预案'],
  },
  {
    key: 'post-market-review',
    name: '盘后复盘团队',
    description: '复盘当日组合表现、风险暴露、交易执行和次日关注事项。',
    roles: ['绩效归因', '风险复盘', '交易复盘', '关注清单'],
  },
]

async function loadPipelines() {
  loading.value = true
  try {
    const res = await listPipelines()
    pipelines.value = Array.isArray(res) ? res : (res as any).data || []
  } catch (e: any) {
    MessagePlugin.error('加载失败')
  } finally {
    loading.value = false
  }
}

async function handleCreate(template?: typeof researchTemplates[number]) {
  try {
    const res = await createPipeline({
      name: template?.name || ('新投研团队 ' + new Date().toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: 'numeric', minute: 'numeric' })),
      description: template?.description || '',
      nodes: [
        { id: 'input_1', type: 'input', label: '输入', position: { x: 100, y: 200 }, data: {} },
        { id: 'output_1', type: 'output', label: '输出', position: { x: 600, y: 200 }, data: {} },
      ],
      edges: [],
    })
    router.push(`/orchestration/${(res as any).id || (res as any).data?.id}`)
  } catch (e: any) {
    MessagePlugin.error('创建失败')
  }
}

function handleEdit(id: string) {
  router.push(`/orchestration/${id}`)
}

function handleRun(pipeline: Pipeline) {
  runPipeline.value = pipeline
  runInput.value = ''
  runResult.value = ''
  showRunDialog.value = true
}

async function executeRun() {
  if (!runPipeline.value || !runInput.value.trim()) return
  running.value = true
  runResult.value = ''
  try {
    const url = getExecuteUrl(runPipeline.value.id)
    const base = (import.meta as any).env?.VITE_API_BASE_URL || ''
    const response = await fetch(`${base}${url}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
      },
      body: JSON.stringify({ input_data: { message: runInput.value } }),
    })
    const reader = response.body?.getReader()
    if (!reader) return
    const decoder = new TextDecoder()
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const text = decoder.decode(value, { stream: true })
      const lines = text.split('\n')
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const event = JSON.parse(line.slice(6))
            if (event.type === 'node_end' && event.output) {
              runResult.value += `[${event.label}] ${event.output}\n\n`
            } else if (event.type === 'complete') {
              runResult.value += `\n--- 完成 ---\n${event.output}`
            } else if (event.type === 'error') {
              runResult.value += `\n[ERROR] ${event.message}`
            }
          } catch {}
        }
      }
    }
  } catch (e: any) {
    runResult.value = `执行失败: ${e.message}`
  } finally {
    running.value = false
  }
}

function handleAction(data: { value: string }, pipeline: Pipeline) {
  if (data.value === 'edit') {
    handleEdit(pipeline.id)
  } else if (data.value === 'delete') {
    const dialog = DialogPlugin.confirm({
      header: '确认删除',
      body: `删除投研团队 "${pipeline.name}" ?`,
      confirmBtn: { theme: 'danger', content: '删除' },
      onConfirm: async () => {
        await deletePipeline(pipeline.id)
        MessagePlugin.success('已删除')
        await loadPipelines()
        dialog.destroy()
      },
    })
  }
}

function statusTheme(status: string) {
  return { draft: 'default', active: 'success', archived: 'warning' }[status] || 'default'
}

function statusLabel(status: string) {
  return { draft: '草稿', active: '活跃', archived: '已归档' }[status] || status
}

function formatTime(t: string) {
  if (!t) return ''
  return new Date(t).toLocaleString('zh-CN')
}

onMounted(loadPipelines)
</script>

<style scoped>
.orchestration-list-page {
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
.header-left h2 { margin: 0; }
.subtitle { color: #8c8c8c; font-size: 13px; margin-left: 12px; }
.template-section { margin-bottom: 24px; }
.section-title { font-weight: 600; margin-bottom: 12px; color: #1d2129; }
.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 16px;
}
.template-card {
  border: 1px solid #e7e7e7;
  border-radius: 8px;
  padding: 16px;
  background: #fbfcff;
}
.template-title { font-weight: 600; color: #1d2129; margin-bottom: 8px; }
.template-card p { color: #666; font-size: 12px; line-height: 1.6; min-height: 40px; }
.template-roles { display: flex; flex-wrap: wrap; gap: 6px; margin: 12px 0; }
.pipeline-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}
.pipeline-card {
  border: 1px solid #e7e7e7;
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s;
  background: white;
}
.pipeline-card:hover {
  border-color: #0052d9;
  box-shadow: 0 2px 8px rgba(0, 82, 217, 0.1);
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.card-header h3 { margin: 0; font-size: 15px; }
.pipeline-desc { font-size: 12px; color: #8c8c8c; margin: 0 0 12px 0; }
.card-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #bbb;
  margin-bottom: 8px;
}
.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.time { font-size: 11px; color: #bbb; }
.empty-state, .loading-state {
  grid-column: 1 / -1;
  text-align: center;
  padding: 60px 0;
  color: #8c8c8c;
}
.run-result {
  margin-top: 16px;
}
.run-result pre {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 300px;
  overflow: auto;
  white-space: pre-wrap;
}
</style>

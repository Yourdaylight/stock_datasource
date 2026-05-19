<template>
  <div class="orchestration-list-page">
    <!-- Header -->
    <div class="page-header">
      <div class="header-left">
        <h2>Agent 编排</h2>
        <span class="subtitle">可视化拖拽 Agent 构建智能管道</span>
      </div>
      <t-button theme="primary" @click="handleCreate">
        <template #icon><add-icon /></template>
        新建编排
      </t-button>
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
          <span>{{ pipeline.nodes.length }} 个节点</span>
          <span>{{ pipeline.edges.length }} 条连线</span>
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
        <p>暂无编排管道</p>
        <t-button theme="primary" @click="handleCreate">创建第一个编排</t-button>
      </div>
    </div>

    <div v-else class="loading-state"><t-loading /></div>

    <!-- Run Dialog -->
    <t-dialog v-model:visible="showRunDialog" header="运行编排" :footer="false" width="500px">
      <t-form v-if="runPipeline" label-align="top">
        <t-form-item label="输入消息">
          <t-textarea v-model="runInput" placeholder="输入要处理的内容..." :autosize="{ minRows: 3 }" />
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

async function handleCreate() {
  try {
    const res = await createPipeline({
      name: '新编排 ' + new Date().toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: 'numeric', minute: 'numeric' }),
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
      body: `删除编排 "${pipeline.name}" ?`,
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

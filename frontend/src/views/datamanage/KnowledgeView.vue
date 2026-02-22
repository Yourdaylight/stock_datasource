<template>
  <div class="knowledge-view">
    <!-- Permission Check -->
    <template v-if="!isAdmin">
      <t-card class="no-permission-card">
        <div class="permission-denied">
          <t-icon name="error-circle" size="64px" style="color: var(--td-warning-color); margin-bottom: 16px" />
          <h3 style="margin: 0 0 8px 0; font-size: 20px">无访问权限</h3>
          <p style="margin: 0 0 24px 0; color: var(--td-text-color-secondary)">
            知识库配置仅限管理员使用。
          </p>
          <t-button theme="primary" @click="$router.push('/')">返回首页</t-button>
        </div>
      </t-card>
    </template>

    <template v-else>
      <t-loading :loading="loading" style="min-height: 200px">
        <!-- Config Card -->
        <t-card title="知识库配置" subtitle="配置 WeKnora 知识库服务连接，启用后 AI 对话将支持引用研报、公告等文档进行分析">
          <template #actions>
            <t-tag v-if="config.enabled && connectionOk" theme="success" variant="light">
              <template #icon><t-icon name="check-circle" /></template>
              已连接
            </t-tag>
            <t-tag v-else-if="config.enabled && !connectionOk" theme="warning" variant="light">
              已启用 · 未连接
            </t-tag>
            <t-tag v-else theme="default">未启用</t-tag>
          </template>

          <t-form
            ref="formRef"
            :data="config"
            :rules="rules"
            label-width="120px"
            @submit="handleSave"
          >
            <t-form-item label="启用知识库">
              <t-switch v-model="config.enabled" />
              <span class="form-help">启用后 AI 对话可引用知识库文档进行分析</span>
            </t-form-item>

            <template v-if="config.enabled">
              <t-form-item label="服务地址" name="base_url">
                <t-input
                  v-model="config.base_url"
                  placeholder="例如: http://weknora-backend:8080/api/v1"
                  style="width: 420px"
                />
                <span class="form-help">WeKnora 后端 API 地址</span>
              </t-form-item>

              <t-form-item label="API Key" name="api_key">
                <t-input
                  v-model="config.api_key"
                  type="password"
                  placeholder="WeKnora 服务的 API Key"
                  style="width: 420px"
                />
              </t-form-item>

              <t-form-item label="知识库 ID">
                <t-input
                  v-model="config.kb_ids"
                  placeholder="可选，多个用逗号分隔，留空则搜索所有知识库"
                  style="width: 420px"
                />
                <span class="form-help">限定搜索的知识库范围</span>
              </t-form-item>

              <t-form-item label="超时时间">
                <t-input-number
                  v-model="config.timeout"
                  :min="1"
                  :max="60"
                  suffix="秒"
                  style="width: 150px"
                />
              </t-form-item>
            </template>

            <t-form-item>
              <t-space>
                <t-button theme="primary" type="submit" :loading="saving">
                  保存配置
                </t-button>
                <t-button
                  v-if="config.enabled && config.base_url && config.api_key"
                  theme="default"
                  :loading="testing"
                  @click="handleTest"
                >
                  测试连接
                </t-button>
              </t-space>
            </t-form-item>
          </t-form>

          <t-alert
            v-if="testResult"
            :theme="testResult.success ? 'success' : 'error'"
            :message="testResult.message"
            :close="true"
            style="margin-top: 8px; max-width: 560px"
            @close="testResult = null"
          />
        </t-card>

        <!-- Knowledge Bases List (only when connected) -->
        <t-card
          v-if="config.enabled && connectionOk"
          title="可用知识库"
          style="margin-top: 16px"
        >
          <template #actions>
            <t-button variant="text" size="small" @click="fetchKnowledgeBases">
              <template #icon><t-icon name="refresh" /></template>
              刷新
            </t-button>
          </template>

          <div v-if="knowledgeBases.length === 0" style="padding: 24px 0; text-align: center">
            <t-empty description="暂无知识库，请在 WeKnora 管理界面中创建并上传文档" />
          </div>

          <div v-else class="kb-list">
            <div v-for="kb in knowledgeBases" :key="kb.id" class="kb-item">
              <div class="kb-icon">
                <t-icon name="folder-open" size="20px" />
              </div>
              <div class="kb-info">
                <div class="kb-name">{{ kb.name }}</div>
                <div class="kb-desc">{{ kb.description || '暂无描述' }}</div>
              </div>
              <t-tag size="small" theme="default" variant="light">{{ kb.id }}</t-tag>
            </div>
          </div>
        </t-card>

        <!-- ========== Knowledge Sync Section ========== -->
        <t-card
          v-if="config.enabled && connectionOk"
          title="知识同步"
          subtitle="将 ClickHouse 已入库数据同步到 WeKnora 知识库，支持按表/条件筛选或自定义 SQL"
          style="margin-top: 16px"
        >
          <t-tabs v-model="syncTab">
            <t-tab-panel value="simple" label="表筛选模式">
              <div class="sync-form">
                <t-form label-width="100px" :colon="true">
                  <t-form-item label="目标知识库">
                    <t-select
                      v-model="syncForm.kb_id"
                      placeholder="选择知识库"
                      style="width: 360px"
                    >
                      <t-option
                        v-for="kb in knowledgeBases"
                        :key="kb.id"
                        :value="kb.id"
                        :label="kb.name"
                      />
                    </t-select>
                  </t-form-item>

                  <t-form-item label="数据表">
                    <t-select
                      v-model="syncForm.table_name"
                      placeholder="选择 ClickHouse 表"
                      filterable
                      style="width: 360px"
                      @change="onTableChange"
                    >
                      <t-option
                        v-for="t in syncTables"
                        :key="t.table_name"
                        :value="t.table_name"
                        :label="t.table_name + (t.comment ? ` (${t.comment})` : '')"
                      />
                    </t-select>
                    <t-button variant="text" size="small" :loading="loadingTables" @click="fetchSyncTables">
                      <template #icon><t-icon name="refresh" /></template>
                    </t-button>
                  </t-form-item>

                  <t-form-item label="股票代码">
                    <t-textarea
                      v-model="syncForm.ts_codes_str"
                      placeholder="可选，多个用逗号分隔，如: 600519.SH,000858.SZ"
                      style="width: 360px"
                      :autosize="{ minRows: 1, maxRows: 3 }"
                    />
                  </t-form-item>

                  <t-form-item label="日期范围">
                    <t-space>
                      <t-input
                        v-model="syncForm.start_date"
                        placeholder="起始日期 如 20240101"
                        style="width: 170px"
                      />
                      <span>~</span>
                      <t-input
                        v-model="syncForm.end_date"
                        placeholder="结束日期 如 20241231"
                        style="width: 170px"
                      />
                    </t-space>
                  </t-form-item>

                  <t-form-item label="自定义标题">
                    <t-input
                      v-model="syncForm.custom_title"
                      placeholder="可选，留空自动生成"
                      style="width: 360px"
                    />
                  </t-form-item>

                  <t-form-item>
                    <t-button
                      theme="primary"
                      :loading="syncing"
                      :disabled="!syncForm.kb_id || !syncForm.table_name"
                      @click="handleSync"
                    >
                      开始同步
                    </t-button>
                  </t-form-item>
                </t-form>
              </div>
            </t-tab-panel>

            <t-tab-panel value="sql" label="自定义 SQL">
              <div class="sync-form">
                <t-form label-width="100px" :colon="true">
                  <t-form-item label="目标知识库">
                    <t-select
                      v-model="syncForm.kb_id"
                      placeholder="选择知识库"
                      style="width: 360px"
                    >
                      <t-option
                        v-for="kb in knowledgeBases"
                        :key="kb.id"
                        :value="kb.id"
                        :label="kb.name"
                      />
                    </t-select>
                  </t-form-item>

                  <t-form-item label="SQL 查询">
                    <t-textarea
                      v-model="syncForm.custom_sql"
                      placeholder="SELECT * FROM ods_income_statement WHERE ts_code='600519.SH' LIMIT 100"
                      style="width: 500px"
                      :autosize="{ minRows: 3, maxRows: 8 }"
                    />
                  </t-form-item>

                  <t-form-item label="文档标题">
                    <t-input
                      v-model="syncForm.custom_title"
                      placeholder="可选，留空自动生成"
                      style="width: 360px"
                    />
                  </t-form-item>

                  <t-form-item>
                    <t-button
                      theme="primary"
                      :loading="syncing"
                      :disabled="!syncForm.kb_id || !syncForm.custom_sql"
                      @click="handleSqlSync"
                    >
                      执行同步
                    </t-button>
                  </t-form-item>
                </t-form>
              </div>
            </t-tab-panel>
          </t-tabs>

          <!-- Sync progress -->
          <div v-if="currentSyncTask" class="sync-progress">
            <t-divider>同步进度</t-divider>
            <div class="progress-info">
              <t-tag :theme="syncStatusTheme(currentSyncTask.status)" variant="light" size="small">
                {{ syncStatusLabel(currentSyncTask.status) }}
              </t-tag>
              <span class="progress-text">
                {{ currentSyncTask.completed }} / {{ currentSyncTask.total }} 文档完成
                <template v-if="currentSyncTask.failed > 0">
                  ，{{ currentSyncTask.failed }} 失败
                </template>
              </span>
            </div>
            <t-progress
              v-if="currentSyncTask.total > 0"
              :percentage="Math.round((currentSyncTask.completed / currentSyncTask.total) * 100)"
              :status="currentSyncTask.status === 'failed' ? 'error' : currentSyncTask.status === 'completed' ? 'success' : 'active'"
              style="margin-top: 8px"
            />
            <t-alert
              v-if="currentSyncTask.error"
              theme="error"
              :message="currentSyncTask.error"
              style="margin-top: 8px"
            />
            <div v-if="currentSyncTask.documents && currentSyncTask.documents.length > 0" class="sync-docs-list">
              <div v-for="doc in currentSyncTask.documents" :key="doc.knowledge_id" class="sync-doc-item">
                <t-tag size="small" :theme="doc.action === 'created' ? 'success' : 'primary'" variant="light">
                  {{ doc.action === 'created' ? '新建' : '更新' }}
                </t-tag>
                <span class="doc-title">{{ doc.title }}</span>
                <span class="doc-rows">{{ doc.rows }} 行</span>
              </div>
            </div>
          </div>
        </t-card>

        <!-- Knowledge Documents List -->
        <t-card
          v-if="config.enabled && connectionOk && syncForm.kb_id"
          title="已导入文档"
          style="margin-top: 16px"
        >
          <template #actions>
            <t-space>
              <t-input
                v-model="docSearch"
                placeholder="搜索文档"
                style="width: 200px"
                clearable
                @change="fetchDocuments"
              />
              <t-button variant="text" size="small" @click="fetchDocuments">
                <template #icon><t-icon name="refresh" /></template>
                刷新
              </t-button>
            </t-space>
          </template>

          <t-table
            :data="documents"
            :columns="docColumns"
            :loading="loadingDocs"
            row-key="id"
            size="small"
            :pagination="docPagination"
            @page-change="onDocPageChange"
          />
        </t-card>

        <!-- Sync History -->
        <t-card
          v-if="config.enabled && connectionOk"
          title="同步历史"
          style="margin-top: 16px"
        >
          <template #actions>
            <t-button variant="text" size="small" @click="fetchSyncHistory">
              <template #icon><t-icon name="refresh" /></template>
              刷新
            </t-button>
          </template>

          <div v-if="syncHistory.length === 0" style="padding: 16px 0; text-align: center">
            <t-empty description="暂无同步记录" />
          </div>

          <div v-else class="history-list">
            <div v-for="h in syncHistory" :key="h.task_id" class="history-item">
              <div class="history-header">
                <t-tag :theme="syncStatusTheme(h.status)" variant="light" size="small">
                  {{ syncStatusLabel(h.status) }}
                </t-tag>
                <span class="history-table">{{ h.table_name || 'SQL' }}</span>
                <span class="history-time">{{ h.created_at }}</span>
              </div>
              <div class="history-detail">
                {{ h.completed }}/{{ h.total }} 文档
                <template v-if="h.failed > 0">，{{ h.failed }} 失败</template>
                <template v-if="h.error"> — {{ h.error }}</template>
              </div>
            </div>
          </div>
        </t-card>

        <!-- Quick Deploy Guide (when not configured) -->
        <t-card
          title="快速部署 WeKnora"
          subtitle="WeKnora 是基于大模型的文档理解检索框架，支持 RAG 增强分析"
          style="margin-top: 16px"
        >
          <div class="feature-list">
            <div v-for="feature in deployFeatures" :key="feature" class="feature-chip">
              <t-icon name="check-circle-filled" size="14px" style="color: var(--td-success-color)" />
              <span>{{ feature }}</span>
            </div>
          </div>

          <t-divider>部署步骤</t-divider>

          <div class="deploy-steps">
            <div v-for="(step, idx) in deploySteps" :key="idx" class="deploy-step">
              <div class="step-header">
                <span class="step-num">{{ idx + 1 }}</span>
                <span class="step-title">{{ step.title }}</span>
                <t-button variant="text" size="small" theme="primary" @click="copyText(step.command)">
                  <template #icon><t-icon name="file-copy" /></template>
                  复制
                </t-button>
              </div>
              <div class="step-command"><code>{{ step.command }}</code></div>
              <p v-if="step.note" class="step-note">{{ step.note }}</p>
            </div>
          </div>

          <div class="deploy-links">
            <t-button variant="outline" @click="openUrl('https://weknora.weixin.qq.com')">
              <template #icon><t-icon name="link" /></template>
              官方文档
            </t-button>
            <t-button variant="outline" @click="openUrl('https://github.com/Tencent/WeKnora')">
              <template #icon><t-icon name="logo-github" /></template>
              GitHub
            </t-button>
          </div>
        </t-card>
      </t-loading>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, h } from 'vue'
import { MessagePlugin, DialogPlugin } from 'tdesign-vue-next'
import { useAuthStore } from '@/stores/auth'
import {
  datamanageApi,
  type KnowledgeConfig,
  type KnowledgeBase,
  type KnowledgeSyncTable,
  type KnowledgeSyncTask,
  type KnowledgeDocument,
} from '@/api/datamanage'

const authStore = useAuthStore()
const isAdmin = computed(() => authStore.isAdmin)

const formRef = ref()
const loading = ref(true)
const saving = ref(false)
const testing = ref(false)
const connectionOk = ref(false)
const testResult = ref<{ success: boolean; message: string } | null>(null)
const knowledgeBases = ref<KnowledgeBase[]>([])

const config = reactive<KnowledgeConfig>({
  enabled: false,
  base_url: 'http://weknora-backend:8080/api/v1',
  api_key: '',
  kb_ids: '',
  timeout: 10,
})

const rules = {
  base_url: [{ required: true, message: '请输入 WeKnora 服务地址', trigger: 'blur' }],
  api_key: [{ required: true, message: '请输入 API Key', trigger: 'blur' }],
}

// ---------- Sync state ----------
const syncTab = ref('simple')
const syncing = ref(false)
const loadingTables = ref(false)
const syncTables = ref<KnowledgeSyncTable[]>([])
const currentSyncTask = ref<KnowledgeSyncTask | null>(null)
const syncHistory = ref<KnowledgeSyncTask[]>([])

const syncForm = reactive({
  kb_id: '',
  table_name: '',
  ts_codes_str: '',
  start_date: '',
  end_date: '',
  custom_sql: '',
  custom_title: '',
})

// ---------- Documents state ----------
const documents = ref<KnowledgeDocument[]>([])
const loadingDocs = ref(false)
const docSearch = ref('')
const docPagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
})

const docColumns = [
  { colKey: 'title', title: '标题', ellipsis: true },
  { colKey: 'parse_status', title: '解析状态', width: 100 },
  { colKey: 'enable_status', title: '启用', width: 80 },
  { colKey: 'created_at', title: '创建时间', width: 170 },
  {
    colKey: 'operation',
    title: '操作',
    width: 80,
    cell: (_h: any, { row }: { row: KnowledgeDocument }) => {
      return h('t-button', {
        variant: 'text',
        theme: 'danger',
        size: 'small',
        onClick: () => handleDeleteDoc(row),
      }, '删除')
    },
  },
]

// ---------- Deploy info ----------
const deployFeatures = [
  '引用研报、公告等文档的精准分析',
  '基于公司财报数据的深度问答',
  '行业政策解读与合规信息检索',
]

const deploySteps = [
  {
    title: '克隆并启动 WeKnora',
    command: 'git clone https://github.com/Tencent/WeKnora.git && cd WeKnora\ndocker-compose up -d',
    note: '需要 Docker 和 Docker Compose',
  },
  {
    title: '或使用本项目自带编排文件',
    command: 'docker-compose -f docker-compose.weknora.yml up -d',
    note: '已预配置好网络互通',
  },
  {
    title: '获取 API Key 并填入上方配置',
    command: '# 在 WeKnora 管理界面中创建 API Key\n# 然后在上方表单中填入服务地址和 API Key',
  },
]

// ---------- Config methods ----------
const loadConfig = async () => {
  loading.value = true
  try {
    const cfg = await datamanageApi.getKnowledgeConfig()
    Object.assign(config, cfg)

    if (config.enabled && config.api_key) {
      const status = await datamanageApi.getKnowledgeStatus()
      connectionOk.value = status.status === 'healthy'
      if (connectionOk.value) {
        await fetchKnowledgeBases()
        await fetchSyncTables()
      }
    }
  } catch (e) {
    console.error('Failed to load knowledge config:', e)
  } finally {
    loading.value = false
  }
}

const fetchKnowledgeBases = async () => {
  try {
    const resp = await datamanageApi.listKnowledgeBases()
    knowledgeBases.value = resp.knowledge_bases || []
    // Auto-select first KB if none selected
    if (!syncForm.kb_id && knowledgeBases.value.length > 0) {
      syncForm.kb_id = knowledgeBases.value[0].id
    }
  } catch (e) {
    console.error('Failed to fetch knowledge bases:', e)
  }
}

const handleSave = async () => {
  if (config.enabled) {
    const valid = await formRef.value?.validate()
    if (valid !== true) return
  }

  saving.value = true
  try {
    await datamanageApi.updateKnowledgeConfig({ ...config })
    MessagePlugin.success('知识库配置已保存')
    if (config.enabled && config.api_key) {
      const status = await datamanageApi.getKnowledgeStatus()
      connectionOk.value = status.status === 'healthy'
      if (connectionOk.value) {
        await fetchKnowledgeBases()
        await fetchSyncTables()
      }
    } else {
      connectionOk.value = false
      knowledgeBases.value = []
    }
  } catch (error) {
    MessagePlugin.error('保存失败')
  } finally {
    saving.value = false
  }
}

const handleTest = async () => {
  testing.value = true
  testResult.value = null
  try {
    const result = await datamanageApi.testKnowledgeConnection({
      base_url: config.base_url,
      api_key: config.api_key,
      timeout: config.timeout,
    })
    testResult.value = result
    if (result.success) {
      connectionOk.value = true
      await fetchKnowledgeBases()
      await fetchSyncTables()
    }
  } catch (e: any) {
    testResult.value = { success: false, message: e?.message || '连接测试失败' }
  } finally {
    testing.value = false
  }
}

// ---------- Sync methods ----------
const fetchSyncTables = async () => {
  loadingTables.value = true
  try {
    const resp = await datamanageApi.getKnowledgeSyncTables()
    syncTables.value = resp.tables || []
  } catch (e) {
    console.error('Failed to fetch sync tables:', e)
  } finally {
    loadingTables.value = false
  }
}

const onTableChange = () => {
  // Could fetch columns here if needed
}

const handleSync = async () => {
  if (!syncForm.kb_id || !syncForm.table_name) return

  syncing.value = true
  currentSyncTask.value = null
  try {
    const tsCodes = syncForm.ts_codes_str
      ? syncForm.ts_codes_str.split(',').map(s => s.trim()).filter(Boolean)
      : undefined

    const task = await datamanageApi.triggerKnowledgeSync({
      kb_id: syncForm.kb_id,
      table_name: syncForm.table_name,
      ts_codes: tsCodes,
      start_date: syncForm.start_date || undefined,
      end_date: syncForm.end_date || undefined,
      custom_title: syncForm.custom_title || undefined,
    })
    currentSyncTask.value = task
    MessagePlugin.success(`同步完成：${task.completed} 个文档已同步`)
    await fetchSyncHistory()
    if (syncForm.kb_id) await fetchDocuments()
  } catch (e: any) {
    MessagePlugin.error(e?.message || '同步失败')
  } finally {
    syncing.value = false
  }
}

const handleSqlSync = async () => {
  if (!syncForm.kb_id || !syncForm.custom_sql) return

  syncing.value = true
  currentSyncTask.value = null
  try {
    const task = await datamanageApi.triggerKnowledgeSync({
      kb_id: syncForm.kb_id,
      table_name: 'custom_sql',
      custom_sql: syncForm.custom_sql,
      custom_title: syncForm.custom_title || undefined,
    })
    currentSyncTask.value = task
    MessagePlugin.success(`同步完成：${task.completed} 个文档已同步`)
    await fetchSyncHistory()
    if (syncForm.kb_id) await fetchDocuments()
  } catch (e: any) {
    MessagePlugin.error(e?.message || '同步失败')
  } finally {
    syncing.value = false
  }
}

const fetchSyncHistory = async () => {
  try {
    const resp = await datamanageApi.getKnowledgeSyncHistory(20)
    syncHistory.value = resp.items || []
  } catch (e) {
    console.error('Failed to fetch sync history:', e)
  }
}

// ---------- Document methods ----------
const fetchDocuments = async () => {
  if (!syncForm.kb_id) return
  loadingDocs.value = true
  try {
    const resp = await datamanageApi.listKnowledgeDocuments(
      syncForm.kb_id,
      docPagination.current,
      docPagination.pageSize,
      docSearch.value || undefined,
    )
    documents.value = resp.data || []
    docPagination.total = resp.total || 0
  } catch (e) {
    console.error('Failed to fetch documents:', e)
  } finally {
    loadingDocs.value = false
  }
}

const onDocPageChange = (pageInfo: any) => {
  docPagination.current = pageInfo.current
  docPagination.pageSize = pageInfo.pageSize
  fetchDocuments()
}

const handleDeleteDoc = (doc: KnowledgeDocument) => {
  const dialog = DialogPlugin.confirm({
    header: '确认删除',
    body: `确定要删除文档「${doc.title}」吗？此操作不可恢复。`,
    onConfirm: async () => {
      try {
        await datamanageApi.deleteKnowledgeDocument(doc.id)
        MessagePlugin.success('文档已删除')
        await fetchDocuments()
      } catch (e: any) {
        MessagePlugin.error(e?.message || '删除失败')
      }
      dialog.destroy()
    },
  })
}

// ---------- Helpers ----------
const syncStatusTheme = (status: string) => {
  const map: Record<string, string> = {
    pending: 'default',
    running: 'primary',
    completed: 'success',
    failed: 'danger',
    idle: 'default',
  }
  return map[status] || 'default'
}

const syncStatusLabel = (status: string) => {
  const map: Record<string, string> = {
    pending: '等待中',
    running: '同步中',
    completed: '已完成',
    failed: '失败',
    idle: '空闲',
  }
  return map[status] || status
}

const copyText = (text: string) => {
  navigator.clipboard.writeText(text).then(() => {
    MessagePlugin.success('已复制到剪贴板')
  }).catch(() => {
    MessagePlugin.warning('复制失败，请手动复制')
  })
}

const openUrl = (url: string) => {
  window.open(url, '_blank')
}

onMounted(async () => {
  await loadConfig()
  if (connectionOk.value) {
    await fetchSyncHistory()
  }
})
</script>

<style scoped>
.knowledge-view {
  height: 100%;
}

.no-permission-card {
  margin-top: 100px;
  max-width: 500px;
  margin-left: auto;
  margin-right: auto;
}

.permission-denied {
  text-align: center;
  padding: 40px 20px;
}

.form-help {
  margin-left: 12px;
  color: #909399;
  font-size: 12px;
}

/* Knowledge Bases List */
.kb-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.kb-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--td-bg-color-secondarycontainer);
  border-radius: 8px;
}

.kb-icon {
  color: var(--td-brand-color);
}

.kb-info {
  flex: 1;
}

.kb-name {
  font-weight: 500;
  font-size: 14px;
}

.kb-desc {
  font-size: 12px;
  color: var(--td-text-color-secondary);
  margin-top: 2px;
}

/* Sync Section */
.sync-form {
  padding: 16px 0;
}

.sync-progress {
  margin-top: 8px;
}

.progress-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.progress-text {
  font-size: 13px;
  color: var(--td-text-color-secondary);
}

.sync-docs-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sync-doc-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: var(--td-bg-color-secondarycontainer);
  border-radius: 6px;
  font-size: 13px;
}

.doc-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-rows {
  color: var(--td-text-color-placeholder);
  font-size: 12px;
  flex-shrink: 0;
}

/* History */
.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.history-item {
  padding: 10px 14px;
  background: var(--td-bg-color-secondarycontainer);
  border-radius: 8px;
}

.history-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.history-table {
  font-weight: 500;
  font-size: 13px;
  flex: 1;
}

.history-time {
  font-size: 12px;
  color: var(--td-text-color-placeholder);
}

.history-detail {
  font-size: 12px;
  color: var(--td-text-color-secondary);
  margin-top: 4px;
}

/* Deploy Guide */
.feature-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}

.feature-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  background: var(--td-bg-color-container-hover);
  border-radius: 16px;
  font-size: 13px;
}

.deploy-steps {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 20px;
}

.deploy-step {
  background: var(--td-bg-color-secondarycontainer);
  border-radius: 8px;
  padding: 12px 16px;
}

.step-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.step-num {
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--td-brand-color);
  color: #fff;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.step-title {
  font-weight: 500;
  font-size: 14px;
  flex: 1;
}

.step-command {
  background: var(--td-bg-color-container);
  border-radius: 4px;
  padding: 8px 12px;
  font-family: monospace;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.5;
  border: 1px solid var(--td-component-stroke);
}

.step-note {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--td-text-color-placeholder);
}

.deploy-links {
  display: flex;
  gap: 12px;
}
</style>

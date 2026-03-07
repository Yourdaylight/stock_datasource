<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { userLlmApi, type LlmConfig } from '@/api/userLlm'

const configs = ref<LlmConfig[]>([])
const loading = ref(false)
const showForm = ref(false)
const testing = ref(false)
const saving = ref(false)

const PROVIDERS = [
  { label: 'OpenAI', value: 'openai' },
  { label: 'DeepSeek', value: 'deepseek' },
  { label: 'Claude (Anthropic)', value: 'anthropic' },
  { label: '通义千问 (Qwen)', value: 'qwen' },
  { label: '智谱 (GLM)', value: 'zhipu' },
  { label: '其他 (OpenAI 兼容)', value: 'custom' },
]

const PROVIDER_DEFAULTS: Record<string, { base_url: string; model: string }> = {
  openai: { base_url: 'https://api.openai.com/v1', model: 'gpt-4o' },
  deepseek: { base_url: 'https://api.deepseek.com/v1', model: 'deepseek-chat' },
  anthropic: { base_url: 'https://api.anthropic.com/v1', model: 'claude-sonnet-4-20250514' },
  qwen: { base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-plus' },
  zhipu: { base_url: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4' },
  custom: { base_url: '', model: '' },
}

const form = ref({
  provider: 'openai',
  api_key: '',
  base_url: '',
  model_name: '',
})

const testResult = ref<{ success: boolean; message: string } | null>(null)

const loadConfigs = async () => {
  loading.value = true
  try {
    const res = await userLlmApi.getConfigs()
    configs.value = res.configs || []
  } catch {
    configs.value = []
  }
  loading.value = false
}

const onProviderChange = (val: string) => {
  const defaults = PROVIDER_DEFAULTS[val] || PROVIDER_DEFAULTS.custom
  form.value.base_url = defaults.base_url
  form.value.model_name = defaults.model
}

const openAddForm = () => {
  form.value = { provider: 'openai', api_key: '', base_url: 'https://api.openai.com/v1', model_name: 'gpt-4o' }
  testResult.value = null
  showForm.value = true
}

const handleTest = async () => {
  if (!form.value.api_key) {
    MessagePlugin.warning('请输入 API Key')
    return
  }
  testing.value = true
  testResult.value = null
  try {
    const res = await userLlmApi.testConfig({
      provider: form.value.provider,
      api_key: form.value.api_key,
      base_url: form.value.base_url,
      model_name: form.value.model_name,
    })
    testResult.value = res
    if (res.success) {
      MessagePlugin.success('连接测试成功')
    } else {
      MessagePlugin.error(res.message)
    }
  } catch (e: any) {
    testResult.value = { success: false, message: e.message || '测试失败' }
    MessagePlugin.error('测试失败')
  }
  testing.value = false
}

const handleSave = async () => {
  if (!form.value.api_key) {
    MessagePlugin.warning('请输入 API Key')
    return
  }
  saving.value = true
  try {
    await userLlmApi.saveConfig({
      provider: form.value.provider,
      api_key: form.value.api_key,
      base_url: form.value.base_url,
      model_name: form.value.model_name,
    })
    MessagePlugin.success('保存成功')
    showForm.value = false
    await loadConfigs()
  } catch (e: any) {
    MessagePlugin.error(e.message || '保存失败')
  }
  saving.value = false
}

const handleDelete = async (provider: string) => {
  try {
    await userLlmApi.deleteConfig(provider)
    MessagePlugin.success('已删除')
    await loadConfigs()
  } catch {
    MessagePlugin.error('删除失败')
  }
}

const getProviderLabel = (val: string) => {
  return PROVIDERS.find(p => p.value === val)?.label || val
}

onMounted(() => {
  loadConfigs()
})
</script>

<template>
  <div class="llm-config">
    <div class="config-header">
      <div>
        <h4 class="section-title">我的大模型配置</h4>
        <p class="section-desc">配置您自己的 LLM API Key，使用自带额度进行 AI 对话</p>
      </div>
      <t-button theme="primary" @click="openAddForm">
        <template #icon><t-icon name="add" /></template>
        添加配置
      </t-button>
    </div>

    <!-- Existing configs -->
    <t-loading :loading="loading">
      <div v-if="configs.length === 0 && !loading" class="empty-state">
        <t-icon name="setting" size="48px" style="color: #c0c4cc; margin-bottom: 12px;" />
        <p>暂无配置，点击"添加配置"来设置您的 LLM API Key</p>
      </div>
      <div v-else class="config-list">
        <div v-for="cfg in configs" :key="cfg.provider" class="config-item">
          <div class="config-info">
            <div class="config-provider">
              <t-tag theme="primary" variant="light">{{ getProviderLabel(cfg.provider) }}</t-tag>
            </div>
            <div class="config-details">
              <span class="detail-label">API Key:</span>
              <span class="detail-value mono">{{ cfg.api_key_masked }}</span>
            </div>
            <div v-if="cfg.base_url" class="config-details">
              <span class="detail-label">Base URL:</span>
              <span class="detail-value mono">{{ cfg.base_url }}</span>
            </div>
            <div v-if="cfg.model_name" class="config-details">
              <span class="detail-label">Model:</span>
              <span class="detail-value">{{ cfg.model_name }}</span>
            </div>
          </div>
          <div class="config-actions">
            <t-popconfirm content="确定删除该配置？" @confirm="handleDelete(cfg.provider)">
              <t-button theme="danger" variant="text" size="small">删除</t-button>
            </t-popconfirm>
          </div>
        </div>
      </div>
    </t-loading>

    <!-- Add/Edit form dialog -->
    <t-dialog
      v-model:visible="showForm"
      header="配置大模型"
      :footer="false"
      width="520px"
      destroy-on-close
    >
      <t-form :data="form" label-width="90px" @submit="handleSave">
        <t-form-item label="服务商" name="provider">
          <t-select v-model="form.provider" :options="PROVIDERS" @change="onProviderChange" />
        </t-form-item>
        <t-form-item label="API Key" name="api_key">
          <t-input v-model="form.api_key" type="password" placeholder="请输入 API Key" clearable />
        </t-form-item>
        <t-form-item label="Base URL" name="base_url">
          <t-input v-model="form.base_url" placeholder="自定义 API 地址（可选）" clearable />
        </t-form-item>
        <t-form-item label="模型名称" name="model_name">
          <t-input v-model="form.model_name" placeholder="默认模型名称（可选）" clearable />
        </t-form-item>

        <!-- Test result -->
        <t-form-item v-if="testResult" label=" ">
          <t-alert
            :theme="testResult.success ? 'success' : 'error'"
            :message="testResult.message"
            close
            @close="testResult = null"
          />
        </t-form-item>

        <t-form-item label=" ">
          <t-space>
            <t-button variant="outline" :loading="testing" @click="handleTest">
              测试连接
            </t-button>
            <t-button theme="primary" :loading="saving" @click="handleSave">
              保存
            </t-button>
          </t-space>
        </t-form-item>
      </t-form>
    </t-dialog>
  </div>
</template>

<style scoped>
.llm-config {
  padding: 0;
}

.config-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.section-title {
  margin: 0 0 4px 0;
  font-size: 16px;
  font-weight: 600;
  color: #262626;
}

.section-desc {
  margin: 0;
  font-size: 13px;
  color: #86909c;
}

.empty-state {
  text-align: center;
  padding: 48px 0;
  color: #86909c;
}

.config-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.config-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #f7f8fa;
  border: 1px solid #e7e9ef;
  border-radius: 8px;
  padding: 16px 20px;
  transition: border-color 0.2s;
}

.config-item:hover {
  border-color: #0052d9;
}

.config-info {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.config-details {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.detail-label {
  color: #86909c;
  min-width: 64px;
}

.detail-value {
  color: #262626;
}

.mono {
  font-family: 'SF Mono', 'Cascadia Code', monospace;
  font-size: 12px;
}

.config-actions {
  flex-shrink: 0;
}
</style>

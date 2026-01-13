<template>
  <div class="config-panels">
    <t-card title="代理配置" class="proxy-config-panel">
      <template #actions>
        <t-tag v-if="proxyConfig.enabled" theme="success">已启用</t-tag>
        <t-tag v-else theme="default">未启用</t-tag>
      </template>

      <t-form
        ref="formRef"
        :data="proxyConfig"
        :rules="rules"
        label-width="100px"
        @submit="handleSave"
      >
        <t-form-item label="启用代理">
          <t-switch v-model="proxyConfig.enabled" />
          <span class="form-help">启用后，数据获取将通过HTTP代理进行</span>
        </t-form-item>

        <template v-if="proxyConfig.enabled">
          <t-form-item label="代理地址" name="host">
            <t-input
              v-model="proxyConfig.host"
              placeholder="例如: 192.168.1.100"
              style="width: 300px"
            />
          </t-form-item>

          <t-form-item label="代理端口" name="port">
          <t-input-number
            v-model="proxyConfig.port"
            :min="1"
            :max="65535"
            placeholder="例如: 8080"
            :allow-input-over-limit="true"
            style="width: 150px"
          />

          </t-form-item>

          <t-form-item label="用户名">
            <t-input
              v-model="proxyConfig.username"
              placeholder="可选，代理认证用户名"
              style="width: 300px"
            />
          </t-form-item>

          <t-form-item label="密码">
            <t-input
              v-model="proxyConfig.password"
              type="password"
              placeholder="可选，代理认证密码"
              style="width: 300px"
            />
          </t-form-item>
        </template>

        <t-form-item>
          <t-space>
            <t-button theme="primary" type="submit" :loading="saving">
              保存配置
            </t-button>
            <t-button
              v-if="proxyConfig.enabled && proxyConfig.host && proxyConfig.port"
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
        :message="testResultMessage"
        :close="true"
        style="margin-top: 16px"
        @close="testResult = null"
      />
    </t-card>

    <t-card title="任务并行与并发" class="concurrency-card">
      <template #actions>
        <t-tag theme="primary" variant="light">运行中 {{ syncConfig.running_tasks_count }} · 排队 {{ syncConfig.pending_tasks_count }}</t-tag>
      </template>

      <t-alert
        theme="warning"
        message="TuShare 仅允许同一 token 同时在线 2 个 IP；使用代理时请确保出口唯一，建议并行任务数设为 1，并控制单任务并发，避免多出口导致封禁。"
        style="margin-bottom: 16px"
      />

      <t-form
        ref="concurrencyFormRef"
        :data="syncConfig"
        :rules="concurrencyRules"
        label-width="160px"
        @submit="handleSaveConcurrency"
      >
        <t-form-item label="并行任务数量" name="max_concurrent_tasks">
          <t-input-number
            v-model="syncConfig.max_concurrent_tasks"
            :min="1"
            :max="10"
            :allow-input-over-limit="true"
            style="width: 160px"
          />
          <span class="form-help">建议 TuShare/代理出口设为 1，确保单一出口</span>
        </t-form-item>

        <t-form-item label="单任务并发请求数" name="max_date_threads">
          <t-input-number
            v-model="syncConfig.max_date_threads"
            :min="1"
            :max="20"
            :allow-input-over-limit="true"
            style="width: 160px"
          />
          <span class="form-help">控制同一任务内的日期并发，避免超限</span>
        </t-form-item>

        <t-form-item>
          <t-space>
            <t-button theme="primary" type="submit" :loading="concurrencySaving">
              保存并发配置
            </t-button>
            <t-button theme="default" variant="text" @click="loadSyncConfig">
              刷新当前状态
            </t-button>
          </t-space>
        </t-form-item>
      </t-form>
    </t-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { datamanageApi, type ProxyConfig, type ProxyTestResult, type SyncConfig } from '@/api/datamanage'

const formRef = ref()
const concurrencyFormRef = ref()
const saving = ref(false)
const testing = ref(false)
const concurrencySaving = ref(false)
const testResult = ref<ProxyTestResult | null>(null)

const proxyConfig = reactive<ProxyConfig>({
  enabled: false,
  host: '',
  port: 0,
  username: '',
  password: ''
})

const syncConfig = reactive<SyncConfig>({
  max_concurrent_tasks: 1,
  max_date_threads: 1,
  running_tasks_count: 0,
  pending_tasks_count: 0,
  running_plugins: []
})

const rules = {
  host: [
    { required: true, message: '请输入代理地址', trigger: 'blur' }
  ],
  port: [
    { required: true, message: '请输入代理端口', trigger: 'blur' }
  ]
}

const concurrencyRules = {
  max_concurrent_tasks: [
    { required: true, message: '请输入并行任务数量', trigger: 'blur', type: 'number' }
  ],
  max_date_threads: [
    { required: true, message: '请输入单任务并发请求数', trigger: 'blur', type: 'number' }
  ]
}

const testResultMessage = computed(() => {
  if (!testResult.value) return ''
  if (testResult.value.success) {
    let msg = testResult.value.message
    if (testResult.value.latency_ms) {
      msg += ` (延迟: ${testResult.value.latency_ms}ms)`
    }
    if (testResult.value.external_ip) {
      msg += ` | 出口IP: ${testResult.value.external_ip}`
    }
    return msg
  }
  return testResult.value.message
})

const loadConfig = async () => {
  try {
    const config = await datamanageApi.getProxyConfig()
    Object.assign(proxyConfig, config)
    // Clear masked password
    if (proxyConfig.password === '******') {
      proxyConfig.password = ''
    }
  } catch (error) {
    console.error('Failed to load proxy config:', error)
  }
}

const loadSyncConfig = async () => {
  try {
    const config = await datamanageApi.getSyncConfig()
    Object.assign(syncConfig, config)
  } catch (error) {
    console.error('Failed to load sync config:', error)
  }
}

const handleSave = async () => {
  if (proxyConfig.enabled) {
    const valid = await formRef.value?.validate()
    if (!valid) return
  }

  saving.value = true
  try {
    await datamanageApi.updateProxyConfig(proxyConfig)
    MessagePlugin.success('代理配置已保存')
  } catch (error) {
    MessagePlugin.error('保存失败')
  } finally {
    saving.value = false
  }
}

const handleSaveConcurrency = async () => {
  const valid = await concurrencyFormRef.value?.validate()
  if (!valid) return

  concurrencySaving.value = true
  try {
    const updated = await datamanageApi.updateSyncConfig({
      max_concurrent_tasks: syncConfig.max_concurrent_tasks,
      max_date_threads: syncConfig.max_date_threads
    })
    Object.assign(syncConfig, updated)
    MessagePlugin.success('并发配置已保存')
  } catch (error) {
    MessagePlugin.error('保存并发配置失败')
  } finally {
    concurrencySaving.value = false
  }
}

const handleTest = async () => {
  testing.value = true
  testResult.value = null
  try {
    testResult.value = await datamanageApi.testProxyConnection(proxyConfig)
  } catch (error) {
    testResult.value = {
      success: false,
      message: '测试请求失败'
    }
  } finally {
    testing.value = false
  }
}

onMounted(() => {
  loadConfig()
  loadSyncConfig()
})
</script>

<style scoped>
.config-panels {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

.proxy-config-panel {
  margin-bottom: 0;
}

.form-help {
  margin-left: 12px;
  color: #909399;
  font-size: 12px;
}
</style>

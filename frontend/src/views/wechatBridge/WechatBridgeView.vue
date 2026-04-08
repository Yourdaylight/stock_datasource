<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import {
  wechatBridgeApi,
  type PicoclawStatus,
  type PicoclawConfig,
} from '@/api/wechatBridge'

// ── State ──────────────────────────────
const status = ref<PicoclawStatus>({
  installed: false, version: null, running: false, pid: null,
  port: null, gateway_url: null, rt_running: false, rt_pid: null,
  config_exists: false, config_path: '',
})
const config = ref<PicoclawConfig | null>(null)
const loading = ref(false)
const starting = ref(false)
const stopping = ref(false)
const qrLoading = ref(false)
const qrOutput = ref('')
const qrUrl = ref('')
const autoRefreshTimer = ref<ReturnType<typeof setInterval> | null>(null)

// Form fields
const formMcpToken = ref('')
const formSymbols = ref('00700.HK,09988.HK,600519.SH')
const formNoRt = ref(false)

// ── Actions ────────────────────────────
async function loadStatus(silent = false) {
  if (!silent) loading.value = true
  try {
    status.value = await wechatBridgeApi.getStatus()
    config.value = await wechatBridgeApi.getConfig()
  } catch (e: any) {
    console.error('Failed to load status:', e)
  } finally {
    if (!silent) loading.value = false
  }
}

async function handleGenerate() {
  try {
    const res = await wechatBridgeApi.generateConfig(formMcpToken.value || undefined)
    MessagePlugin.success(res.message)
    await loadStatus()
  } catch (e: any) {
    MessagePlugin.error(e?.message || '生成配置失败')
  }
}

async function handleStart() {
  starting.value = true
  try {
    const res = await wechatBridgeApi.start({
      mcpToken: formMcpToken.value || undefined,
      symbols: formSymbols.value || undefined,
      noRt: formNoRt.value,
    })
    MessagePlugin.success(res.message)
    startAutoRefresh(5)
    await loadStatus(true)
    // 启动成功后自动获取微信登录二维码
    handleWechatLogin()
  } catch (e: any) {
    MessagePlugin.error(e?.response?.data?.detail || e?.message || '启动失败')
  } finally {
    starting.value = false
  }
}

async function handleStop() {
  stopping.value = true
  try {
    const res = await wechatBridgeApi.stop()
    MessagePlugin.success(res.message)
    stopAutoRefresh()
    await loadStatus(true)
  } catch (e: any) {
    MessagePlugin.error(e?.response?.data?.detail || e?.message || '停止失败')
  } finally {
    stopping.value = false
  }
}

async function handleWechatLogin() {
  if (!status.value.running) {
    MessagePlugin.warning('请先启动 PicoClaw 服务')
    return
  }
  qrLoading.value = true
  qrOutput.value = ''
  qrUrl.value = ''
  try {
    const res = await wechatBridgeApi.triggerWechatLogin()
    if (res.success && res.qr_url) {
      qrUrl.value = res.qr_url
      MessagePlugin.success('二维码已生成，请使用微信扫描')
    } else {
      qrOutput.value = res.output || res.message || '未能获取二维码'
      MessagePlugin.warning(res.message || '未能获取二维码链接')
    }
  } catch (e: any) {
    MessagePlugin.error(e?.response?.data?.detail || e?.message || '触发微信登录失败')
  } finally {
    qrLoading.value = false
  }
}

// Auto-refresh when running
function startAutoRefresh(intervalSec = 10) {
  stopAutoRefresh()
  autoRefreshTimer.value = setInterval(() => loadStatus(true), intervalSec * 1000)
}
function stopAutoRefresh() {
  if (autoRefreshTimer.value) {
    clearInterval(autoRefreshTimer.value)
    autoRefreshTimer.value = null
  }
}

onMounted(() => loadStatus())
onUnmounted(() => stopAutoRefresh())
</script>

<template>
  <div class="wechat-bridge-page">
    <!-- Page Header -->
    <div class="page-header">
      <div class="header-left">
        <div class="header-icon">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M8.691 2.188C3.891 2.188 0 5.476 0 9.53c0 2.212 1.17 4.203 3.002 5.55a.59.59 0 01.213.665l-.39 1.48c-.019.07-.048.141-.048.213 0 .163.13.295.29.295a.326.326 0 00.167-.054l1.903-1.114a.864.864 0 01.717-.098 10.16 10.16 0 002.837.403c.276 0 .543-.027.811-.05-.857-2.578.157-4.972 1.932-6.446 1.703-1.415 3.882-1.98 5.853-1.838-.576-3.583-4.196-6.348-8.596-6.348zM5.785 5.991c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 01-1.162 1.178A1.17 1.17 0 014.623 7.17c0-.651.52-1.18 1.162-1.18zm5.813 0c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 01-1.162 1.178 1.17 1.17 0 01-1.162-1.178c0-.651.52-1.18 1.162-1.18zm5.34 2.867c-1.797-.052-3.746.512-5.28 1.786-1.72 1.428-2.687 3.72-1.78 6.22.942 2.453 3.666 4.229 6.884 4.229.826 0 1.622-.12 2.361-.336a.722.722 0 01.598.082l1.584.926a.272.272 0 00.14.045c.134 0 .24-.11.24-.245 0-.06-.023-.12-.038-.177l-.327-1.233a.49.49 0 01.176-.554C23.138 18.477 24 16.82 24 14.98c0-3.166-2.975-5.99-7.062-6.122zm-2.97 3.25c.535 0 .969.44.969.982a.976.976 0 01-.969.983.976.976 0 01-.969-.983c0-.542.434-.982.97-.982zm4.844 0c.535 0 .969.44.969.982a.976.976 0 01-.969.983.976.976 0 01-.969-.983c0-.542.434-.982.97-.982z" fill="#07C160"/>
          </svg>
        </div>
        <div>
          <h2 style="margin:0;font-size:20px;font-weight:700">微信联动</h2>
          <p style="margin:4px 0 0;color:#86909c;font-size:13px">通过 PicoClaw 连接微信，在微信中查询股票数据、订阅实时行情</p>
        </div>
      </div>
    </div>

    <!-- Status Cards -->
    <div v-if="!loading" class="status-cards">
      <!-- PicoClaw Status Card -->
      <t-card :bordered="false" class="status-card">
        <template #title>
          <div class="card-title-row">
            <span>PicoClaw 服务</span>
            <t-tag :theme="status.running ? 'success' : (status.installed ? 'warning' : 'danger')" variant="light" shape="round">
              {{ status.running ? '运行中' : (status.installed ? '未启动' : '未安装') }}
            </t-tag>
          </div>
        </template>

        <div class="card-body">
          <div class="info-row-inline">
            <span class="info-tag">版本 <strong>{{ status.version || '--' }}</strong></span>
            <span class="info-tag">PID <strong>{{ status.pid || '--' }}</strong></span>
            <span class="info-tag">端口 <strong>{{ status.port || '--' }}</strong></span>
            <span v-if="status.gateway_url" class="info-tag">Gateway <strong>{{ status.gateway_url }}</strong></span>
          </div>

          <div class="action-row">
            <t-button
              theme="primary"
              :loading="starting"
              :disabled="status.running"
              @click="handleStart"
            >
              <template #icon><t-icon name="play-circle" /></template>
              {{ starting ? '正在启动...' : (status.installed ? '启动服务' : '下载并启动') }}
            </t-button>
            <t-button
              theme="default"
              variant="outline"
              :loading="stopping"
              :disabled="!status.running"
              @click="handleStop"
            >
              <template #icon><t-icon name="poweroff" /></template>
              停止服务
            </t-button>
          </div>

          <t-divider style="margin:16px 0 12px" />
          <div class="guide-inline">
            <p class="guide-title">使用指南</p>
            <ol>
              <li><strong>点击「启动服务」</strong> — 自动下载 PicoClaw（首次），启动 Gateway 并生成微信登录二维码</li>
              <li><strong>使用微信扫描右侧二维码</strong> — 完成登录绑定</li>
              <li><strong>在微信中发送消息</strong> — 直接对话即可查询股票数据，例如：
                <ul>
                  <li>「查一下贵州茅台最近30天的日K线」</li>
                  <li>「腾讯控股现在多少钱」</li>
                  <li>「今天涨幅最大的10只A股是哪些」</li>
                </ul>
              </li>
            </ol>
          </div>
        </div>
      </t-card>

      <!-- WeChat Login QR Card -->
      <t-card :bordered="false" class="status-card">
        <template #title>
          <div class="card-title-row">
            <span>微信登录</span>
            <t-tag :theme="qrUrl ? 'success' : 'default'" variant="light" shape="round">
              {{ qrUrl ? '待扫码' : '未登录' }}
            </t-tag>
          </div>
        </template>
        <div class="card-body">
          <!-- QR Code -->
          <div v-if="qrUrl" class="qr-area">
            <img
              :src="`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(qrUrl)}`"
              alt="微信登录二维码"
              class="qr-img"
            />
            <p class="qr-hint">请使用微信扫描二维码</p>
            <p class="qr-expire">有效期约 5 分钟，过期请重新获取</p>
          </div>
          <!-- Fallback text output -->
          <div v-else-if="qrOutput" class="qr-area">
            <pre class="qr-output">{{ qrOutput }}</pre>
          </div>
          <!-- Loading -->
          <div v-else-if="qrLoading" class="qr-area qr-placeholder">
            <t-loading size="medium" />
            <p style="color:#86909c;font-size:13px;margin:12px 0 0">正在获取二维码...</p>
          </div>
          <!-- Default: prompt -->
          <div v-else class="qr-area qr-placeholder">
            <t-icon name="qrcode" size="48px" style="color:#c2c8d1" />
            <p style="color:#86909c;font-size:13px;margin:8px 0 0">点击「启动服务」后自动生成登录二维码</p>
          </div>
        </div>
      </t-card>

      <!-- Config Preview Card -->
      <t-card :bordered="false" class="status-card full-width">
        <template #title>
          <div class="card-title-row">
            <span>配置预览</span>
            <t-tag v-if="config" theme="primary" variant="light" shape="round" size="small">
              {{ config.config_exists ? '已生成' : '待生成' }}
            </t-tag>
          </div>
        </template>
        <div class="card-body">
          <div v-if="config" class="config-preview">
            <div class="config-info-row">
              <span class="cfg-label">LLM 模型:</span>
              <t-tag size="small" variant="light">{{ config.llm_model || '未配置' }}</t-tag>
              <span class="cfg-label" style="margin-left:20px">Base URL:</span>
              <span class="mono small">{{ config.llm_base_url || '--' }}</span>
            </div>
            <div class="config-info-row">
              <span class="cfg-label">MCP Server:</span>
              <t-tag :theme="config.mcp_connected ? 'success' : 'warning'" size="small" variant="light">
                {{ config.mcp_server_url || '--' }} ({{ config.mcp_connected ? '已连接' : '未设 Token' }})
              </t-tag>
              <span class="cfg-label" style="margin-left:20px">微信 Channel:</span>
              <t-tag :theme="config.channel_weixin_enabled ? 'success' : 'default'" size="small" variant="light">
                {{ config.channel_weixin_enabled ? '已启用' : '未启用' }}
              </t-tag>
            </div>
          </div>
          <t-divider />
          <div class="form-area">
            <t-form layout="inline">
              <t-form-item label="MCP Token">
                <t-input
                  v-model="formMcpToken"
                  placeholder="输入 MCP 认证 Token（可选）"
                  style="width:280px"
                  clearable
                />
              </t-form-item>
              <t-form-item label="默认订阅">
                <t-input
                  v-model="formSymbols"
                  placeholder="00700.HK,600519.SH"
                  style="width:220px"
                  clearable
                />
              </t-form-item>
              <t-form-item label="跳过RT">
                <t-switch v-model="formNoRt" />
              </t-form-item>
              <t-form-item>
                <t-space>
                  <t-button theme="primary" size="small" @click="handleGenerate">
                    重新生成配置
                  </t-button>
                </t-space>
              </t-form-item>
            </t-form>
          </div>
        </div>
      </t-card>
    </div>

    <!-- Loading State -->
    <div v-if="loading" style="text-align:center;padding:60px 0;">
      <t-loading size="middle" />
      <p style="color:#86909c;margin-top:12px">加载中...</p>
    </div>

  </div>
</template>

<style scoped>
.wechat-bridge-page {
  padding: 0 4px;
  min-height: 100%;
}

.page-header {
  margin-bottom: 20px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.header-icon {
  width: 48px;
  height: 48px;
  background: linear-gradient(135deg, #07C160, #06AE56);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.status-cards {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.status-card {
  min-width: 320px;
  max-width: calc(50% - 8px);
  flex: 1 1 340px;
}

.status-card.full-width {
  max-width: 100%;
  flex: 100%;
}

.card-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.card-body {
  padding-top: 4px;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.info-label {
  font-size: 12px;
  color: #86909c;
}

.info-value {
  font-size: 14px;
  font-weight: 500;
  color: #262626;
}

.mono {
  font-family: 'SF Mono', 'Cascadia Code', monospace;
  font-size: 13px;
}

.mono.small {
  font-size: 11px;
  word-break: break-all;
}

.info-row-inline {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.info-tag {
  font-size: 12px;
  color: #86909c;
  background: #f2f3f5;
  padding: 2px 10px;
  border-radius: 4px;
}

.info-tag strong {
  color: #262626;
  font-family: 'SF Mono', 'Cascadia Code', monospace;
  font-size: 12px;
  margin-left: 4px;
}

.action-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.config-preview {
  margin-bottom: 8px;
}

.config-info-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  font-size: 13px;
}

.cfg-label {
  color: #86909c;
  font-size: 12px;
  white-space: nowrap;
}

.form-area {
  padding-top: 8px;
}

.qr-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px 0;
}

.qr-placeholder {
  padding: 32px 0;
}

.qr-img {
  width: 200px;
  height: 200px;
  border: 1px solid #e7e7e7;
  border-radius: 8px;
}

.qr-hint {
  margin: 10px 0 0;
  color: #333;
  font-size: 14px;
  font-weight: 500;
}

.qr-expire {
  margin: 4px 0 0;
  color: #999;
  font-size: 12px;
}

.qr-output {
  background: #f7f8fa;
  border-radius: 6px;
  padding: 12px;
  font-size: 12px;
  line-height: 1.6;
  color: #4e5969;
  overflow-x: auto;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'SF Mono', 'Cascadia Code', monospace;
  width: 100%;
}

.guide-inline {
  font-size: 13px;
  line-height: 1.7;
  color: #4e5969;
}

.guide-inline .guide-title {
  font-size: 13px;
  font-weight: 600;
  color: #262626;
  margin: 0 0 6px;
}

.guide-inline ol {
  padding-left: 18px;
  margin: 0;
}

.guide-inline li {
  margin-bottom: 4px;
}

.guide-inline ul {
  padding-left: 16px;
  margin: 2px 0;
}

.guide-note {
  margin-top: 12px;
  padding: 10px 14px;
  background: #ecf8ff;
  border-radius: 6px;
  font-size: 13px;
  color: #0052d9;
}
</style>

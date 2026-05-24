<template>
  <div class="runtime-page">
    <div class="page-header">
      <h2>工具运行时</h2>
      <span class="subtitle">投研 Agent 执行引擎、工具调用和外部能力探测</span>
    </div>

    <div class="runtime-grid" v-if="!loading">
      <div
        v-for="rt in runtimes"
        :key="rt.id"
        class="runtime-card"
        :class="{ available: rt.status === 'available', disabled: rt.status !== 'available' }"
      >
        <div class="rt-header">
          <span class="rt-icon">{{ rtIcon(rt.id) }}</span>
          <t-tag :theme="rt.status === 'available' ? 'success' : 'default'" size="small">
            {{ rt.status === 'available' ? '可用' : '未安装' }}
          </t-tag>
        </div>
        <h3>{{ rt.name }}</h3>
        <p class="rt-desc">{{ rt.description }}</p>
        <div class="rt-details" v-if="rt.status === 'available'">
          <div class="rt-detail" v-if="rt.command">
            <span class="label">命令:</span>
            <code>{{ rt.command }}</code>
          </div>
          <div class="rt-detail" v-if="rt.version">
            <span class="label">版本:</span>
            <span>{{ rt.version }}</span>
          </div>
          <div class="rt-detail" v-if="rt.default_working_dir">
            <span class="label">默认目录:</span>
            <code>{{ rt.default_working_dir }}</code>
          </div>
        </div>
        <div class="rt-actions" v-if="rt.status !== 'available'">
          <p class="install-hint">请安装后刷新探测</p>
        </div>
      </div>
    </div>

    <div v-else class="loading"><t-loading /></div>

    <t-button variant="outline" class="refresh-btn" @click="loadRuntimes" :loading="loading">
      重新探测
    </t-button>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { request } from '@/utils/request'

interface RuntimeInfo {
  id: string
  name: string
  description: string
  status: 'available' | 'not_installed'
  command: string
  version: string
  default_working_dir: string
}

const runtimes = ref<RuntimeInfo[]>([])
const loading = ref(true)

function rtIcon(id: string) {
  const icons: Record<string, string> = { langgraph: '🔗', claude: '🤖', codebuddy: '💻' }
  return icons[id] || '⚙️'
}

async function loadRuntimes() {
  loading.value = true
  try {
    const res = await request.get('/api/agents/runtimes/detect')
    runtimes.value = Array.isArray(res) ? res : (res as any).data || []
  } catch (e) {
    console.error('Failed to detect runtimes:', e)
  } finally {
    loading.value = false
  }
}

onMounted(loadRuntimes)
</script>

<style scoped>
.runtime-page { padding: 24px; max-width: 1000px; margin: 0 auto; }
.page-header { margin-bottom: 20px; }
.page-header h2 { margin: 0; }
.subtitle { color: #8c8c8c; font-size: 13px; }
.runtime-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.runtime-card {
  border: 1px solid #e7e7e7; border-radius: 10px; padding: 20px;
  background: white; transition: all 0.2s;
}
.runtime-card.available { border-color: #b7eb8f; }
.runtime-card.disabled { opacity: 0.6; }
.rt-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.rt-icon { font-size: 28px; }
.runtime-card h3 { margin: 0 0 4px 0; font-size: 16px; }
.rt-desc { font-size: 13px; color: #666; margin: 0 0 12px 0; }
.rt-details { font-size: 12px; }
.rt-detail { margin-bottom: 4px; display: flex; gap: 6px; align-items: center; }
.rt-detail .label { color: #8c8c8c; min-width: 60px; }
.rt-detail code { background: #f5f5f5; padding: 1px 4px; border-radius: 3px; font-size: 11px; word-break: break-all; }
.install-hint { font-size: 12px; color: #bbb; font-style: italic; }
.refresh-btn { margin-top: 16px; }
.loading { text-align: center; padding: 40px; }
</style>

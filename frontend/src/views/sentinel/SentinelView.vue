<template>
  <div class="sentinel-page">
    <!-- Header -->
    <div class="page-header">
      <div class="header-left">
        <h2>哨兵选股</h2>
        <span class="subtitle">基于 Agent Team 的异常监控与投资决策</span>
      </div>
      <t-space>
        <t-button variant="outline" @click="router.push('/orchestration')">编辑团队</t-button>
        <t-button theme="primary" :loading="scanning" @click="handleScan">
          执行扫描
        </t-button>
      </t-space>
    </div>

    <!-- Team Overview -->
    <div class="team-overview">
      <t-card title="哨兵 Agent Team" :bordered="true">
        <div class="team-agents">
          <div class="agent-flow">
            <div class="flow-stage">
              <div class="stage-label">Tier 1: 数据哨兵</div>
              <div class="stage-agents">
                <div v-for="s in sentinelAgents" :key="s.name" class="agent-chip" :class="{ active: s.alert_count > 0 }">
                  {{ s.icon }} {{ s.name }}
                  <span class="chip-badge" v-if="s.alert_count > 0">{{ s.alert_count }}</span>
                </div>
              </div>
            </div>
            <div class="flow-arrow">▼ 异常信号</div>
            <div class="flow-stage">
              <div class="stage-label">Tier 2: 分析师</div>
              <div class="stage-agents">
                <div v-for="a in analystAgents" :key="a.name" class="agent-chip analyst">
                  {{ a.icon }} {{ a.name }}
                </div>
              </div>
            </div>
            <div class="flow-arrow">▼ 研报汇总</div>
            <div class="flow-stage">
              <div class="stage-label">Tier 3: 投资总监 (LLM)</div>
              <div class="stage-agents">
                <div class="agent-chip director">🧠 LLM决策引擎</div>
              </div>
            </div>
          </div>
        </div>
      </t-card>
    </div>

    <!-- Status + Alerts -->
    <div class="content-grid">
      <!-- 左: 状态统计 -->
      <div class="stats-col">
        <t-card :bordered="true" size="small">
          <div class="stat-grid">
            <div class="stat-item">
              <div class="stat-num">{{ alerts.length }}</div>
              <div class="stat-label">今日告警</div>
            </div>
            <div class="stat-item">
              <div class="stat-num">{{ decisions.length }}</div>
              <div class="stat-label">投资决策</div>
            </div>
            <div class="stat-item">
              <div class="stat-num">{{ status?.sentinels?.length || 0 }}</div>
              <div class="stat-label">哨兵数</div>
            </div>
            <div class="stat-item">
              <div class="stat-num">{{ status?.analysts?.length || 0 }}</div>
              <div class="stat-label">分析师数</div>
            </div>
          </div>
        </t-card>

        <!-- 最近决策 -->
        <t-card title="投资决策" :bordered="true" size="small" class="mt-12" v-if="decisions.length > 0">
          <div v-for="d in decisions.slice(0, 3)" :key="d.decision_id" class="decision-item">
            <div class="decision-header">
              <t-tag :theme="regimeTheme(d.market_regime)" size="small">{{ regimeLabel(d.market_regime) }}</t-tag>
              <span class="decision-date">{{ d.trade_date }}</span>
            </div>
            <div class="decision-body">
              仓位建议: {{ ((d.suggested_total_position || 0) * 100).toFixed(0) }}%
              | 信心: {{ ((d.confidence || 0) * 100).toFixed(0) }}%
            </div>
          </div>
        </t-card>
      </div>

      <!-- 右: 告警列表 -->
      <div class="alerts-col">
        <t-card title="最近告警" :bordered="true" size="small">
          <template #actions>
            <t-select v-model="alertFilter" placeholder="全部类型" clearable size="small" style="width:120px">
              <t-option label="市场风险" value="market_risk" />
              <t-option label="量能异常" value="volume_anomaly" />
              <t-option label="资金流向" value="capital_flow" />
              <t-option label="MA交叉" value="ma_crossover" />
            </t-select>
          </template>
          <t-table
            :data="filteredAlerts"
            :columns="alertColumns"
            :max-height="400"
            size="small"
            stripe
            row-key="alert_id"
          />
        </t-card>
      </div>
    </div>

    <!-- Scan Result -->
    <t-dialog v-model:visible="showResult" header="扫描结果" width="600px">
      <div v-if="scanResult">
        <p>告警数: {{ scanResult.sentinel_alerts }} | 报告数: {{ scanResult.analyst_reports }} | 决策: {{ scanResult.decision_produced ? '已生成' : '无' }}</p>
        <pre v-if="scanResult.decision" style="background:#f5f7fa;padding:12px;border-radius:4px;font-size:12px;max-height:300px;overflow:auto">{{ JSON.stringify(scanResult.decision, null, 2) }}</pre>
      </div>
    </t-dialog>

    <!-- Scan Progress Panel -->
    <div v-if="showScanPanel" class="scan-panel">
      <t-card title="扫描进度" :bordered="true" size="small">
        <template #actions>
          <t-button variant="text" size="small" @click="showScanPanel = false">关闭</t-button>
        </template>
        <div class="scan-logs">
          <div v-for="(log, idx) in scanLogs" :key="idx" class="scan-log-item" :class="`log-${log.phase}`">
            <span class="log-icon">{{ logIcon(log) }}</span>
            <span class="log-msg">{{ log.message }}</span>
            <span class="log-status" v-if="log.status">
              <t-tag size="small" :theme="log.status === 'alert' ? 'warning' : log.status === 'error' ? 'danger' : 'success'">
                {{ log.status === 'alert' ? '告警' : log.status === 'error' ? '错误' : log.status === 'silent' ? '正常' : log.status }}
              </t-tag>
            </span>
          </div>
          <div v-if="scanning" class="scan-loading">
            <t-loading size="small" /> 执行中...
          </div>
        </div>
      </t-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { triggerScan, getStatus, getDecisions, getAlerts } from '@/api/sentinel'
import type { SentinelAlert, InvestmentDecision, SentinelStatus } from '@/api/sentinel'

const router = useRouter()
const scanning = ref(false)
const showResult = ref(false)
const showScanPanel = ref(false)
const scanResult = ref<any>(null)
const scanLogs = ref<any[]>([])
const status = ref<SentinelStatus | null>(null)
const alerts = ref<SentinelAlert[]>([])
const decisions = ref<InvestmentDecision[]>([])
const alertFilter = ref('')

const sentinelAgents = [
  { name: '市场风险', icon: '📊', alert_count: 0 },
  { name: 'MA交叉', icon: '📈', alert_count: 0 },
  { name: '量能异常', icon: '🔊', alert_count: 0 },
  { name: '资金流向', icon: '💰', alert_count: 0 },
  { name: '新闻情绪', icon: '📰', alert_count: 0 },
  { name: 'RPS突破', icon: '🚀', alert_count: 0 },
  { name: '板块资金', icon: '🔄', alert_count: 0 },
  { name: '财务异常', icon: '⚠️', alert_count: 0 },
  { name: '池变动', icon: '🎯', alert_count: 0 },
]

const analystAgents = [
  { name: '市场环境', icon: '🌐' },
  { name: '板块轮动', icon: '🔄' },
  { name: '个股质量', icon: '💎' },
  { name: '择时', icon: '⏰' },
]

const alertColumns = [
  { colKey: 'severity', title: '级别', width: 70, cell: (h: any, { row }: any) => {
    const map: Record<string, string> = { critical: '🔴', warning: '🟡', info: '🔵' }
    return map[row.severity] || '⚪'
  }},
  { colKey: 'sentinel_type', title: '来源', width: 90 },
  { colKey: 'ts_code', title: '标的', width: 90 },
  { colKey: 'description', title: '描述', ellipsis: true },
  { colKey: 'timestamp', title: '时间', width: 140 },
]

const filteredAlerts = computed(() => {
  if (!alertFilter.value) return alerts.value
  return alerts.value.filter(a => a.sentinel_type === alertFilter.value)
})

function regimeTheme(r: string) {
  return { bull: 'success', bear: 'danger', consolidation: 'default' }[r] || 'default'
}
function regimeLabel(r: string) {
  return { bull: '牛市', bear: '熊市', consolidation: '震荡', transition_up: '转多', transition_down: '转空' }[r] || r
}
function logIcon(log: any) {
  const icons: Record<string, string> = {
    start: '🚀', sentinels_start: '👁️', sentinel_scan: '🔍', sentinel_done: '✅',
    sentinels_complete: '📋', analysts_start: '🧠', analyst_analyze: '🔬',
    analyst_done: '📊', analysts_complete: '📋', director_start: '🎯',
    director_done: '💡', director_skip: '⏭️', complete: '🏁', error: '❌',
  }
  if (log.status === 'error') return '❌'
  if (log.status === 'alert') return '🚨'
  return icons[log.phase] || '•'
}

async function handleScan() {
  scanning.value = true
  scanLogs.value = []
  showScanPanel.value = true
  try {
    const base = import.meta.env.VITE_API_BASE_URL || ''
    const response = await fetch(`${base}/api/sentinel/scan/stream`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` },
    })
    const reader = response.body?.getReader()
    if (!reader) return
    const decoder = new TextDecoder()
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const text = decoder.decode(value, { stream: true })
      for (const line of text.split('\n')) {
        if (line.startsWith('data: ')) {
          try {
            const event = JSON.parse(line.slice(6))
            scanLogs.value.push(event)
            // Update sentinel agent counts live
            if (event.phase === 'sentinel_done' && event.alert_count > 0) {
              const s = sentinelAgents.find(a => {
                const map: Record<string, string> = { '市场风险': 'market_risk', 'MA交叉': 'ma_crossover', '量能异常': 'volume_anomaly', '资金流向': 'capital_flow', '新闻情绪': 'news_sentiment', 'RPS突破': 'rps_breakout', '板块资金': 'sector_flow', '财务异常': 'financial_anomaly', '池变动': 'pool_change' }
                return map[a.name] === event.sentinel
              })
              if (s) s.alert_count = event.alert_count
            }
            if (event.phase === 'complete') {
              scanResult.value = event.result
            }
          } catch {}
        }
      }
    }
    await loadData()
  } catch (e: any) {
    scanLogs.value.push({ phase: 'error', message: `请求失败: ${e.message}` })
  } finally { scanning.value = false }
}

async function loadData() {
  try {
    const [statusRes, alertsRes, decisionsRes] = await Promise.allSettled([
      getStatus(), getAlerts({ limit: 50 }), getDecisions(10)
    ])
    if (statusRes.status === 'fulfilled') {
      const d = statusRes.value as any
      status.value = d?.data?.data || d?.data || d
    }
    if (alertsRes.status === 'fulfilled') {
      const d = alertsRes.value as any
      alerts.value = d?.data?.data || d?.data || d || []
      // Update sentinel alert counts
      for (const s of sentinelAgents) {
        const typeName: Record<string, string> = { '市场风险': 'market_risk', 'MA交叉': 'ma_crossover', '量能异常': 'volume_anomaly', '资金流向': 'capital_flow', '新闻情绪': 'news_sentiment', 'RPS突破': 'rps_breakout', '板块资金': 'sector_flow', '财务异常': 'financial_anomaly', '池变动': 'pool_change' }
        s.alert_count = alerts.value.filter(a => a.sentinel_type === typeName[s.name]).length
      }
    }
    if (decisionsRes.status === 'fulfilled') {
      const d = decisionsRes.value as any
      decisions.value = d?.data?.data || d?.data || d || []
    }
  } catch (e) { console.error('Load data failed:', e) }
}

onMounted(loadData)
</script>

<style scoped>
.sentinel-page { padding: 20px; max-width: 1400px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.header-left h2 { margin: 0; }
.subtitle { color: #8c8c8c; font-size: 13px; margin-left: 12px; }
.team-overview { margin-bottom: 16px; }
.agent-flow { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.flow-stage { width: 100%; padding: 12px; border-radius: 8px; background: #fafafa; }
.stage-label { font-size: 12px; font-weight: 600; color: #666; margin-bottom: 8px; }
.stage-agents { display: flex; flex-wrap: wrap; gap: 6px; }
.agent-chip { padding: 4px 10px; border-radius: 14px; font-size: 12px; background: white; border: 1px solid #e7e7e7; position: relative; }
.agent-chip.active { border-color: #e6a23c; background: #fef0e0; }
.agent-chip.analyst { border-color: #b7eb8f; background: #f6ffed; }
.agent-chip.director { border-color: #91caff; background: #e6f4ff; font-weight: 600; }
.chip-badge { position: absolute; top: -4px; right: -4px; background: #f56c6c; color: white; border-radius: 50%; width: 14px; height: 14px; font-size: 9px; display: flex; align-items: center; justify-content: center; }
.flow-arrow { font-size: 12px; color: #bbb; padding: 2px 0; }
.content-grid { display: grid; grid-template-columns: 300px 1fr; gap: 16px; }
.stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.stat-item { text-align: center; }
.stat-num { font-size: 24px; font-weight: 700; color: #1d2129; }
.stat-label { font-size: 11px; color: #8c8c8c; }
.mt-12 { margin-top: 12px; }
.decision-item { padding: 8px 0; border-bottom: 1px solid #f0f0f0; }
.decision-item:last-child { border-bottom: none; }
.decision-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.decision-date { font-size: 11px; color: #bbb; }
.decision-body { font-size: 12px; color: #666; }
@media (max-width: 900px) { .content-grid { grid-template-columns: 1fr; } }

.scan-panel { margin-top: 16px; }
.scan-logs { max-height: 350px; overflow-y: auto; }
.scan-log-item {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 8px; border-radius: 4px; font-size: 12px;
  border-bottom: 1px solid #f8f8f8;
}
.scan-log-item:hover { background: #fafafa; }
.log-icon { font-size: 14px; flex-shrink: 0; }
.log-msg { flex: 1; color: #333; }
.log-status { flex-shrink: 0; }
.log-sentinels_complete, .log-analysts_complete, .log-complete { background: #f6ffed; font-weight: 500; }
.log-error { background: #fff2f0; }
.scan-loading { display: flex; align-items: center; gap: 8px; padding: 12px; color: #666; font-size: 12px; }
</style>

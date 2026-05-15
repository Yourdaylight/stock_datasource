<template>
  <div class="sentinel-view">
    <!-- Header -->
    <div class="page-header">
      <div class="header-left">
        <h2>哨兵选股系统</h2>
        <span class="subtitle">三层Agent分级监控 · 异常驱动决策</span>
      </div>
      <el-button type="primary" :loading="scanning" @click="handleScan">
        <el-icon><Refresh /></el-icon>
        执行扫描
      </el-button>
    </div>

    <!-- System Status Cards -->
    <el-row :gutter="16" class="status-row">
      <el-col :span="6">
        <el-card shadow="hover" class="status-card">
          <div class="stat-label">数据哨兵</div>
          <div class="stat-value">{{ status?.sentinels?.length || 0 }}</div>
          <div class="stat-desc">持续监控中</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="status-card">
          <div class="stat-label">分析师</div>
          <div class="stat-value">{{ status?.analysts?.length || 0 }}</div>
          <div class="stat-desc">等待异常信号</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="status-card">
          <div class="stat-label">今日告警</div>
          <div class="stat-value highlight">{{ alerts.length }}</div>
          <div class="stat-desc">异常事件</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="status-card">
          <div class="stat-label">投资决策</div>
          <div class="stat-value">{{ decisions.length }}</div>
          <div class="stat-desc">历史决策</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Architecture Diagram -->
    <el-card class="arch-card">
      <template #header>
        <span>系统架构</span>
      </template>
      <div class="arch-diagram">
        <div class="tier tier-3">
          <div class="tier-label">Tier 3: 投资总监</div>
          <div class="agent-box director">LLM驱动决策</div>
        </div>
        <div class="tier-arrow">▲ AnalystReport</div>
        <div class="tier tier-2">
          <div class="tier-label">Tier 2: 分析师</div>
          <div class="agent-row">
            <div class="agent-box analyst" v-for="a in (status?.analysts || [])" :key="a.type">
              {{ analystNames[a.type] || a.type }}
              <span class="badge" v-if="a.report_count > 0">{{ a.report_count }}</span>
            </div>
          </div>
        </div>
        <div class="tier-arrow">▲ SentinelAlert (Redis Pub/Sub)</div>
        <div class="tier tier-1">
          <div class="tier-label">Tier 1: 数据哨兵</div>
          <div class="agent-row">
            <div
              class="agent-box sentinel"
              v-for="s in (status?.sentinels || [])"
              :key="s.type"
              :class="{ active: s.alert_count > 0, silent: s.consecutive_silent > 0 }"
            >
              {{ sentinelNames[s.type] || s.type }}
              <span class="badge" v-if="s.alert_count > 0">{{ s.alert_count }}</span>
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- Alerts Table -->
    <el-card class="alerts-card">
      <template #header>
        <div class="card-header">
          <span>最近告警</span>
          <el-select v-model="alertFilter" placeholder="所有类型" clearable size="small" style="width: 150px">
            <el-option label="市场风险" value="market_risk" />
            <el-option label="MA交叉" value="ma_crossover" />
            <el-option label="量能异常" value="volume_anomaly" />
            <el-option label="资金流向" value="capital_flow" />
            <el-option label="新闻情绪" value="news_sentiment" />
            <el-option label="RPS突破" value="rps_breakout" />
            <el-option label="财务异常" value="financial_anomaly" />
            <el-option label="板块资金" value="sector_flow" />
            <el-option label="池变动" value="pool_change" />
          </el-select>
        </div>
      </template>
      <el-table :data="filteredAlerts" stripe style="width: 100%" max-height="400">
        <el-table-column prop="severity" label="级别" width="80">
          <template #default="{ row }">
            <el-tag :type="severityType(row.severity)" size="small">
              {{ severityLabel(row.severity) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="sentinel_type" label="来源" width="110">
          <template #default="{ row }">
            {{ sentinelNames[row.sentinel_type] || row.sentinel_type }}
          </template>
        </el-table-column>
        <el-table-column prop="ts_code" label="标的" width="100" />
        <el-table-column prop="description" label="描述" min-width="300" />
        <el-table-column prop="deviation_pct" label="偏离度" width="90">
          <template #default="{ row }">
            <span :class="row.deviation_pct > 0 ? 'text-red' : 'text-green'">
              {{ row.deviation_pct?.toFixed(1) }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="timestamp" label="时间" width="180" />
      </el-table>
    </el-card>

    <!-- Decisions -->
    <el-card class="decisions-card" v-if="decisions.length > 0">
      <template #header>
        <span>投资决策历史</span>
      </template>
      <el-table :data="decisions" stripe style="width: 100%">
        <el-table-column prop="trade_date" label="日期" width="100" />
        <el-table-column prop="market_regime" label="市场环境" width="120">
          <template #default="{ row }">
            <el-tag :type="regimeType(row.market_regime)" size="small">
              {{ regimeLabel(row.market_regime) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="market_risk_level" label="风险" width="80" />
        <el-table-column prop="suggested_position" label="建议仓位" width="100">
          <template #default="{ row }">
            {{ (row.suggested_position * 100).toFixed(0) }}%
          </template>
        </el-table-column>
        <el-table-column prop="buy_count" label="买入" width="60" />
        <el-table-column prop="sell_count" label="卖出" width="60" />
        <el-table-column prop="confidence" label="信心度" width="90">
          <template #default="{ row }">
            {{ (row.confidence * 100).toFixed(0) }}%
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="生成时间" width="180" />
      </el-table>
    </el-card>

    <!-- Scan Result Dialog -->
    <el-dialog v-model="showResult" title="扫描结果" width="700px">
      <div v-if="scanResult">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="告警数">{{ scanResult.sentinel_alerts }}</el-descriptions-item>
          <el-descriptions-item label="报告数">{{ scanResult.analyst_reports }}</el-descriptions-item>
          <el-descriptions-item label="生成决策">{{ scanResult.decision_produced ? '是' : '否' }}</el-descriptions-item>
          <el-descriptions-item label="时间">{{ scanResult.timestamp }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="scanResult.decision" class="decision-detail">
          <h4>投资决策</h4>
          <pre>{{ JSON.stringify(scanResult.decision, null, 2) }}</pre>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { triggerScan, getStatus, getDecisions, getAlerts } from '@/api/sentinel'
import type { SentinelAlert, InvestmentDecision, SentinelStatus } from '@/api/sentinel'

const scanning = ref(false)
const showResult = ref(false)
const scanResult = ref<any>(null)
const status = ref<SentinelStatus | null>(null)
const alerts = ref<SentinelAlert[]>([])
const decisions = ref<InvestmentDecision[]>([])
const alertFilter = ref('')

const sentinelNames: Record<string, string> = {
  market_risk: '市场风险',
  sector_flow: '板块资金',
  ma_crossover: 'MA交叉',
  volume_anomaly: '量能异常',
  news_sentiment: '新闻情绪',
  capital_flow: '资金流向',
  rps_breakout: 'RPS突破',
  financial_anomaly: '财务异常',
  pool_change: '池变动',
}

const analystNames: Record<string, string> = {
  market_environment: '市场环境',
  sector_rotation: '板块轮动',
  stock_quality: '个股质量',
  timing: '择时',
}

const filteredAlerts = computed(() => {
  if (!alertFilter.value) return alerts.value
  return alerts.value.filter(a => a.sentinel_type === alertFilter.value)
})

function severityType(severity: string) {
  return { critical: 'danger', warning: 'warning', info: 'info' }[severity] || 'info'
}
function severityLabel(severity: string) {
  return { critical: '严重', warning: '警告', info: '信息' }[severity] || severity
}
function regimeType(regime: string) {
  const map: Record<string, string> = { bull: 'success', bear: 'danger', consolidation: 'info', transition_up: 'warning', transition_down: 'warning' }
  return map[regime] || 'info'
}
function regimeLabel(regime: string) {
  const map: Record<string, string> = { bull: '牛市', bear: '熊市', consolidation: '震荡', transition_up: '转多', transition_down: '转空' }
  return map[regime] || regime
}

async function handleScan() {
  scanning.value = true
  try {
    const res = await triggerScan()
    scanResult.value = res.data?.result || res.data
    showResult.value = true
    // Refresh data after scan
    await loadData()
  } catch (e: any) {
    console.error('Scan failed:', e)
  } finally {
    scanning.value = false
  }
}

async function loadData() {
  try {
    const [statusRes, alertsRes, decisionsRes] = await Promise.allSettled([
      getStatus(),
      getAlerts({ limit: 50 }),
      getDecisions(10),
    ])
    if (statusRes.status === 'fulfilled') status.value = (statusRes.value as any).data?.data
    if (alertsRes.status === 'fulfilled') alerts.value = (alertsRes.value as any).data?.data || []
    if (decisionsRes.status === 'fulfilled') decisions.value = (decisionsRes.value as any).data?.data || []
  } catch (e) {
    console.error('Load data failed:', e)
  }
}

onMounted(loadData)
</script>

<style scoped>
.sentinel-view {
  padding: 20px;
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
.subtitle { color: #909399; font-size: 14px; margin-left: 12px; }
.status-row { margin-bottom: 20px; }
.status-card { text-align: center; }
.stat-label { color: #909399; font-size: 13px; }
.stat-value { font-size: 32px; font-weight: bold; margin: 8px 0; color: #303133; }
.stat-value.highlight { color: #e6a23c; }
.stat-desc { color: #c0c4cc; font-size: 12px; }
.arch-card { margin-bottom: 20px; }
.arch-diagram { padding: 10px 0; }
.tier { margin: 8px 0; padding: 12px; border-radius: 8px; }
.tier-1 { background: #f0f9eb; }
.tier-2 { background: #fdf6ec; }
.tier-3 { background: #ecf5ff; }
.tier-label { font-weight: bold; margin-bottom: 8px; font-size: 13px; color: #606266; }
.tier-arrow { text-align: center; color: #909399; font-size: 12px; margin: 4px 0; }
.agent-row { display: flex; flex-wrap: wrap; gap: 8px; }
.agent-box {
  padding: 6px 12px; border-radius: 4px; font-size: 12px;
  border: 1px solid #dcdfe6; background: white; position: relative;
}
.agent-box.sentinel.active { border-color: #e6a23c; background: #fef0e0; }
.agent-box.sentinel.silent { opacity: 0.6; }
.agent-box.analyst { border-color: #e6a23c; }
.agent-box.director { border-color: #409eff; font-weight: bold; }
.badge {
  position: absolute; top: -6px; right: -6px;
  background: #f56c6c; color: white; border-radius: 50%;
  width: 16px; height: 16px; font-size: 10px;
  display: flex; align-items: center; justify-content: center;
}
.alerts-card, .decisions-card { margin-bottom: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.text-red { color: #f56c6c; }
.text-green { color: #67c23a; }
.decision-detail { margin-top: 16px; }
.decision-detail pre { background: #f5f7fa; padding: 12px; border-radius: 4px; font-size: 12px; max-height: 400px; overflow: auto; }
</style>

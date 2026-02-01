<template>
  <div class="arena-detail">
    <!-- Header -->
    <div class="page-header">
      <div class="header-left">
        <t-button variant="text" @click="goBack">
          <template #icon><t-icon name="chevron-left" /></template>
          返回列表
        </t-button>
        <h1>{{ arena?.name || '竞技场详情' }}</h1>
        <t-tag :theme="getStateTagTheme(arena?.state)" size="large">
          {{ getStateLabel(arena?.state) }}
        </t-tag>
      </div>
      <div class="header-actions">
        <t-button 
          v-if="arena?.state === 'created'" 
          theme="primary"
          @click="handleStart"
        >
          启动竞技
        </t-button>
        <t-button 
          v-else-if="isRunning" 
          theme="warning"
          @click="handlePause"
        >
          暂停
        </t-button>
        <t-button 
          v-else-if="arena?.state === 'paused'" 
          theme="success"
          @click="handleResume"
        >
          恢复
        </t-button>
        <t-button @click="showInterventionDialog = true" :disabled="!isRunning">
          <template #icon><t-icon name="edit" /></template>
          人工干预
        </t-button>
      </div>
    </div>

    <!-- Stats Overview -->
    <div class="stats-overview">
      <t-card class="stat-card">
        <div class="stat-content">
          <t-icon name="user" class="stat-icon" size="32px" />
          <div class="stat-info">
            <span class="stat-value">{{ arena?.active_strategies || 0 }}</span>
            <span class="stat-label">活跃策略</span>
          </div>
        </div>
      </t-card>
      <t-card class="stat-card">
        <div class="stat-content">
          <t-icon name="chat" class="stat-icon" size="32px" />
          <div class="stat-info">
            <span class="stat-value">{{ arena?.discussion_rounds || 0 }}</span>
            <span class="stat-label">讨论轮次</span>
          </div>
        </div>
      </t-card>
      <t-card class="stat-card">
        <div class="stat-content">
          <t-icon name="time" class="stat-icon" size="32px" />
          <div class="stat-info">
            <span class="stat-value">{{ formatDuration(arena?.duration_seconds) }}</span>
            <span class="stat-label">运行时长</span>
          </div>
        </div>
      </t-card>
      <t-card class="stat-card">
        <div class="stat-content">
          <t-icon name="chart-pie" class="stat-icon" size="32px" />
          <div class="stat-info">
            <span class="stat-value">{{ arena?.eliminated_strategies || 0 }}</span>
            <span class="stat-label">已淘汰</span>
          </div>
        </div>
      </t-card>
    </div>

    <!-- Main Content -->
    <div class="main-content">
      <!-- Left: Thinking Stream -->
      <t-card class="thinking-panel">
        <template #header>
          <div class="panel-header">
            <span>思考流</span>
            <t-button variant="text" size="small" @click="clearMessages">清空</t-button>
          </div>
        </template>
        <div ref="messagesContainer" class="messages-container">
          <div 
            v-for="message in thinkingMessages" 
            :key="message.id"
            class="message-item"
            :class="`message-${message.message_type}`"
          >
            <div class="message-header">
              <t-tag :theme="getAgentTagTheme(message.agent_role)" size="small">
                {{ getAgentLabel(message.agent_role) }}
              </t-tag>
              <span class="message-time">{{ formatTime(message.timestamp) }}</span>
            </div>
            <div class="message-content" v-html="formatContent(message.content)"></div>
          </div>
          <div v-if="thinkingMessages.length === 0" class="no-messages">
            <t-empty description="暂无思考消息">
              <p v-if="!isRunning">启动竞技场后将显示Agent思考过程</p>
            </t-empty>
          </div>
        </div>
      </t-card>

      <!-- Right: Leaderboard & Charts -->
      <div class="right-panel">
        <!-- Tabs for different views -->
        <t-card class="right-tabs-panel">
          <t-tabs v-model="activeRightTab">
            <!-- Leaderboard Tab -->
            <t-tab-panel label="排行榜" value="leaderboard">
              <t-table 
                :data="leaderboard" 
                size="small"
                row-key="strategy_id"
                @row-click="handleStrategyClick"
                style="cursor: pointer;"
              >
                <t-table-column prop="rank" title="排名" width="60">
                  <template #cell="{ row }">
                    <span :class="`rank-${row.rank}`">{{ row.rank }}</span>
                  </template>
                </t-table-column>
                <t-table-column prop="name" title="策略名称" />
                <t-table-column prop="score" title="评分" width="80">
                  <template #cell="{ row }">
                    {{ row.score.toFixed(1) }}
                  </template>
                </t-table-column>
                <t-table-column prop="stage" title="阶段" width="80">
                  <template #cell="{ row }">
                    <t-tag size="small">{{ getStageLabel(row.stage) }}</t-tag>
                  </template>
                </t-table-column>
              </t-table>
            </t-tab-panel>

            <!-- Radar Chart Tab -->
            <t-tab-panel label="评分维度" value="radar">
              <ScoreRadarChart :data="radarChartData" />
            </t-tab-panel>

            <!-- Return Curve Tab -->
            <t-tab-panel label="收益曲线" value="returns">
              <ReturnCurveChart :data="returnCurveData" :benchmark="benchmarkData" />
            </t-tab-panel>

            <!-- Elimination Timeline Tab -->
            <t-tab-panel label="淘汰历史" value="elimination">
              <EliminationTimeline :events="eliminationEvents" />
            </t-tab-panel>
          </t-tabs>
        </t-card>

        <!-- Discussion Control -->
        <t-card class="discussion-panel">
          <template #header>
            <span>讨论控制</span>
          </template>
          <div class="discussion-controls">
            <t-button 
              theme="primary" 
              @click="triggerDiscussion('debate')"
              :disabled="!isRunning"
            >
              辩论模式
            </t-button>
            <t-button 
              @click="triggerDiscussion('collaboration')"
              :disabled="!isRunning"
            >
              协作模式
            </t-button>
            <t-button 
              @click="triggerDiscussion('review')"
              :disabled="!isRunning"
            >
              评审模式
            </t-button>
          </div>
          <t-divider>周期评估</t-divider>
          <div class="evaluation-controls">
            <t-button 
              size="small" 
              @click="triggerEvaluation('weekly')"
              :disabled="!isRunning"
            >
              周评
            </t-button>
            <t-button 
              size="small" 
              @click="triggerEvaluation('monthly')"
              :disabled="!isRunning"
            >
              月评
            </t-button>
          </div>
        </t-card>
      </div>
    </div>

    <!-- Human Intervention Dialog -->
    <t-dialog 
      v-model:visible="showInterventionDialog" 
      header="人工干预" 
      width="500px"
      :confirm-btn="{ content: '确认干预', loading: interventionLoading }"
      @confirm="submitIntervention"
    >
      <t-form :data="interventionForm" label-width="100px">
        <t-form-item label="干预类型">
          <t-select v-model="interventionForm.action" style="width: 100%;">
            <t-option label="注入消息" value="inject_message" />
            <t-option label="调整评分" value="adjust_score" />
            <t-option label="强制淘汰" value="eliminate_strategy" />
            <t-option label="添加策略" value="add_strategy" />
          </t-select>
        </t-form-item>

        <template v-if="interventionForm.action === 'inject_message'">
          <t-form-item label="消息内容">
            <t-textarea 
              v-model="interventionForm.message" 
              :autosize="{ minRows: 4 }"
              placeholder="输入要注入到讨论中的消息..."
            />
          </t-form-item>
        </template>

        <template v-if="interventionForm.action === 'adjust_score' || interventionForm.action === 'eliminate_strategy'">
          <t-form-item label="目标策略">
            <t-select v-model="interventionForm.target_strategy_id" style="width: 100%;">
              <t-option 
                v-for="item in leaderboard" 
                :key="item.strategy_id"
                :label="item.name"
                :value="item.strategy_id"
              />
            </t-select>
          </t-form-item>
        </template>

        <template v-if="interventionForm.action === 'adjust_score'">
          <t-form-item label="分数调整">
            <t-slider 
              v-model="interventionForm.score_adjustment" 
              :min="-50" 
              :max="50"
              :marks="{ '-50': '-50', 0: '0', 50: '+50' }"
              :input-number-props="{ theme: 'normal' }"
            />
          </t-form-item>
        </template>

        <t-form-item label="原因说明">
          <t-textarea 
            v-model="interventionForm.reason" 
            :autosize="{ minRows: 2 }"
            placeholder="说明干预原因..."
          />
        </t-form-item>
      </t-form>
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { MessagePlugin } from 'tdesign-vue-next';
import { useArenaStore } from '@/stores/arena';
import { marked } from 'marked';
import ScoreRadarChart from './components/ScoreRadarChart.vue';
import ReturnCurveChart from './components/ReturnCurveChart.vue';
import EliminationTimeline from './components/EliminationTimeline.vue';

const route = useRoute();
const router = useRouter();
const arenaStore = useArenaStore();

// Refs
const messagesContainer = ref<HTMLElement | null>(null);
const activeRightTab = ref('leaderboard');
const showInterventionDialog = ref(false);
const interventionLoading = ref(false);
const interventionForm = ref({
  action: 'inject_message' as 'inject_message' | 'adjust_score' | 'eliminate_strategy' | 'add_strategy',
  target_strategy_id: '',
  message: '',
  score_adjustment: 0,
  reason: '',
});

// Computed
const arenaId = computed(() => route.params.id as string);
const arena = computed(() => arenaStore.currentArena);
const leaderboard = computed(() => arenaStore.leaderboard);
const thinkingMessages = computed(() => arenaStore.thinkingMessages);
const eliminationEvents = computed(() => arenaStore.eliminationEvents);
const isRunning = computed(() => arenaStore.isRunning);

// Radar chart data
const radarChartData = computed(() => {
  return leaderboard.value.slice(0, 5).map((item) => ({
    name: item.name,
    profitability: Math.min(100, item.score * 1.2),
    risk_control: Math.min(100, item.score * 0.9),
    stability: Math.min(100, item.score * 1.0),
    adaptability: Math.min(100, item.score * 0.85),
  }));
});

// Return curve data (mock)
const returnCurveData = computed(() => {
  return leaderboard.value.slice(0, 3).map((item, index) => ({
    name: item.name,
    dates: Array.from({ length: 30 }, (_, i) => {
      const date = new Date();
      date.setDate(date.getDate() - (30 - i));
      return date.toISOString().split('T')[0];
    }),
    returns: Array.from({ length: 30 }, (_, i) => {
      const base = (item.score - 50) / 10;
      return base + Math.sin(i / 5 + index) * 2 + i * 0.2;
    }),
  }));
});

const benchmarkData = computed(() => ({
  name: '沪深300',
  dates: returnCurveData.value[0]?.dates || [],
  returns: Array.from({ length: 30 }, (_, i) => i * 0.1 - 2),
}));

// Methods
function goBack() {
  router.push('/arena');
}

function handleStrategyClick({ row }: { row: { strategy_id: string } }) {
  router.push(`/arena/${arenaId.value}/strategy/${row.strategy_id}`);
}

function getStateTagTheme(state?: string): 'default' | 'primary' | 'warning' | 'danger' | 'success' {
  if (!state) return 'default';
  const themes: Record<string, 'default' | 'primary' | 'warning' | 'danger' | 'success'> = {
    created: 'default',
    initializing: 'warning',
    discussing: 'primary',
    backtesting: 'primary',
    simulating: 'success',
    evaluating: 'warning',
    paused: 'warning',
    completed: 'success',
    failed: 'danger',
  };
  return themes[state] || 'default';
}

function getStateLabel(state?: string) {
  if (!state) return '未知';
  const labels: Record<string, string> = {
    created: '已创建',
    initializing: '初始化中',
    discussing: '讨论中',
    backtesting: '回测中',
    simulating: '模拟交易',
    evaluating: '评估中',
    paused: '已暂停',
    completed: '已完成',
    failed: '失败',
  };
  return labels[state] || state;
}

function getAgentTagTheme(role: string): 'default' | 'primary' | 'warning' | 'danger' | 'success' {
  const themes: Record<string, 'default' | 'primary' | 'warning' | 'danger' | 'success'> = {
    strategy_generator: 'primary',
    strategy_reviewer: 'warning',
    risk_analyst: 'danger',
    market_sentiment: 'success',
    quant_researcher: 'default',
    human: 'success',
    system: 'default',
  };
  return themes[role] || 'default';
}

function getAgentLabel(role: string) {
  const labels: Record<string, string> = {
    strategy_generator: '策略生成',
    strategy_reviewer: '策略评审',
    risk_analyst: '风险分析',
    market_sentiment: '情绪分析',
    quant_researcher: '量化研究',
    human: '人工干预',
    system: '系统',
  };
  return labels[role] || role;
}

function getStageLabel(stage: string) {
  const labels: Record<string, string> = {
    backtest: '回测',
    simulated: '模拟',
    live: '实盘',
  };
  return labels[stage] || stage;
}

function formatDuration(seconds?: number) {
  if (!seconds) return '0秒';
  if (seconds < 60) return `${Math.round(seconds)}秒`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}分钟`;
  return `${Math.round(seconds / 3600)}小时`;
}

function formatTime(timestamp: string) {
  const date = new Date(timestamp);
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function formatContent(content: string) {
  try {
    return marked.parse(content);
  } catch {
    return content;
  }
}

function clearMessages() {
  arenaStore.clearThinkingMessages();
}

async function handleStart() {
  try {
    await arenaStore.startArena(arenaId.value);
    MessagePlugin.success('竞技场已启动');
  } catch {
    MessagePlugin.error('启动失败');
  }
}

async function handlePause() {
  try {
    await arenaStore.pauseArena(arenaId.value);
    MessagePlugin.success('竞技场已暂停');
  } catch {
    MessagePlugin.error('暂停失败');
  }
}

async function handleResume() {
  try {
    await arenaStore.resumeArena(arenaId.value);
    MessagePlugin.success('竞技场已恢复');
  } catch {
    MessagePlugin.error('恢复失败');
  }
}

async function triggerDiscussion(mode: 'debate' | 'collaboration' | 'review') {
  try {
    await arenaStore.startDiscussion(arenaId.value, mode);
    MessagePlugin.success(`已触发${mode}讨论`);
  } catch {
    MessagePlugin.error('触发讨论失败');
  }
}

async function triggerEvaluation(period: 'daily' | 'weekly' | 'monthly') {
  try {
    await arenaStore.triggerEvaluation(arenaId.value, period);
    MessagePlugin.success(`已触发${period}评估`);
  } catch {
    MessagePlugin.error('触发评估失败');
  }
}

async function submitIntervention() {
  interventionLoading.value = true;
  try {
    await arenaStore.sendIntervention(arenaId.value, {
      action: interventionForm.value.action,
      target_strategy_id: interventionForm.value.target_strategy_id || undefined,
      message: interventionForm.value.message || undefined,
      score_adjustment: interventionForm.value.score_adjustment || undefined,
      reason: interventionForm.value.reason || undefined,
    });
    MessagePlugin.success('干预指令已发送');
    showInterventionDialog.value = false;
    // Reset form
    interventionForm.value = {
      action: 'inject_message',
      target_strategy_id: '',
      message: '',
      score_adjustment: 0,
      reason: '',
    };
  } catch {
    MessagePlugin.error('干预失败');
  } finally {
    interventionLoading.value = false;
  }
}

// Auto-scroll to bottom when new messages arrive
watch(thinkingMessages, () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
    }
  });
}, { deep: true });

// Lifecycle
onMounted(async () => {
  // Validate arenaId before making requests
  const id = arenaId.value;
  if (!id || id === 'undefined' || id === 'null') {
    MessagePlugin.error('无效的竞技场ID，返回列表页');
    router.push('/arena');
    return;
  }

  try {
    await Promise.all([
      arenaStore.fetchArenaStatus(id),
      arenaStore.fetchLeaderboard(id),
      arenaStore.fetchEliminationHistory(id),
    ]);
    arenaStore.connectThinkingStream(id);
  } catch {
    MessagePlugin.error('加载竞技场失败');
    router.push('/arena');
    return;
  }

  // Periodic refresh
  const intervalId = setInterval(async () => {
    if (arena.value && arenaId.value && arenaId.value !== 'undefined') {
      await arenaStore.fetchArenaStatus(arenaId.value);
      await arenaStore.fetchLeaderboard(arenaId.value);
    }
  }, 5000);

  onUnmounted(() => {
    clearInterval(intervalId);
    arenaStore.disconnectThinkingStream();
  });
});
</script>

<style scoped>
.arena-detail {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-left h1 {
  font-size: 20px;
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.stats-overview {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  padding: 16px;
}

.stat-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon {
  color: var(--td-brand-color);
}

.stat-info {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
}

.stat-label {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.main-content {
  display: grid;
  grid-template-columns: 1fr 450px;
  gap: 20px;
}

.thinking-panel {
  height: calc(100vh - 320px);
  display: flex;
  flex-direction: column;
}

.thinking-panel :deep(.t-card__body) {
  flex: 1;
  overflow: hidden;
  padding: 0;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.messages-container {
  height: 100%;
  overflow-y: auto;
  padding: 16px;
}

.message-item {
  margin-bottom: 16px;
  padding: 12px;
  background: var(--td-bg-color-container);
  border-radius: 8px;
}

.message-item.message-thinking {
  background: var(--td-brand-color-light);
  border-left: 3px solid var(--td-brand-color);
}

.message-item.message-argument {
  background: var(--td-warning-color-light);
  border-left: 3px solid var(--td-warning-color);
}

.message-item.message-conclusion {
  background: var(--td-success-color-light);
  border-left: 3px solid var(--td-success-color);
}

.message-item.message-intervention {
  background: var(--td-success-color-light);
  border-left: 3px solid var(--td-success-color);
}

.message-item.message-error {
  background: var(--td-error-color-light);
  border-left: 3px solid var(--td-error-color);
}

.message-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.message-time {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.message-content {
  font-size: 14px;
  line-height: 1.6;
}

.message-content :deep(h1),
.message-content :deep(h2),
.message-content :deep(h3) {
  margin-top: 0;
  margin-bottom: 8px;
}

.message-content :deep(p) {
  margin: 0 0 8px;
}

.message-content :deep(ul),
.message-content :deep(ol) {
  margin: 0 0 8px;
  padding-left: 20px;
}

.no-messages {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.right-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.right-tabs-panel {
  flex: 1;
  min-height: 400px;
}

.right-tabs-panel :deep(.t-card__body) {
  padding: 12px;
}

.rank-1 {
  color: #f5a623;
  font-weight: bold;
}

.rank-2 {
  color: #909399;
  font-weight: bold;
}

.rank-3 {
  color: #cd7f32;
  font-weight: bold;
}

.discussion-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.evaluation-controls {
  display: flex;
  gap: 8px;
}
</style>

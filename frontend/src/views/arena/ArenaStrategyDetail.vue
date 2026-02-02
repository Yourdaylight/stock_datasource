<template>
  <div class="arena-strategy-detail">
    <!-- Header -->
    <div class="page-header">
      <div class="header-left">
        <t-button variant="text" @click="goBack">
          <template #icon><t-icon name="chevron-left" /></template>
          返回竞技场
        </t-button>
        <h1>{{ strategy?.name || '策略详情' }}</h1>
        <t-tag v-if="strategy" :theme="getStageTagTheme(strategy.stage)">
          {{ getStageLabel(strategy.stage) }}
        </t-tag>
        <t-tag v-if="strategy && !strategy.is_active" theme="danger">已淘汰</t-tag>
      </div>
      <div class="header-actions">
        <t-button @click="refreshData">
          <template #icon><t-icon name="refresh" /></template>
          刷新
        </t-button>
      </div>
    </div>

    <!-- Loading state -->
    <t-skeleton v-if="loading" :loading="true" :row-col="[{ width: '100%' }, { width: '80%' }, { width: '60%' }, { width: '90%' }, { width: '70%' }]" />

    <template v-else-if="strategy">
      <!-- Basic Info -->
      <t-row :gutter="20" class="info-section">
        <t-col :span="8">
          <t-card>
            <template #header>
              <span>策略信息</span>
            </template>
            <t-descriptions :column="2" bordered>
              <t-descriptions-item label="策略ID">{{ strategy.id }}</t-descriptions-item>
              <t-descriptions-item label="生成Agent">
                <t-tag size="small">{{ getAgentLabel(strategy.agent_role) }}</t-tag>
              </t-descriptions-item>
              <t-descriptions-item label="当前排名">
                <span :class="`rank-${strategy.current_rank}`">
                  第 {{ strategy.current_rank }} 名
                </span>
              </t-descriptions-item>
              <t-descriptions-item label="当前评分">
                <span class="score">{{ strategy.current_score.toFixed(1) }}</span>
              </t-descriptions-item>
              <t-descriptions-item label="策略描述" :span="2">
                {{ strategy.description }}
              </t-descriptions-item>
            </t-descriptions>
          </t-card>
        </t-col>
        <t-col :span="4">
          <t-card>
            <template #header>
              <span>评分维度</span>
            </template>
            <ScoreRadarChart :data="radarData" />
          </t-card>
        </t-col>
      </t-row>

      <!-- Strategy Logic -->
      <t-card class="logic-section">
        <template #header>
          <span>策略逻辑</span>
        </template>
        <div class="logic-content">
          <div v-if="strategy.logic" class="logic-text" v-html="formatLogic(strategy.logic)"></div>
          <t-empty v-else description="暂无策略逻辑描述" />
        </div>
        
        <t-divider align="left">交易规则</t-divider>
        <div class="rules-section" v-if="strategy.rules">
          <t-row :gutter="20">
            <t-col :span="4">
              <div class="rule-item">
                <span class="rule-label">买入条件</span>
                <div class="rule-value">{{ strategy.rules.buy_condition || '-' }}</div>
              </div>
            </t-col>
            <t-col :span="4">
              <div class="rule-item">
                <span class="rule-label">卖出条件</span>
                <div class="rule-value">{{ strategy.rules.sell_condition || '-' }}</div>
              </div>
            </t-col>
            <t-col :span="4">
              <div class="rule-item">
                <span class="rule-label">止损/止盈</span>
                <div class="rule-value">
                  {{ strategy.rules.stop_loss ? `-${(Number(strategy.rules.stop_loss) * 100).toFixed(1)}%` : '-' }}
                  /
                  {{ strategy.rules.take_profit ? `+${(Number(strategy.rules.take_profit) * 100).toFixed(1)}%` : '-' }}
                </div>
              </div>
            </t-col>
          </t-row>
        </div>
      </t-card>

      <!-- Performance Tabs -->
      <t-card class="performance-section">
        <template #header>
          <span>绩效表现</span>
        </template>
        <t-tabs v-model="activeTab">
          <t-tab-panel label="回测结果" value="backtest">
            <div v-if="backtestResult">
              <t-row :gutter="20" class="metrics-row">
                <t-col :span="3">
                  <div class="metric-card">
                    <span class="metric-value" :class="{ positive: backtestResult.total_return > 0, negative: backtestResult.total_return < 0 }">
                      {{ (backtestResult.total_return * 100).toFixed(2) }}%
                    </span>
                    <span class="metric-label">总收益率</span>
                  </div>
                </t-col>
                <t-col :span="3">
                  <div class="metric-card">
                    <span class="metric-value" :class="{ positive: backtestResult.annual_return > 0, negative: backtestResult.annual_return < 0 }">
                      {{ (backtestResult.annual_return * 100).toFixed(2) }}%
                    </span>
                    <span class="metric-label">年化收益</span>
                  </div>
                </t-col>
                <t-col :span="3">
                  <div class="metric-card">
                    <span class="metric-value negative">
                      {{ (backtestResult.max_drawdown * 100).toFixed(2) }}%
                    </span>
                    <span class="metric-label">最大回撤</span>
                  </div>
                </t-col>
                <t-col :span="3">
                  <div class="metric-card">
                    <span class="metric-value">{{ backtestResult.sharpe_ratio.toFixed(2) }}</span>
                    <span class="metric-label">夏普比率</span>
                  </div>
                </t-col>
              </t-row>
              <ReturnCurveChart 
                :data="[{ name: strategy.name, dates: backtestResult.dates, returns: backtestResult.cumulative_returns }]" 
                :benchmark="benchmarkData"
              />
            </div>
            <t-empty v-else description="暂无回测数据" />
          </t-tab-panel>
          
          <t-tab-panel label="模拟持仓" value="simulated">
            <div v-if="positions.length > 0">
              <t-table :data="positions" stripe row-key="symbol">
                <t-table-column prop="symbol" title="股票代码" width="120" />
                <t-table-column prop="name" title="股票名称" />
                <t-table-column prop="quantity" title="持仓数量" width="100" />
                <t-table-column prop="avg_cost" title="成本价" width="100">
                  <template #cell="{ row }">
                    {{ row.avg_cost.toFixed(2) }}
                  </template>
                </t-table-column>
                <t-table-column prop="current_price" title="现价" width="100">
                  <template #cell="{ row }">
                    {{ row.current_price.toFixed(2) }}
                  </template>
                </t-table-column>
                <t-table-column prop="profit_loss" title="盈亏" width="120">
                  <template #cell="{ row }">
                    <span :class="{ positive: row.profit_loss > 0, negative: row.profit_loss < 0 }">
                      {{ row.profit_loss > 0 ? '+' : '' }}{{ row.profit_loss.toFixed(2) }}
                      ({{ row.profit_loss_pct > 0 ? '+' : '' }}{{ (row.profit_loss_pct * 100).toFixed(2) }}%)
                    </span>
                  </template>
                </t-table-column>
              </t-table>
            </div>
            <t-empty v-else description="暂无持仓数据" />
          </t-tab-panel>

          <t-tab-panel label="讨论历史" value="discussions">
            <div v-if="relatedDiscussions.length > 0">
              <t-collapse v-model="activeDiscussion">
                <t-collapse-panel 
                  v-for="discussion in relatedDiscussions" 
                  :key="discussion.id"
                  :header="`第 ${discussion.round_number} 轮 - ${getModeLabel(discussion.mode)}`"
                  :value="discussion.id"
                >
                  <div class="discussion-detail">
                    <p class="discussion-time">
                      {{ formatDateTime(discussion.started_at) }} - 
                      {{ discussion.completed_at ? formatDateTime(discussion.completed_at) : '进行中' }}
                    </p>
                    <div class="discussion-conclusions">
                      <div 
                        v-for="(conclusion, agentId) in discussion.conclusions" 
                        :key="agentId"
                        class="conclusion-item"
                      >
                        <t-tag size="small">{{ agentId }}</t-tag>
                        <p>{{ conclusion }}</p>
                      </div>
                    </div>
                  </div>
                </t-collapse-panel>
              </t-collapse>
            </div>
            <t-empty v-else description="暂无相关讨论记录" />
          </t-tab-panel>
        </t-tabs>
      </t-card>
    </template>

    <t-empty v-else description="策略不存在或已被删除" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { MessagePlugin } from 'tdesign-vue-next';
import { marked } from 'marked';
import * as arenaApi from '@/api/arena';
import type { Strategy, DiscussionRound } from '@/api/arena';
import ScoreRadarChart from './components/ScoreRadarChart.vue';
import ReturnCurveChart from './components/ReturnCurveChart.vue';

const route = useRoute();
const router = useRouter();

// State
const loading = ref(true);
const strategy = ref<Strategy | null>(null);
const backtestResult = ref<{
  total_return: number;
  annual_return: number;
  max_drawdown: number;
  sharpe_ratio: number;
  dates: string[];
  cumulative_returns: number[];
} | null>(null);
const positions = ref<Array<{
  symbol: string;
  name: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  profit_loss: number;
  profit_loss_pct: number;
}>>([]);
const relatedDiscussions = ref<DiscussionRound[]>([]);
const activeTab = ref('backtest');
const activeDiscussion = ref<string[]>([]);

// Computed
const arenaId = computed(() => route.params.arenaId as string);
const strategyId = computed(() => route.params.strategyId as string);

const radarData = computed(() => {
  if (!strategy.value) return [];
  // Mock score breakdown - in real implementation, this would come from API
  const score = strategy.value.current_score;
  return [{
    name: strategy.value.name,
    profitability: Math.min(100, score * 1.2),
    risk_control: Math.min(100, score * 0.9),
    stability: Math.min(100, score * 1.0),
    adaptability: Math.min(100, score * 0.85),
  }];
});

const benchmarkData = computed(() => {
  if (!backtestResult.value) return undefined;
  // Mock benchmark data
  return {
    name: '沪深300',
    dates: backtestResult.value.dates,
    returns: backtestResult.value.dates.map((_, i) => i * 0.05 - 5),
  };
});

// Methods
function goBack() {
  router.push(`/arena/${arenaId.value}`);
}

function getStageTagTheme(stage: string): 'default' | 'primary' | 'warning' | 'danger' | 'success' {
  const themes: Record<string, 'default' | 'primary' | 'warning' | 'danger' | 'success'> = {
    backtest: 'default',
    simulated: 'warning',
    live: 'success',
  };
  return themes[stage] || 'default';
}

function getStageLabel(stage: string) {
  const labels: Record<string, string> = {
    backtest: '回测阶段',
    simulated: '模拟交易',
    live: '实盘交易',
  };
  return labels[stage] || stage;
}

function getAgentLabel(role: string) {
  const labels: Record<string, string> = {
    strategy_generator: '策略生成Agent',
    strategy_reviewer: '策略评审Agent',
    risk_analyst: '风险分析Agent',
    market_sentiment: '情绪分析Agent',
    quant_researcher: '量化研究Agent',
  };
  return labels[role] || role;
}

function getModeLabel(mode: string) {
  const labels: Record<string, string> = {
    debate: '辩论模式',
    collaboration: '协作模式',
    review: '评审模式',
  };
  return labels[mode] || mode;
}

function formatLogic(logic: string) {
  try {
    return marked.parse(logic);
  } catch {
    return logic;
  }
}

function formatDateTime(timestamp: string) {
  return new Date(timestamp).toLocaleString('zh-CN');
}

async function fetchStrategyDetail() {
  loading.value = true;
  try {
    strategy.value = await arenaApi.getStrategyDetail(arenaId.value, strategyId.value);
    
    // Fetch related data in parallel
    await Promise.all([
      fetchBacktestResult(),
      fetchPositions(),
      fetchRelatedDiscussions(),
    ]);
  } catch (error) {
    MessagePlugin.error('获取策略详情失败');
    console.error(error);
  } finally {
    loading.value = false;
  }
}

async function fetchBacktestResult() {
  // Mock backtest data - in real implementation, this would come from API
  backtestResult.value = {
    total_return: 0.156,
    annual_return: 0.234,
    max_drawdown: -0.089,
    sharpe_ratio: 1.45,
    dates: Array.from({ length: 100 }, (_, i) => {
      const date = new Date();
      date.setDate(date.getDate() - (100 - i));
      return date.toISOString().split('T')[0];
    }),
    cumulative_returns: Array.from({ length: 100 }, (_, i) => {
      return Math.sin(i / 10) * 5 + i * 0.15 + Math.random() * 2 - 1;
    }),
  };
}

async function fetchPositions() {
  // Mock positions data
  if (strategy.value?.stage === 'simulated' || strategy.value?.stage === 'live') {
    positions.value = [
      {
        symbol: '000001.SZ',
        name: '平安银行',
        quantity: 1000,
        avg_cost: 10.5,
        current_price: 11.2,
        profit_loss: 700,
        profit_loss_pct: 0.067,
      },
      {
        symbol: '600000.SH',
        name: '浦发银行',
        quantity: 500,
        avg_cost: 8.0,
        current_price: 7.6,
        profit_loss: -200,
        profit_loss_pct: -0.05,
      },
    ];
  }
}

async function fetchRelatedDiscussions() {
  try {
    const response = await arenaApi.getDiscussions(arenaId.value);
    relatedDiscussions.value = response.discussions;
  } catch (error) {
    console.error('Failed to fetch discussions:', error);
  }
}

async function refreshData() {
  await fetchStrategyDetail();
  MessagePlugin.success('数据已刷新');
}

onMounted(() => {
  fetchStrategyDetail();
});
</script>

<style scoped>
.arena-strategy-detail {
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

.info-section {
  margin-bottom: 20px;
}

.rank-1 { color: #f5a623; font-weight: bold; }
.rank-2 { color: #909399; font-weight: bold; }
.rank-3 { color: #cd7f32; font-weight: bold; }

.score {
  font-size: 18px;
  font-weight: bold;
  color: var(--td-brand-color);
}

.logic-section {
  margin-bottom: 20px;
}

.logic-content {
  min-height: 100px;
}

.logic-text {
  line-height: 1.8;
}

.logic-text :deep(h1),
.logic-text :deep(h2),
.logic-text :deep(h3) {
  margin-top: 0;
}

.rules-section {
  margin-top: 16px;
}

.rule-item {
  text-align: center;
  padding: 16px;
  background: var(--td-bg-color-container);
  border-radius: 8px;
}

.rule-label {
  display: block;
  color: var(--td-text-color-secondary);
  font-size: 12px;
  margin-bottom: 8px;
}

.rule-value {
  font-size: 14px;
  font-weight: 500;
}

.performance-section :deep(.t-card__body) {
  padding: 16px;
}

.metrics-row {
  margin-bottom: 20px;
}

.metric-card {
  text-align: center;
  padding: 16px;
  background: var(--td-bg-color-container);
  border-radius: 8px;
}

.metric-value {
  display: block;
  font-size: 24px;
  font-weight: bold;
  margin-bottom: 8px;
}

.metric-value.positive {
  color: var(--td-success-color);
}

.metric-value.negative {
  color: var(--td-error-color);
}

.metric-label {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.positive {
  color: var(--td-success-color);
}

.negative {
  color: var(--td-error-color);
}

.discussion-detail {
  padding: 12px;
}

.discussion-time {
  color: var(--td-text-color-secondary);
  font-size: 12px;
  margin-bottom: 12px;
}

.conclusion-item {
  margin-bottom: 12px;
  padding: 12px;
  background: var(--td-bg-color-container);
  border-radius: 8px;
}

.conclusion-item p {
  margin: 8px 0 0;
}
</style>

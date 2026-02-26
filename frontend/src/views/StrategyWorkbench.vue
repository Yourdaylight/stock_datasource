<template>
  <div class="strategy-workbench">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1>智能策略工作台</h1>
      <p class="subtitle">创建、测试和优化您的交易策略</p>
    </div>

    <!-- 主要内容区域 -->
    <div class="workbench-content">
      <!-- 左侧策略列表 -->
      <div class="strategy-sidebar">
        <div class="sidebar-header">
          <h3>策略库</h3>
          <t-button 
            theme="primary" 
            size="small" 
            @click="showAIWizard = true"
          >
            <template #icon><AddIcon /></template>
            AI生成策略
          </t-button>
        </div>

        <!-- 策略分类标签 -->
        <div class="strategy-categories">
          <t-tag 
            v-for="category in categories" 
            :key="category.key"
            :theme="selectedCategory === category.key ? 'primary' : 'default'"
            @click="selectCategory(category.key)"
            class="category-tag"
          >
            {{ category.name }} ({{ category.count }})
          </t-tag>
        </div>

        <!-- 策略搜索 -->
        <t-input
          v-model="searchQuery"
          placeholder="搜索策略..."
          size="small"
          class="strategy-search"
        >
          <template #prefix-icon><SearchIcon /></template>
        </t-input>

        <!-- 策略列表 -->
        <div class="strategy-list">
          <div 
            v-for="strategy in filteredStrategies" 
            :key="strategy.id"
            :class="['strategy-item', { active: selectedStrategy?.id === strategy.id }]"
            @click="selectStrategy(strategy)"
          >
            <div class="strategy-header">
              <h4>{{ strategy.name }}</h4>
              <t-tag 
                :theme="getStrategyTypeColor(strategy.category)" 
                size="small"
              >
                {{ getCategoryName(strategy.category) }}
              </t-tag>
            </div>
            <p class="strategy-description">{{ strategy.description }}</p>
            <div class="strategy-meta">
              <span class="usage-count">使用: {{ strategy.usage_count }}次</span>
              <span class="risk-level" :class="`risk-${strategy.risk_level}`">
                {{ getRiskLevelName(strategy.risk_level) }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧主工作区 -->
      <div class="main-workspace">
        <!-- 策略详情 -->
        <div v-if="selectedStrategy" class="strategy-details">
          <div class="details-header">
            <h2>{{ selectedStrategy.name }}</h2>
            <div class="action-buttons">
              <t-button 
                theme="success" 
                @click="startBacktest"
                :loading="backtesting"
              >
                开始回测
              </t-button>
              <t-button 
                theme="warning" 
                @click="optimizeStrategy"
                :disabled="!selectedStrategy"
              >
                参数优化
              </t-button>
              <t-button 
                v-if="selectedStrategy.is_ai_generated"
                theme="default" 
                @click="explainStrategy"
              >
                AI解释
              </t-button>
            </div>
          </div>

          <!-- 策略信息标签页 -->
          <t-tabs v-model="activeTab" class="strategy-tabs">
            <!-- 基本信息 -->
            <t-tab-panel label="基本信息" value="info">
              <div class="strategy-info">
                <t-descriptions :column="2" bordered>
                  <t-descriptions-item label="策略ID">
                    {{ selectedStrategy.id }}
                  </t-descriptions-item>
                  <t-descriptions-item label="分类">
                    {{ getCategoryName(selectedStrategy.category) }}
                  </t-descriptions-item>
                  <t-descriptions-item label="风险等级">
                    <t-tag :theme="getRiskLevelColor(selectedStrategy.risk_level)">
                      {{ getRiskLevelName(selectedStrategy.risk_level) }}
                    </t-tag>
                  </t-descriptions-item>
                  <t-descriptions-item label="作者">
                    {{ selectedStrategy.author }}
                  </t-descriptions-item>
                  <t-descriptions-item label="版本">
                    {{ selectedStrategy.version }}
                  </t-descriptions-item>
                  <t-descriptions-item label="创建时间">
                    {{ formatDate(selectedStrategy.created_at) }}
                  </t-descriptions-item>
                </t-descriptions>

                <div class="strategy-description-full">
                  <h4>策略描述</h4>
                  <p>{{ selectedStrategy.description }}</p>
                </div>

                <div v-if="selectedStrategy.tags?.length" class="strategy-tags">
                  <h4>标签</h4>
                  <t-tag 
                    v-for="tag in selectedStrategy.tags" 
                    :key="tag"
                    size="small"
                    class="tag-item"
                  >
                    {{ tag }}
                  </t-tag>
                </div>
              </div>
            </t-tab-panel>

            <!-- 参数配置 -->
            <t-tab-panel label="参数配置" value="parameters">
              <div class="parameter-config">
                <h4>策略参数</h4>
                <t-form 
                  :data="strategyParams" 
                  label-width="120px"
                  size="small"
                >
                  <t-form-item 
                    v-for="param in selectedStrategy.parameter_schema" 
                    :key="param.name"
                    :label="param.description || param.name"
                    :name="param.name"
                  >
                    <t-input-number
                      v-if="param.type === 'int' || param.type === 'float'"
                      v-model="strategyParams[param.name]"
                      :min="param.min_value"
                      :max="param.max_value"
                      :decimal-places="param.type === 'float' ? 2 : 0"
                      :step="param.type === 'float' ? 0.01 : 1"
                    />
                    <t-switch
                      v-else-if="param.type === 'bool'"
                      v-model="strategyParams[param.name]"
                    />
                    <t-input
                      v-else
                      v-model="strategyParams[param.name]"
                    />
                    <div class="param-help">
                      默认值: {{ param.default }}
                      <span v-if="param.min_value !== undefined">
                        , 范围: {{ param.min_value }} - {{ param.max_value }}
                      </span>
                    </div>
                  </t-form-item>
                </t-form>
              </div>
            </t-tab-panel>

            <!-- 回测结果 -->
            <t-tab-panel label="回测结果" value="backtest">
              <div v-if="backtestResult" class="backtest-results">
                <BacktestResults :result="backtestResult" />
              </div>
              <div v-else class="no-backtest">
                <t-empty description="暂无回测结果">
                  <template #action>
                    <t-button theme="primary" @click="startBacktest">
                      开始回测
                    </t-button>
                  </template>
                </t-empty>
              </div>
            </t-tab-panel>

            <!-- 回测历史 -->
            <t-tab-panel label="回测历史" value="backtest_history">
              <div class="history-panel">
                <t-table
                  :data="filteredBacktestHistory"
                  :columns="historyColumns"
                  row-key="task_id"
                  size="small"
                  :loading="historyLoading"
                />
                <div v-if="!filteredBacktestHistory.length && !historyLoading" class="history-empty">
                  <t-empty description="暂无历史记录" />
                </div>
              </div>
            </t-tab-panel>

            <!-- AI洞察 -->
            <t-tab-panel 
              v-if="selectedStrategy?.is_ai_generated" 
              label="AI洞察" 
              value="ai_insights"
            >
              <div class="ai-insights">
                <div v-if="aiExplanation" class="ai-explanation">
                  <h4>策略解释</h4>
                  <div class="explanation-content" v-html="aiExplanation"></div>
                </div>
                
                <div v-if="selectedStrategy.generation_prompt" class="generation-info">
                  <h4>生成信息</h4>
                  <t-descriptions :column="1" bordered>
                    <t-descriptions-item label="生成提示">
                      {{ selectedStrategy.generation_prompt }}
                    </t-descriptions-item>
                    <t-descriptions-item label="使用模型">
                      {{ selectedStrategy.llm_model || '未知' }}
                    </t-descriptions-item>
                    <t-descriptions-item label="置信度">
                      <t-progress 
                        :percentage="(selectedStrategy.confidence_score || 0) * 100"
                        :color="getConfidenceColor(selectedStrategy.confidence_score)"
                      />
                    </t-descriptions-item>
                  </t-descriptions>
                </div>
              </div>
            </t-tab-panel>
          </t-tabs>
        </div>

        <!-- 空状态 -->
        <div v-else class="empty-workspace">
          <t-empty description="请选择一个策略开始工作">
            <template #action>
              <t-button theme="primary" @click="showAIWizard = true">
                创建AI策略
              </t-button>
            </template>
          </t-empty>
        </div>
      </div>
    </div>

    <!-- AI策略创建向导 -->
    <AIStrategyWizard 
      v-model="showAIWizard"
      @strategy-created="onStrategyCreated"
    />

    <!-- 回测配置对话框 -->
    <BacktestDialog
      v-model="showBacktestDialog"
      :strategy="selectedStrategy"
      :parameters="strategyParams"
      @backtest-started="onBacktestStarted"
    />
  </div>
</template>

<script>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { MessagePlugin, DialogPlugin } from 'tdesign-vue-next'
import { AddIcon, SearchIcon } from 'tdesign-icons-vue-next'
import AIStrategyWizard from '@/components/strategy/AIStrategyWizard.vue'
import BacktestDialog from '@/components/strategy/BacktestDialog.vue'
import BacktestResults from '@/components/strategy/BacktestResults.vue'
import { strategyApi } from '@/api/strategy'
import { backtestApi } from '@/api/backtest'

export default {
  name: 'StrategyWorkbench',
  components: {
    AIStrategyWizard,
    BacktestDialog,
    BacktestResults,
    AddIcon,
    SearchIcon
  },
  setup() {
    // 响应式数据
    const strategies = ref([])
    const selectedStrategy = ref(null)
    const selectedCategory = ref('all')
    const searchQuery = ref('')
    const activeTab = ref('info')
    const showAIWizard = ref(false)
    const showBacktestDialog = ref(false)
    const backtesting = ref(false)
    const backtestResult = ref(null)
    const backtestHistory = ref([])
    const historyLoading = ref(false)
    const aiExplanation = ref('')
    const strategyParams = reactive({})

    // 策略分类
    const categories = computed(() => [
      { key: 'all', name: '全部', count: strategies.value.length },
      { key: 'trend', name: '趋势策略', count: strategies.value.filter(s => s.category === 'trend').length },
      { key: 'mean_reversion', name: '均值回归', count: strategies.value.filter(s => s.category === 'mean_reversion').length },
      { key: 'momentum', name: '动量策略', count: strategies.value.filter(s => s.category === 'momentum').length },
      { key: 'ai_generated', name: 'AI策略', count: strategies.value.filter(s => s.is_ai_generated).length }
    ])

    // 过滤后的策略列表
    const filteredStrategies = computed(() => {
      let filtered = strategies.value || []

      // 分类过滤
      if (selectedCategory.value !== 'all') {
        if (selectedCategory.value === 'ai_generated') {
          filtered = filtered.filter(s => s.is_ai_generated)
        } else {
          filtered = filtered.filter(s => s.category === selectedCategory.value)
        }
      }

      // 搜索过滤
      if (searchQuery.value) {
        const query = searchQuery.value.toLowerCase()
        filtered = filtered.filter(s => 
          s.name.toLowerCase().includes(query) ||
          s.description.toLowerCase().includes(query) ||
          s.tags?.some(tag => tag.toLowerCase().includes(query))
        )
      }

      return filtered
    })

    const formatPercentValue = (value) => {
      if (value === null || value === undefined || Number.isNaN(value)) return '-'
      return `${Number(value).toFixed(2)}%`
    }

    const formatDateTime = (dateStr) => {
      if (!dateStr) return '-'
      return new Date(dateStr).toLocaleString('zh-CN')
    }

    const getReturnClass = (value) => {
      if (value > 0) return 'positive'
      if (value < 0) return 'negative'
      return ''
    }

    const loadBacktestHistory = async () => {
      historyLoading.value = true
      try {
        const results = await backtestApi.getResults(50)
        backtestHistory.value = Array.isArray(results) ? results : []
      } catch (error) {
        backtestHistory.value = []
      } finally {
        historyLoading.value = false
      }
    }

    const normalizeBacktestResult = (rawResult, fallbackStrategyId) => {
      if (!rawResult) return null

      const strategyId = rawResult.strategy_id || fallbackStrategyId || rawResult.strategy_name || ''
      const equityCurve = Array.isArray(rawResult.equity_curve)
        ? rawResult.equity_curve.reduce((acc, point) => {
            acc[point.date] = point.value
            return acc
          }, {})
        : (rawResult.equity_curve || {})

      const normalizedTrades = (rawResult.trades || []).map(trade => ({
        timestamp: trade.date || trade.timestamp,
        symbol: (rawResult.ts_codes && rawResult.ts_codes[0]) || trade.symbol || '',
        trade_type: trade.direction || trade.trade_type,
        quantity: trade.quantity,
        price: trade.price,
        commission: trade.commission ?? 0,
        trade_value: trade.amount ?? trade.trade_value ?? trade.quantity * trade.price,
        signal_reason: trade.signal_reason || ''
      }))

      return {
        id: rawResult.task_id || rawResult.id,
        strategy_id: strategyId,
        config: {
          strategy_id: strategyId,
          symbol: (rawResult.ts_codes && rawResult.ts_codes[0]) || '',
          start_date: rawResult.start_date,
          end_date: rawResult.end_date,
          initial_capital: rawResult.initial_capital,
          parameters: strategyParams
        },
        performance_metrics: rawResult.performance_metrics || {
          total_return: (rawResult.total_return ?? 0) / 100,
          annualized_return: (rawResult.annual_return ?? 0) / 100,
          excess_return: (rawResult.excess_return ?? 0) / 100,
          volatility: (rawResult.volatility ?? 0) / 100,
          sharpe_ratio: rawResult.sharpe_ratio ?? 0,
          max_drawdown: (rawResult.max_drawdown ?? 0) / 100,
          max_drawdown_duration: rawResult.max_drawdown_duration ?? 0,
          sortino_ratio: rawResult.sortino_ratio ?? 0,
          calmar_ratio: rawResult.calmar_ratio ?? 0,
          information_ratio: rawResult.information_ratio ?? 0,
          alpha: rawResult.alpha ?? 0,
          beta: rawResult.beta ?? 0,
          win_rate: (rawResult.win_rate ?? 0) / 100,
          profit_factor: rawResult.profit_factor ?? 0,
          total_trades: rawResult.trade_count ?? 0,
          winning_trades: rawResult.winning_trades ?? 0,
          losing_trades: rawResult.losing_trades ?? 0,
          avg_win: rawResult.avg_win ?? 0,
          avg_loss: rawResult.avg_loss ?? 0
        },
        risk_metrics: rawResult.risk_metrics || {
          var_95: (rawResult.var_95 ?? 0) / 100,
          cvar_95: (rawResult.cvar_95 ?? 0) / 100,
          skewness: rawResult.skewness ?? 0,
          kurtosis: rawResult.kurtosis ?? 0
        },
        trades: normalizedTrades,
        equity_curve: equityCurve,
        drawdown_series: rawResult.drawdown_series || {},
        daily_returns: rawResult.daily_returns || {},
        benchmark_curve: rawResult.benchmark_curve || {},
        created_at: rawResult.created_at || new Date().toISOString()
      }
    }

    const selectHistoryResult = (row) => {
      if (!row) return
      backtestResult.value = normalizeBacktestResult(row, selectedStrategy.value?.id)
      activeTab.value = 'backtest'
    }

    const historyColumns = [
      {
        colKey: 'created_at',
        title: '时间',
        width: 160,
        cell: (h, { row }) => formatDateTime(row.created_at || row.start_date)
      },
      {
        colKey: 'strategy_name',
        title: '策略',
        width: 140
      },
      {
        colKey: 'ts_codes',
        title: '标的',
        minWidth: 140,
        cell: (h, { row }) => (row.ts_codes || []).join(', ')
      },
      {
        colKey: 'total_return',
        title: '总收益率',
        width: 120,
        cell: (h, { row }) => h('span', { class: getReturnClass(row.total_return) }, formatPercentValue(row.total_return))
      },
      {
        colKey: 'max_drawdown',
        title: '最大回撤',
        width: 120,
        cell: (h, { row }) => formatPercentValue(row.max_drawdown)
      },
      {
        colKey: 'trade_count',
        title: '交易次数',
        width: 100
      },
      {
        colKey: 'actions',
        title: '操作',
        width: 80,
        cell: (h, { row }) => h('t-button', {
          theme: 'primary',
          size: 'small',
          variant: 'text',
          onClick: () => selectHistoryResult(row)
        }, '查看')
      }
    ]

    const filteredBacktestHistory = computed(() => {
      if (!selectedStrategy.value) return backtestHistory.value
      return backtestHistory.value.filter(item => item.strategy_name === selectedStrategy.value.id)
    })

    // 方法
    const loadStrategies = async () => {
      try {
        const response = await strategyApi.getStrategies()
        
        // 处理不同的响应格式
        let strategiesData = response.strategies || response.data || response
        
        if (Array.isArray(strategiesData)) {
          strategies.value = strategiesData
          console.log(`成功加载 ${strategies.value.length} 个策略:`, strategies.value.map(s => s.name))
        } else {
          console.error('策略数据不是数组:', strategiesData)
          strategies.value = []
        }
        
        if (!strategies.value || strategies.value.length === 0) {
          MessagePlugin.warning('未找到任何策略')
        } else {
          MessagePlugin.success(`成功加载 ${strategies.value.length} 个策略`)
        }
      } catch (error) {
        MessagePlugin.error('加载策略列表失败')
        console.error('加载策略失败:', error)
      }
    }

    const selectCategory = (category) => {
      selectedCategory.value = category
    }

    const selectStrategy = (strategy) => {
      selectedStrategy.value = strategy
      
      // 初始化参数
      Object.keys(strategyParams).forEach(key => {
        delete strategyParams[key]
      })
      
      if (strategy.parameter_schema) {
        strategy.parameter_schema.forEach(param => {
          strategyParams[param.name] = param.default
        })
      }

      // 清空之前的结果
      backtestResult.value = null
      aiExplanation.value = ''
      activeTab.value = 'info'
    }

    const startBacktest = () => {
      if (!selectedStrategy.value) {
        MessagePlugin.warning('请先选择一个策略')
        return
      }
      showBacktestDialog.value = true
    }

    const onBacktestStarted = async (config) => {
      backtesting.value = true
      showBacktestDialog.value = false
      
      try {
        const rawResult = await backtestApi.runBacktest({
          strategy_id: selectedStrategy.value.id,
          ts_codes: config.symbols || [],
          start_date: config.start_date,
          end_date: config.end_date,
          initial_capital: config.trading_config?.initial_capital,
          params: strategyParams
        })

        if ((rawResult.trade_count ?? 0) === 0) {
          MessagePlugin.warning('本次回测未产生交易，指标为 0。可延长日期区间或降低过滤条件（如关闭趋势过滤、降低分离度）。')
        }

        backtestResult.value = normalizeBacktestResult(rawResult, selectedStrategy.value.id)
        await loadBacktestHistory()
        activeTab.value = 'backtest'
        MessagePlugin.success('回测完成')
      } catch (error) {
        MessagePlugin.error('回测失败')
        console.error(error)
      } finally {
        backtesting.value = false
      }
    }

    const optimizeStrategy = async () => {
      if (!selectedStrategy.value) return

      try {
        const confirmResult = await DialogPlugin.confirm({
          header: '确认优化',
          body: '参数优化可能需要较长时间，确定要继续吗？',
          theme: 'warning'
        })

        if (confirmResult) {
          const response = await strategyApi.optimizeStrategy({
            strategy_id: selectedStrategy.value.id,
            parameters: strategyParams
          })

          MessagePlugin.success('优化完成')
          // 更新参数
          Object.assign(strategyParams, response.data.optimal_parameters)
        }
      } catch (error) {
        if (error !== 'cancel') {
          MessagePlugin.error('优化失败')
          console.error(error)
        }
      }
    }

    const explainStrategy = async () => {
      if (!selectedStrategy.value?.is_ai_generated) return

      try {
        const response = await strategyApi.explainStrategy(selectedStrategy.value.id)
        aiExplanation.value = response.data.explanation
        activeTab.value = 'ai_insights'
      } catch (error) {
        MessagePlugin.error('获取AI解释失败')
        console.error(error)
      }
    }

    const onStrategyCreated = (newStrategy) => {
      strategies.value.unshift(newStrategy)
      selectStrategy(newStrategy)
      MessagePlugin.success('AI策略创建成功')
    }

    // 辅助方法
    const getCategoryName = (category) => {
      const categoryMap = {
        trend: '趋势策略',
        mean_reversion: '均值回归',
        momentum: '动量策略',
        arbitrage: '套利策略',
        ai_generated: 'AI策略',
        custom: '自定义'
      }
      return categoryMap[category] || category
    }

    const getRiskLevelName = (level) => {
      const levelMap = {
        low: '低风险',
        medium: '中风险',
        high: '高风险',
        very_high: '极高风险'
      }
      return levelMap[level] || level
    }

    const getStrategyTypeColor = (category) => {
      const colorMap = {
        trend: 'success',
        mean_reversion: 'warning',
        momentum: 'danger',
        ai_generated: 'primary'
      }
      return colorMap[category] || 'info'
    }

    const getRiskLevelColor = (level) => {
      const colorMap = {
        low: 'success',
        medium: 'warning', 
        high: 'danger',
        very_high: 'danger'
      }
      return colorMap[level] || 'info'
    }

    const getConfidenceColor = (confidence) => {
      if (confidence >= 0.8) return '#67c23a'
      if (confidence >= 0.6) return '#e6a23c'
      return '#f56c6c'
    }

    const formatDate = (dateStr) => {
      return new Date(dateStr).toLocaleString('zh-CN')
    }

    // 生命周期
    onMounted(() => {
      loadStrategies()
      loadBacktestHistory()
    })

    return {
      // 数据
      strategies,
      selectedStrategy,
      selectedCategory,
      searchQuery,
      activeTab,
      showAIWizard,
      showBacktestDialog,
      backtesting,
      backtestResult,
      backtestHistory,
      historyLoading,
      aiExplanation,
      strategyParams,
      filteredBacktestHistory,
      historyColumns,
      categories,
      filteredStrategies,

      // 方法
      selectCategory,
      selectStrategy,
      startBacktest,
      onBacktestStarted,
      optimizeStrategy,
      explainStrategy,
      onStrategyCreated,
      getCategoryName,
      getRiskLevelName,
      getStrategyTypeColor,
      getRiskLevelColor,
      getConfidenceColor,
      formatDate
    }
  }
}
</script>

<style scoped>
.strategy-workbench {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #f5f7fa;
}

.page-header {
  background: white;
  padding: 24px;
  border-bottom: 1px solid #e4e7ed;
}

.page-header h1 {
  margin: 0 0 8px 0;
  font-size: 24px;
  color: #303133;
}

.subtitle {
  margin: 0;
  color: #909399;
  font-size: 14px;
}

.workbench-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.strategy-sidebar {
  width: 320px;
  background: white;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.sidebar-header h3 {
  margin: 0;
  font-size: 16px;
}

.strategy-categories {
  padding: 16px;
  border-bottom: 1px solid #e4e7ed;
}

.category-tag {
  margin: 0 8px 8px 0;
  cursor: pointer;
}

.strategy-search {
  margin: 16px;
}

.strategy-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 16px;
}

.strategy-item {
  padding: 12px;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.3s;
}

.strategy-item:hover {
  border-color: #409eff;
  box-shadow: 0 2px 4px rgba(64, 158, 255, 0.12);
}

.strategy-item.active {
  border-color: #409eff;
  background-color: #ecf5ff;
}

.strategy-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.strategy-header h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
}

.strategy-description {
  margin: 0 0 8px 0;
  font-size: 12px;
  color: #606266;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.strategy-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  color: #909399;
}

.risk-level {
  padding: 2px 6px;
  border-radius: 2px;
  font-size: 10px;
}

.risk-low { background-color: #f0f9ff; color: #67c23a; }
.risk-medium { background-color: #fdf6ec; color: #e6a23c; }
.risk-high { background-color: #fef0f0; color: #f56c6c; }

.main-workspace {
  flex: 1;
  background: white;
  margin: 16px;
  border-radius: 4px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.strategy-details {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.details-header {
  padding: 24px;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex: 0 0 auto;
}

.details-header h2 {
  margin: 0;
  font-size: 20px;
}

.action-buttons .el-button {
  margin-left: 8px;
}

.strategy-tabs {
  flex: 1;
  padding: 0 24px;
  overflow-y: auto;
  min-height: 0;
}

.strategy-info {
  padding: 16px 0;
}

.history-panel {
  padding: 16px 0;
}

.history-empty {
  margin-top: 16px;
}

.positive {
  color: #67c23a;
}

.negative {
  color: #f56c6c;
}

.strategy-description-full {
  margin: 24px 0;
}

.strategy-description-full h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
}

.strategy-tags {
  margin: 24px 0;
}

.strategy-tags h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
}

.tag-item {
  margin: 0 8px 8px 0;
}

.parameter-config {
  padding: 16px 0;
}

.parameter-config h4 {
  margin: 0 0 16px 0;
  font-size: 14px;
}

.param-help {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.backtest-results {
  padding: 16px 0;
}

.no-backtest {
  padding: 40px 0;
  text-align: center;
}

.ai-insights {
  padding: 16px 0;
}

.ai-explanation {
  margin-bottom: 24px;
}

.ai-explanation h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
}

.explanation-content {
  background: #f8f9fa;
  padding: 16px;
  border-radius: 4px;
  line-height: 1.6;
}

.generation-info h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
}

.empty-workspace {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
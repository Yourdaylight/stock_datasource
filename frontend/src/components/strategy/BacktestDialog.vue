<template>
  <t-dialog
    v-model:visible="visible"
    header="回测配置"
    width="600px"
    :close-on-overlay-click="false"
    @close="handleClose"
  >
    <t-form 
      ref="formRef"
      :data="config" 
      :rules="rules"
      label-width="120px"
    >
      <!-- 基本配置 -->
      <div class="config-section">
        <h4>基本配置</h4>
        
        <t-form-item label="股票代码" name="symbols" required>
          <t-select
            v-model="config.symbols"
            multiple
            filterable
            creatable
            placeholder="输入股票代码，如 000001.SZ"
            style="width: 100%"
          >
            <t-option
              v-for="symbol in popularSymbols"
              :key="symbol.code"
              :label="`${symbol.code} - ${symbol.name}`"
              :value="symbol.code"
            />
          </t-select>
          <div class="form-help">
            支持多个股票，格式如：000001.SZ, 600000.SH
          </div>
        </t-form-item>

        <t-form-item label="回测期间" required>
          <t-date-range-picker
            v-model="dateRange"
            :enable-time-picker="false"
            format="YYYY-MM-DD"
            :placeholder="['开始日期', '结束日期']"
            style="width: 100%"
          />
        </t-form-item>

        <t-form-item label="基准指数" name="benchmark">
          <t-select v-model="config.benchmark" placeholder="选择基准指数">
            <t-option label="沪深300" value="000300.SH" />
            <t-option label="中证500" value="000905.SH" />
            <t-option label="创业板指" value="399006.SZ" />
            <t-option label="上证指数" value="000001.SH" />
            <t-option label="深证成指" value="399001.SZ" />
          </t-select>
        </t-form-item>
      </div>

      <!-- 交易配置 -->
      <div class="config-section">
        <h4>交易配置</h4>
        
        <t-form-item label="初始资金" name="initial_capital">
          <t-input-number
            v-model="config.initial_capital"
            :min="10000"
            :max="100000000"
            :step="10000"
            style="width: 200px"
          />
          <span class="unit">元</span>
        </t-form-item>

        <t-form-item label="手续费率" name="commission_rate">
          <t-input-number
            v-model="config.commission_rate"
            :min="0"
            :max="0.01"
            :step="0.0001"
            :decimal-places="4"
            style="width: 200px"
          />
          <span class="unit">%</span>
        </t-form-item>

        <t-form-item label="滑点率" name="slippage_rate">
          <t-input-number
            v-model="config.slippage_rate"
            :min="0"
            :max="0.01"
            :step="0.0001"
            :decimal-places="4"
            style="width: 200px"
          />
          <span class="unit">%</span>
        </t-form-item>

        <t-form-item label="最小手续费" name="min_commission">
          <t-input-number
            v-model="config.min_commission"
            :min="0"
            :max="100"
            :step="1"
            style="width: 200px"
          />
          <span class="unit">元</span>
        </t-form-item>
      </div>

      <!-- 高级配置 -->
      <div class="config-section">
        <h4>高级配置</h4>
        
        <t-form-item label="智能回测">
          <t-switch v-model="config.enable_intelligent" />
          <div class="form-help">
            启用参数优化和AI洞察分析
          </div>
        </t-form-item>

        <t-form-item 
          v-if="config.enable_intelligent"
          label="参数优化"
        >
          <t-switch v-model="config.enable_optimization" />
          <div class="form-help">
            自动优化策略参数以获得更好的回测结果
          </div>
        </t-form-item>

        <t-form-item 
          v-if="config.enable_optimization"
          label="优化算法"
        >
          <t-select v-model="config.optimization_algorithm">
            <t-option label="网格搜索" value="grid_search" />
            <t-option label="随机搜索" value="random_search" />
            <t-option label="贝叶斯优化" value="bayesian" />
          </t-select>
        </t-form-item>

        <t-form-item 
          v-if="config.enable_intelligent"
          label="鲁棒性测试"
        >
          <t-switch v-model="config.enable_robustness" />
          <div class="form-help">
            测试策略在不同市场环境下的稳定性
          </div>
        </t-form-item>
      </div>

      <!-- 预计执行时间 -->
      <div class="execution-estimate">
        <t-alert
          :message="`预计执行时间: ${estimatedTime}`"
          theme="info"
          :close="false"
        />
      </div>
    </t-form>

    <template #footer>
      <div class="dialog-footer">
        <t-button @click="handleClose">取消</t-button>
        <t-button 
          theme="primary" 
          @click="startBacktest"
          :loading="submitting"
        >
          开始回测
        </t-button>
      </div>
    </template>
  </t-dialog>
</template>

<script>
import { ref, reactive, computed, watch } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'

export default {
  name: 'BacktestDialog',
  props: {
    modelValue: {
      type: Boolean,
      default: false
    },
    strategy: {
      type: Object,
      default: null
    },
    parameters: {
      type: Object,
      default: () => ({})
    }
  },
  emits: ['update:modelValue', 'backtest-started'],
  setup(props, { emit }) {
    // 响应式数据
    const visible = ref(false)
    const submitting = ref(false)
    const formRef = ref(null)
    const dateRange = ref([])

    // 回测配置
    const config = reactive({
      symbols: ['000001.SZ'],
      start_date: '',
      end_date: '',
      benchmark: '000300.SH',
      initial_capital: 1000000,
      commission_rate: 0.0003,
      slippage_rate: 0.001,
      min_commission: 5,
      enable_intelligent: false,
      enable_optimization: false,
      optimization_algorithm: 'grid_search',
      enable_robustness: false
    })

    // 热门股票列表
    const popularSymbols = ref([
      { code: '000001.SZ', name: '平安银行' },
      { code: '000002.SZ', name: '万科A' },
      { code: '000858.SZ', name: '五粮液' },
      { code: '600000.SH', name: '浦发银行' },
      { code: '600036.SH', name: '招商银行' },
      { code: '600519.SH', name: '贵州茅台' },
      { code: '600887.SH', name: '伊利股份' },
      { code: '000858.SZ', name: '五粮液' }
    ])

    // 日期快捷选项
    const dateShortcuts = [
      {
        text: '最近1个月',
        value: () => {
          const end = new Date()
          const start = new Date()
          start.setMonth(start.getMonth() - 1)
          return [start, end]
        }
      },
      {
        text: '最近3个月',
        value: () => {
          const end = new Date()
          const start = new Date()
          start.setMonth(start.getMonth() - 3)
          return [start, end]
        }
      },
      {
        text: '最近6个月',
        value: () => {
          const end = new Date()
          const start = new Date()
          start.setMonth(start.getMonth() - 6)
          return [start, end]
        }
      },
      {
        text: '最近1年',
        value: () => {
          const end = new Date()
          const start = new Date()
          start.setFullYear(start.getFullYear() - 1)
          return [start, end]
        }
      }
    ]

    // 表单验证规则
    const rules = {
      symbols: [
        { required: true, message: '请选择至少一个股票', trigger: 'change' }
      ],
      initial_capital: [
        { required: true, message: '请输入初始资金', trigger: 'blur' },
        { type: 'number', min: 10000, message: '初始资金不能少于1万元', trigger: 'blur' }
      ],
      commission_rate: [
        { required: true, message: '请输入手续费率', trigger: 'blur' },
        { type: 'number', min: 0, max: 0.01, message: '手续费率应在0-1%之间', trigger: 'blur' }
      ]
    }

    // 计算属性
    const estimatedTime = computed(() => {
      let baseTime = 10 // 基础时间（秒）
      
      // 根据股票数量调整
      baseTime += config.symbols.length * 5
      
      // 根据回测期间调整
      if (dateRange.value && dateRange.value.length === 2) {
        const days = Math.ceil((new Date(dateRange.value[1]) - new Date(dateRange.value[0])) / (1000 * 60 * 60 * 24))
        baseTime += Math.floor(days / 30) * 2
      }
      
      // 根据高级功能调整
      if (config.enable_optimization) {
        baseTime *= 5
      }
      if (config.enable_robustness) {
        baseTime *= 2
      }
      
      if (baseTime < 60) {
        return `${baseTime}秒`
      } else if (baseTime < 3600) {
        return `${Math.ceil(baseTime / 60)}分钟`
      } else {
        return `${Math.ceil(baseTime / 3600)}小时`
      }
    })

    // 监听器
    watch(() => props.modelValue, (val) => {
      visible.value = val
      if (val) {
        initializeConfig()
      }
    })

    watch(visible, (val) => {
      emit('update:modelValue', val)
    })

    watch(dateRange, (val) => {
      if (val && val.length === 2) {
        config.start_date = val[0]
        config.end_date = val[1]
      }
    })

    // 方法
    const initializeConfig = () => {
      // 设置默认日期范围（最近3个月）
      const end = new Date()
      const start = new Date()
      start.setMonth(start.getMonth() - 3)
      
      dateRange.value = [
        start.toISOString().split('T')[0],
        end.toISOString().split('T')[0]
      ]
    }

    const startBacktest = async () => {
      try {
        // 验证表单
        const valid = await formRef.value.validate()
        if (!valid) return

        // 验证日期范围
        if (!dateRange.value || dateRange.value.length !== 2) {
          MessagePlugin.error('请选择回测日期范围')
          return
        }

        submitting.value = true

        // 构建回测配置
        const backtestConfig = {
          strategy_id: props.strategy.id,
          symbols: config.symbols,
          start_date: config.start_date,
          end_date: config.end_date,
          benchmark: config.benchmark,
          trading_config: {
            initial_capital: config.initial_capital,
            commission_rate: config.commission_rate,
            slippage_rate: config.slippage_rate,
            min_commission: config.min_commission
          },
          parameters: props.parameters
        }

        // 智能回测配置
        if (config.enable_intelligent) {
          backtestConfig.intelligent_config = {
            enable_optimization: config.enable_optimization,
            enable_robustness: config.enable_robustness,
            optimization_algorithm: config.optimization_algorithm
          }
        }

        emit('backtest-started', backtestConfig)
      } catch (error) {
        MessagePlugin.error('配置验证失败')
      } finally {
        submitting.value = false
      }
    }

    const handleClose = () => {
      visible.value = false
    }

    return {
      // 数据
      visible,
      submitting,
      formRef,
      dateRange,
      config,
      popularSymbols,
      dateShortcuts,
      rules,
      estimatedTime,

      // 方法
      startBacktest,
      handleClose
    }
  }
}
</script>

<style scoped>
.config-section {
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid #f0f0f0;
}

.config-section:last-child {
  border-bottom: none;
}

.config-section h4 {
  margin: 0 0 16px 0;
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}

.form-help {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  line-height: 1.4;
}

.unit {
  margin-left: 8px;
  color: #606266;
  font-size: 14px;
}

.execution-estimate {
  margin-top: 24px;
}

.dialog-footer {
  text-align: right;
}

.dialog-footer .t-button {
  margin-left: 8px;
}

:deep(.t-form-item__label) {
  font-weight: 500;
}

:deep(.t-input-number) {
  width: 200px;
}

:deep(.t-select) {
  width: 100%;
}
</style>
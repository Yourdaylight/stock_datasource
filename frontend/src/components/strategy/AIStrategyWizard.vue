<template>
  <t-dialog
    v-model:visible="visible"
    header="AI策略创建向导"
    width="800px"
    :close-on-overlay-click="false"
    @close="handleClose"
  >
    <div class="wizard-container">
      <!-- 步骤指示器 -->
      <t-steps :current="currentStep" class="wizard-steps">
        <t-step title="策略描述" content="用自然语言描述您的策略"></t-step>
        <t-step title="参数配置" content="调整策略参数"></t-step>
        <t-step title="预览确认" content="预览生成的策略"></t-step>
      </t-steps>

      <!-- 步骤内容 -->
      <div class="step-content">
        <!-- 第一步：策略描述 -->
        <div v-if="currentStep === 0" class="step-description">
          <h3>描述您的交易策略</h3>
          <p class="step-hint">
            请用自然语言描述您想要的交易策略。AI将根据您的描述生成相应的策略代码。
          </p>

          <!-- 策略模板 -->
          <div class="strategy-templates">
            <h4>常用策略模板</h4>
            <div class="template-grid">
              <div 
                v-for="template in strategyTemplates" 
                :key="template.id"
                class="template-card"
                @click="selectTemplate(template)"
              >
                <h5>{{ template.name }}</h5>
                <p>{{ template.description }}</p>
              </div>
            </div>
          </div>

          <!-- 自然语言输入 -->
          <div class="nl-input-section">
            <h4>策略描述</h4>
            <t-textarea
              v-model="strategyDescription"
              :maxlength="1000"
              placeholder="例如：创建一个基于5日和20日移动平均线交叉的策略，当短期均线上穿长期均线时买入，下穿时卖出。同时加入RSI指标作为过滤条件，只在RSI小于70时买入。"
              :autosize="{ minRows: 6, maxRows: 8 }"
            />
          </div>

          <!-- 风险偏好 -->
          <div class="risk-preference">
            <h4>风险偏好</h4>
            <t-radio-group v-model="riskPreference">
              <t-radio value="conservative">保守型 - 注重资本保护</t-radio>
              <t-radio value="moderate">稳健型 - 平衡收益与风险</t-radio>
              <t-radio value="aggressive">激进型 - 追求高收益</t-radio>
            </t-radio-group>
          </div>

          <!-- 市场环境 -->
          <div class="market-environment">
            <h4>适用市场环境</h4>
            <t-checkbox-group v-model="marketEnvironments">
              <t-checkbox value="trending">趋势市场</t-checkbox>
              <t-checkbox value="sideways">震荡市场</t-checkbox>
              <t-checkbox value="volatile">高波动市场</t-checkbox>
              <t-checkbox value="low_volatility">低波动市场</t-checkbox>
            </t-checkbox-group>
          </div>
        </div>

        <!-- 第二步：参数配置 -->
        <div v-if="currentStep === 1" class="step-parameters">
          <h3>策略参数配置</h3>
          <p class="step-hint">
            AI已根据您的描述识别出以下参数，您可以调整这些参数的默认值。
          </p>

          <div v-if="generatedStrategy" class="parameter-form">
            <t-form :data="strategyParameters" label-width="150px">
              <t-form-item 
                v-for="param in generatedStrategy.parameter_schema" 
                :key="param.name"
                :label="param.description || param.name"
                :name="param.name"
              >
                <t-input-number
                  v-if="param.type === 'int' || param.type === 'float'"
                  v-model="strategyParameters[param.name]"
                  :min="param.min_value"
                  :max="param.max_value"
                  :decimal-places="param.type === 'float' ? 2 : 0"
                  :step="param.type === 'float' ? 0.01 : 1"
                />
                <t-switch
                  v-else-if="param.type === 'bool'"
                  v-model="strategyParameters[param.name]"
                />
                <t-input
                  v-else
                  v-model="strategyParameters[param.name]"
                />
                <div class="param-description">
                  {{ param.description }}
                  <span v-if="param.min_value !== undefined">
                    (范围: {{ param.min_value }} - {{ param.max_value }})
                  </span>
                </div>
              </t-form-item>
            </t-form>
          </div>

          <div v-else class="generating-strategy">
            <t-loading />
            <p>AI正在生成策略...</p>
          </div>
        </div>

        <!-- 第三步：预览确认 -->
        <div v-if="currentStep === 2" class="step-preview">
          <h3>策略预览</h3>
          <p class="step-hint">
            请确认生成的策略是否符合您的预期。
          </p>

          <div v-if="generatedStrategy" class="strategy-preview">
            <!-- 策略基本信息 -->
            <div class="preview-section">
              <h4>基本信息</h4>
              <t-descriptions :column="2" bordered>
                <t-descriptions-item label="策略名称">
                  <t-input v-model="strategyName" size="small" />
                </t-descriptions-item>
                <t-descriptions-item label="策略类型">
                  {{ getCategoryName(generatedStrategy.category) }}
                </t-descriptions-item>
                <t-descriptions-item label="风险等级">
                  <t-tag :theme="getRiskLevelColor(generatedStrategy.risk_level)">
                    {{ getRiskLevelName(generatedStrategy.risk_level) }}
                  </t-tag>
                </t-descriptions-item>
                <t-descriptions-item label="AI置信度">
                  <t-progress 
                    :percentage="(generatedStrategy.confidence_score || 0) * 100"
                    :color="getConfidenceColor(generatedStrategy.confidence_score)"
                  />
                  {{ ((generatedStrategy.confidence_score || 0) * 100).toFixed(1) }}%
                </t-descriptions-item>
              </t-descriptions>
            </div>

            <!-- 策略逻辑解释 -->
            <div class="preview-section">
              <h4>策略逻辑</h4>
              <div class="strategy-explanation">
                {{ strategyExplanation }}
              </div>
            </div>

            <!-- 风险警告 -->
            <div v-if="riskWarnings.length" class="preview-section">
              <h4>风险警告</h4>
              <t-alert
                v-for="warning in riskWarnings"
                :key="warning"
                :message="warning"
                theme="warning"
                :close="false"
                class="risk-warning"
              />
            </div>

            <!-- 参数摘要 -->
            <div class="preview-section">
              <h4>参数配置</h4>
              <t-table :data="parameterSummary" size="small">
                <t-table-column prop="name" label="参数名称" width="120" />
                <t-table-column prop="description" label="描述" />
                <t-table-column prop="value" label="当前值" width="100" />
                <t-table-column prop="range" label="取值范围" width="120" />
              </t-table>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 对话框底部按钮 -->
    <template #footer>
      <div class="dialog-footer">
        <t-button @click="handleClose">取消</t-button>
        <t-button 
          v-if="currentStep > 0" 
          @click="previousStep"
        >
          上一步
        </t-button>
        <t-button 
          v-if="currentStep < 2"
          theme="primary" 
          @click="nextStep"
          :loading="generating"
          :disabled="!canProceed"
        >
          {{ currentStep === 0 ? '生成策略' : '下一步' }}
        </t-button>
        <t-button 
          v-if="currentStep === 2"
          theme="success" 
          @click="createStrategy"
          :loading="creating"
        >
          创建策略
        </t-button>
      </div>
    </template>
  </t-dialog>
</template>

<script>
import { ref, reactive, computed, watch } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { strategyApi } from '@/api/strategy'

export default {
  name: 'AIStrategyWizard',
  props: {
    modelValue: {
      type: Boolean,
      default: false
    }
  },
  emits: ['update:modelValue', 'strategy-created'],
  setup(props, { emit }) {
    // 响应式数据
    const visible = ref(false)
    const currentStep = ref(0)
    const generating = ref(false)
    const creating = ref(false)
    
    const strategyDescription = ref('')
    const riskPreference = ref('moderate')
    const marketEnvironments = ref(['trending'])
    const strategyName = ref('')
    const strategyParameters = reactive({})
    const generatedStrategy = ref(null)
    const strategyExplanation = ref('')
    const riskWarnings = ref([])

    // 策略模板
    const strategyTemplates = ref([
      {
        id: 'ma_cross',
        name: '双均线策略',
        description: '基于快慢均线交叉的经典趋势策略',
        template: '创建一个基于{fast}日和{slow}日移动平均线交叉的策略，当短期均线上穿长期均线时买入，下穿时卖出。'
      },
      {
        id: 'rsi_reversal',
        name: 'RSI反转策略',
        description: '基于RSI超买超卖的均值回归策略',
        template: '创建一个基于RSI指标的策略，当RSI低于{oversold}时买入，高于{overbought}时卖出。'
      },
      {
        id: 'macd_momentum',
        name: 'MACD动量策略',
        description: '基于MACD指标的动量跟踪策略',
        template: '创建一个基于MACD指标的策略，当DIF上穿DEA时买入，下穿时卖出。'
      },
      {
        id: 'bollinger_bands',
        name: '布林带策略',
        description: '基于布林带的均值回归策略',
        template: '创建一个基于布林带的策略，当价格触及下轨时买入，触及上轨时卖出。'
      }
    ])

    // 计算属性
    const canProceed = computed(() => {
      if (currentStep.value === 0) {
        return strategyDescription.value.trim().length > 10
      }
      return true
    })

    const parameterSummary = computed(() => {
      if (!generatedStrategy.value?.parameter_schema) return []
      
      return generatedStrategy.value.parameter_schema.map(param => ({
        name: param.name,
        description: param.description || param.name,
        value: strategyParameters[param.name],
        range: param.min_value !== undefined 
          ? `${param.min_value} - ${param.max_value}`
          : '-'
      }))
    })

    // 监听器
    watch(() => props.modelValue, (val) => {
      visible.value = val
      if (val) {
        resetWizard()
      }
    })

    watch(visible, (val) => {
      emit('update:modelValue', val)
    })

    // 方法
    const resetWizard = () => {
      currentStep.value = 0
      strategyDescription.value = ''
      riskPreference.value = 'moderate'
      marketEnvironments.value = ['trending']
      strategyName.value = ''
      generatedStrategy.value = null
      strategyExplanation.value = ''
      riskWarnings.value = []
      
      Object.keys(strategyParameters).forEach(key => {
        delete strategyParameters[key]
      })
    }

    const selectTemplate = (template) => {
      strategyDescription.value = template.template
        .replace('{fast}', '5')
        .replace('{slow}', '20')
        .replace('{oversold}', '30')
        .replace('{overbought}', '70')
    }

    const nextStep = async () => {
      if (currentStep.value === 0) {
        await generateStrategy()
      } else {
        currentStep.value++
      }
    }

    const previousStep = () => {
      currentStep.value--
    }

    const generateStrategy = async () => {
      generating.value = true
      
      try {
        const response = await strategyApi.generateAIStrategy({
          description: strategyDescription.value,
          risk_preference: riskPreference.value,
          market_environments: marketEnvironments.value
        })
        
        generatedStrategy.value = response.data.strategy
        strategyExplanation.value = response.data.explanation
        riskWarnings.value = response.data.risk_warnings || []
        
        // 初始化参数
        if (generatedStrategy.value.parameter_schema) {
          generatedStrategy.value.parameter_schema.forEach(param => {
            strategyParameters[param.name] = param.default
          })
        }
        
        // 生成默认策略名称
        strategyName.value = `AI策略_${new Date().toLocaleDateString()}`
        
        currentStep.value++
        MessagePlugin.success('策略生成成功')
      } catch (error) {
        MessagePlugin.error('策略生成失败：' + (error.response?.data?.message || error.message))
      } finally {
        generating.value = false
      }
    }

    const createStrategy = async () => {
      creating.value = true
      
      try {
        const response = await strategyApi.createStrategy({
          name: strategyName.value,
          strategy_data: generatedStrategy.value,
          parameters: strategyParameters,
          description: strategyDescription.value
        })
        
        emit('strategy-created', response.data)
        handleClose()
        MessagePlugin.success('策略创建成功')
      } catch (error) {
        MessagePlugin.error('策略创建失败：' + (error.response?.data?.message || error.message))
      } finally {
        creating.value = false
      }
    }

    const handleClose = () => {
      visible.value = false
    }

    // 辅助方法
    const getCategoryName = (category) => {
      const categoryMap = {
        trend: '趋势策略',
        mean_reversion: '均值回归',
        momentum: '动量策略',
        ai_generated: 'AI策略'
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

    return {
      // 数据
      visible,
      currentStep,
      generating,
      creating,
      strategyDescription,
      riskPreference,
      marketEnvironments,
      strategyName,
      strategyParameters,
      generatedStrategy,
      strategyExplanation,
      riskWarnings,
      strategyTemplates,
      canProceed,
      parameterSummary,

      // 方法
      selectTemplate,
      nextStep,
      previousStep,
      createStrategy,
      handleClose,
      getCategoryName,
      getRiskLevelName,
      getRiskLevelColor,
      getConfidenceColor
    }
  }
}
</script>

<style scoped>
.wizard-container {
  min-height: 500px;
}

.wizard-steps {
  margin-bottom: 32px;
}

.step-content {
  min-height: 400px;
}

.step-hint {
  color: #606266;
  margin-bottom: 24px;
  line-height: 1.6;
}

.strategy-templates {
  margin-bottom: 24px;
}

.strategy-templates h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 500;
}

.template-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.template-card {
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.3s;
}

.template-card:hover {
  border-color: #409eff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.12);
}

.template-card h5 {
  margin: 0 0 8px 0;
  font-size: 14px;
  font-weight: 500;
}

.template-card p {
  margin: 0;
  font-size: 12px;
  color: #606266;
  line-height: 1.4;
}

.nl-input-section {
  margin-bottom: 24px;
}

.nl-input-section h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 500;
}

.risk-preference {
  margin-bottom: 24px;
}

.risk-preference h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 500;
}

.market-environment h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 500;
}

.parameter-form {
  background: #f8f9fa;
  padding: 20px;
  border-radius: 4px;
}

.param-description {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.generating-strategy {
  text-align: center;
  padding: 60px 0;
  color: #606266;
}

.strategy-preview {
  max-height: 400px;
  overflow-y: auto;
}

.preview-section {
  margin-bottom: 24px;
}

.preview-section h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 500;
}

.strategy-explanation {
  background: #f8f9fa;
  padding: 16px;
  border-radius: 4px;
  line-height: 1.6;
  font-size: 14px;
}

.risk-warning {
  margin-bottom: 8px;
}

.dialog-footer {
  text-align: right;
}

.dialog-footer .t-button {
  margin-left: 8px;
}
</style>
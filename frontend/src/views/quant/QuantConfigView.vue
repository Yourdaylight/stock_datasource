<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { useQuantStore } from '@/stores/quant'

const store = useQuantStore()

// Factor weights
const factorWeights = ref({
  quality: 30,
  growth: 30,
  value: 20,
  momentum: 20,
})

// Signal params
const signalParams = ref({
  ma_short: 25,
  ma_long: 120,
  stop_loss_pct: 15,
  trailing_stop_pct: 10,
  rps_exit_threshold: 75,
})

const handleSaveWeights = async () => {
  await store.updateConfig('factor_weights', {
    quality: factorWeights.value.quality / 100,
    growth: factorWeights.value.growth / 100,
    value: factorWeights.value.value / 100,
    momentum: factorWeights.value.momentum / 100,
  })
  MessagePlugin.success('因子权重已保存')
}

const handleSaveSignalParams = async () => {
  await store.updateConfig('signal_params', {
    ma_short: signalParams.value.ma_short,
    ma_long: signalParams.value.ma_long,
    stop_loss_pct: signalParams.value.stop_loss_pct / 100,
    trailing_stop_pct: signalParams.value.trailing_stop_pct / 100,
    rps_exit_threshold: signalParams.value.rps_exit_threshold,
  })
  MessagePlugin.success('信号参数已保存')
}

onMounted(async () => {
  await store.fetchConfig()
  // Load existing config
  for (const cfg of store.configs) {
    if (cfg.config_type === 'factor_weights' && cfg.config_data) {
      factorWeights.value = {
        quality: (cfg.config_data.quality || 0.3) * 100,
        growth: (cfg.config_data.growth || 0.3) * 100,
        value: (cfg.config_data.value || 0.2) * 100,
        momentum: (cfg.config_data.momentum || 0.2) * 100,
      }
    }
    if (cfg.config_type === 'signal_params' && cfg.config_data) {
      signalParams.value = {
        ma_short: cfg.config_data.ma_short || 25,
        ma_long: cfg.config_data.ma_long || 120,
        stop_loss_pct: (cfg.config_data.stop_loss_pct || 0.15) * 100,
        trailing_stop_pct: (cfg.config_data.trailing_stop_pct || 0.10) * 100,
        rps_exit_threshold: cfg.config_data.rps_exit_threshold || 75,
      }
    }
  }
})
</script>

<template>
  <div class="config-view">
    <t-row :gutter="16">
      <!-- Factor Weights -->
      <t-col :span="6">
        <t-card title="因子权重配置" :bordered="false">
          <t-form label-width="100px">
            <t-form-item label="质量因子">
              <t-slider v-model="factorWeights.quality" :min="0" :max="100" :step="5" />
              <span style="margin-left: 8px; min-width: 40px;">{{ factorWeights.quality }}%</span>
            </t-form-item>
            <t-form-item label="成长因子">
              <t-slider v-model="factorWeights.growth" :min="0" :max="100" :step="5" />
              <span style="margin-left: 8px; min-width: 40px;">{{ factorWeights.growth }}%</span>
            </t-form-item>
            <t-form-item label="估值因子">
              <t-slider v-model="factorWeights.value" :min="0" :max="100" :step="5" />
              <span style="margin-left: 8px; min-width: 40px;">{{ factorWeights.value }}%</span>
            </t-form-item>
            <t-form-item label="动量因子">
              <t-slider v-model="factorWeights.momentum" :min="0" :max="100" :step="5" />
              <span style="margin-left: 8px; min-width: 40px;">{{ factorWeights.momentum }}%</span>
            </t-form-item>
            <t-form-item>
              <t-tag :theme="factorWeights.quality + factorWeights.growth + factorWeights.value + factorWeights.momentum === 100 ? 'success' : 'danger'" variant="light">
                合计: {{ factorWeights.quality + factorWeights.growth + factorWeights.value + factorWeights.momentum }}%
              </t-tag>
            </t-form-item>
            <t-form-item>
              <t-button theme="primary" @click="handleSaveWeights">保存权重</t-button>
            </t-form-item>
          </t-form>
        </t-card>
      </t-col>

      <!-- Signal Params -->
      <t-col :span="6">
        <t-card title="信号参数配置" :bordered="false">
          <t-form label-width="120px">
            <t-form-item label="短期均线">
              <t-input-number v-model="signalParams.ma_short" :min="5" :max="60" theme="normal" />
              <span style="margin-left: 8px;">日</span>
            </t-form-item>
            <t-form-item label="长期均线">
              <t-input-number v-model="signalParams.ma_long" :min="60" :max="250" theme="normal" />
              <span style="margin-left: 8px;">日</span>
            </t-form-item>
            <t-form-item label="止损比例">
              <t-slider v-model="signalParams.stop_loss_pct" :min="5" :max="30" />
              <span style="margin-left: 8px;">{{ signalParams.stop_loss_pct }}%</span>
            </t-form-item>
            <t-form-item label="移动止盈">
              <t-slider v-model="signalParams.trailing_stop_pct" :min="5" :max="20" />
              <span style="margin-left: 8px;">{{ signalParams.trailing_stop_pct }}%</span>
            </t-form-item>
            <t-form-item label="RPS退出阈值">
              <t-slider v-model="signalParams.rps_exit_threshold" :min="50" :max="90" />
              <span style="margin-left: 8px;">{{ signalParams.rps_exit_threshold }}</span>
            </t-form-item>
            <t-form-item>
              <t-button theme="primary" @click="handleSaveSignalParams">保存参数</t-button>
            </t-form-item>
          </t-form>
        </t-card>
      </t-col>
    </t-row>
  </div>
</template>

<style scoped>
.config-view {
  padding: 16px;
}
</style>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { useQuantStore } from '@/stores/quant'

const store = useQuantStore()
const analyzeCode = ref('')

const handleAnalyze = async () => {
  if (!analyzeCode.value) {
    MessagePlugin.warning('请输入股票代码')
    return
  }
  const result = await store.analyzeStock(analyzeCode.value)
  if (result) {
    MessagePlugin.success(`分析完成: ${result.stock_name || result.ts_code}`)
  }
}

onMounted(() => {
  store.fetchAnalysisDashboard()
})
</script>

<template>
  <div class="analysis-view">
    <t-card title="深度分析" :bordered="false">
      <template #actions>
        <t-space>
          <t-input v-model="analyzeCode" placeholder="输入股票代码" style="width: 200px" />
          <t-button theme="primary" :loading="store.analysisLoading" @click="handleAnalyze">分析</t-button>
        </t-space>
      </template>

      <!-- Latest Analysis Result -->
      <div v-if="store.analysisResult" class="analysis-result">
        <t-row :gutter="16">
          <!-- Tech Snapshot -->
          <t-col :span="6">
            <t-card title="技术指标" :bordered="false">
              <div v-if="store.analysisResult.tech_snapshot" class="tech-grid">
                <div class="tech-item">
                  <span class="tech-label">收盘价</span>
                  <span class="tech-value">{{ store.analysisResult.tech_snapshot.close }}</span>
                </div>
                <div class="tech-item">
                  <span class="tech-label">MA25</span>
                  <span class="tech-value">{{ store.analysisResult.tech_snapshot.ma25 || '-' }}</span>
                </div>
                <div class="tech-item">
                  <span class="tech-label">MA120</span>
                  <span class="tech-value">{{ store.analysisResult.tech_snapshot.ma120 || '-' }}</span>
                </div>
                <div class="tech-item">
                  <span class="tech-label">MA250</span>
                  <span class="tech-value">{{ store.analysisResult.tech_snapshot.ma250 || '-' }}</span>
                </div>
                <div class="tech-item">
                  <span class="tech-label">MACD</span>
                  <span class="tech-value">{{ store.analysisResult.tech_snapshot.macd || '-' }}</span>
                </div>
                <div class="tech-item">
                  <span class="tech-label">RSI(14)</span>
                  <span class="tech-value">{{ store.analysisResult.tech_snapshot.rsi_14 || '-' }}</span>
                </div>
                <div class="tech-item">
                  <span class="tech-label">量比</span>
                  <span class="tech-value">{{ store.analysisResult.tech_snapshot.volume_ratio || '-' }}</span>
                </div>
                <div class="tech-item">
                  <span class="tech-label">均线位置</span>
                  <t-tag
                    :theme="store.analysisResult.tech_snapshot.ma_position === 'above_all' ? 'success' : store.analysisResult.tech_snapshot.ma_position === 'below_all' ? 'danger' : 'warning'"
                    variant="light" size="small"
                  >
                    {{ store.analysisResult.tech_snapshot.ma_position === 'above_all' ? '多头排列' : store.analysisResult.tech_snapshot.ma_position === 'below_all' ? '空头排列' : '交叉' }}
                  </t-tag>
                </div>
              </div>
              <t-empty v-else description="无技术数据" />
            </t-card>
          </t-col>

          <!-- AI Analysis Card -->
          <t-col :span="6">
            <t-card title="AI 分析" :bordered="false">
              <div v-if="store.analysisResult.ai_analysis">
                <div class="ai-scores">
                  <div class="score-item">
                    <span>可信度</span>
                    <t-progress :percentage="store.analysisResult.ai_analysis.credibility_score" />
                  </div>
                  <div class="score-item">
                    <span>乐观度</span>
                    <t-progress :percentage="store.analysisResult.ai_analysis.optimism_score" />
                  </div>
                </div>

                <div v-if="store.analysisResult.ai_analysis.ai_summary" class="ai-summary">
                  {{ store.analysisResult.ai_analysis.ai_summary }}
                </div>

                <div v-if="store.analysisResult.ai_analysis.key_findings.length" style="margin-top: 12px;">
                  <div style="font-weight: 600; margin-bottom: 4px;">关键发现:</div>
                  <div v-for="(f, i) in store.analysisResult.ai_analysis.key_findings" :key="i" class="finding-item">
                    {{ f }}
                  </div>
                </div>

                <div v-if="store.analysisResult.ai_analysis.risk_factors.length" style="margin-top: 12px;">
                  <div style="font-weight: 600; margin-bottom: 4px;">风险因素:</div>
                  <t-tag v-for="(r, i) in store.analysisResult.ai_analysis.risk_factors" :key="i"
                    theme="danger" variant="outline" size="small" style="margin: 2px;">
                    {{ r }}
                  </t-tag>
                </div>

                <div v-if="store.analysisResult.ai_analysis.verification_points.length" style="margin-top: 12px;">
                  <div style="font-weight: 600; margin-bottom: 4px;">验证点:</div>
                  <div v-for="(v, i) in store.analysisResult.ai_analysis.verification_points" :key="i" class="finding-item">
                    {{ v }}
                  </div>
                </div>
              </div>
              <t-empty v-else description="暂无AI分析" />
            </t-card>
          </t-col>
        </t-row>
      </div>

      <!-- Dashboard -->
      <t-card v-if="store.analysisDashboard.length" title="目标池分析概览" :bordered="false" style="margin-top: 16px">
        <t-table
          :data="store.analysisDashboard"
          :columns="[
            { colKey: 'ts_code', title: '代码', width: 120 },
            { colKey: 'stock_name', title: '名称', width: 120 },
            { colKey: 'tech_score', title: '技术评分', width: 100 },
            { colKey: 'mgmt_discussion_score', title: '可信度', width: 100 },
            { colKey: 'prospect_score', title: '乐观度', width: 100 },
          ]"
          row-key="ts_code"
          size="small"
          :hover="true"
        />
      </t-card>
    </t-card>
  </div>
</template>

<style scoped>
.analysis-view {
  padding: 16px;
}
.analysis-result {
  margin-top: 16px;
}
.tech-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.tech-item {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  border-bottom: 1px solid var(--td-border-level-1-color);
}
.tech-label {
  color: var(--td-text-color-secondary);
}
.tech-value {
  font-weight: 600;
}
.ai-scores {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.score-item {
  display: flex;
  align-items: center;
  gap: 12px;
}
.score-item span {
  min-width: 50px;
  color: var(--td-text-color-secondary);
}
.ai-summary {
  margin-top: 12px;
  padding: 12px;
  background: var(--td-bg-color-secondarycontainer);
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.6;
}
.finding-item {
  padding: 4px 0;
  font-size: 13px;
  color: var(--td-text-color-primary);
}
</style>

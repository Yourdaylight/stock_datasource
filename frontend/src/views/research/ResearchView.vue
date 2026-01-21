<script setup lang="ts">
import { ref } from 'vue'
import InstitutionalSurveyPanel from './components/InstitutionalSurveyPanel.vue'
import ResearchReportPanel from './components/ResearchReportPanel.vue'
import FinancialReportPanel from './components/FinancialReportPanel.vue'

const activeTab = ref('survey')
</script>

<template>
  <div class="research-view">
    <t-card :bordered="false">
      <t-tabs v-model="activeTab" size="large">
        <t-tab-panel value="survey" label="机构调研">
          <InstitutionalSurveyPanel />
        </t-tab-panel>
        
        <t-tab-panel value="report" label="研报数据">
          <ResearchReportPanel />
        </t-tab-panel>
        
        <t-tab-panel value="financial" label="财报研读">
          <FinancialReportPanel />
        </t-tab-panel>
      </t-tabs>
    </t-card>
  </div>
</template>

<style scoped>
.research-view {
  height: 100%;
  padding: 16px;
  background: var(--td-bg-color-page);
}

:deep(.t-card__body) {
  padding: 16px;
}

:deep(.t-tabs__content) {
  padding-top: 16px;
}
</style>

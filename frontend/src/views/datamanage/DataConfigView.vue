<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useDataManageStore } from '@/stores/datamanage'
import SchedulePanel from './components/SchedulePanel.vue'
import ProxyConfigPanel from './components/ProxyConfigPanel.vue'

const authStore = useAuthStore()
const dataStore = useDataManageStore()

// Check admin permission
const isAdmin = computed(() => authStore.isAdmin)

const activeTab = ref('schedule')

onMounted(() => {
  // Ensure plugins are loaded for schedule panel
  if (dataStore.plugins.length === 0) {
    dataStore.fetchPlugins()
  }
})
</script>

<template>
  <div class="data-config-view">
    <!-- Permission Check -->
    <template v-if="!isAdmin">
      <t-card class="no-permission-card">
        <div class="permission-denied">
          <t-icon name="error-circle" size="64px" style="color: var(--td-warning-color); margin-bottom: 16px" />
          <h3 style="margin: 0 0 8px 0; font-size: 20px">无访问权限</h3>
          <p style="margin: 0 0 24px 0; color: var(--td-text-color-secondary)">
            数据配置管理仅限管理员使用。如需访问，请联系系统管理员。
          </p>
          <t-button theme="primary" @click="$router.push('/')">返回首页</t-button>
        </div>
      </t-card>
    </template>

    <template v-else>
      <t-card title="数据配置" subtitle="配置数据同步调度和代理设置">
        <t-tabs v-model="activeTab">
          <t-tab-panel value="schedule" label="调度配置">
            <SchedulePanel />
          </t-tab-panel>
          
          <t-tab-panel value="proxy" label="代理配置">
            <ProxyConfigPanel />
          </t-tab-panel>
        </t-tabs>
      </t-card>
    </template>
  </div>
</template>

<style scoped>
.data-config-view {
  height: 100%;
}

.no-permission-card {
  margin-top: 100px;
  max-width: 500px;
  margin-left: auto;
  margin-right: auto;
}

.permission-denied {
  text-align: center;
  padding: 40px 20px;
}
</style>

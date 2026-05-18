<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useMemoryStore } from '@/stores/memory'
import { MessagePlugin } from 'tdesign-vue-next'
import ProfileHeader from './components/ProfileHeader.vue'
import DailyMemory from './components/DailyMemory.vue'
import LongTermMemory from './components/LongTermMemory.vue'
import ScenarioMemory from './components/ScenarioMemory.vue'
import PreferencePanel from './components/PreferencePanel.vue'
import CreateFactDialog from './components/CreateFactDialog.vue'

const memoryStore = useMemoryStore()
const createFactRef = ref<InstanceType<typeof CreateFactDialog> | null>(null)
const refreshing = ref(false)

async function handleRefresh() {
  refreshing.value = true
  await memoryStore.fetchAll()
  refreshing.value = false
  MessagePlugin.success('记忆数据已刷新')
}

async function handleDeleteFact(factId: string) {
  await memoryStore.deleteFact(factId)
  MessagePlugin.success('记忆已删除')
}

function handleCreateFact() {
  createFactRef.value?.open()
}

onMounted(() => {
  memoryStore.fetchAll()
})
</script>

<template>
  <div class="memory-page">
    <!-- Page header with profile summary -->
    <ProfileHeader />

    <!-- Action bar -->
    <div class="action-bar">
      <div class="action-bar__left">
        <h3 class="page-section-title">记忆架构</h3>
        <p class="page-section-desc">
          参考 mem0 / MemGPT / deer-flow 架构，记忆分为每日、长期、场景三层
        </p>
      </div>
      <div class="action-bar__right">
        <t-button variant="outline" @click="handleRefresh" :loading="refreshing">
          <template #icon><t-icon name="refresh" /></template>
          刷新
        </t-button>
        <t-button theme="primary" @click="handleCreateFact">
          <template #icon><t-icon name="add" /></template>
          手动添加记忆
        </t-button>
      </div>
    </div>

    <!-- Main dashboard grid -->
    <div class="memory-grid">
      <!-- Row 1: Daily Memory (left) + Long-term Memory (right) -->
      <div class="memory-grid__row memory-grid__row--top">
        <div class="memory-grid__col memory-grid__col--daily">
          <DailyMemory @delete-fact="handleDeleteFact" />
        </div>
        <div class="memory-grid__col memory-grid__col--longterm">
          <LongTermMemory @delete-fact="handleDeleteFact" />
        </div>
      </div>

      <!-- Row 2: Scenario Memory (left) + Preferences (right) -->
      <div class="memory-grid__row memory-grid__row--bottom">
        <div class="memory-grid__col memory-grid__col--scenario">
          <ScenarioMemory @delete-fact="handleDeleteFact" />
        </div>
        <div class="memory-grid__col memory-grid__col--preference">
          <PreferencePanel />
        </div>
      </div>
    </div>

    <!-- Create fact dialog -->
    <CreateFactDialog ref="createFactRef" />
  </div>
</template>

<style scoped>
.memory-page {
  padding: 20px;
  max-width: 1600px;
  margin: 0 auto;
  min-height: 100%;
}

/* Action bar */
.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  gap: 16px;
  flex-wrap: wrap;
}

.action-bar__left {
  flex: 1;
}

.page-section-title {
  margin: 0 0 2px 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--td-text-color-primary);
}

.page-section-desc {
  margin: 0;
  font-size: 12px;
  color: var(--td-text-color-placeholder);
}

.action-bar__right {
  display: flex;
  gap: 8px;
}

/* Grid layout */
.memory-grid {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.memory-grid__row {
  display: grid;
  gap: 20px;
}

.memory-grid__row--top {
  grid-template-columns: 1fr 1.4fr;
}

.memory-grid__row--bottom {
  grid-template-columns: 1.4fr 1fr;
}

.memory-grid__col {
  min-width: 0;
}

/* Responsive */
@media (max-width: 1200px) {
  .memory-grid__row--top,
  .memory-grid__row--bottom {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .memory-page {
    padding: 12px;
  }

  .action-bar {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>

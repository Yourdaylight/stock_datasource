<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { useDataManageStore } from '@/stores/datamanage'
import { MessagePlugin } from 'tdesign-vue-next'

const dataStore = useDataManageStore()

const runningTasks = computed(() => 
  dataStore.syncTasks.filter(t => t.status === 'running' || t.status === 'pending')
)

const recentTasks = computed(() => {
  const completed = dataStore.syncTasks.filter(t => 
    t.status === 'completed' || t.status === 'failed' || t.status === 'cancelled'
  )
  return completed.slice(0, 5)
})

const handleCancel = async (taskId: string) => {
  await dataStore.cancelTask(taskId)
}

const handleDelete = async (taskId: string) => {
  try {
    await dataStore.deleteTask(taskId)
    MessagePlugin.success('任务已删除')
  } catch (e) {
    MessagePlugin.error('删除失败')
  }
}

const getStatusTheme = (status: string) => {
  const themes: Record<string, string> = {
    pending: 'warning',
    running: 'primary',
    completed: 'success',
    failed: 'danger',
    cancelled: 'default'
  }
  return themes[status] || 'default'
}

const getStatusText = (status: string) => {
  const texts: Record<string, string> = {
    pending: '等待中',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消'
  }
  return texts[status] || status
}

const formatTime = (timeStr?: string) => {
  if (!timeStr) return '-'
  const date = new Date(timeStr)
  return date.toLocaleTimeString('zh-CN')
}

onMounted(() => {
  dataStore.startTaskPolling()
})

onUnmounted(() => {
  dataStore.stopTaskPolling()
})
</script>

<template>
  <div class="sync-task-panel">
    <div v-if="runningTasks.length > 0" class="running-section">
      <h5>运行中的任务</h5>
      <div v-for="task in runningTasks" :key="task.task_id" class="task-item running">
        <div class="task-info">
          <span class="plugin-name">{{ task.plugin_name }}</span>
          <t-tag :theme="getStatusTheme(task.status)" size="small">
            {{ getStatusText(task.status) }}
          </t-tag>
        </div>
        <t-progress 
          :percentage="task.progress" 
          :status="task.status === 'running' ? 'active' : 'default'"
          size="small"
        />
        <div class="task-meta">
          <span>已处理: {{ task.records_processed.toLocaleString() }} 条</span>
          <t-link 
            v-if="task.status === 'pending'" 
            theme="danger" 
            size="small"
            @click="handleCancel(task.task_id)"
          >
            取消
          </t-link>
        </div>
      </div>
    </div>

    <div v-if="recentTasks.length > 0" class="history-section">
      <h5>最近任务</h5>
      <t-table
        :data="recentTasks"
        :columns="[
          { colKey: 'plugin_name', title: '插件', width: 150 },
          { colKey: 'task_type', title: '类型', width: 80 },
          { colKey: 'status', title: '状态', width: 80 },
          { colKey: 'records_processed', title: '记录数', width: 100 },
          { colKey: 'completed_at', title: '完成时间', width: 100 },
          { colKey: 'operation', title: '操作', width: 80 }
        ]"
        row-key="task_id"
        size="small"
        bordered
      >
        <template #task_type="{ row }">
          {{ row.task_type === 'incremental' ? '增量' : row.task_type === 'full' ? '全量' : '补录' }}
        </template>
        <template #status="{ row }">
          <t-tag :theme="getStatusTheme(row.status)" size="small">
            {{ getStatusText(row.status) }}
          </t-tag>
        </template>
        <template #records_processed="{ row }">
          {{ row.records_processed.toLocaleString() }}
        </template>
        <template #completed_at="{ row }">
          {{ formatTime(row.completed_at) }}
        </template>
        <template #operation="{ row }">
          <t-popconfirm content="确定删除此任务？" @confirm="handleDelete(row.task_id)">
            <t-link theme="danger" size="small">删除</t-link>
          </t-popconfirm>
        </template>
      </t-table>
    </div>

    <t-empty 
      v-if="runningTasks.length === 0 && recentTasks.length === 0" 
      description="暂无同步任务"
      style="padding: 20px 0"
    />
  </div>
</template>

<style scoped>
.sync-task-panel {
  background: var(--td-bg-color-container);
  border-radius: 6px;
  padding: 16px;
}

.running-section,
.history-section {
  margin-bottom: 16px;
}

.running-section h5,
.history-section h5 {
  margin: 0 0 12px 0;
  font-size: 14px;
}

.task-item {
  padding: 12px;
  background: var(--td-bg-color-secondarycontainer);
  border-radius: 4px;
  margin-bottom: 8px;
}

.task-item.running {
  border-left: 3px solid var(--td-brand-color);
}

.task-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.plugin-name {
  font-weight: 500;
}

.task-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
  font-size: 12px;
  color: var(--td-text-color-secondary);
}
</style>

<template>
  <div class="arena-management">
    <!-- Header -->
    <div class="page-header">
      <h1>多Agent竞技场</h1>
      <p class="description">AI Agent 自动生成、讨论和优化交易策略的竞技系统</p>
    </div>

    <!-- Actions -->
    <div class="actions-bar">
      <t-button theme="primary" @click="showCreateDialog = true">
        <template #icon><t-icon name="add" /></template>
        创建竞技场
      </t-button>
      <t-button @click="refreshArenas">
        <template #icon><t-icon name="refresh" /></template>
        刷新
      </t-button>
    </div>

    <!-- Arena List -->
    <div class="arena-list">
      <t-card v-if="loading" class="loading-card">
        <t-skeleton :loading="true" :row-col="[{ width: '100%' }, { width: '80%' }, { width: '60%' }]" />
      </t-card>
      
      <t-empty v-else-if="arenas.length === 0" description="暂无竞技场，点击上方按钮创建">
        <t-button theme="primary" @click="showCreateDialog = true">创建第一个竞技场</t-button>
      </t-empty>

      <div v-else class="arena-grid">
        <t-card 
          v-for="arena in arenas" 
          :key="arena.id" 
          class="arena-card"
          :class="{ 'is-running': isArenaRunning(arena.state) }"
          hover-shadow
          @click="goToArena(arena.id)"
        >
          <template #header>
            <div class="card-header">
              <span class="arena-name">{{ arena.name }}</span>
              <t-tag :theme="getStateTagTheme(arena.state)" size="small">
                {{ getStateLabel(arena.state) }}
              </t-tag>
            </div>
          </template>
          
          <div class="arena-stats">
            <div class="stat-item">
              <span class="stat-value">{{ arena.active_strategies }}</span>
              <span class="stat-label">活跃策略</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ arena.discussion_rounds }}</span>
              <span class="stat-label">讨论轮次</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ formatDuration(arena.duration_seconds) }}</span>
              <span class="stat-label">运行时长</span>
            </div>
          </div>

          <div class="arena-actions" @click.stop>
            <t-button 
              v-if="arena.state === 'created'" 
              theme="primary" 
              size="small"
              @click="handleStart(arena.id)"
            >
              启动
            </t-button>
            <t-button 
              v-else-if="isArenaRunning(arena.state)" 
              theme="warning" 
              size="small"
              @click="handlePause(arena.id)"
            >
              暂停
            </t-button>
            <t-button 
              v-else-if="arena.state === 'paused'" 
              theme="success" 
              size="small"
              @click="handleResume(arena.id)"
            >
              恢复
            </t-button>
            <t-button 
              theme="danger" 
              size="small"
              @click="handleDelete(arena.id)"
            >
              <template #icon><t-icon name="delete" /></template>
            </t-button>
          </div>
        </t-card>
      </div>
    </div>

    <!-- Create Dialog -->
    <t-dialog 
      v-model:visible="showCreateDialog" 
      header="创建竞技场" 
      width="500px"
      :confirm-btn="{ content: '创建', loading: creating }"
      @confirm="handleCreate"
      @close="showCreateDialog = false"
    >
      <t-form 
        ref="createFormRef"
        :data="createForm" 
        :rules="createRules"
        label-width="100px"
      >
        <t-form-item label="名称" name="name">
          <t-input v-model="createForm.name" placeholder="输入竞技场名称" />
        </t-form-item>
        
        <t-form-item label="描述">
          <t-textarea 
            v-model="createForm.description" 
            placeholder="可选描述"
          />
        </t-form-item>
        
        <t-form-item label="Agent数量" name="agent_count">
          <t-slider 
            v-model="createForm.agent_count" 
            :min="3" 
            :max="10" 
            :step="1"
          />
        </t-form-item>
        
        <t-form-item label="目标股票">
          <t-select 
            v-model="createForm.symbols" 
            multiple 
            filterable
            creatable
            placeholder="输入股票代码"
          >
            <t-option label="000001.SZ (平安银行)" value="000001.SZ" />
            <t-option label="600000.SH (浦发银行)" value="600000.SH" />
            <t-option label="000002.SZ (万科A)" value="000002.SZ" />
            <t-option label="600519.SH (贵州茅台)" value="600519.SH" />
          </t-select>
        </t-form-item>
        
        <t-form-item label="初始资金">
          <t-input-number 
            v-model="createForm.initial_capital" 
            :min="10000" 
            :max="10000000"
            :step="10000"
            theme="normal"
          />
        </t-form-item>
        
        <t-form-item label="讨论轮次">
          <t-input-number 
            v-model="createForm.discussion_max_rounds" 
            :min="1" 
            :max="10"
            theme="normal"
          />
        </t-form-item>
      </t-form>
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import { MessagePlugin, DialogPlugin } from 'tdesign-vue-next';
import type { FormInstanceFunctions, FormRule } from 'tdesign-vue-next';
import { useArenaStore } from '@/stores/arena';

const router = useRouter();
const arenaStore = useArenaStore();

// State
const showCreateDialog = ref(false);
const creating = ref(false);
const createFormRef = ref<FormInstanceFunctions>();

const createForm = ref({
  name: '',
  description: '',
  agent_count: 5,
  symbols: ['000001.SZ', '600000.SH'],
  initial_capital: 100000,
  discussion_max_rounds: 3,
});

const createRules: Record<string, FormRule[]> = {
  name: [{ required: true, message: '请输入竞技场名称', trigger: 'blur' }],
  agent_count: [{ required: true, message: '请选择Agent数量', trigger: 'change' }],
};

// Use computed to properly track store state
const arenas = computed(() => arenaStore.arenas || []);
const loading = computed(() => arenaStore.loading);

// Methods
function isArenaRunning(state: string) {
  return ['discussing', 'backtesting', 'simulating', 'evaluating', 'initializing'].includes(state);
}

function getStateTagTheme(state: string): 'default' | 'primary' | 'warning' | 'danger' | 'success' {
  const themes: Record<string, 'default' | 'primary' | 'warning' | 'danger' | 'success'> = {
    created: 'default',
    initializing: 'warning',
    discussing: 'primary',
    backtesting: 'primary',
    simulating: 'success',
    evaluating: 'warning',
    paused: 'warning',
    completed: 'success',
    failed: 'danger',
  };
  return themes[state] || 'default';
}

function getStateLabel(state: string) {
  const labels: Record<string, string> = {
    created: '已创建',
    initializing: '初始化中',
    discussing: '讨论中',
    backtesting: '回测中',
    simulating: '模拟交易',
    evaluating: '评估中',
    paused: '已暂停',
    completed: '已完成',
    failed: '失败',
  };
  return labels[state] || state;
}

function formatDuration(seconds: number) {
  if (seconds < 60) {
    return `${Math.round(seconds)}秒`;
  }
  if (seconds < 3600) {
    return `${Math.round(seconds / 60)}分钟`;
  }
  return `${Math.round(seconds / 3600)}小时`;
}

async function refreshArenas() {
  await arenaStore.fetchArenas();
  // computed will automatically reflect the updated store state
}

async function handleCreate() {
  const result = await createFormRef.value?.validate();
  if (result !== true) return;

  creating.value = true;
  try {
    const arena = await arenaStore.createArena(createForm.value);
    console.log('创建竞技场返回:', arena);
    
    if (!arena || !arena.id) {
      MessagePlugin.error('创建失败：返回数据异常');
      return;
    }
    
    MessagePlugin.success('竞技场创建成功');
    showCreateDialog.value = false;
    router.push(`/arena/${arena.id}`);
  } catch {
    MessagePlugin.error('创建失败');
  } finally {
    creating.value = false;
  }
}

async function handleStart(arenaId: string) {
  try {
    await arenaStore.startArena(arenaId);
    MessagePlugin.success('竞技场已启动');
    await refreshArenas();
  } catch {
    MessagePlugin.error('启动失败');
  }
}

async function handlePause(arenaId: string) {
  try {
    await arenaStore.pauseArena(arenaId);
    MessagePlugin.success('竞技场已暂停');
    await refreshArenas();
  } catch {
    MessagePlugin.error('暂停失败');
  }
}

async function handleResume(arenaId: string) {
  try {
    await arenaStore.resumeArena(arenaId);
    MessagePlugin.success('竞技场已恢复');
    await refreshArenas();
  } catch {
    MessagePlugin.error('恢复失败');
  }
}

async function handleDelete(arenaId: string) {
  const confirmDialog = DialogPlugin.confirm({
    header: '删除确认',
    body: '确定要删除这个竞技场吗？此操作不可恢复。',
    theme: 'warning',
    onConfirm: async () => {
      try {
        await arenaStore.deleteArena(arenaId);
        MessagePlugin.success('竞技场已删除');
        await refreshArenas();
      } catch {
        MessagePlugin.error('删除失败');
      }
      confirmDialog.destroy();
    },
  });
}

function goToArena(arenaId: string) {
  router.push(`/arena/${arenaId}`);
}

// Lifecycle
onMounted(() => {
  refreshArenas();
});
</script>

<style scoped>
.arena-management {
  padding: 20px;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 24px;
  margin-bottom: 8px;
}

.page-header .description {
  color: #909399;
}

.actions-bar {
  margin-bottom: 20px;
  display: flex;
  gap: 12px;
}

.arena-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
}

.arena-card {
  cursor: pointer;
  transition: all 0.3s;
}

.arena-card:hover {
  transform: translateY(-4px);
}

.arena-card.is-running {
  border-left: 4px solid var(--td-brand-color);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.arena-name {
  font-weight: 600;
}

.arena-stats {
  display: flex;
  justify-content: space-around;
  margin: 16px 0;
}

.stat-item {
  text-align: center;
}

.stat-value {
  display: block;
  font-size: 20px;
  font-weight: 600;
  color: var(--td-text-color-primary);
}

.stat-label {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.arena-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.loading-card {
  padding: 20px;
}
</style>

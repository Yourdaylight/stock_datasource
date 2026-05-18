<script setup lang="ts">
import { ref } from 'vue'
import { useMemoryStore } from '@/stores/memory'
import { MessagePlugin } from 'tdesign-vue-next'

const memoryStore = useMemoryStore()
const saving = ref(false)

const riskLevelOptions = [
  { value: 'conservative', label: '保守型' },
  { value: 'moderate', label: '稳健型' },
  { value: 'aggressive', label: '激进型' }
]

const styleOptions = [
  { value: 'value', label: '价值投资' },
  { value: 'growth', label: '成长投资' },
  { value: 'balanced', label: '均衡投资' },
  { value: 'momentum', label: '动量投资' }
]

const sectorOptions = [
  { value: '科技', label: '科技' },
  { value: '金融', label: '金融' },
  { value: '消费', label: '消费' },
  { value: '医药', label: '医药' },
  { value: '新能源', label: '新能源' },
  { value: '半导体', label: '半导体' },
  { value: '军工', label: '军工' },
  { value: '地产', label: '地产' }
]

const watchlistColumns = [
  { colKey: 'ts_code', title: '代码', width: 100 },
  { colKey: 'stock_name', title: '名称', width: 100 },
  { colKey: 'group_name', title: '分组', width: 80 },
  { colKey: 'add_reason', title: '添加原因', ellipsis: true },
  { colKey: 'created_at', title: '时间', width: 100 },
  { colKey: 'operation', title: '操作', width: 80 }
]

async function handleSave() {
  saving.value = true
  await memoryStore.updatePreference(memoryStore.preference)
  saving.value = false
  MessagePlugin.success('偏好已保存')
}

function handleRemoveFromWatchlist(tsCode: string) {
  memoryStore.removeFromWatchlist(tsCode)
}
</script>

<template>
  <t-card class="preference-card" :bordered="false">
    <template #header>
      <div class="card-header">
        <div class="card-header__left">
          <t-icon name="setting" class="header-icon pref-icon" />
          <span class="header-title">偏好设置 & 自选股</span>
        </div>
      </div>
    </template>

    <div class="preference-content">
      <!-- Preference form -->
      <div class="pref-section">
        <div class="section-label">投资偏好</div>
        <t-form label-width="80px" :colon="true">
          <t-form-item label="风险偏好">
            <t-radio-group v-model="memoryStore.preference.risk_level" variant="default-filled">
              <t-radio-button
                v-for="opt in riskLevelOptions"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </t-radio-button>
            </t-radio-group>
          </t-form-item>

          <t-form-item label="投资风格">
            <t-radio-group v-model="memoryStore.preference.investment_style" variant="default-filled">
              <t-radio-button
                v-for="opt in styleOptions"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </t-radio-button>
            </t-radio-group>
          </t-form-item>

          <t-form-item label="偏好行业">
            <t-select
              v-model="memoryStore.preference.favorite_sectors"
              multiple
              placeholder="选择偏好行业"
              :options="sectorOptions"
            />
          </t-form-item>

          <t-form-item>
            <t-button theme="primary" @click="handleSave" :loading="saving">
              保存设置
            </t-button>
          </t-form-item>
        </t-form>
      </div>

      <!-- Watchlist -->
      <div class="pref-section" v-if="memoryStore.watchlist.length > 0">
        <div class="section-label">自选股列表</div>
        <t-table
          :data="memoryStore.watchlist"
          :columns="watchlistColumns"
          :loading="memoryStore.loading"
          row-key="ts_code"
          size="small"
          :max-height="300"
        >
          <template #operation="{ row }">
            <t-popconfirm content="确定移除？" @confirm="handleRemoveFromWatchlist(row.ts_code)">
              <t-link theme="danger" size="small">移除</t-link>
            </t-popconfirm>
          </template>
        </t-table>
      </div>
    </div>
  </t-card>
</template>

<style scoped>
.preference-card {
  height: 100%;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-header__left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-icon {
  font-size: 18px;
}

.pref-icon {
  color: var(--td-text-color-secondary);
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--td-text-color-primary);
}

.preference-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.pref-section {
  /* */
}

.section-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--td-text-color-secondary);
  margin-bottom: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
</style>

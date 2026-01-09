<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useMemoryStore } from '@/stores/memory'

const memoryStore = useMemoryStore()
const activeTab = ref('preference')

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

const watchlistColumns = [
  { colKey: 'ts_code', title: '代码', width: 100 },
  { colKey: 'stock_name', title: '名称', width: 100 },
  { colKey: 'group_name', title: '分组', width: 100 },
  { colKey: 'add_reason', title: '添加原因', width: 150 },
  { colKey: 'created_at', title: '添加时间', width: 150 },
  { colKey: 'operation', title: '操作', width: 100 }
]

const handleRemoveFromWatchlist = (tsCode: string) => {
  memoryStore.removeFromWatchlist(tsCode)
}

const handleSavePreference = () => {
  memoryStore.updatePreference(memoryStore.preference)
}

onMounted(() => {
  memoryStore.fetchPreference()
  memoryStore.fetchWatchlist()
  memoryStore.fetchProfile()
})
</script>

<template>
  <div class="memory-view">
    <t-row :gutter="16">
      <t-col :span="4">
        <t-card title="用户画像">
          <div class="profile-section">
            <div class="profile-item">
              <span class="label">活跃度</span>
              <t-tag :theme="memoryStore.profile?.active_level === 'high' ? 'success' : 'default'">
                {{ memoryStore.profile?.active_level || '未知' }}
              </t-tag>
            </div>
            <div class="profile-item">
              <span class="label">专业度</span>
              <t-tag>{{ memoryStore.profile?.expertise_level || '未知' }}</t-tag>
            </div>
            <div class="profile-item">
              <span class="label">交易风格</span>
              <t-tag>{{ memoryStore.profile?.trading_style || '未知' }}</t-tag>
            </div>
            <div class="profile-item">
              <span class="label">关注行业</span>
              <div class="tags">
                <t-tag
                  v-for="ind in memoryStore.profile?.focus_industries || []"
                  :key="ind"
                  size="small"
                >
                  {{ ind }}
                </t-tag>
              </div>
            </div>
          </div>
        </t-card>
      </t-col>

      <t-col :span="8">
        <t-card>
          <t-tabs v-model="activeTab">
            <t-tab-panel value="preference" label="偏好设置">
              <t-form label-width="100px">
                <t-form-item label="风险偏好">
                  <t-radio-group v-model="memoryStore.preference.risk_level">
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
                  <t-radio-group v-model="memoryStore.preference.investment_style">
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
                    :options="[
                      { value: '科技', label: '科技' },
                      { value: '金融', label: '金融' },
                      { value: '消费', label: '消费' },
                      { value: '医药', label: '医药' },
                      { value: '新能源', label: '新能源' }
                    ]"
                  />
                </t-form-item>
                
                <t-form-item>
                  <t-button theme="primary" @click="handleSavePreference">保存设置</t-button>
                </t-form-item>
              </t-form>
            </t-tab-panel>
            
            <t-tab-panel value="watchlist" label="自选股">
              <t-table
                :data="memoryStore.watchlist"
                :columns="watchlistColumns"
                :loading="memoryStore.loading"
                row-key="ts_code"
              >
                <template #operation="{ row }">
                  <t-popconfirm content="确定移除该股票？" @confirm="handleRemoveFromWatchlist(row.ts_code)">
                    <t-link theme="danger">移除</t-link>
                  </t-popconfirm>
                </template>
              </t-table>
            </t-tab-panel>
            
            <t-tab-panel value="history" label="交互历史">
              <t-timeline>
                <t-timeline-item
                  v-for="item in memoryStore.history"
                  :key="item.id"
                  :label="item.timestamp"
                >
                  <p><strong>{{ item.intent }}</strong></p>
                  <p>{{ item.user_input }}</p>
                  <t-space v-if="item.stocks_mentioned?.length">
                    <t-tag v-for="stock in item.stocks_mentioned" :key="stock" size="small">
                      {{ stock }}
                    </t-tag>
                  </t-space>
                </t-timeline-item>
              </t-timeline>
            </t-tab-panel>
          </t-tabs>
        </t-card>
      </t-col>
    </t-row>
  </div>
</template>

<style scoped>
.memory-view {
  height: 100%;
}

.profile-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.profile-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.profile-item .label {
  font-size: 12px;
  color: #666;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
</style>

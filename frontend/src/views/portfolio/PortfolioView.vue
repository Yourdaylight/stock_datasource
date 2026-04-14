<script setup lang="ts">
import { ref, computed, onMounted, onActivated, onDeactivated } from 'vue'
import { usePortfolioStore } from '@/stores/portfolio'
import { useMemoryStore } from '@/stores/memory'
import { MessagePlugin } from 'tdesign-vue-next'
import request from '@/utils/request'
import DataEmptyGuide from '@/components/DataEmptyGuide.vue'
import StockDetailDialog from '@/components/StockDetailDialog.vue'
import type { BrokerProfile } from '@/api/profile'

const portfolioStore = usePortfolioStore()
const memoryStore = useMemoryStore()
const activeTab = ref('positions')
const showAddModal = ref(false)
const addForm = ref({
  ts_code: '',
  quantity: 100,
  cost_price: 0,
  buy_date: '',
  notes: ''
})

// ---- Profile management ----
const showProfileDialog = ref(false)
const profileFormMode = ref<'create' | 'edit'>('create')
const profileForm = ref({ name: '', broker: '', is_default: false })
const editingProfileId = ref('')
const profileLoading = ref(false)

const activeProfile = computed(() =>
  portfolioStore.profiles.find(p => p.id === portfolioStore.activeProfileId)
)

const handleOpenCreateProfile = () => {
  profileFormMode.value = 'create'
  profileForm.value = { name: '', broker: '', is_default: portfolioStore.profiles.length === 0 }
  editingProfileId.value = ''
  showProfileDialog.value = true
}

const handleOpenEditProfile = (profile: BrokerProfile) => {
  profileFormMode.value = 'edit'
  profileForm.value = { name: profile.name, broker: profile.broker || '', is_default: profile.is_default }
  editingProfileId.value = profile.id
  showProfileDialog.value = true
}

const handleProfileSubmit = async () => {
  if (!profileForm.value.name.trim()) {
    MessagePlugin.warning('请输入账户名称')
    return
  }
  profileLoading.value = true
  try {
    if (profileFormMode.value === 'create') {
      await portfolioStore.createProfile({
        name: profileForm.value.name.trim(),
        broker: profileForm.value.broker.trim() || undefined,
        is_default: profileForm.value.is_default
      })
      MessagePlugin.success('账户创建成功')
    } else {
      await portfolioStore.updateProfile(editingProfileId.value, {
        name: profileForm.value.name.trim(),
        broker: profileForm.value.broker.trim() || undefined
      })
      MessagePlugin.success('账户更新成功')
    }
    showProfileDialog.value = false
  } catch (e: any) {
    MessagePlugin.error(e?.response?.data?.detail || e?.message || '操作失败')
  } finally {
    profileLoading.value = false
  }
}

const handleDeleteProfile = async (profile: BrokerProfile) => {
  if (profile.is_default) {
    MessagePlugin.warning('默认账户不可删除')
    return
  }
  profileLoading.value = true
  try {
    await portfolioStore.deleteProfile(profile.id)
    MessagePlugin.success('账户已删除')
  } catch (e: any) {
    MessagePlugin.error(e?.response?.data?.detail || e?.message || '删除失败')
  } finally {
    profileLoading.value = false
  }
}

const handleSwitchProfile = (profileId: string) => {
  if (profileId === portfolioStore.activeProfileId) return
  portfolioStore.setActiveProfile(profileId)
}

// ---- Auto-refresh positions (prices come from backend rt_minute_latest) ----
let refreshTimer: ReturnType<typeof setInterval> | null = null

const startAutoRefresh = () => {
  if (refreshTimer) return
  refreshTimer = setInterval(() => {
    portfolioStore.fetchPositions()
  }, 30000)
}

const stopAutoRefresh = () => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

// Positions displayed directly (backend returns latest price + update time)
const displayPositions = computed(() => portfolioStore.positions)

// Show latest update time from positions data
const latestUpdateTime = computed(() => {
  const times = portfolioStore.positions
    ?.map(p => p.price_update_time)
    .filter(Boolean) as string[] || []
  if (!times.length) return ''
  
  // Return the most recent update time (show only HH:MM part)
  const latest = times.sort().reverse()[0]
  
  // Extract time portion (HH:MM or HH:MM:SS)
  const match = latest?.match(/(\d{2}:\d{2})(:\d{2})?/)
  return match ? match[1] : latest
})

// Determine if data is truly realtime (within last 5 minutes) vs stale
const isDataRealtime = computed(() => {
  const times = portfolioStore.positions
    ?.map(p => p.price_update_time)
    .filter(Boolean) as string[] || []
  if (!times.length) return false
  
  // Find most recent update
  const sorted = [...times].sort().reverse()
  const latestStr = sorted[0]
  
  // Try to parse datetime
  try {
    // Format: "2026-04-14 15:00:00" or "2026-04-14 15:00"
    const parts = latestStr.match(/(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})/)
    if (parts) {
      const [, datePart, timePart] = parts
      const [h, m] = timePart.split(':').map(Number)
      const updateTime = new Date(`${datePart}T${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:00`)
      
      // Data is "realtime" if updated within last 10 minutes AND during trading hours today
      const now = new Date()
      const diffMin = (now.getTime() - updateTime.getTime()) / 60000
      const isToday = datePart === now.toISOString().split('T')[0]
      
      // Trading hours: 09:25-11:35, 12:55-15:05 (A-share), extended to 16:05 (HK)
      const hhmm = h * 100 + m
      const inTradingHours = (hhmm >= 925 && hhmm <= 1135) || (hhmm >= 1255 && hhmm <= 1505)
      
      return isToday && diffMin < 10 && inTradingHours
    }
  } catch {
    // ignore parse errors
  }
  return false
})

// Display text for the time tag
const timeTagLabel = computed(() => {
  if (!latestUpdateTime.value) return ''
  return isDataRealtime.value ? `实时 ${latestUpdateTime.value}` : `更新 ${latestUpdateTime.value}`
})

const timeTagTheme = computed(() => isDataRealtime.value ? 'success' : 'default')

// ---- Stock search autocomplete ----
interface StockOption {
  code: string
  name: string
  market: string
  label: string
  value: string
}

const stockOptions = ref<StockOption[]>([])
const stockSearchLoading = ref(false)
let searchTimer: ReturnType<typeof setTimeout> | null = null

const handleStockSearch = (keyword: string) => {
  if (searchTimer) clearTimeout(searchTimer)
  if (!keyword || keyword.length < 1) {
    stockOptions.value = []
    return
  }
  searchTimer = setTimeout(async () => {
    stockSearchLoading.value = true
    try {
      const resp = await request.get('/api/market/search', { params: { keyword } })
      const results = resp.data || resp || []
      stockOptions.value = results.map((item: any) => ({
        code: item.code,
        name: item.name,
        market: item.market,
        label: `${item.code} ${item.name}`,
        value: item.code
      }))
    } catch {
      stockOptions.value = []
    } finally {
      stockSearchLoading.value = false
    }
  }, 300)
}

const handleStockSelect = (val: string) => {
  addForm.value.ts_code = val
  const found = stockOptions.value.find(o => o.value === val)
  if (found) {
    stockSearchLabel.value = found.label
  }
}

const stockSearchLabel = ref('')

// Market display helpers
const getMarketLabel = (market?: string) => {
  const map: Record<string, string> = {
    a_share: 'A股', etf: 'ETF', hk_stock: '港股', index: '指数'
  }
  return map[market || ''] || 'A股'
}
const getMarketTagTheme = (market?: string) => {
  const map: Record<string, string> = {
    etf: 'warning', hk_stock: 'primary', index: 'success'
  }
  return map[market || ''] || 'default'
}

// Resolve incomplete code (e.g. '000001' -> '000001.SZ')
const resolveStockCode = async (code: string): Promise<string> => {
  if (!code) return code
  if (/\.\w{2}$/i.test(code)) return code.toUpperCase()
  try {
    const resp = await request.get('/api/market/resolve', { params: { code } })
    const result = resp.data || resp
    if (result && result.code) return result.code
  } catch {
    // Not found, return as-is
  }
  return code
}

// ---- Stock detail dialog ----
const showDetailDialog = ref(false)
const selectedStockCode = ref('')
const handleShowDetail = (row: any) => {
  selectedStockCode.value = row.ts_code
  showDetailDialog.value = true
}
const handleDetailDialogClose = () => {
  showDetailDialog.value = false
  selectedStockCode.value = ''
}

const positionColumns = [
  { colKey: 'ts_code', title: '代码', width: 100 },
  { colKey: 'stock_name', title: '名称', width: 90 },
  { colKey: 'quantity', title: '数量', width: 70 },
  { colKey: 'cost_price', title: '成本价', width: 85 },
  { colKey: 'current_price', title: '现价', width: 85 },
  { colKey: 'daily_pct_chg', title: '今日涨跌', width: 90 },
  { colKey: 'market_value', title: '市值', width: 110 },
  { colKey: 'profit_loss', title: '盈亏', width: 100 },
  { colKey: 'profit_rate', title: '收益率', width: 80 },
  { colKey: 'buy_date', title: '买入日期', width: 100 },
  { colKey: 'price_update_time', title: '更新时间', width: 160 },
  { colKey: 'operation', title: '操作', width: 80 }
]

const watchlistColumns = [
  { colKey: 'ts_code', title: '代码', width: 100 },
  { colKey: 'stock_name', title: '名称', width: 100 },
  { colKey: 'group_name', title: '分组', width: 100 },
  { colKey: 'add_reason', title: '添加原因', width: 150 },
  { colKey: 'created_at', title: '添加时间', width: 150 },
  { colKey: 'operation', title: '操作', width: 100 }
]

const formatMoney = (num?: number, decimals: number = 2) => {
  if (num === undefined) return '-'
  return num.toLocaleString('zh-CN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

const handleAddPosition = async () => {
  if (!addForm.value.ts_code) {
    MessagePlugin.warning('请输入或选择股票代码')
    return
  }
  try {
    addForm.value.ts_code = await resolveStockCode(addForm.value.ts_code)
    await portfolioStore.addPosition(addForm.value)
    showAddModal.value = false
    addForm.value = { ts_code: '', quantity: 100, cost_price: 0, buy_date: '', notes: '' }
    stockSearchLabel.value = ''
    stockOptions.value = []
    MessagePlugin.success('添加成功')
  } catch (e) {
    // Error handled by request interceptor
  }
}

const handleDeletePosition = (id: string) => {
  portfolioStore.deletePosition(id)
}

const handleTriggerAnalysis = () => {
  portfolioStore.triggerDailyAnalysis()
}

// ---- Memory / preference handlers ----
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

const handleSavePreference = () => {
  memoryStore.updatePreference(memoryStore.preference)
  MessagePlugin.success('偏好已保存')
}

const handleRemoveFromWatchlist = (tsCode: string) => {
  memoryStore.removeFromWatchlist(tsCode)
}

const refreshData = () => {
  portfolioStore.fetchPositions()
  portfolioStore.fetchSummary()
  portfolioStore.fetchAnalysis()
}

onMounted(() => {
  portfolioStore.fetchProfiles()
  refreshData()
  startAutoRefresh()
  memoryStore.fetchPreference()
  memoryStore.fetchWatchlist()
  memoryStore.fetchProfile()
})

onActivated(() => {
  refreshData()
  startAutoRefresh()
})

onDeactivated(() => {
  stopAutoRefresh()
})
</script>

<template>
  <div class="portfolio-view">
    <!-- Summary cards -->
    <t-row :gutter="16" style="margin-bottom: 16px">
      <t-col :span="3">
        <t-card title="总市值" :bordered="false">
          <div class="stat-value">{{ formatMoney(portfolioStore.summary?.total_value) }}</div>
        </t-card>
      </t-col>
      <t-col :span="3">
        <t-card title="当日盈亏" :bordered="false">
          <div
            class="stat-value"
            :style="{ color: (portfolioStore.summary?.daily_change || 0) >= 0 ? '#e34d59' : '#00a870' }"
          >
            {{ (portfolioStore.summary?.daily_change || 0) >= 0 ? '+' : '' }}{{ formatMoney(portfolioStore.summary?.daily_change) }}
          </div>
        </t-card>
      </t-col>
      <t-col :span="3">
        <t-card title="当日收益率" :bordered="false">
          <div
            class="stat-value"
            :style="{ color: (portfolioStore.summary?.daily_change_rate || 0) >= 0 ? '#e34d59' : '#00a870' }"
          >
            {{ (portfolioStore.summary?.daily_change_rate || 0) >= 0 ? '+' : '' }}{{ portfolioStore.summary?.daily_change_rate?.toFixed(2) }}%
          </div>
        </t-card>
      </t-col>
      <t-col :span="3">
        <t-card title="总收益率" :bordered="false">
          <div
            class="stat-value"
            :style="{ color: (portfolioStore.summary?.profit_rate || 0) >= 0 ? '#e34d59' : '#00a870' }"
          >
            {{ portfolioStore.summary?.profit_rate?.toFixed(2) }}%
          </div>
        </t-card>
      </t-col>
    </t-row>

    <!-- Tab-based content area -->
    <t-card :bordered="false">
      <t-tabs v-model="activeTab">
        <!-- Tab 1: Positions -->
        <t-tab-panel value="positions" label="持仓列表">
          <!-- Account selector bar -->
          <div class="profile-bar">
            <div class="profile-bar-left">
              <t-select
                :value="portfolioStore.activeProfileId"
                placeholder="选择账户"
                size="small"
                style="width: 200px"
                @change="handleSwitchProfile"
              >
                <t-option
                  v-for="p in portfolioStore.profiles"
                  :key="p.id"
                  :value="p.id"
                  :label="p.name + (p.broker ? ` (${p.broker})` : '') + (p.is_default ? ' [默认]' : '')"
                />
              </t-select>
              <t-tag v-if="activeProfile" size="small" variant="light" theme="primary">
                {{ activeProfile.broker || '未指定券商' }}
              </t-tag>
            </div>
            <div class="profile-bar-right">
              <t-tag v-if="latestUpdateTime" size="small" :theme="timeTagTheme" variant="light">{{ timeTagLabel }}</t-tag>
              <t-button theme="default" variant="text" size="small" @click="showProfileDialog = true; handleOpenCreateProfile()">
                <template #icon><t-icon name="setting" /></template>
                管理账户
              </t-button>
              <t-button theme="primary" size="small" @click="showAddModal = true">
                <template #icon><t-icon name="add" /></template>
                添加持仓
              </t-button>
            </div>
          </div>

          <t-row :gutter="16">
            <t-col :span="8">
              <t-table
                :data="displayPositions"
                :columns="positionColumns"
                :loading="portfolioStore.loading"
                row-key="id"
                size="small"
              >
                <template #ts_code="{ row }">
                  <t-link theme="primary" @click="handleShowDetail(row)">{{ row.ts_code }}</t-link>
                </template>
                <template #stock_name="{ row }">
                  <t-link theme="primary" @click="handleShowDetail(row)">{{ row.stock_name }}</t-link>
                </template>
                <template #cost_price="{ row }">
                  {{ formatMoney(row.cost_price, 3) }}
                </template>
                <template #current_price="{ row }">
                  <span :style="{ color: (row.current_price || 0) >= (row.cost_price || 0) ? '#e34d59' : '#00a870' }">
                    {{ formatMoney(row.current_price, 3) }}
                  </span>
                </template>
                <template #daily_pct_chg="{ row }">
                  <span v-if="row.daily_pct_chg != null" :style="{ color: row.daily_pct_chg >= 0 ? '#e34d59' : '#00a870' }">
                    {{ row.daily_pct_chg >= 0 ? '+' : '' }}{{ row.daily_pct_chg?.toFixed(2) }}%
                  </span>
                  <span v-else style="color: #999">-</span>
                </template>
                <template #profit_loss="{ row }">
                  <span :style="{ color: (row.profit_loss || 0) >= 0 ? '#e34d59' : '#00a870' }">
                    {{ formatMoney(row.profit_loss) }}
                  </span>
                </template>
                <template #profit_rate="{ row }">
                  <span :style="{ color: (row.profit_rate || 0) >= 0 ? '#e34d59' : '#00a870' }">
                    {{ row.profit_rate?.toFixed(2) }}%
                  </span>
                </template>
                <template #price_update_time="{ row }">
                  <span style="font-size: 12px; color: #999">{{ row.price_update_time || '-' }}</span>
                </template>
                <template #operation="{ row }">
                  <t-popconfirm content="确定删除该持仓？" @confirm="handleDeletePosition(row.id)">
                    <t-link theme="danger">删除</t-link>
                  </t-popconfirm>
                </template>
              </t-table>
            </t-col>

            <t-col :span="4">
              <t-card title="每日分析" :bordered="false" size="small">
                <template #actions>
                  <t-button variant="text" size="small" @click="handleTriggerAnalysis">
                    <template #icon><t-icon name="refresh" /></template>
                  </t-button>
                </template>
                <div v-if="portfolioStore.analysis" class="analysis-content">
                  <div class="analysis-date">{{ portfolioStore.analysis.analysis_date }}</div>
                  <t-divider />
                  <div class="analysis-summary">{{ portfolioStore.analysis.analysis_summary }}</div>
                  <div v-if="portfolioStore.analysis.risk_alerts?.length" class="risk-alerts">
                    <h4>风险提示</h4>
                    <t-alert
                      v-for="(alert, index) in portfolioStore.analysis.risk_alerts"
                      :key="index"
                      theme="warning"
                      :message="alert"
                      style="margin-bottom: 8px"
                    />
                  </div>
                  <div v-if="portfolioStore.analysis.recommendations?.length" class="recommendations">
                    <h4>操作建议</h4>
                    <ul>
                      <li v-for="(rec, index) in portfolioStore.analysis.recommendations" :key="index">{{ rec }}</li>
                    </ul>
                  </div>
                </div>
                <DataEmptyGuide v-else description="暂无分析数据" plugin-name="tushare_daily" />
              </t-card>
            </t-col>
          </t-row>
        </t-tab-panel>

        <!-- Tab 2: Watchlist -->
        <t-tab-panel value="watchlist" label="自选股">
          <t-table
            :data="memoryStore.watchlist"
            :columns="watchlistColumns"
            :loading="memoryStore.loading"
            row-key="ts_code"
            size="small"
          >
            <template #operation="{ row }">
              <t-popconfirm content="确定移除该股票？" @confirm="handleRemoveFromWatchlist(row.ts_code)">
                <t-link theme="danger">移除</t-link>
              </t-popconfirm>
            </template>
          </t-table>
          <DataEmptyGuide v-if="!memoryStore.watchlist?.length" description="暂无自选股，可通过智能对话添加" :show-guide="false" />
        </t-tab-panel>

        <!-- Tab 3: Investment Profile -->
        <t-tab-panel value="profile" label="投资偏好">
          <t-row :gutter="16">
            <t-col :span="4">
              <t-card title="用户画像" :bordered="false" size="small">
                <div class="profile-section">
                  <div class="profile-item">
                    <span class="label">活跃度</span>
                    <t-tag :theme="memoryStore.profile?.active_level === 'high' ? 'success' : 'default'" size="small">
                      {{ memoryStore.profile?.active_level || '未知' }}
                    </t-tag>
                  </div>
                  <div class="profile-item">
                    <span class="label">专业度</span>
                    <t-tag size="small">{{ memoryStore.profile?.expertise_level || '未知' }}</t-tag>
                  </div>
                  <div class="profile-item">
                    <span class="label">交易风格</span>
                    <t-tag size="small">{{ memoryStore.profile?.trading_style || '未知' }}</t-tag>
                  </div>
                  <div class="profile-item">
                    <span class="label">关注行业</span>
                    <div class="tags">
                      <t-tag
                        v-for="ind in memoryStore.profile?.focus_industries || []"
                        :key="ind"
                        size="small"
                      >{{ ind }}</t-tag>
                    </div>
                  </div>
                </div>
              </t-card>
            </t-col>
            <t-col :span="8">
              <t-card title="偏好设置" :bordered="false" size="small">
                <t-form label-width="100px">
                  <t-form-item label="风险偏好">
                    <t-radio-group v-model="memoryStore.preference.risk_level">
                      <t-radio-button
                        v-for="opt in riskLevelOptions"
                        :key="opt.value"
                        :value="opt.value"
                      >{{ opt.label }}</t-radio-button>
                    </t-radio-group>
                  </t-form-item>
                  <t-form-item label="投资风格">
                    <t-radio-group v-model="memoryStore.preference.investment_style">
                      <t-radio-button
                        v-for="opt in styleOptions"
                        :key="opt.value"
                        :value="opt.value"
                      >{{ opt.label }}</t-radio-button>
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
              </t-card>
            </t-col>
          </t-row>
        </t-tab-panel>
      </t-tabs>
    </t-card>

    <!-- Add Position Modal -->
    <t-dialog v-model:visible="showAddModal" header="添加持仓" @confirm="handleAddPosition">
      <t-form label-width="80px">
        <t-form-item label="所属账户">
          <t-select v-model="portfolioStore.activeProfileId" disabled size="small" style="width: 100%">
            <t-option
              v-for="p in portfolioStore.profiles"
              :key="p.id"
              :value="p.id"
              :label="p.name + (p.broker ? ` (${p.broker})` : '')"
            />
          </t-select>
        </t-form-item>
        <t-form-item label="股票代码">
          <t-select
            v-model="addForm.ts_code"
            filterable
            creatable
            :loading="stockSearchLoading"
            placeholder="输入代码或名称搜索，支持纯数字如 000001"
            :on-search="handleStockSearch"
            @change="handleStockSelect"
            clearable
          >
            <t-option
              v-for="opt in stockOptions"
              :key="opt.code"
              :value="opt.code"
              :label="opt.label"
            >
              <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
                <span>{{ opt.code }}</span>
                <span style="color: var(--td-text-color-secondary); font-size: 12px;">{{ opt.name }}</span>
                <t-tag size="small" variant="light" :theme="getMarketTagTheme(opt.market)">
                  {{ getMarketLabel(opt.market) }}
                </t-tag>
              </div>
            </t-option>
          </t-select>
        </t-form-item>
        <t-form-item label="数量">
          <t-input-number v-model="addForm.quantity" :min="100" :step="100" />
        </t-form-item>
        <t-form-item label="成本价">
          <t-input-number v-model="addForm.cost_price" :min="0" :decimal-places="3" :step="0.001" />
        </t-form-item>
        <t-form-item label="买入日期">
          <t-date-picker v-model="addForm.buy_date" />
        </t-form-item>
        <t-form-item label="备注">
          <t-textarea v-model="addForm.notes" />
        </t-form-item>
      </t-form>
    </t-dialog>

    <!-- Profile Management Dialog -->
    <t-dialog
      v-model:visible="showProfileDialog"
      :header="profileFormMode === 'create' ? '新建账户' : '编辑账户'"
      @confirm="handleProfileSubmit"
      :confirm-btn="{ loading: profileLoading }"
    >
      <t-form label-width="80px">
        <t-form-item label="账户名称">
          <t-input v-model="profileForm.name" placeholder="如：华泰主账户" />
        </t-form-item>
        <t-form-item label="券商">
          <t-input v-model="profileForm.broker" placeholder="如：华泰证券" />
        </t-form-item>
        <t-form-item v-if="profileFormMode === 'create'" label="设为默认">
          <t-switch v-model="profileForm.is_default" />
        </t-form-item>
      </t-form>

      <!-- Existing profiles list -->
      <t-divider>已有账户</t-divider>
      <div v-if="portfolioStore.profiles.length" class="profile-list">
        <div v-for="p in portfolioStore.profiles" :key="p.id" class="profile-list-item">
          <div class="profile-list-info">
            <span class="profile-list-name">{{ p.name }}</span>
            <t-tag v-if="p.broker" size="small" variant="light">{{ p.broker }}</t-tag>
            <t-tag v-if="p.is_default" size="small" variant="light" theme="success">默认</t-tag>
          </div>
          <div class="profile-list-actions">
            <t-link theme="primary" size="small" @click="handleOpenEditProfile(p)">编辑</t-link>
            <t-popconfirm content="确定删除该账户？" @confirm="handleDeleteProfile(p)">
              <t-link theme="danger" size="small">删除</t-link>
            </t-popconfirm>
          </div>
        </div>
      </div>
      <div v-else style="color: #999; text-align: center; padding: 12px 0;">暂无账户，请创建</div>
    </t-dialog>

    <!-- Stock Detail Dialog -->
    <StockDetailDialog
      v-model:visible="showDetailDialog"
      :stock-code="selectedStockCode"
      @close="handleDetailDialogClose"
    />
  </div>
</template>

<style scoped>
.portfolio-view {
  height: 100%;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
}

/* Profile bar */
.profile-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  gap: 8px;
}
.profile-bar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.profile-bar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Profile list in dialog */
.profile-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.profile-list-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border-radius: 6px;
  background: var(--td-bg-color-container-hover);
}
.profile-list-info {
  display: flex;
  align-items: center;
  gap: 8px;
}
.profile-list-name {
  font-weight: 500;
}
.profile-list-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.analysis-content {
  font-size: 14px;
  line-height: 1.8;
}

.analysis-date {
  color: #999;
  font-size: 12px;
}

.analysis-summary {
  margin-bottom: 16px;
}

.risk-alerts, .recommendations {
  margin-top: 16px;
}

.risk-alerts h4, .recommendations h4 {
  font-size: 14px;
  margin-bottom: 8px;
}

.recommendations ul {
  padding-left: 20px;
}

/* Profile section */
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

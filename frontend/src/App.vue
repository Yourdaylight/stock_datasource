<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { MessagePlugin } from 'tdesign-vue-next'
import QuotaIndicator from '@/components/QuotaIndicator.vue'
import {
  ChatIcon,
  ChartLineIcon,
  FilterIcon,
  FileSearchIcon,
  FileIcon,
  UserIcon,
  ServerIcon,
  WalletIcon,
  ChartBubbleIcon,
  ToolsIcon,
  ControlPlatformIcon,
  LockOnIcon,
  LogoutIcon,
  QueueIcon,
  TrendingUpIcon,
  SearchIcon,
  TimeIcon,
  SettingIcon,
  NotificationIcon,
  DataDisplayIcon,
  BookOpenIcon,
  PreciseMonitorIcon,
  LinkIcon,
  RootListIcon
} from 'tdesign-icons-vue-next'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

// Public routes that don't require authentication
const PUBLIC_ROUTES = ['/login', '/market', '/research']

// Menu items with submenu support
interface MenuItem {
  path: string
  title: string
  icon: any
  public?: boolean
  requiresAuth?: boolean
  requiresAdmin?: boolean
  requiresTier?: 'pro' | 'admin'
  children?: MenuItem[]
}

const menuItems: MenuItem[] = [
  { path: '/market', title: '行情分析', icon: ChartLineIcon, public: true },
  { path: '/research', title: '财报分析', icon: FileSearchIcon, public: true },
  { path: '/news', title: '资讯中心', icon: NotificationIcon, requiresAuth: true },
  { path: '/chat', title: '智能对话', icon: ChatIcon, requiresAuth: true },
  { path: '/screener', title: '智能选股', icon: FilterIcon, requiresAuth: true },
  { path: '/portfolio', title: '持仓管理', icon: WalletIcon, requiresAuth: true },
  { path: '/etf', title: '智能选ETF', icon: ControlPlatformIcon, requiresAuth: true },
  { path: '/index', title: '指数行情', icon: TrendingUpIcon, requiresAuth: true },
  {
    path: '/strategy',
    title: '策略系统',
    icon: ToolsIcon,
    requiresAuth: true,
    requiresTier: 'pro',
    children: [
      { path: '/strategy', title: '策略工具台', icon: ToolsIcon, requiresAuth: true, requiresTier: 'pro' },
      { path: '/arena', title: 'Agent竞技场', icon: DataDisplayIcon, requiresAuth: true, requiresTier: 'pro' }
    ]
  },
  {
    path: '/quant',
    title: '量化选股',
    icon: PreciseMonitorIcon,
    requiresAuth: true,
    requiresTier: 'pro',
    children: [
      { path: '/quant', title: '模型总览', icon: PreciseMonitorIcon, requiresAuth: true, requiresTier: 'pro' },
      { path: '/quant/screening', title: '全市场初筛', icon: FilterIcon, requiresAuth: true, requiresTier: 'pro' },
      { path: '/quant/pool', title: '核心目标池', icon: DataDisplayIcon, requiresAuth: true, requiresTier: 'pro' },
      { path: '/quant/rps', title: 'RPS排名', icon: TrendingUpIcon, requiresAuth: true, requiresTier: 'pro' },
      { path: '/quant/analysis', title: '深度分析', icon: FileSearchIcon, requiresAuth: true, requiresTier: 'pro' },
      { path: '/quant/signals', title: '交易信号', icon: NotificationIcon, requiresAuth: true, requiresTier: 'pro' },
      { path: '/quant/config', title: '模型配置', icon: SettingIcon, requiresAuth: true, requiresTier: 'pro' }
    ]
  },
  { path: '/workflow', title: 'AI工作流', icon: QueueIcon, requiresAuth: true, requiresTier: 'pro' },
  { path: '/wechat-bridge', title: '微信联动', icon: RootListIcon, requiresAuth: true, requiresAdmin: true },
  { path: '/memory', title: '用户记忆', icon: UserIcon, requiresAuth: true },
  {
    path: '/system-logs',
    title: '系统日志',
    icon: FileIcon,
    requiresAuth: true,
    requiresAdmin: true
  },
  {
    path: '/api-access',
    title: '开放API',
    icon: LinkIcon,
    requiresAuth: true,
    requiresAdmin: true
  },
  {
    path: '/datamanage',
    title: '数据管理',
    icon: ServerIcon,
    requiresAuth: true,
    requiresAdmin: true,
    children: [
      { path: '/datamanage', title: '数据概览', icon: ServerIcon, requiresAuth: true, requiresAdmin: true },
      { path: '/datamanage/explorer', title: '数据浏览器', icon: SearchIcon, requiresAuth: true, requiresAdmin: true },
      { path: '/datamanage/tasks', title: '同步任务', icon: TimeIcon, requiresAuth: true, requiresAdmin: true },
      { path: '/datamanage/knowledge', title: '知识库', icon: BookOpenIcon, requiresAuth: true, requiresAdmin: true },
      { path: '/datamanage/config', title: '数据配置', icon: SettingIcon, requiresAuth: true, requiresAdmin: true }
    ]
  }
]

// Tier hierarchy for menu visibility
const TIER_LEVELS: Record<string, number> = { free: 0, pro: 1, admin: 2 }

// Filter menu items based on user's tier and role
const visibleMenuItems = computed(() => {
  const userTier = authStore.user?.subscription_tier || 'free'
  const userLevel = TIER_LEVELS[userTier] ?? 0
  const isAdmin = authStore.isAdmin

  const canSee = (item: MenuItem): boolean => {
    if (item.requiresAdmin && !isAdmin) return false
    if (item.requiresTier) {
      const requiredLevel = TIER_LEVELS[item.requiresTier] ?? 0
      if (userLevel < requiredLevel && !isAdmin) return false
    }
    return true
  }

  return menuItems.filter(canSee)
})

const activeMenu = computed(() => route.path)
const isLoginPage = computed(() => route.path === '/login')

// Find menu item including children
const findMenuItem = (path: string, items: MenuItem[] = menuItems): MenuItem | undefined => {
  for (const item of items) {
    if (item.path === path) return item
    if (item.children) {
      const found = findMenuItem(path, item.children)
      if (found) return found
    }
  }
  return undefined
}

const handleMenuChange = (value: string) => {
  const item = findMenuItem(value)
  if (item?.requiresAuth && !authStore.isAuthenticated) {
    MessagePlugin.warning('请先登录')
    router.push({ path: '/login', query: { redirect: value } })
    return
  }
  if (item?.requiresAdmin && !authStore.user?.is_admin) {
    MessagePlugin.warning('需要管理员权限')
    return
  }
  router.push(value)
}

const currentTitle = computed(() => {
  const item = findMenuItem(route.path)
  return item?.title || 'AI 智能选股平台'
})

const handleLogin = () => {
  router.push('/login')
}

const handleLogout = async () => {
  authStore.logout()
  MessagePlugin.success('已退出登录')
  router.push('/market')
}

const handleUserAction = (data: { value: string }) => {
  if (data.value === 'logout') {
    handleLogout()
  } else if (data.value === 'user') {
    router.push('/user')
  }
}

onMounted(async () => {
  // Try to restore auth state
  if (authStore.token) {
    await authStore.checkAuth()
  }
})
</script>

<template>
  <!-- Login page has its own layout -->
  <router-view v-if="isLoginPage" />
  
  <!-- Main layout for other pages -->
  <div v-else class="main-layout">
    <aside class="sidebar">
      <div class="logo">
        <span>AI 智能选股</span>
      </div>
      <t-menu
        :value="activeMenu"
        theme="light"
        @change="handleMenuChange"
      >
        <template v-for="item in visibleMenuItems" :key="item.path">
          <!-- Item with submenu -->
          <t-submenu v-if="item.children" :value="item.path">
            <template #icon>
              <component :is="item.icon" />
            </template>
            <template #title>
              <div class="menu-item-content">
                <span>{{ item.title }}</span>
                <LockOnIcon 
                  v-if="item.requiresAuth && !authStore.isAuthenticated" 
                  class="lock-icon"
                />
              </div>
            </template>
            <t-menu-item
              v-for="child in item.children"
              :key="child.path"
              :value="child.path"
            >
              <template #icon>
                <component :is="child.icon" />
              </template>
              {{ child.title }}
            </t-menu-item>
          </t-submenu>
          <!-- Regular item -->
          <t-menu-item v-else :value="item.path">
            <template #icon>
              <component :is="item.icon" />
            </template>
            <div class="menu-item-content">
              <span>{{ item.title }}</span>
              <LockOnIcon 
                v-if="item.requiresAuth && !authStore.isAuthenticated" 
                class="lock-icon"
              />
            </div>
          </t-menu-item>
        </template>
      </t-menu>
    </aside>
    
    <main class="main-content">
      <header class="header">
        <h2>{{ currentTitle }}</h2>
        <t-space>
          <template v-if="authStore.isAuthenticated">
            <QuotaIndicator />
            <t-dropdown :options="[{ content: '个人中心', value: 'user' }, { content: '退出登录', value: 'logout' }]" @click="handleUserAction">
              <t-button variant="text">
                <template #icon><UserIcon /></template>
                {{ authStore.user?.username || authStore.user?.email }}
              </t-button>
            </t-dropdown>
          </template>
          <template v-else>
            <t-button theme="primary" @click="handleLogin">
              <template #icon><UserIcon /></template>
              登录
            </t-button>
          </template>
        </t-space>
      </header>
      
      <div class="content">
        <router-view v-slot="{ Component, route }">
          <transition name="fade" mode="out-in">
            <component :is="Component" :key="route.path" />
          </transition>
        </router-view>
      </div>
    </main>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.menu-item-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.lock-icon {
  font-size: 12px;
  color: #86909c;
  margin-left: 8px;
}
</style>

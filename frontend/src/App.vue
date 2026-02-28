<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { MessagePlugin } from 'tdesign-vue-next'
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
  PreciseMonitorIcon
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
    children: [
      { path: '/strategy', title: '策略工具台', icon: ToolsIcon, requiresAuth: true },
      { path: '/backtest', title: '策略回测', icon: ChartBubbleIcon, requiresAuth: true },
      { path: '/arena', title: 'Agent竞技场', icon: DataDisplayIcon, requiresAuth: true }
    ]
  },
  {
    path: '/quant',
    title: '量化选股',
    icon: PreciseMonitorIcon,
    requiresAuth: true,
    children: [
      { path: '/quant', title: '模型总览', icon: PreciseMonitorIcon, requiresAuth: true },
      { path: '/quant/screening', title: '全市场初筛', icon: FilterIcon, requiresAuth: true },
      { path: '/quant/pool', title: '核心目标池', icon: DataDisplayIcon, requiresAuth: true },
      { path: '/quant/rps', title: 'RPS排名', icon: TrendingUpIcon, requiresAuth: true },
      { path: '/quant/analysis', title: '深度分析', icon: FileSearchIcon, requiresAuth: true },
      { path: '/quant/signals', title: '交易信号', icon: NotificationIcon, requiresAuth: true },
      { path: '/quant/config', title: '模型配置', icon: SettingIcon, requiresAuth: true }
    ]
  },
  { path: '/workflow', title: 'AI工作流', icon: QueueIcon, requiresAuth: true },
  { path: '/memory', title: '用户记忆', icon: UserIcon, requiresAuth: true },
  {
    path: '/system-logs',
    title: '系统日志',
    icon: FileIcon,
    requiresAuth: true,
    requiresAdmin: true
  },
  {
    path: '/datamanage',
    title: '数据管理',
    icon: ServerIcon,
    requiresAuth: true,
    children: [
      { path: '/datamanage', title: '数据概览', icon: ServerIcon, requiresAuth: true },
      { path: '/datamanage/explorer', title: '数据浏览器', icon: SearchIcon, requiresAuth: true },
      { path: '/datamanage/tasks', title: '同步任务', icon: TimeIcon, requiresAuth: true },
      { path: '/datamanage/knowledge', title: '知识库', icon: BookOpenIcon, requiresAuth: true },
      { path: '/datamanage/config', title: '数据配置', icon: SettingIcon, requiresAuth: true }
    ]
  }
]

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
        <template v-for="item in menuItems" :key="item.path">
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
            <t-dropdown :options="[{ content: '退出登录', value: 'logout' }]" @click="handleLogout">
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

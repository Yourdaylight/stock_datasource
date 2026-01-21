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
  UserIcon,
  ServerIcon,
  WalletIcon,
  ChartBubbleIcon,
  ToolsIcon,
  ControlPlatformIcon,
  LockOnIcon,
  LogoutIcon,
  QueueIcon
} from 'tdesign-icons-vue-next'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

// Public routes that don't require authentication
const PUBLIC_ROUTES = ['/login', '/market', '/research']

const menuItems = [
  { path: '/market', title: '行情分析', icon: ChartLineIcon, public: true },
  { path: '/research', title: '研究数据', icon: FileSearchIcon, public: true },
  { path: '/chat', title: '智能对话', icon: ChatIcon, requiresAuth: true },
  { path: '/screener', title: '智能选股', icon: FilterIcon, requiresAuth: true },
  { path: '/portfolio', title: '持仓管理', icon: WalletIcon, requiresAuth: true },
  { path: '/etf', title: '智能选ETF', icon: ControlPlatformIcon, requiresAuth: true },
  { path: '/strategy', title: '策略工具台', icon: ToolsIcon, requiresAuth: true },
  { path: '/workflow', title: 'AI工作流', icon: QueueIcon, requiresAuth: true },
  { path: '/backtest', title: '策略回测', icon: ChartBubbleIcon, requiresAuth: true },
  { path: '/memory', title: '用户记忆', icon: UserIcon, requiresAuth: true },
  { path: '/datamanage', title: '数据管理', icon: ServerIcon, requiresAuth: true }
]

const activeMenu = computed(() => route.path)
const isLoginPage = computed(() => route.path === '/login')

const handleMenuChange = (value: string) => {
  const item = menuItems.find(m => m.path === value)
  if (item?.requiresAuth && !authStore.isAuthenticated) {
    MessagePlugin.warning('请先登录')
    router.push({ path: '/login', query: { redirect: value } })
    return
  }
  router.push(value)
}

const currentTitle = computed(() => {
  const item = menuItems.find(m => m.path === route.path)
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
        <t-menu-item
          v-for="item in menuItems"
          :key="item.path"
          :value="item.path"
        >
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

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ChatIcon,
  ChartLineIcon,
  FilterIcon,
  FileExcelIcon,
  UserIcon,
  ServerIcon,
  WalletIcon,
  ChartBubbleIcon,
  ToolsIcon,
  ControlPlatformIcon,
  ChartBarIcon
} from 'tdesign-icons-vue-next'

const route = useRoute()
const router = useRouter()

const menuItems = [
  { path: '/market', title: '行情分析', icon: ChartLineIcon },
  { path: '/toplist', title: '龙虎榜分析', icon: ChartBarIcon },
  { path: '/report', title: '财报研读', icon: FileExcelIcon },
  { path: '/chat', title: '智能对话', icon: ChatIcon },
  { path: '/screener', title: '智能选股', icon: FilterIcon },
  { path: '/portfolio', title: '持仓管理', icon: WalletIcon },
  { path: '/etf', title: '智能选ETF', icon: ControlPlatformIcon },
  { path: '/strategy', title: '策略工具台', icon: ToolsIcon },
  { path: '/backtest', title: '策略回测', icon: ChartBubbleIcon },
  { path: '/memory', title: '用户记忆', icon: UserIcon },
  { path: '/datamanage', title: '数据管理', icon: ServerIcon }
]

const activeMenu = computed(() => route.path)

const handleMenuChange = (value: string) => {
  router.push(value)
}

const currentTitle = computed(() => {
  const item = menuItems.find(m => m.path === route.path)
  return item?.title || 'AI 智能选股平台'
})
</script>

<template>
  <div class="main-layout">
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
          {{ item.title }}
        </t-menu-item>
      </t-menu>
    </aside>
    
    <main class="main-content">
      <header class="header">
        <h2>{{ currentTitle }}</h2>
        <t-space>
          <t-button variant="text" shape="circle">
            <template #icon><UserIcon /></template>
          </t-button>
        </t-space>
      </header>
      
      <div class="content">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
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
</style>

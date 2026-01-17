import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// Public routes that don't require authentication
const PUBLIC_ROUTES = ['/login', '/market', '/toplist']

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/market'
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/LoginView.vue'),
    meta: { title: '登录', public: true }
  },
  {
    path: '/market',
    name: 'Market',
    component: () => import('@/views/market/MarketView.vue'),
    meta: { title: '行情分析', icon: 'chart-line', public: true }
  },
  {
    path: '/toplist',
    name: 'TopList',
    component: () => import('@/views/TopListView.vue'),
    meta: { title: '龙虎榜分析', icon: 'chart-bar', public: true }
  },
  {
    path: '/report',
    name: 'Report',
    component: () => import('@/views/report/ReportView.vue'),
    meta: { title: '财报研读', icon: 'file-excel', requiresAuth: true }
  },
  {
    path: '/chat',
    name: 'Chat',
    component: () => import('@/views/chat/ChatView.vue'),
    meta: { title: '智能对话', icon: 'chat', requiresAuth: true }
  },
  {
    path: '/screener',
    name: 'Screener',
    component: () => import('@/views/screener/ScreenerView.vue'),
    meta: { title: '智能选股', icon: 'filter', requiresAuth: true }
  },
  {
    path: '/portfolio',
    name: 'Portfolio',
    component: () => import('@/views/portfolio/PortfolioView.vue'),
    meta: { title: '持仓管理', icon: 'wallet', requiresAuth: true }
  },
  {
    path: '/etf',
    name: 'ETF',
    component: () => import('@/views/index/IndexScreenerView.vue'),
    meta: { title: '智能选ETF', icon: 'control-platform', requiresAuth: true }
  },
  {
    path: '/strategy',
    name: 'Strategy',
    component: () => import('@/views/StrategyWorkbench.vue'),
    meta: { title: '策略工具台', icon: 'tools', requiresAuth: true }
  },
  {
    path: '/backtest',
    name: 'Backtest',
    component: () => import('@/views/backtest/BacktestView.vue'),
    meta: { title: '策略回测', icon: 'chart-bubble', requiresAuth: true }
  },
  {
    path: '/memory',
    name: 'Memory',
    component: () => import('@/views/memory/MemoryView.vue'),
    meta: { title: '用户记忆', icon: 'user', requiresAuth: true }
  },
  {
    path: '/datamanage',
    name: 'DataManage',
    component: () => import('@/views/datamanage/DataManageView.vue'),
    meta: { title: '数据管理', icon: 'server', requiresAuth: true }
  },
  {
    path: '/index',
    name: 'Index',
    component: () => import('@/views/index/IndexScreenerView.vue'),
    meta: { title: '指数选股', icon: 'chart-pie', requiresAuth: true }
  },
  {
    path: '/etf',
    name: 'Etf',
    component: () => import('@/views/etf/EtfScreenerView.vue'),
    meta: { title: 'ETF基金', icon: 'coin' }
  },
  {
    path: '/strategy',
    name: 'Strategy',
    component: () => import('@/views/StrategyWorkbench.vue'),
    meta: { title: '策略工作台', icon: 'tools' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Navigation guard for authentication
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()
  
  // Check if route requires authentication
  const requiresAuth = to.meta.requiresAuth === true
  const isPublic = to.meta.public === true || PUBLIC_ROUTES.includes(to.path)
  
  // If route is public, allow access
  if (isPublic) {
    // If user is logged in and trying to access login page, redirect to market
    if (to.path === '/login' && authStore.isAuthenticated) {
      next('/market')
      return
    }
    next()
    return
  }
  
  // For protected routes, check authentication
  if (requiresAuth) {
    const isAuth = await authStore.checkAuth()
    if (!isAuth) {
      // Redirect to login with return URL
      next({ path: '/login', query: { redirect: to.fullPath } })
      return
    }
  }
  
  next()
})

export default router

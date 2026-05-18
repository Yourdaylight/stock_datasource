import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// Public routes that don't require authentication
const PUBLIC_ROUTES = ['/login', '/market', '/research']

// Helper: check if path is public (including sub-paths)
function isPublicPath(path: string): boolean {
  return PUBLIC_ROUTES.some(p => path === p || path.startsWith(p + '/'))
}

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/chat'
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
    path: '/research',
    component: () => import('@/views/research/ResearchView.vue'),
    meta: { title: '财报分析', icon: 'file-search', public: true },
    children: [
      {
        path: '',
        name: 'Research',
        component: () => import('@/views/research/CompanyListView.vue'),
        meta: { title: '财报分析', public: true }
      },
      {
        path: ':code',
        name: 'ReportList',
        component: () => import('@/views/research/ReportListView.vue'),
        meta: { title: '财报列表', public: true },
        props: true
      },
      {
        path: ':code/:period',
        name: 'ReportDetail',
        component: () => import('@/views/research/ReportDetailView.vue'),
        meta: { title: '财报详情', public: true },
        props: true
      }
    ]
  },
  {
    path: '/news',
    name: 'News',
    component: () => import('@/views/news/NewsView.vue'),
    meta: { title: '资讯中心', icon: 'notification', requiresAuth: true }
  },
  {
    path: '/chat/:sessionId?',
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
    meta: { title: '我的持仓', icon: 'wallet', requiresAuth: true }
  },
  {
    path: '/etf',
    name: 'ETF',
    component: () => import('@/views/etf/EtfView.vue'),
    meta: { title: '智能选ETF', icon: 'control-platform', requiresAuth: true }
  },
  {
    path: '/index',
    name: 'Index',
    component: () => import('@/views/index/IndexScreenerView.vue'),
    meta: { title: '指数行情', icon: 'trending-up', requiresAuth: true }
  },
  {
    path: '/strategy',
    name: 'Strategy',
    component: () => import('@/views/StrategyWorkbench.vue'),
    meta: { title: '策略工具台', icon: 'tools', requiresAuth: true, requiresTier: 'pro' }
  },
  {
    path: '/backtest',
    name: 'Backtest',
    component: () => import('@/views/backtest/BacktestView.vue'),
    meta: { title: '策略回测', icon: 'chart-bubble', requiresAuth: true, requiresTier: 'pro' }
  },
  {
    path: '/memory',
    name: 'Memory',
    component: () => import('@/views/memory/MemoryView.vue'),
    meta: { title: '用户记忆', icon: 'brain', requiresAuth: true }
  },
  {
    path: '/datamanage',
    name: 'DataManage',
    component: () => import('@/views/datamanage/DataManageView.vue'),
    meta: { title: '数据管理', icon: 'server', requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/datamanage/explorer',
    name: 'DataExplorer',
    component: () => import('@/views/datamanage/DataExplorerView.vue'),
    meta: { title: '数据浏览器', icon: 'search', requiresAuth: true }
  },
  {
    path: '/datamanage/tasks',
    name: 'SyncTasks',
    component: () => import('@/views/datamanage/SyncTasksView.vue'),
    meta: { title: '同步任务', icon: 'time', requiresAuth: true }
  },
  {
    path: '/datamanage/config',
    name: 'DataConfig',
    component: () => import('@/views/datamanage/DataConfigView.vue'),
    meta: { title: '数据配置', icon: 'setting', requiresAuth: true }
  },
  {
    path: '/datamanage/knowledge',
    name: 'KnowledgeBase',
    component: () => import('@/views/datamanage/KnowledgeView.vue'),
    meta: { title: '知识库', icon: 'book-open', requiresAuth: true }
  },
  {
    path: '/system-logs',
    name: 'SystemLogs',
    component: () => import('@/views/SystemLogs.vue'),
    meta: { title: '系统日志', icon: 'file-list', requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/api-access',
    name: 'ApiAccess',
    component: () => import('@/views/apiAccess/ApiAccessView.vue'),
    meta: { title: '开放API管理', icon: 'link', requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/workflow',
    redirect: '/orchestration'
  },
  {
    path: '/orchestration',
    name: 'OrchestrationList',
    component: () => import('@/views/orchestration/OrchestrationList.vue'),
    meta: { title: 'Agent编排', icon: 'flow', requiresAuth: true, requiresTier: 'pro' }
  },
  {
    path: '/orchestration/:id',
    name: 'OrchestrationEditor',
    component: () => import('@/views/orchestration/OrchestrationEditor.vue'),
    meta: { title: '编排编辑器', requiresAuth: true, requiresTier: 'pro' }
  },
  {
    path: '/agents',
    name: 'AgentManagement',
    component: () => import('@/views/agent-management/AgentList.vue'),
    meta: { title: 'Agent管理', icon: 'user-setting', requiresAuth: true }
  },
  {
    path: '/runtimes',
    name: 'RuntimeManagement',
    component: () => import('@/views/agent-management/RuntimeManagement.vue'),
    meta: { title: 'Runtime管理', requiresAuth: true }
  },
  {
    path: '/agents/:id/edit',
    name: 'AgentEditor',
    component: () => import('@/views/agent-management/AgentEditor.vue'),
    meta: { title: '编辑Agent', requiresAuth: true }
  },
  {
    path: '/arena',
    name: 'Arena',
    component: () => import('@/views/arena/ArenaManagement.vue'),
    meta: { title: '多Agent竞技场', icon: 'data-analysis', requiresAuth: true }
  },
{
    path: '/arena/:id',
    name: 'ArenaDetail',
    component: () => import('@/views/arena/ArenaDetail.vue'),
    meta: { title: '竞技场详情', requiresAuth: true }
  },
  {
    path: '/arena/:arenaId/strategy/:strategyId',
    name: 'ArenaStrategyDetail',
    component: () => import('@/views/arena/ArenaStrategyDetail.vue'),
    meta: { title: '策略详情', requiresAuth: true }
  },
  // Decision Dashboard
  {
    path: '/decision',
    name: 'DecisionDashboard',
    component: () => import('@/views/decision/DecisionDashboard.vue'),
    meta: { title: '决策看板', icon: 'chart-analytics', requiresAuth: true }
  },
  // Quant model routes
  {
    path: '/quant',
    name: 'Quant',
    component: () => import('@/views/quant/QuantView.vue'),
    meta: { title: '量化选股', icon: 'chart-analytics', requiresAuth: true, requiresTier: 'pro' }
  },
  // Signal Observatory
  {
    path: '/signal',
    name: 'Signal',
    component: () => import('@/views/signal/SignalDashboard.vue'),
    meta: { title: '信号可观测', icon: 'chart-radar', requiresAuth: true, requiresTier: 'pro' }
  },
  // Sentinel System (哨兵选股)
  {
    path: '/sentinel',
    name: 'Sentinel',
    component: () => import('@/views/sentinel/SentinelView.vue'),
    meta: { title: '哨兵选股', icon: 'alarm-clock', requiresAuth: true }
  },
  {
    path: '/quant/screening',
    name: 'QuantScreening',
    component: () => import('@/views/quant/QuantScreeningView.vue'),
    meta: { title: '全市场初筛', requiresAuth: true }
  },
  {
    path: '/quant/pool',
    name: 'QuantPool',
    component: () => import('@/views/quant/QuantPoolView.vue'),
    meta: { title: '核心目标池', requiresAuth: true }
  },
  {
    path: '/quant/rps',
    name: 'QuantRps',
    component: () => import('@/views/quant/QuantRpsView.vue'),
    meta: { title: 'RPS排名', requiresAuth: true }
  },
  {
    path: '/quant/analysis',
    name: 'QuantAnalysis',
    component: () => import('@/views/quant/QuantAnalysisView.vue'),
    meta: { title: '深度分析', requiresAuth: true }
  },
  {
    path: '/quant/signals',
    name: 'QuantSignals',
    component: () => import('@/views/quant/QuantSignalsView.vue'),
    meta: { title: '交易信号', requiresAuth: true }
  },
  {
    path: '/quant/config',
    name: 'QuantConfig',
    component: () => import('@/views/quant/QuantConfigView.vue'),
    meta: { title: '模型配置', requiresAuth: true }
  },
  // User center
  {
    path: '/user',
    name: 'UserCenter',
    component: () => import('@/views/user/UserCenter.vue'),
    meta: { title: '个人中心', icon: 'user', requiresAuth: true }
  },
  // WeChat Bridge
  {
    path: '/wechat-bridge',
    name: 'WechatBridge',
    component: () => import('@/views/wechatBridge/WechatBridgeView.vue'),
    meta: { title: '微信联动', icon: 'wechat', requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/user/llm-config',
    name: 'UserLlmConfig',
    component: () => import('@/views/user/UserCenter.vue'),
    meta: { title: 'LLM配置', requiresAuth: true }
  },
  {
    path: '/user/mcp-usage',
    name: 'UserMcpUsage',
    component: () => import('@/views/user/UserCenter.vue'),
    meta: { title: 'MCP调用统计', requiresAuth: true }
  },
  // Legacy routes redirect
  {
    path: '/report',
    redirect: '/research'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Tier hierarchy: admin > pro > free
const TIER_LEVELS: Record<string, number> = { free: 0, pro: 1, admin: 2 }

function hasRequiredTier(userTier: string, requiredTier: string): boolean {
  return (TIER_LEVELS[userTier] ?? 0) >= (TIER_LEVELS[requiredTier] ?? 0)
}

// Navigation guard for authentication
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()

  // Check if route requires authentication
  const requiresAuth = to.meta.requiresAuth === true
  const requiresAdmin = to.meta.requiresAdmin === true
  const requiresTier = to.meta.requiresTier as string | undefined
  const isPublic = to.meta.public === true || isPublicPath(to.path)

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

    // Check admin permission if required
    if (requiresAdmin && !authStore.user?.is_admin) {
      next('/market')
      return
    }

    // Check subscription tier if required
    if (requiresTier) {
      const userTier = authStore.user?.subscription_tier || 'free'
      if (!hasRequiredTier(userTier, requiresTier)) {
        // Redirect to market with a hint — the user doesn't have the required tier
        next('/market')
        return
      }
    }
  }

  next()
})

export default router

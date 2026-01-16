import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/market'
  },
  {
    path: '/market',
    name: 'Market',
    component: () => import('@/views/market/MarketView.vue'),
    meta: { title: '行情分析', icon: 'chart-line' }
  },
  {
    path: '/toplist',
    name: 'TopList',
    component: () => import('@/views/TopListView.vue'),
    meta: { title: '龙虎榜分析', icon: 'chart-bar' }
  },
  {
    path: '/report',
    name: 'Report',
    component: () => import('@/views/report/ReportView.vue'),
    meta: { title: '财报研读', icon: 'file-excel' }
  },
  {
    path: '/chat',
    name: 'Chat',
    component: () => import('@/views/chat/ChatView.vue'),
    meta: { title: '智能对话', icon: 'chat' }
  },
  {
    path: '/screener',
    name: 'Screener',
    component: () => import('@/views/screener/ScreenerView.vue'),
    meta: { title: '智能选股', icon: 'filter' }
  },
  {
    path: '/portfolio',
    name: 'Portfolio',
    component: () => import('@/views/portfolio/PortfolioView.vue'),
    meta: { title: '持仓管理', icon: 'wallet' }
  },
  {
    path: '/etf',
    name: 'Etf',
    component: () => import('@/views/etf/EtfScreenerView.vue'),
    meta: { title: '智能选ETF', icon: 'control-platform' }
  },
  {
    path: '/strategy',
    name: 'Strategy',
    component: () => import('@/views/StrategyWorkbench.vue'),
    meta: { title: '策略工具台', icon: 'tools' }
  },
  {
    path: '/backtest',
    name: 'Backtest',
    component: () => import('@/views/backtest/BacktestView.vue'),
    meta: { title: '策略回测', icon: 'chart-bubble' }
  },
  {
    path: '/memory',
    name: 'Memory',
    component: () => import('@/views/memory/MemoryView.vue'),
    meta: { title: '用户记忆', icon: 'user' }
  },
  {
    path: '/datamanage',
    name: 'DataManage',
    component: () => import('@/views/datamanage/DataManageView.vue'),
    meta: { title: '数据管理', icon: 'server' }
  },
  {
    path: '/index',
    name: 'Index',
    component: () => import('@/views/index/IndexScreenerView.vue'),
    meta: { title: '指数选股', icon: 'chart-pie' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router

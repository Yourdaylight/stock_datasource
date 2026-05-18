/** Shared category label/theme/icon definitions for the memory module. */
export const CATEGORY_MAP: Record<string, { label: string; theme: string; icon: string }> = {
  risk_preference: { label: '风险偏好', theme: 'warning', icon: 'shield' },
  sector_focus: { label: '板块关注', theme: 'primary', icon: 'chart-pie' },
  stock_opinion: { label: '个股观点', theme: 'success', icon: 'trending-up' },
  trading_style: { label: '交易风格', theme: 'default', icon: 'swap' },
  conclusion: { label: '分析结论', theme: 'primary', icon: 'lightbulb' },
  market_signal: { label: '市场信号', theme: 'danger', icon: 'alarm' },
  capital_flow: { label: '资金流向', theme: 'warning', icon: 'swap' },
}

const FALLBACK = { label: '未知', theme: 'default', icon: 'file' }

export function getCategoryInfo(category: string) {
  return CATEGORY_MAP[category] || FALLBACK
}

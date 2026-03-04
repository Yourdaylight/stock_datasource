import { ref, onUnmounted } from 'vue'

export interface UseRealtimePollingOptions {
  /** 轮询间隔毫秒数，默认 30000 (30s) */
  intervalMs?: number
  /** 是否立即执行一次，默认 true */
  immediate?: boolean
  /** 是否仅在交易时间内轮询，默认 true */
  tradingHoursOnly?: boolean
}

/**
 * 判断当前是否在 A 股交易时间内
 * 上午 09:25 - 11:35，下午 12:55 - 15:05
 */
function isTradingTime(): boolean {
  const now = new Date()
  const day = now.getDay()
  // 周末不交易
  if (day === 0 || day === 6) return false

  const hhmm = now.getHours() * 100 + now.getMinutes()
  return (hhmm >= 925 && hhmm <= 1135) || (hhmm >= 1255 && hhmm <= 1505)
}

/**
 * 可复用的实时数据轮询 composable
 *
 * @param fetchFn 每次轮询执行的异步函数
 * @param options 轮询选项
 */
export function useRealtimePolling(
  fetchFn: () => Promise<void>,
  options: UseRealtimePollingOptions = {}
) {
  const {
    intervalMs = 30000,
    immediate = true,
    tradingHoursOnly = true,
  } = options

  const isPolling = ref(false)
  const lastUpdateTime = ref('')
  let timer: ReturnType<typeof setInterval> | null = null

  const executeFetch = async () => {
    if (tradingHoursOnly && !isTradingTime()) return
    try {
      await fetchFn()
      lastUpdateTime.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
    } catch (e) {
      console.warn('[useRealtimePolling] fetch error:', e)
    }
  }

  const start = () => {
    if (timer) return
    isPolling.value = true
    if (immediate) {
      executeFetch()
    }
    timer = setInterval(executeFetch, intervalMs)
  }

  const stop = () => {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
    isPolling.value = false
  }

  // 自动清理
  onUnmounted(() => {
    stop()
  })

  return { start, stop, isPolling, lastUpdateTime, isTradingTime }
}

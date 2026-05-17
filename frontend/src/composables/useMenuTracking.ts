/**
 * Menu Click Tracking for Progressive Disclosure
 *
 * Tracks which features each user actually uses, stored in localStorage.
 * Data shape: { [path]: { clicks: number, lastClick: timestamp } }
 *
 * Usage:
 *   const { trackClick, getClickCount, getTopFeatures, shouldShowFeature } = useMenuTracking()
 *   trackClick('/screener')
 *   const top = getTopFeatures(5)  // top 5 most-used features
 */

const STORAGE_KEY = 'menu_click_tracking'
const FEATURE_DISCOVERY_KEY = 'feature_discovery'

interface ClickRecord {
  clicks: number
  lastClick: number
  firstClick: number
}

type TrackingData = Record<string, ClickRecord>

function loadTracking(): TrackingData {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

function saveTracking(data: TrackingData): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
  } catch { /* localStorage full, ignore */ }
}

export function useMenuTracking() {
  /**
   * Record a click on a menu path.
   */
  const trackClick = (path: string) => {
    const data = loadTracking()
    const now = Date.now()
    if (data[path]) {
      data[path].clicks++
      data[path].lastClick = now
    } else {
      data[path] = { clicks: 1, lastClick: now, firstClick: now }
    }
    saveTracking(data)
  }

  /**
   * Get click count for a specific path.
   */
  const getClickCount = (path: string): number => {
    const data = loadTracking()
    return data[path]?.clicks || 0
  }

  /**
   * Get all tracking data.
   */
  const getAllTracking = (): TrackingData => {
    return loadTracking()
  }

  /**
   * Get top N most-used features, sorted by click count.
   */
  const getTopFeatures = (n = 5): Array<{ path: string; clicks: number; lastClick: number }> => {
    const data = loadTracking()
    return Object.entries(data)
      .map(([path, record]) => ({ path, ...record }))
      .sort((a, b) => b.clicks - a.clicks)
      .slice(0, n)
  }

  /**
   * Get total distinct features the user has tried.
   */
  const getFeatureCount = (): number => {
    return Object.keys(loadTracking()).length
  }

  /**
   * Progressive disclosure: should we show an advanced feature?
   * Rule: show advanced features only after user has tried >= minFeatures basic features.
   */
  const shouldShowFeature = (featurePath: string, minFeatures = 3): boolean => {
    // Always show if user has already clicked it
    if (getClickCount(featurePath) > 0) return true
    // Show if user has explored enough features
    return getFeatureCount() >= minFeatures
  }

  /**
   * Mark a feature as "discovered" (user has seen the tooltip/highlight).
   */
  const markDiscovered = (featureId: string) => {
    try {
      const raw = localStorage.getItem(FEATURE_DISCOVERY_KEY)
      const discovered: string[] = raw ? JSON.parse(raw) : []
      if (!discovered.includes(featureId)) {
        discovered.push(featureId)
        localStorage.setItem(FEATURE_DISCOVERY_KEY, JSON.stringify(discovered))
      }
    } catch { /* ignore */ }
  }

  /**
   * Check if a feature has been discovered.
   */
  const isDiscovered = (featureId: string): boolean => {
    try {
      const raw = localStorage.getItem(FEATURE_DISCOVERY_KEY)
      const discovered: string[] = raw ? JSON.parse(raw) : []
      return discovered.includes(featureId)
    } catch {
      return false
    }
  }

  /**
   * Get user engagement level based on feature usage patterns.
   * Returns: 'new' | 'exploring' | 'active' | 'power'
   */
  const getEngagementLevel = (): 'new' | 'exploring' | 'active' | 'power' => {
    const data = loadTracking()
    const features = Object.keys(data).length
    const totalClicks = Object.values(data).reduce((sum, r) => sum + r.clicks, 0)

    if (features === 0) return 'new'
    if (features <= 2 && totalClicks < 10) return 'exploring'
    if (features <= 5 || totalClicks < 30) return 'active'
    return 'power'
  }

  return {
    trackClick,
    getClickCount,
    getAllTracking,
    getTopFeatures,
    getFeatureCount,
    shouldShowFeature,
    markDiscovered,
    isDiscovered,
    getEngagementLevel,
  }
}

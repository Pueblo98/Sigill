import type { Vertical } from './market'

export type FreshnessStatus = 'fresh' | 'stale' | 'critical' | 'down'
export type SourceCategory = 'sports' | 'polling' | 'economic' | 'weather' | 'crypto' | 'social' | 'exchange'

export interface DataSource {
  id: string
  name: string
  category: SourceCategory
  vertical: Vertical
  status: FreshnessStatus
  lastUpdated: string
  updateFrequency: number    // seconds
  maxAcceptableStaleness: number  // seconds
  latencyMs: number
  errorCount24h: number
  successRate7d: number
  endpoint: string
  description: string
}

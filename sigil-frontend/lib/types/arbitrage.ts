import type { Vertical, Platform } from './market'

export type ArbStatus = 'live' | 'stale' | 'executed' | 'expired'

export interface ArbOpportunity {
  id: string
  marketTitle: string
  vertical: Vertical
  platformA: Platform
  platformAPrice: number
  platformB: Platform
  platformBPrice: number
  grossArb: number
  feesEstimate: number
  netArb: number
  matchConfidence: number
  resolutionDate: string
  volumeA: number
  volumeB: number
  maxExecutableUsd: number
  detectedAt: string
  status: ArbStatus
}

import type { Vertical, Platform } from './market'

export type SignalStatus = 'pending' | 'executed' | 'watching' | 'dismissed' | 'expired'

export interface Signal {
  id: string
  marketId: string
  marketTitle: string
  vertical: Vertical
  platform: Platform
  modelId: string
  modelName: string
  modelProb: number
  marketProb: number
  edge: number
  weightedEdge: number
  confidence: number
  kellyPct: number
  recommendedSizeUsd: number
  status: SignalStatus
  generatedAt: string
  expiresAt: string
  isHighEdge: boolean
  side: 'yes' | 'no'
}

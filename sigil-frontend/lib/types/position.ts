import type { Vertical, Platform } from './market'

export type PositionStatus = 'open' | 'settled' | 'cancelled'

export interface Position {
  id: string
  marketId: string
  marketTitle: string
  vertical: Vertical
  platform: Platform
  side: 'yes' | 'no'
  contracts: number
  avgEntry: number
  currentPrice: number
  unrealizedPnl: number
  unrealizedPnlPct: number
  modelCurrentProb: number
  edgeRemaining: number
  totalCost: number
  currentValue: number
  resolutionDate: string
  timeToExpiry: number    // seconds
  status: PositionStatus
  openedAt: string
  signalId: string
}

export interface ExposureSummary {
  byVertical: Record<string, number>
  byPlatform: Record<string, number>
  totalDeployed: number
  totalBankroll: number
  largestPosition: number
  kellyUtilizationPct: number
}

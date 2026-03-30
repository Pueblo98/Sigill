import type { Vertical, Platform } from './market'

export type OrderStatus = 'created' | 'submitted' | 'pending' | 'filled' | 'partial' | 'cancelled' | 'rejected' | 'failed'
export type ExecutionMode = 'passive' | 'aggressive' | 'scaled'

export interface Order {
  id: string
  externalId: string
  platform: Platform
  marketId: string
  marketTitle: string
  vertical: Vertical
  side: 'buy' | 'sell'
  outcome: 'yes' | 'no'
  type: 'limit' | 'market'
  price: number
  quantity: number
  filledQuantity: number
  avgFillPrice: number
  fees: number
  status: OrderStatus
  signalId: string
  modelId: string
  modelProb: number
  edgeAtEntry: number
  executionMode: ExecutionMode
  pnl?: number
  pnlPct?: number
  createdAt: string
  filledAt?: string
  settledAt?: string
}

export type KalshiVertical = 'sports' | 'politics' | 'economics' | 'weather' | 'crypto'

export interface KalshiMarket {
  ticker: string
  title: string
  vertical: KalshiVertical
  category: string
  subCategory: string
  platform: 'kalshi'
  marketProbability: number // exchange-implied probability
  modelProbability: number  // Sigil model probability
  yesBid: number            // cents as decimal (0-1 scale)
  yesAsk: number
  yesMid: number
  openInterest: number
  volume24h: number
  liquidity: 'thin' | 'medium' | 'thick'
  resolutionDate: string
  confidence: number
  kellySize: number
  watchlisted: boolean
  eventGroup: string
  lastUpdated: string
}

export interface KalshiPortfolioSnapshot {
  platform: 'kalshi'
  balance: {
    availableUsd: number
    totalUsd: number
    maintenanceUsd: number
  }
  limits: {
    perEventUsd: number
    usedUsd: number
  }
  pnl: {
    realizedUsd: number
    unrealizedUsd: number
  }
  lastUpdated: string
}

export interface KalshiPosition {
  ticker: string
  title: string
  side: 'yes' | 'no'
  contracts: number
  avgPrice: number // cents represented as decimal (0-1 scale)
  markPrice: number
  pnlUsd: number
  marketProbability: number
  modelProbability: number
  resolutionDate: string
  updatedAt: string
}

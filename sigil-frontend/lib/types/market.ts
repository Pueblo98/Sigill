export type Vertical = 'sports' | 'politics' | 'economics' | 'weather' | 'crypto' | 'entertainment'
export type Platform = 'kalshi' | 'polymarket' | 'predictit'
export type LiquidityProfile = 'thin' | 'medium' | 'thick'

export interface PricePoint {
  timestamp: string
  marketProb: number
  modelProb: number
  volume?: number
}

export interface OrderBookLevel {
  price: number
  quantity: number
  totalUsd: number
}

export interface OrderBook {
  marketId: string
  timestamp: string
  bids: OrderBookLevel[]
  asks: OrderBookLevel[]
  bidDepthUsd: number
  askDepthUsd: number
  spread: number
}

export interface Market {
  id: string
  title: string
  vertical: Vertical
  subCategory: string
  platform: Platform
  externalId: string
  marketProb: number
  modelProb: number
  edge: number           // (modelProb - marketProb) × 100 in cents
  confidence: number
  kellySize: number      // recommended % of bankroll
  weightedEdge: number   // edge × confidence
  volume24h: number
  openInterest: number
  liquidityProfile: LiquidityProfile
  resolutionDate: string
  resolutionSource: string
  priceHistory: PricePoint[]
  isWatchlisted: boolean
  lastUpdated: string
}

export interface MarketFilters {
  verticals: Vertical[]
  platforms: Platform[]
  minEdge: number
  maxEdge: number
  minVolume: number
  liquidityProfiles: LiquidityProfile[]
  searchQuery: string
  showWatchlistOnly: boolean
}

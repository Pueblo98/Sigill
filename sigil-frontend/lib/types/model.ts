import type { Vertical } from './market'
import type { EquityPoint } from './portfolio'

export type ModelStatus = 'active' | 'shadow' | 'degraded' | 'deactivated'
export type ModelRole = 'champion' | 'challenger'

export interface FeatureImportanceItem {
  feature: string
  importance: number
  direction: 'positive' | 'negative' | 'neutral'
}

export interface CalibrationPoint {
  predictedBin: number
  actualFrequency: number
  count: number
}

export interface Model {
  id: string
  name: string
  version: string
  vertical: Vertical
  status: ModelStatus
  role: ModelRole
  brierScore30d: number
  brierScore90d: number
  logLoss: number
  calibrationError: number
  roi30d: number
  winRate: number
  tradeCount: number
  lastRetrained: string
  nextRetrainScheduled: string
  backtestR2: number
  liveVsBacktestRatio: number
  featureImportance: FeatureImportanceItem[]
  calibrationPoints: CalibrationPoint[]
  brierHistory: { date: string; score: number }[]
}

export interface BacktestConfig {
  modelId: string
  startDate: string
  endDate: string
  initialCapital: number
  kellyFraction: number
  minEdgeCents: number
}

export interface BacktestMetrics {
  roi: number
  sharpe: number
  maxDrawdown: number
  winRate: number
  avgEdgeCaptured: number
  brierScore: number
  tradeCount: number
  netPnl: number
  calmarRatio: number
}

export interface BacktestTrade {
  date: string
  market: string
  side: string
  entry: number
  exit: number
  pnl: number
  edge: number
}

export interface BacktestResult {
  id: string
  modelId: string
  modelName: string
  runAt: string
  config: BacktestConfig
  metrics: BacktestMetrics
  equityCurve: EquityPoint[]
  trades: BacktestTrade[]
  status: 'running' | 'complete' | 'failed'
  progress: number
}

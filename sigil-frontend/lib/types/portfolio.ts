export type CircuitBreakerStatus = 'clear' | 'warning' | 'halted' | 'shutdown'

export interface Portfolio {
  totalValue: number
  totalDeployed: number
  totalDeployable: number
  unrealizedPnl: number
  realizedPnlToday: number
  realizedPnlAllTime: number
  roi: number
  roiMtd: number
  drawdownFromPeak: number
  peakValue: number
  circuitBreakerStatus: CircuitBreakerStatus
  lastUpdated: string
}

export interface DrawdownPoint {
  timestamp: string
  value: number
  drawdownPct: number
}

export interface EquityPoint {
  date: string
  value: number
  drawdown: number
}

export type AlertSeverity = 'critical' | 'warning' | 'info'
export type AlertChannel = 'in_app' | 'telegram'
export type AlertStatus = 'active' | 'acknowledged' | 'resolved'

export interface Alert {
  id: string
  severity: AlertSeverity
  title: string
  message: string
  source: string
  status: AlertStatus
  createdAt: string
  acknowledgedAt?: string
}

export type AlertConditionType =
  | 'drawdown_threshold'
  | 'model_degradation'
  | 'pipeline_stale'
  | 'high_edge_signal'
  | 'position_expiry'
  | 'circuit_breaker'
  | 'pnl_threshold'

export interface AlertRule {
  id: string
  name: string
  condition: AlertConditionType
  threshold: number
  channel: AlertChannel
  enabled: boolean
  severity: AlertSeverity
  description: string
}

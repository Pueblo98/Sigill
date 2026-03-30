import type { Vertical, Platform } from '../types/market'

export const VERTICAL_META: Record<Vertical, {
  label: string
  color: string
  bgColor: string
  icon: string
}> = {
  sports: {
    label: 'SPORTS',
    color: '#60a5fa',
    bgColor: 'rgba(96, 165, 250, 0.1)',
    icon: 'sports_score',
  },
  politics: {
    label: 'POLITICS',
    color: '#f87171',
    bgColor: 'rgba(248, 113, 113, 0.1)',
    icon: 'how_to_vote',
  },
  economics: {
    label: 'ECON',
    color: '#34d399',
    bgColor: 'rgba(52, 211, 153, 0.1)',
    icon: 'bar_chart',
  },
  weather: {
    label: 'WEATHER',
    color: '#fbbf24',
    bgColor: 'rgba(251, 191, 36, 0.1)',
    icon: 'wb_sunny',
  },
  crypto: {
    label: 'CRYPTO',
    color: '#c084fc',
    bgColor: 'rgba(192, 132, 252, 0.1)',
    icon: 'currency_bitcoin',
  },
  entertainment: {
    label: 'ENTMT',
    color: '#f472b6',
    bgColor: 'rgba(244, 114, 182, 0.1)',
    icon: 'movie',
  },
}

export const PLATFORM_META: Record<Platform, {
  label: string
  color: string
  shortLabel: string
}> = {
  kalshi: {
    label: 'KALSHI',
    shortLabel: 'KAL',
    color: '#34d399',
  },
  polymarket: {
    label: 'POLYMARKET',
    shortLabel: 'POLY',
    color: '#60a5fa',
  },
  predictit: {
    label: 'PREDICTIT',
    shortLabel: 'PI',
    color: '#f59e0b',
  },
}

export function edgeColor(edge: number): string {
  if (edge >= 10) return '#10b981'
  if (edge >= 5) return '#34d399'
  if (edge >= 2) return '#fbbf24'
  if (edge <= -5) return '#f43f5e'
  return '#958da1'
}

export function edgeLabel(edge: number): string {
  if (edge >= 10) return 'STRONG'
  if (edge >= 5) return 'SOLID'
  if (edge >= 2) return 'WEAK'
  if (edge <= -5) return 'FADE'
  return 'NEUTRAL'
}

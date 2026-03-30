import { NextResponse } from 'next/server'
import { MOCK_KALSHI_PORTFOLIO } from '@/lib/mock/kalshi'

export function GET() {
  return NextResponse.json({
    portfolio: MOCK_KALSHI_PORTFOLIO,
    meta: {
      source: 'kalshi',
      lastUpdated: MOCK_KALSHI_PORTFOLIO.lastUpdated,
    },
  })
}

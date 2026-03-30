import { NextResponse } from 'next/server'
import { MOCK_KALSHI_MARKETS } from '@/lib/mock/kalshi'

export function GET() {
  return NextResponse.json({
    markets: MOCK_KALSHI_MARKETS,
    meta: {
      source: 'kalshi',
      count: MOCK_KALSHI_MARKETS.length,
      lastUpdated: new Date().toISOString(),
    },
  })
}

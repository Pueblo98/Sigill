import { NextResponse } from 'next/server'
import { MOCK_KALSHI_POSITIONS } from '@/lib/mock/kalshi'

export function GET() {
  return NextResponse.json({
    positions: MOCK_KALSHI_POSITIONS,
    meta: {
      source: 'kalshi',
      count: MOCK_KALSHI_POSITIONS.length,
      lastUpdated: new Date().toISOString(),
    },
  })
}

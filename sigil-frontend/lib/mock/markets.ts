import type { Market, PricePoint } from '../types/market'

function genPriceHistory(baseProb: number, modelProb: number, days = 30): PricePoint[] {
  const points: PricePoint[] = []
  const now = Date.now()
  let current = baseProb * 0.6 + 0.1

  for (let i = days; i >= 0; i--) {
    const t = now - i * 86400_000
    current = Math.max(0.02, Math.min(0.98, current + (Math.random() - 0.48) * 0.04))
    points.push({
      timestamp: new Date(t).toISOString(),
      marketProb: parseFloat(current.toFixed(3)),
      modelProb: parseFloat((modelProb + (Math.random() - 0.5) * 0.05).toFixed(3)),
      volume: Math.floor(Math.random() * 50000 + 5000),
    })
  }
  return points
}

function future(days: number): string {
  return new Date(Date.now() + days * 86400_000).toISOString()
}

export const MOCK_MARKETS: Market[] = [
  // ── SPORTS ──────────────────────────────────────────────────────────────────
  {
    id: 'mkt-001', title: 'Chiefs win Super Bowl LX', vertical: 'sports', subCategory: 'NFL',
    platform: 'kalshi', externalId: 'NFL-SB60-KC', marketProb: 0.31, modelProb: 0.42,
    edge: 11.0, confidence: 0.78, kellySize: 0.031, weightedEdge: 8.58,
    volume24h: 124500, openInterest: 480000, liquidityProfile: 'thick',
    resolutionDate: future(210), resolutionSource: 'NFL Official',
    priceHistory: genPriceHistory(0.31, 0.42), isWatchlisted: true, lastUpdated: new Date().toISOString(),
  },
  {
    id: 'mkt-002', title: 'Lakers make NBA playoffs 2025', vertical: 'sports', subCategory: 'NBA',
    platform: 'kalshi', externalId: 'NBA-LAL-PLAYOFFS', marketProb: 0.62, modelProb: 0.74,
    edge: 12.0, confidence: 0.71, kellySize: 0.028, weightedEdge: 8.52,
    volume24h: 87300, openInterest: 210000, liquidityProfile: 'medium',
    resolutionDate: future(45), resolutionSource: 'NBA Official',
    priceHistory: genPriceHistory(0.62, 0.74), isWatchlisted: false, lastUpdated: new Date().toISOString(),
  },
  {
    id: 'mkt-003', title: 'Djokovic wins Wimbledon 2025', vertical: 'sports', subCategory: 'Tennis',
    platform: 'polymarket', externalId: 'WIMB25-NJK', marketProb: 0.28, modelProb: 0.22,
    edge: -6.0, confidence: 0.65, kellySize: 0.0, weightedEdge: -3.9,
    volume24h: 42100, openInterest: 95000, liquidityProfile: 'medium',
    resolutionDate: future(120), resolutionSource: 'ATP',
    priceHistory: genPriceHistory(0.28, 0.22), isWatchlisted: false, lastUpdated: new Date().toISOString(),
  },
  {
    id: 'mkt-004', title: 'Bengals cover spread vs. Ravens', vertical: 'sports', subCategory: 'NFL',
    platform: 'kalshi', externalId: 'NFL-CIN-BAL-SPREAD', marketProb: 0.48, modelProb: 0.56,
    edge: 8.0, confidence: 0.62, kellySize: 0.018, weightedEdge: 4.96,
    volume24h: 61200, openInterest: 145000, liquidityProfile: 'medium',
    resolutionDate: future(3), resolutionSource: 'NFL Official',
    priceHistory: genPriceHistory(0.48, 0.56), isWatchlisted: true, lastUpdated: new Date().toISOString(),
  },
  {
    id: 'mkt-005', title: 'Tiger Woods top-20 finish Masters 2025', vertical: 'sports', subCategory: 'Golf',
    platform: 'kalshi', externalId: 'GOLF-TW-MASTERS25', marketProb: 0.18, modelProb: 0.11,
    edge: -7.0, confidence: 0.55, kellySize: 0.0, weightedEdge: -3.85,
    volume24h: 29800, openInterest: 62000, liquidityProfile: 'thin',
    resolutionDate: future(15), resolutionSource: 'PGA Tour',
    priceHistory: genPriceHistory(0.18, 0.11), isWatchlisted: false, lastUpdated: new Date().toISOString(),
  },

  // ── POLITICS ─────────────────────────────────────────────────────────────
  {
    id: 'mkt-010', title: 'Democrats win 2026 House majority', vertical: 'politics', subCategory: 'US Congress',
    platform: 'kalshi', externalId: 'US-HOUSE-2026-DEM', marketProb: 0.38, modelProb: 0.47,
    edge: 9.0, confidence: 0.72, kellySize: 0.022, weightedEdge: 6.48,
    volume24h: 215000, openInterest: 890000, liquidityProfile: 'thick',
    resolutionDate: future(580), resolutionSource: 'AP Elections',
    priceHistory: genPriceHistory(0.38, 0.47), isWatchlisted: true, lastUpdated: new Date().toISOString(),
  },
  {
    id: 'mkt-011', title: 'Federal Reserve cuts rates June 2025', vertical: 'politics', subCategory: 'Federal Policy',
    platform: 'kalshi', externalId: 'FED-RATE-CUT-JUN25', marketProb: 0.54, modelProb: 0.63,
    edge: 9.0, confidence: 0.80, kellySize: 0.026, weightedEdge: 7.2,
    volume24h: 342000, openInterest: 1200000, liquidityProfile: 'thick',
    resolutionDate: future(75), resolutionSource: 'Fed Press Release',
    priceHistory: genPriceHistory(0.54, 0.63), isWatchlisted: true, lastUpdated: new Date().toISOString(),
  },
  {
    id: 'mkt-012', title: 'UK PM resigns in 2025', vertical: 'politics', subCategory: 'UK',
    platform: 'polymarket', externalId: 'UK-PM-RESIGN-25', marketProb: 0.21, modelProb: 0.19,
    edge: -2.0, confidence: 0.40, kellySize: 0.0, weightedEdge: -0.8,
    volume24h: 18400, openInterest: 47000, liquidityProfile: 'thin',
    resolutionDate: future(270), resolutionSource: 'BBC',
    priceHistory: genPriceHistory(0.21, 0.19), isWatchlisted: false, lastUpdated: new Date().toISOString(),
  },
  {
    id: 'mkt-013', title: 'Trump approval above 45% end of Q2', vertical: 'politics', subCategory: 'US Federal',
    platform: 'kalshi', externalId: 'TRUMP-APPR-Q2-45', marketProb: 0.34, modelProb: 0.41,
    edge: 7.0, confidence: 0.58, kellySize: 0.015, weightedEdge: 4.06,
    volume24h: 98700, openInterest: 310000, liquidityProfile: 'medium',
    resolutionDate: future(95), resolutionSource: '538/RCP Average',
    priceHistory: genPriceHistory(0.34, 0.41), isWatchlisted: false, lastUpdated: new Date().toISOString(),
  },
  {
    id: 'mkt-014', title: 'Georgia Senate seat flips in 2026', vertical: 'politics', subCategory: 'US Senate',
    platform: 'kalshi', externalId: 'GA-SEN-2026-FLIP', marketProb: 0.29, modelProb: 0.37,
    edge: 8.0, confidence: 0.55, kellySize: 0.016, weightedEdge: 4.4,
    volume24h: 67400, openInterest: 189000, liquidityProfile: 'medium',
    resolutionDate: future(590), resolutionSource: 'AP Elections',
    priceHistory: genPriceHistory(0.29, 0.37), isWatchlisted: false, lastUpdated: new Date().toISOString(),
  },

  // ── ECONOMICS ────────────────────────────────────────────────────────────
  {
    id: 'mkt-020', title: 'US CPI above 3.5% in April 2025', vertical: 'economics', subCategory: 'Inflation',
    platform: 'kalshi', externalId: 'CPI-APR25-35', marketProb: 0.26, modelProb: 0.35,
    edge: 9.0, confidence: 0.76, kellySize: 0.023, weightedEdge: 6.84,
    volume24h: 189000, openInterest: 560000, liquidityProfile: 'thick',
    resolutionDate: future(45), resolutionSource: 'BLS',
    priceHistory: genPriceHistory(0.26, 0.35), isWatchlisted: true, lastUpdated: new Date().toISOString(),
  },
  {
    id: 'mkt-021', title: 'NFP exceeds 200k in March 2025', vertical: 'economics', subCategory: 'Employment',
    platform: 'kalshi', externalId: 'NFP-MAR25-200K', marketProb: 0.41, modelProb: 0.52,
    edge: 11.0, confidence: 0.73, kellySize: 0.028, weightedEdge: 8.03,
    volume24h: 154000, openInterest: 420000, liquidityProfile: 'thick',
    resolutionDate: future(12), resolutionSource: 'BLS',
    priceHistory: genPriceHistory(0.41, 0.52), isWatchlisted: true, lastUpdated: new Date().toISOString(),
  },
  {
    id: 'mkt-022', title: 'US GDP growth above 2% Q1 2025', vertical: 'economics', subCategory: 'GDP',
    platform: 'kalshi', externalId: 'GDP-Q125-2PCT', marketProb: 0.58, modelProb: 0.64,
    edge: 6.0, confidence: 0.68, kellySize: 0.014, weightedEdge: 4.08,
    volume24h: 98200, openInterest: 280000, liquidityProfile: 'medium',
    resolutionDate: future(60), resolutionSource: 'BEA',
    priceHistory: genPriceHistory(0.58, 0.64), isWatchlisted: false, lastUpdated: new Date().toISOString(),
  },
  {
    id: 'mkt-023', title: 'ECB cuts rates in March meeting', vertical: 'economics', subCategory: 'Central Banks',
    platform: 'polymarket', externalId: 'ECB-RATE-MAR25', marketProb: 0.72, modelProb: 0.68,
    edge: -4.0, confidence: 0.61, kellySize: 0.0, weightedEdge: -2.44,
    volume24h: 76500, openInterest: 198000, liquidityProfile: 'medium',
    resolutionDate: future(8), resolutionSource: 'ECB Press Release',
    priceHistory: genPriceHistory(0.72, 0.68), isWatchlisted: false, lastUpdated: new Date().toISOString(),
  },

  // ── WEATHER ──────────────────────────────────────────────────────────────
  {
    id: 'mkt-030', title: 'Atlantic hurricane season above avg 2025', vertical: 'weather', subCategory: 'Hurricanes',
    platform: 'kalshi', externalId: 'HURR-2025-ABOVE', marketProb: 0.55, modelProb: 0.67,
    edge: 12.0, confidence: 0.71, kellySize: 0.029, weightedEdge: 8.52,
    volume24h: 45600, openInterest: 98000, liquidityProfile: 'medium',
    resolutionDate: future(240), resolutionSource: 'NHC',
    priceHistory: genPriceHistory(0.55, 0.67), isWatchlisted: false, lastUpdated: new Date().toISOString(),
  },
  {
    id: 'mkt-031', title: 'NYC temperature record broken in July', vertical: 'weather', subCategory: 'Temperature',
    platform: 'kalshi', externalId: 'NYC-TEMP-REC-JUL25', marketProb: 0.14, modelProb: 0.09,
    edge: -5.0, confidence: 0.82, kellySize: 0.0, weightedEdge: -4.1,
    volume24h: 12800, openInterest: 34000, liquidityProfile: 'thin',
    resolutionDate: future(120), resolutionSource: 'NOAA',
    priceHistory: genPriceHistory(0.14, 0.09), isWatchlisted: false, lastUpdated: new Date().toISOString(),
  },
  {
    id: 'mkt-032', title: 'February 2025 global temp hottest on record', vertical: 'weather', subCategory: 'Climate',
    platform: 'kalshi', externalId: 'GLOBAL-TEMP-FEB25', marketProb: 0.44, modelProb: 0.53,
    edge: 9.0, confidence: 0.67, kellySize: 0.021, weightedEdge: 6.03,
    volume24h: 31200, openInterest: 71000, liquidityProfile: 'thin',
    resolutionDate: future(30), resolutionSource: 'NOAA/NASA',
    priceHistory: genPriceHistory(0.44, 0.53), isWatchlisted: false, lastUpdated: new Date().toISOString(),
  },

  // ── CRYPTO ───────────────────────────────────────────────────────────────
  {
    id: 'mkt-040', title: 'Bitcoin above $120k by end of June', vertical: 'crypto', subCategory: 'BTC',
    platform: 'polymarket', externalId: 'BTC-120K-JUN25', marketProb: 0.39, modelProb: 0.51,
    edge: 12.0, confidence: 0.62, kellySize: 0.026, weightedEdge: 7.44,
    volume24h: 287000, openInterest: 760000, liquidityProfile: 'thick',
    resolutionDate: future(95), resolutionSource: 'Coinbase price feed',
    priceHistory: genPriceHistory(0.39, 0.51), isWatchlisted: true, lastUpdated: new Date().toISOString(),
  },
  {
    id: 'mkt-041', title: 'ETH above $5k by end of Q2', vertical: 'crypto', subCategory: 'ETH',
    platform: 'polymarket', externalId: 'ETH-5K-Q225', marketProb: 0.32, modelProb: 0.38,
    edge: 6.0, confidence: 0.58, kellySize: 0.013, weightedEdge: 3.48,
    volume24h: 198000, openInterest: 530000, liquidityProfile: 'thick',
    resolutionDate: future(95), resolutionSource: 'Coinbase price feed',
    priceHistory: genPriceHistory(0.32, 0.38), isWatchlisted: false, lastUpdated: new Date().toISOString(),
  },
  {
    id: 'mkt-042', title: 'SEC approves spot ETH ETF options', vertical: 'crypto', subCategory: 'Regulatory',
    platform: 'kalshi', externalId: 'SEC-ETH-ETF-OPT', marketProb: 0.61, modelProb: 0.70,
    edge: 9.0, confidence: 0.66, kellySize: 0.021, weightedEdge: 5.94,
    volume24h: 145000, openInterest: 390000, liquidityProfile: 'medium',
    resolutionDate: future(180), resolutionSource: 'SEC Filing',
    priceHistory: genPriceHistory(0.61, 0.70), isWatchlisted: false, lastUpdated: new Date().toISOString(),
  },
  {
    id: 'mkt-043', title: 'Solana hits $500 in 2025', vertical: 'crypto', subCategory: 'Altcoins',
    platform: 'polymarket', externalId: 'SOL-500-2025', marketProb: 0.23, modelProb: 0.18,
    edge: -5.0, confidence: 0.51, kellySize: 0.0, weightedEdge: -2.55,
    volume24h: 89000, openInterest: 231000, liquidityProfile: 'medium',
    resolutionDate: future(280), resolutionSource: 'Binance/Coinbase',
    priceHistory: genPriceHistory(0.23, 0.18), isWatchlisted: false, lastUpdated: new Date().toISOString(),
  },

  // ── ENTERTAINMENT ─────────────────────────────────────────────────────────
  {
    id: 'mkt-050', title: 'Wicked wins Best Picture Oscar 2025', vertical: 'entertainment', subCategory: 'Oscars',
    platform: 'kalshi', externalId: 'OSCAR25-BP-WICKED', marketProb: 0.24, modelProb: 0.31,
    edge: 7.0, confidence: 0.69, kellySize: 0.017, weightedEdge: 4.83,
    volume24h: 62400, openInterest: 154000, liquidityProfile: 'medium',
    resolutionDate: future(8), resolutionSource: 'Academy Awards',
    priceHistory: genPriceHistory(0.24, 0.31), isWatchlisted: false, lastUpdated: new Date().toISOString(),
  },
  {
    id: 'mkt-051', title: 'Taylor Swift wins Album of Year Grammy 2025', vertical: 'entertainment', subCategory: 'Grammys',
    platform: 'kalshi', externalId: 'GRAMMY25-AOTY-TS', marketProb: 0.47, modelProb: 0.55,
    edge: 8.0, confidence: 0.60, kellySize: 0.018, weightedEdge: 4.8,
    volume24h: 41800, openInterest: 87000, liquidityProfile: 'thin',
    resolutionDate: future(18), resolutionSource: 'Recording Academy',
    priceHistory: genPriceHistory(0.47, 0.55), isWatchlisted: false, lastUpdated: new Date().toISOString(),
  },
  {
    id: 'mkt-052', title: 'Minecraft movie grosses $500M globally', vertical: 'entertainment', subCategory: 'Box Office',
    platform: 'polymarket', externalId: 'MINECRAFT-MOVIE-500M', marketProb: 0.38, modelProb: 0.45,
    edge: 7.0, confidence: 0.57, kellySize: 0.015, weightedEdge: 3.99,
    volume24h: 28900, openInterest: 64000, liquidityProfile: 'thin',
    resolutionDate: future(60), resolutionSource: 'Box Office Mojo',
    priceHistory: genPriceHistory(0.38, 0.45), isWatchlisted: false, lastUpdated: new Date().toISOString(),
  },

  // ── MORE MARKETS (to reach 25+) ───────────────────────────────────────────
  {
    id: 'mkt-060', title: 'NFL Draft: QB picked #1 overall', vertical: 'sports', subCategory: 'NFL Draft',
    platform: 'kalshi', externalId: 'NFL-DRAFT25-QB1', marketProb: 0.78, modelProb: 0.85,
    edge: 7.0, confidence: 0.81, kellySize: 0.019, weightedEdge: 5.67,
    volume24h: 89300, openInterest: 213000, liquidityProfile: 'medium',
    resolutionDate: future(25), resolutionSource: 'NFL',
    priceHistory: genPriceHistory(0.78, 0.85), isWatchlisted: false, lastUpdated: new Date().toISOString(),
  },
  {
    id: 'mkt-061', title: 'US debt ceiling deal before August', vertical: 'politics', subCategory: 'US Federal',
    platform: 'kalshi', externalId: 'US-DEBT-CEIL-AUG25', marketProb: 0.71, modelProb: 0.79,
    edge: 8.0, confidence: 0.65, kellySize: 0.018, weightedEdge: 5.2,
    volume24h: 134000, openInterest: 380000, liquidityProfile: 'medium',
    resolutionDate: future(150), resolutionSource: 'Treasury.gov',
    priceHistory: genPriceHistory(0.71, 0.79), isWatchlisted: false, lastUpdated: new Date().toISOString(),
  },
  {
    id: 'mkt-062', title: 'PCE inflation below 2.5% in March', vertical: 'economics', subCategory: 'Inflation',
    platform: 'kalshi', externalId: 'PCE-MAR25-25', marketProb: 0.33, modelProb: 0.41,
    edge: 8.0, confidence: 0.74, kellySize: 0.021, weightedEdge: 5.92,
    volume24h: 112000, openInterest: 295000, liquidityProfile: 'medium',
    resolutionDate: future(28), resolutionSource: 'BEA',
    priceHistory: genPriceHistory(0.33, 0.41), isWatchlisted: true, lastUpdated: new Date().toISOString(),
  },
  {
    id: 'mkt-063', title: 'XRP ETF approved in 2025', vertical: 'crypto', subCategory: 'Regulatory',
    platform: 'polymarket', externalId: 'XRP-ETF-2025', marketProb: 0.56, modelProb: 0.63,
    edge: 7.0, confidence: 0.59, kellySize: 0.015, weightedEdge: 4.13,
    volume24h: 178000, openInterest: 445000, liquidityProfile: 'thick',
    resolutionDate: future(200), resolutionSource: 'SEC',
    priceHistory: genPriceHistory(0.56, 0.63), isWatchlisted: false, lastUpdated: new Date().toISOString(),
  },
  {
    id: 'mkt-064', title: 'Champions League final: Spanish club wins', vertical: 'sports', subCategory: 'Soccer',
    platform: 'polymarket', externalId: 'UCL25-SPAIN', marketProb: 0.44, modelProb: 0.53,
    edge: 9.0, confidence: 0.61, kellySize: 0.02, weightedEdge: 5.49,
    volume24h: 94600, openInterest: 247000, liquidityProfile: 'medium',
    resolutionDate: future(65), resolutionSource: 'UEFA',
    priceHistory: genPriceHistory(0.44, 0.53), isWatchlisted: false, lastUpdated: new Date().toISOString(),
  },
]

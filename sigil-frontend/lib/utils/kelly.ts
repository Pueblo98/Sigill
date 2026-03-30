/**
 * Kelly Criterion for binary markets (prediction markets).
 * Returns the fraction of bankroll to bet.
 *
 * @param modelProb  - Model's estimated probability of YES (0–1)
 * @param marketProb - Market's implied probability / price (0–1)
 * @param kellyFraction - Scaling factor (0.25 = quarter Kelly)
 */
export function kellySize(
  modelProb: number,
  marketProb: number,
  kellyFraction = 0.25
): number {
  if (marketProb <= 0 || marketProb >= 1) return 0
  if (modelProb <= 0 || modelProb >= 1) return 0

  // Full Kelly: f* = (p - q) / (b - a) simplified for binary
  // For YES bet: edge = modelProb - marketProb
  // b = (1 - marketProb) / marketProb (odds in decimal terms on YES)
  const edge = modelProb - marketProb
  if (edge <= 0) return 0

  const b = (1 - marketProb) / marketProb
  const fullKelly = (edge * (b + 1) - 1) / b

  return Math.max(0, fullKelly * kellyFraction)
}

/**
 * Recommended USD size given bankroll and kelly fraction
 */
export function kellySizeUsd(
  bankroll: number,
  modelProb: number,
  marketProb: number,
  kellyFraction = 0.25,
  maxPositionPct = 0.05
): number {
  const k = kellySize(modelProb, marketProb, kellyFraction)
  const capped = Math.min(k, maxPositionPct)
  return bankroll * capped
}

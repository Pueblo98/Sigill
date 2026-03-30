export function formatCents(cents: number): string {
  const sign = cents >= 0 ? '+' : ''
  return `${sign}${cents.toFixed(1)}¢`
}

export function formatPct(pct: number, decimals = 1): string {
  const sign = pct >= 0 ? '+' : ''
  return `${sign}${pct.toFixed(decimals)}%`
}

export function formatProb(prob: number): string {
  return `${(prob * 100).toFixed(1)}%`
}

export function formatUsd(amount: number, compact = false): string {
  if (compact && Math.abs(amount) >= 1000) {
    return `$${(amount / 1000).toFixed(1)}k`
  }
  const sign = amount < 0 ? '-' : ''
  return `${sign}$${Math.abs(amount).toFixed(2)}`
}

export function formatUsdCompact(amount: number): string {
  if (Math.abs(amount) >= 1_000_000) return `$${(amount / 1_000_000).toFixed(2)}M`
  if (Math.abs(amount) >= 1_000) return `$${(amount / 1_000).toFixed(1)}k`
  return `$${amount.toFixed(0)}`
}

export function formatAge(isoTimestamp: string): string {
  const now = Date.now()
  const then = new Date(isoTimestamp).getTime()
  const diffSec = Math.floor((now - then) / 1000)

  if (diffSec < 60) return `${diffSec}s ago`
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`
  return `${Math.floor(diffSec / 86400)}d ago`
}

export function formatTimestamp(isoTimestamp: string): string {
  return new Date(isoTimestamp).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

export function formatDate(isoTimestamp: string): string {
  return new Date(isoTimestamp).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

export function formatDateTime(isoTimestamp: string): string {
  return `${formatDate(isoTimestamp)} ${formatTimestamp(isoTimestamp)}`
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return `${h}h ${m}m`
}

export function formatContracts(n: number): string {
  return n.toLocaleString('en-US')
}

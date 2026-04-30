// Types matching backend response shapes from src/sigil/api/routes.py.
// Keep in sync when route shapes change.

export type PortfolioState = "ok" | "no_data";

export interface Portfolio {
  state: PortfolioState;
  mode: string;
  balance: number;
  roi: number;
  unrealized_pnl: number;
  realized_pnl: number;
  settled_trades_total: number;
  settled_trades_30d: number;
  as_of: string | null;
}

export interface ApiMarket {
  id: string;
  platform: string;
  title: string;
  resolution_date: string | null;
  external_id: string;
  market_type: string;
  taxonomy_l1: string | null;
  taxonomy_l2?: string | null;
  status: string;
}

export interface MarketDetail extends ApiMarket {
  bid: number | null;
  ask: number | null;
  last_price: number | null;
  volume_24h: number | null;
  last_updated: string | null;
}

export interface ApiPosition {
  id: string;
  platform: string;
  market_id: string;
  market_title: string;
  external_id: string;
  mode: string;
  outcome: "yes" | "no";
  quantity: number;
  avg_entry_price: number;
  current_price: number | null;
  unrealized_pnl: number | null;
  realized_pnl: number;
  status: string;
  opened_at: string | null;
}

export interface ApiOrder {
  id: string;
  client_order_id: string;
  external_order_id: string | null;
  platform: string;
  market_id: string;
  mode: string;
  side: "buy" | "sell";
  outcome: "yes" | "no";
  order_type: "limit" | "market" | "ioc";
  price: number;
  quantity: number;
  filled_quantity: number;
  avg_fill_price: number | null;
  fees: number;
  edge_at_entry: number | null;
  status: string;
  created_at: string | null;
}

export interface ApiPrediction {
  id: string;
  market_id: string;
  model_id: string;
  model_version: string;
  predicted_prob: number;
  confidence: number | null;
  market_price_at_prediction: number | null;
  edge: number | null;
  created_at: string | null;
}

export interface HealthSource {
  source_name: string;
  status: string;
  error_count_24h: number;
  latency_p50_ms: number | null;
  latency_p95_ms: number | null;
  records_fetched_latest: number | null;
  last_checked: string | null;
  last_error: string | null;
}

export interface Health {
  state: "ok" | "no_data";
  sources: HealthSource[];
  as_of: string | null;
}

export interface ArbitrageOpp {
  event: string;
  kalshi_ticker: string;
  poly_ticker: string;
  kalshi_bid: number;
  kalshi_ask: number;
  kalshi_min_size: number;
  poly_bid: number;
  poly_ask: number;
  poly_min_size: number;
  implied_sum: number;
  net_arb: number;
  match_score: number;
  opportunity_type: "PURE_ARB" | "STAT_EDGE";
  kelly_size: number;
  display_only: boolean;
}

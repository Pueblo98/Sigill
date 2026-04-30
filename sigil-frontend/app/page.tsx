"use client";

import React from "react";
import { useApi } from "@/lib/api/client";
import type {
  ApiPosition,
  ApiPrediction,
  Health,
  Portfolio,
} from "@/lib/types/api";

function formatCurrency(n: number): string {
  return n.toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  });
}

function formatTime(iso: string | null | undefined): string {
  if (!iso) return "--:--:--";
  try {
    return new Date(iso).toLocaleTimeString();
  } catch {
    return "--:--:--";
  }
}

export default function Dashboard() {
  const portfolio = useApi<Portfolio>("/api/portfolio");
  const positions = useApi<ApiPosition[]>("/api/positions");
  const predictions = useApi<ApiPrediction[]>("/api/predictions");
  const health = useApi<Health>("/api/health");

  const noPortfolio = portfolio.data?.state === "no_data";
  const balance = portfolio.data?.balance ?? 0;
  const roi = portfolio.data?.roi ?? 0;
  const unrealized = portfolio.data?.unrealized_pnl ?? 0;
  const realized = portfolio.data?.realized_pnl ?? 0;

  return (
    <div className="p-4 grid grid-cols-12 gap-4 flex-1">
      {/* Portfolio Overview */}
      <section className="col-span-12 lg:col-span-5 bg-[#201f21] p-6 flex flex-col gap-6">
        <div className="flex justify-between items-end">
          <h3 className="text-xs font-medium uppercase tracking-wider text-[#e5e1e4]/60">
            Portfolio Overview
          </h3>
          <span className="text-[10px] font-mono text-[#e5e1e4]/30">
            LAST UPDATE: {formatTime(portfolio.data?.as_of)}
          </span>
        </div>

        {portfolio.isLoading ? (
          <div className="text-[10px] font-mono text-[#e5e1e4]/40 uppercase tracking-widest">
            Loading portfolio...
          </div>
        ) : noPortfolio ? (
          <div className="bg-[#1b1b1d] border border-dashed border-[#39393b] p-6 text-center">
            <p className="text-[10px] font-mono uppercase tracking-widest text-[#e5e1e4]/40 mb-2">
              No bankroll snapshot yet
            </p>
            <p className="text-[10px] font-mono text-[#e5e1e4]/30">
              Run a paper trade or settle a position to populate.
            </p>
          </div>
        ) : (
          <>
            <div className="flex items-baseline gap-4">
              <span className="text-3xl font-black font-mono tracking-tighter">
                {formatCurrency(balance)}
              </span>
              <span
                className={`text-xs font-mono px-2 py-0.5 ${
                  roi >= 0
                    ? "text-emerald-500 bg-emerald-500/10"
                    : "text-rose-500 bg-rose-500/10"
                }`}
              >
                {roi >= 0 ? "+" : ""}
                {roi.toFixed(2)}% ROI
              </span>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-[#1b1b1d] p-4">
                <p className="text-[10px] uppercase text-[#e5e1e4]/40 mb-1">
                  Unrealized P&amp;L
                </p>
                <p
                  className={`text-lg font-mono font-bold ${
                    unrealized >= 0 ? "text-emerald-500" : "text-rose-500"
                  }`}
                >
                  {unrealized >= 0 ? "+" : ""}
                  {formatCurrency(unrealized)}
                </p>
              </div>
              <div className="bg-[#1b1b1d] p-4">
                <p className="text-[10px] uppercase text-[#e5e1e4]/40 mb-1">
                  Realized P&amp;L
                </p>
                <p
                  className={`text-lg font-mono font-bold ${
                    realized >= 0 ? "text-emerald-500" : "text-rose-500"
                  }`}
                >
                  {realized >= 0 ? "+" : ""}
                  {formatCurrency(realized)}
                </p>
              </div>
            </div>
          </>
        )}
      </section>

      {/* Active Signals */}
      <section className="col-span-12 lg:col-span-7 bg-[#201f21] flex flex-col">
        <div className="p-6 border-b border-[#1b1b1d] flex justify-between items-center">
          <h3 className="text-xs font-medium uppercase tracking-wider text-[#e5e1e4]/60">
            Active Signals
          </h3>
          <span className="bg-[#d2bbff]/10 text-[#d2bbff] text-[9px] font-mono px-2 py-0.5">
            {predictions.data?.length ?? 0} TOTAL
          </span>
        </div>
        <div className="flex-1 overflow-y-auto max-h-[400px]">
          {predictions.isLoading ? (
            <div className="p-8 text-[10px] font-mono uppercase tracking-widest text-[#e5e1e4]/40">
              Loading signals...
            </div>
          ) : !predictions.data || predictions.data.length === 0 ? (
            <div className="p-8 text-[10px] font-mono uppercase tracking-widest text-[#e5e1e4]/40">
              No active signals.
            </div>
          ) : (
            predictions.data.slice(0, 8).map((p) => (
              <div
                key={p.id}
                className="p-4 border-b border-[#1b1b1d] flex items-center gap-4 hover:bg-[#39393b] transition-colors relative"
              >
                <div className="absolute left-0 top-0 bottom-0 w-1 bg-[#7C3AED]"></div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="bg-[#353437] text-[9px] font-bold px-1.5 py-0.5">
                      {p.model_id}
                    </span>
                    {p.edge !== null && (
                      <span className="text-[10px] font-mono text-emerald-500">
                        {(p.edge * 100).toFixed(1)}¢ EDGE
                      </span>
                    )}
                  </div>
                  <h4 className="text-xs font-bold truncate">
                    Predicted {(p.predicted_prob * 100).toFixed(1)}% (v
                    {p.model_version})
                  </h4>
                </div>
              </div>
            ))
          )}
        </div>
      </section>

      {/* Open Positions */}
      <section className="col-span-12 lg:col-span-8 bg-[#201f21] flex flex-col overflow-hidden">
        <div className="p-6 border-b border-[#1b1b1d] flex justify-between items-center">
          <h3 className="text-xs font-medium uppercase tracking-wider text-[#e5e1e4]/60">
            Open Positions
          </h3>
          <span className="text-[10px] font-mono text-[#e5e1e4]/40">
            {positions.data?.length ?? 0} ACTIVE
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-[#1b1b1d] text-[10px] font-mono uppercase text-[#e5e1e4]/40">
                <th className="px-6 py-3 font-medium">Market</th>
                <th className="px-2 py-3 font-medium">Side</th>
                <th className="px-2 py-3 font-medium text-right">Contracts</th>
                <th className="px-2 py-3 font-medium text-right">Avg Entry</th>
                <th className="px-2 py-3 font-medium text-right">
                  Unrealized P&amp;L
                </th>
              </tr>
            </thead>
            <tbody className="text-[11px] font-mono divide-y divide-[#1b1b1d]">
              {positions.isLoading ? (
                <tr>
                  <td
                    colSpan={5}
                    className="px-6 py-5 text-center text-[#958da1]"
                  >
                    Loading positions...
                  </td>
                </tr>
              ) : !positions.data || positions.data.length === 0 ? (
                <tr>
                  <td
                    colSpan={5}
                    className="px-6 py-5 text-center text-[#958da1]"
                  >
                    No open positions.
                  </td>
                </tr>
              ) : (
                positions.data.map((p) => (
                  <tr key={p.id} className="hover:bg-[#39393b]/50">
                    <td className="px-6 py-4 font-bold">{p.market_title}</td>
                    <td
                      className={`px-2 py-4 font-bold ${
                        p.outcome === "yes"
                          ? "text-emerald-500"
                          : "text-rose-500"
                      }`}
                    >
                      {p.outcome.toUpperCase()}
                    </td>
                    <td className="px-2 py-4 text-right">
                      {p.quantity.toLocaleString()}
                    </td>
                    <td className="px-2 py-4 text-right">
                      {(p.avg_entry_price * 100).toFixed(1)}¢
                    </td>
                    <td
                      className={`px-2 py-4 text-right ${
                        (p.unrealized_pnl ?? 0) >= 0
                          ? "text-emerald-500"
                          : "text-rose-500"
                      }`}
                    >
                      {p.unrealized_pnl !== null
                        ? formatCurrency(p.unrealized_pnl)
                        : "--"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Source Health */}
      <section className="col-span-12 lg:col-span-4 bg-[#201f21] p-6 flex flex-col gap-6">
        <h3 className="text-xs font-medium uppercase tracking-wider text-[#e5e1e4]/60">
          Source Health
        </h3>
        <div className="space-y-4">
          {health.isLoading ? (
            <div className="text-[10px] font-mono uppercase tracking-widest text-[#e5e1e4]/40">
              Loading...
            </div>
          ) : !health.data?.sources?.length ? (
            <div className="text-[10px] font-mono uppercase tracking-widest text-[#e5e1e4]/40">
              No health checks recorded yet.
            </div>
          ) : (
            health.data.sources.map((s) => (
              <div key={s.source_name} className="space-y-1">
                <div className="flex justify-between text-[9px] font-mono">
                  <span className="uppercase">{s.source_name}</span>
                  <span
                    className={
                      s.status === "ok" || s.status === "healthy"
                        ? "text-emerald-500"
                        : s.status === "degraded"
                        ? "text-yellow-500"
                        : "text-rose-500"
                    }
                  >
                    {s.status.toUpperCase()}
                  </span>
                </div>
                <div className="text-[8px] font-mono text-[#e5e1e4]/40">
                  p50 {s.latency_p50_ms ?? "--"}ms · errs/24h{" "}
                  {s.error_count_24h}
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}

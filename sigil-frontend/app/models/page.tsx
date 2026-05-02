"use client";

import React from "react";
import Link from "next/link";
import { useApi } from "@/lib/api/client";
import type { ApiModelSummary } from "@/lib/types/api";

function formatRelative(iso: string | null): string {
  if (!iso) return "never";
  const t = new Date(iso).getTime();
  const ms = Date.now() - t;
  if (ms < 0) return "just now";
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

function formatPnL(v: number): string {
  const sign = v >= 0 ? "+" : "";
  return `${sign}$${v.toFixed(2)}`;
}

function formatPercent(v: number | null): string {
  if (v === null || Number.isNaN(v)) return "--";
  return `${(v * 100).toFixed(1)}%`;
}

function StatusDot({
  enabled,
  has24h,
}: {
  enabled: boolean;
  has24h: boolean;
}) {
  let color = "bg-[#4a4455]";
  let label = "disabled";
  if (enabled && has24h) {
    color = "bg-emerald-500";
    label = "live";
  } else if (enabled && !has24h) {
    color = "bg-amber-500";
    label = "idle";
  }
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`w-1.5 h-1.5 rounded-full ${color}`} />
      <span className="text-[9px] font-mono uppercase tracking-widest text-[#958da1]">
        {label}
      </span>
    </span>
  );
}

function ModelCard({ m }: { m: ApiModelSummary }) {
  const s = m.summary;
  const noData = s.state === "no_data";
  const has24h = s.predictions_24h > 0;
  return (
    <Link
      href={`/models/${encodeURIComponent(m.model_id)}`}
      className="group relative bg-[#201f21] border border-[#1b1b1d] hover:border-[#7C3AED]/40 hover:shadow-[0_0_30px_rgba(124,58,237,0.1)] transition-all duration-300 p-6 flex flex-col cursor-pointer"
    >
      <div className="flex justify-between items-start mb-3">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-bold leading-tight text-[#e5e1e4] group-hover:text-[#d2bbff] transition-colors">
            {m.display_name}
          </h2>
          <span className="bg-[#39393b] text-[#958da1] text-[9px] font-bold px-1.5 py-0.5 font-mono tracking-widest uppercase">
            {m.version}
          </span>
        </div>
        <StatusDot enabled={m.enabled} has24h={has24h} />
      </div>

      <p className="text-[11px] text-[#958da1] mb-4 line-clamp-2">
        {m.description || "—"}
      </p>

      {m.tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-5">
          {m.tags.map((t) => (
            <span
              key={t}
              className="text-[9px] font-bold px-1.5 py-0.5 bg-[#7C3AED]/20 text-[#d2bbff] font-mono uppercase tracking-widest"
            >
              {t}
            </span>
          ))}
        </div>
      )}

      <div className="grid grid-cols-4 gap-2 mb-4">
        <div className="bg-[#1b1b1d] p-2.5">
          <div className="text-[9px] font-mono uppercase tracking-widest text-[#958da1]">
            Trades
          </div>
          <div className="text-base font-mono text-[#e5e1e4] mt-0.5">
            {noData ? "--" : s.trades_total}
          </div>
        </div>
        <div className="bg-[#1b1b1d] p-2.5">
          <div className="text-[9px] font-mono uppercase tracking-widest text-[#958da1]">
            Win Rate
          </div>
          <div className="text-base font-mono text-[#e5e1e4] mt-0.5">
            {formatPercent(s.win_rate)}
          </div>
        </div>
        <div className="bg-[#1b1b1d] p-2.5">
          <div className="text-[9px] font-mono uppercase tracking-widest text-[#958da1]">
            P&amp;L
          </div>
          <div
            className={`text-base font-mono mt-0.5 ${
              noData
                ? "text-[#e5e1e4]/40"
                : s.realized_pnl > 0
                ? "text-emerald-400"
                : s.realized_pnl < 0
                ? "text-rose-400"
                : "text-[#e5e1e4]"
            }`}
          >
            {noData ? "--" : formatPnL(s.realized_pnl)}
          </div>
        </div>
        <div className="bg-[#1b1b1d] p-2.5">
          <div className="text-[9px] font-mono uppercase tracking-widest text-[#958da1]">
            Drawdown
          </div>
          <div className="text-base font-mono text-[#e5e1e4] mt-0.5">
            {s.max_drawdown !== null && !noData
              ? `-$${s.max_drawdown.toFixed(2)}`
              : "--"}
          </div>
        </div>
      </div>

      <div className="mt-auto pt-3 border-t border-[#1b1b1d] flex justify-between items-center text-[10px] font-mono">
        <div className="text-[#958da1]">
          {noData ? (
            <span className="text-[#958da1]/60">no signals yet</span>
          ) : (
            <>
              <span className="text-[#958da1]/60">last trade </span>
              <span className="text-[#e5e1e4]">{formatRelative(s.last_trade_at)}</span>
            </>
          )}
        </div>
        <div className="text-[#958da1]/60">
          {s.predictions_24h} pred / 24h
        </div>
      </div>
    </Link>
  );
}

export default function Models() {
  const { data, error, isLoading } = useApi<ApiModelSummary[]>("/api/models");
  const models = data ?? [];

  return (
    <div className="p-6">
      <header className="flex justify-between items-end mb-8 pb-4 border-b border-[#4a4455]/10">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-[#e5e1e4] mb-1">
            MODELS
          </h1>
          <p className="text-[11px] font-mono text-[#958da1]">
            every registered signal source — click into one for trades &amp; P&amp;L
          </p>
        </div>
        <div className="text-[10px] font-mono uppercase tracking-widest text-[#958da1]">
          {models.length} model{models.length === 1 ? "" : "s"}
        </div>
      </header>

      {isLoading ? (
        <div className="text-[10px] font-mono uppercase tracking-widest text-[#958da1] p-8">
          Loading models...
        </div>
      ) : error ? (
        <div className="text-[10px] font-mono uppercase tracking-widest text-rose-500 p-8">
          API error: {error.message}
        </div>
      ) : models.length === 0 ? (
        <div className="text-[10px] font-mono uppercase tracking-widest text-[#958da1] p-8">
          No models registered. Add a register_model() call in a signal module.
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3 gap-6">
          {models.map((m) => (
            <ModelCard key={m.model_id} m={m} />
          ))}
        </div>
      )}
    </div>
  );
}

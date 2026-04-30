"use client";

import React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useApi } from "@/lib/api/client";
import type { MarketDetail } from "@/lib/types/api";

export default function TradeDetail() {
  const params = useParams<{ id: string }>();
  const id = params?.id;
  const endpoint = id ? `/api/markets/${encodeURIComponent(id)}` : null;
  const { data: market, error, isLoading } = useApi<MarketDetail>(endpoint);

  if (isLoading) {
    return (
      <div className="p-12 font-mono text-xs uppercase text-[#958da1] tracking-widest">
        Loading market datapoints…
      </div>
    );
  }

  if (error || !market) {
    return (
      <div className="p-12">
        <h1 className="text-3xl font-black text-rose-500 mb-4">404: NOT FOUND</h1>
        <p className="font-mono text-[#958da1] text-xs">
          Market id <code>{id}</code> was not found in the ingestion engine.
        </p>
        <Link
          href="/markets"
          className="mt-8 font-mono text-[10px] uppercase text-[#7C3AED] hover:text-[#d2bbff] underline inline-block"
        >
          Return to grid
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-[#0e0e10] p-8 text-[#e5e1e4] overflow-y-auto w-full">
      <div className="mb-12 max-w-5xl">
        <div className="flex items-center gap-4 mb-4">
          <Link
            href="/markets"
            className="text-[#958da1] hover:text-[#e5e1e4] transition-colors text-xs"
          >
            ← back
          </Link>
          <span
            className={`text-[10px] font-mono font-bold px-3 py-1 uppercase tracking-widest ${
              market.platform === "kalshi"
                ? "bg-emerald-900/30 text-emerald-400 border border-emerald-900"
                : "bg-blue-900/30 text-blue-400 border border-blue-900"
            }`}
          >
            {market.platform} | {market.taxonomy_l1 || "GENERAL"}
          </span>
          <span className="text-[10px] font-mono text-[#958da1] border border-[#201f21] px-2 py-1">
            EX-ID: {market.external_id}
          </span>
          <span
            className={`text-[10px] font-mono font-bold px-2 py-1 uppercase ${
              market.status === "open"
                ? "text-emerald-400"
                : "text-[#958da1]"
            }`}
          >
            {market.status}
          </span>
        </div>

        <h1 className="text-4xl md:text-5xl lg:text-6xl font-black leading-none tracking-tight mb-8">
          {market.title}
        </h1>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pb-8 border-b border-[#201f21]">
          <Stat
            label="Current Ask"
            value={
              market.ask !== null
                ? `${(market.ask * 100).toFixed(1)}¢`
                : "--"
            }
          />
          <Stat
            label="Current Bid"
            value={
              market.bid !== null
                ? `${(market.bid * 100).toFixed(1)}¢`
                : "--"
            }
          />
          <Stat
            label="Last Trade"
            value={
              market.last_price !== null
                ? `${(market.last_price * 100).toFixed(1)}¢`
                : "--"
            }
            accent
          />
          <Stat
            label="24H Volume"
            value={
              market.volume_24h !== null
                ? `$${market.volume_24h.toLocaleString()}`
                : "--"
            }
          />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 max-w-5xl flex-1">
        <div className="bg-[#1b1b1d] border border-[#201f21] p-8 flex flex-col gap-8">
          <div>
            <h3 className="text-[10px] font-mono font-bold text-[#7C3AED] uppercase tracking-[0.2em] mb-4">
              Resolution Target
            </h3>
            <p className="font-mono text-sm text-[#e5e1e4] uppercase">
              {market.resolution_date
                ? new Date(market.resolution_date).toLocaleDateString(
                    undefined,
                    {
                      weekday: "long",
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                    }
                  )
                : "Open-ended"}
            </p>
          </div>

          <div>
            <h3 className="text-[10px] font-mono font-bold text-[#7C3AED] uppercase tracking-[0.2em] mb-4">
              Last Sync
            </h3>
            <p className="font-mono text-xs text-[#958da1] uppercase tracking-wider">
              {market.last_updated
                ? new Date(market.last_updated).toLocaleString()
                : "No price data"}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className="bg-[#1b1b1d] border border-[#201f21] p-4 flex flex-col items-center justify-center gap-1">
      <span className="text-[9px] font-mono uppercase tracking-[0.2em] text-[#958da1]">
        {label}
      </span>
      <span
        className={`text-3xl font-mono ${
          accent ? "text-[#7C3AED]" : "text-[#e5e1e4]"
        }`}
      >
        {value}
      </span>
    </div>
  );
}
